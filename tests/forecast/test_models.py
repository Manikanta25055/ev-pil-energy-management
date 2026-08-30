"""Each arm is checked on a problem whose answer is known.

Real data cannot tell you whether an arm is wired correctly, because a wiring
fault and a hard problem produce the same disappointing number. A synthetic
window whose target is a known function of the inputs can.
"""

from __future__ import annotations

import numpy as np
import pytest

from evpil.forecast.models import (
    ArmResult,
    Standardiser,
    fit_lstm,
    fit_ridge,
    fit_transformer,
    fit_xgboost,
)

SEQ, FEAT, HORIZON = 8, 3, 4


def _problem(n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Targets are a linear function of the window's last two samples.

    Learnable by every arm, and only by an arm that actually reads the
    sequence dimension.
    """
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, SEQ, FEAT)).astype(np.float32)
    signal = 3.0 * X[:, -1, 0] - 2.0 * X[:, -2, 1] + 0.5 * X[:, -1, 2]
    Y = np.stack([signal * (1.0 + 0.1 * h) for h in range(HORIZON)], axis=1)
    Y += rng.normal(scale=0.05, size=Y.shape)
    return X, Y.astype(np.float32)


def _rmse(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.sqrt(((a - b) ** 2).mean()))


def _mean_baseline(Y_tr: np.ndarray, n: int) -> np.ndarray:
    return np.repeat(Y_tr.mean(axis=0)[None, :], n, axis=0)


# --- Standardiser -----------------------------------------------------------

def test_standardiser_centres_and_scales_each_channel():
    X = np.stack([np.full((5, 2), 3.0), np.full((5, 2), 7.0)]).astype(np.float32)
    s = Standardiser.fit(X)
    np.testing.assert_allclose(s.mu, [5.0, 5.0])
    np.testing.assert_allclose(s.transform(X).mean(axis=(0, 1)), [0.0, 0.0], atol=1e-6)


def test_standardiser_survives_a_constant_channel():
    X = np.zeros((4, 3, 2), dtype=np.float32)
    X[:, :, 0] = 9.0
    out = Standardiser.fit(X).transform(X)
    assert np.isfinite(out).all()


def test_standardiser_statistics_come_only_from_what_it_was_fitted_on():
    train = np.zeros((10, 4, 1), dtype=np.float32)
    evaluation = np.full((10, 4, 1), 100.0, dtype=np.float32)
    s = Standardiser.fit(train)
    # If the scaler had seen the evaluation split, its mean would not be 0.
    assert s.mu.tolist() == [0.0]
    assert s.transform(evaluation).mean() == pytest.approx(100.0)


# --- arms -------------------------------------------------------------------

def test_ridge_recovers_a_linear_target():
    X_tr, Y_tr = _problem(600, 0)
    X_ev, Y_ev = _problem(200, 1)
    out = fit_ridge(X_tr, Y_tr, X_ev)
    assert isinstance(out, ArmResult)
    assert out.pred.shape == Y_ev.shape
    assert _rmse(out.pred, Y_ev) < 0.2 * _rmse(_mean_baseline(Y_tr, len(Y_ev)), Y_ev)


def test_ridge_reports_one_weight_per_input_per_horizon_step():
    X_tr, Y_tr = _problem(200, 0)
    out = fit_ridge(X_tr, Y_tr, X_tr)
    assert out.n_params == (SEQ * FEAT + 1) * HORIZON


def test_ridge_is_deterministic():
    X_tr, Y_tr = _problem(300, 0)
    X_ev, _ = _problem(100, 1)
    np.testing.assert_allclose(
        fit_ridge(X_tr, Y_tr, X_ev).pred, fit_ridge(X_tr, Y_tr, X_ev).pred
    )


def test_xgboost_beats_predicting_the_training_mean():
    X_tr, Y_tr = _problem(800, 0)
    X_ev, Y_ev = _problem(300, 1)
    out = fit_xgboost(X_tr, Y_tr, X_ev, Y_ev, n_estimators=120,
                      early_stopping_rounds=20)
    assert out.pred.shape == Y_ev.shape
    assert _rmse(out.pred, Y_ev) < 0.5 * _rmse(_mean_baseline(Y_tr, len(Y_ev)), Y_ev)


def test_xgboost_fits_one_booster_per_horizon_step():
    X_tr, Y_tr = _problem(400, 0)
    X_ev, Y_ev = _problem(150, 1)
    out = fit_xgboost(X_tr, Y_tr, X_ev, Y_ev, n_estimators=60,
                      early_stopping_rounds=15)
    assert len(out.info["best_rounds"]) == HORIZON


def test_lstm_learns_the_sequence_rather_than_the_last_sample():
    # The target needs sample -2 as well as sample -1, so an arm that collapses
    # the sequence dimension cannot reach this error level. That collapse is
    # exactly defect D4.
    X_tr, Y_tr = _problem(2000, 0)
    X_ev, Y_ev = _problem(500, 1)
    out = fit_lstm(X_tr, Y_tr, X_ev, Y_ev, hidden=32, epochs=25,
                   batch_size=128, lr=5e-3, seed=0, device="cpu")
    assert out.pred.shape == Y_ev.shape
    assert _rmse(out.pred, Y_ev) < 0.4 * _rmse(_mean_baseline(Y_tr, len(Y_ev)), Y_ev)


def test_lstm_receives_a_real_sequence_dimension():
    X_tr, Y_tr = _problem(200, 0)
    X_ev, Y_ev = _problem(50, 1)
    out = fit_lstm(X_tr, Y_tr, X_ev, Y_ev, hidden=8, epochs=1, device="cpu")
    # LSTM gate weights: 4 gates over (input, hidden) plus two bias vectors.
    expected_rnn = 4 * (8 * FEAT + 8 * 8 + 2 * 8)
    assert out.n_params == expected_rnn + (8 * HORIZON + HORIZON)


def test_lstm_returns_its_best_epoch_not_its_last():
    X_tr, Y_tr = _problem(400, 0)
    X_ev, Y_ev = _problem(150, 1)
    out = fit_lstm(X_tr, Y_tr, X_ev, Y_ev, hidden=16, epochs=6, seed=0, device="cpu")
    curve = out.info["val_rmse_curve"]
    assert out.info["best_epoch"] == int(np.argmin(curve))
    assert _rmse(out.pred, Y_ev) == pytest.approx(min(curve), rel=1e-6)


def test_lstm_is_reproducible_for_a_given_seed():
    X_tr, Y_tr = _problem(300, 0)
    X_ev, Y_ev = _problem(100, 1)
    kw = dict(hidden=8, epochs=2, seed=7, device="cpu")
    a = fit_lstm(X_tr, Y_tr, X_ev, Y_ev, **kw)
    b = fit_lstm(X_tr, Y_tr, X_ev, Y_ev, **kw)
    np.testing.assert_allclose(a.pred, b.pred)


def test_lstm_runs_after_xgboost_in_the_same_process():
    """Regression: this combination used to hang, not fail.

    XGBoost and PyTorch each load their own OpenMP runtime on macOS, and an
    LSTM forward pass big enough to take the parallel path deadlocks once
    XGBoost has fitted in the same process. The ladder script does exactly
    this, so the ordering is the normal case rather than a contrived one.
    A batch of 256 is the size that triggered it; smaller batches stayed on
    the serial path and hid the fault.
    """
    X_tr, Y_tr = _problem(400, 0)
    X_ev, Y_ev = _problem(300, 1)

    fit_xgboost(X_tr, Y_tr, X_ev, Y_ev, n_estimators=40, early_stopping_rounds=10)
    out = fit_lstm(X_tr, Y_tr, X_ev, Y_ev, hidden=8, epochs=1,
                   batch_size=256, device="cpu")
    assert out.pred.shape == Y_ev.shape


def test_lstm_pins_the_cpu_thread_count_by_default():
    import torch

    X_tr, Y_tr = _problem(120, 0)
    X_ev, Y_ev = _problem(40, 1)
    fit_lstm(X_tr, Y_tr, X_ev, Y_ev, hidden=8, epochs=1, device="cpu")
    assert torch.get_num_threads() == 1


# --- transformer ------------------------------------------------------------

def _multitarget_problem(n: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """A window whose four target channels are physically consistent.

    Built so that a model which learns the targets also satisfies r1, r2 and
    r3, which is what lets a test tell "the physics term is wired up" apart
    from "the physics term fights the data".
    """
    from evpil.forecast.physics import PhysicsConstants, ocv_v

    const = PhysicsConstants()
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, SEQ, FEAT)).astype(np.float32)

    current = 40.0 * X[:, -1, 0:1] + 60.0 + np.zeros((n, HORIZON))
    step = np.arange(HORIZON)[None, :]
    soc = 0.6 - current * step * const.dt_s / (3600.0 * const.capacity_ah)
    volt = ocv_v(soc, const) - current * const.r0_ohm
    power = volt * current
    Y = np.stack([power, current, volt, soc], axis=-1)
    return X, Y.astype(np.float32)


def test_transformer_defaults_to_the_configuration_g1_sized():
    X_tr, Y_tr = _multitarget_problem(120, 0)
    out = fit_transformer(X_tr, Y_tr, X_tr[:40], Y_tr[:40], epochs=1, device="cpu")
    assert out.info["d_model"] == 32 and out.info["layers"] == 2
    assert out.pred.shape == (40, HORIZON, 4)


def test_plain_and_physics_informed_have_identical_parameter_counts():
    from evpil.forecast.physics import PhysicsConstants, ResidualWeights

    X_tr, Y_tr = _multitarget_problem(120, 0)
    kw = dict(epochs=1, device="cpu", seed=0)
    plain = fit_transformer(X_tr, Y_tr, X_tr[:40], Y_tr[:40], **kw)
    informed = fit_transformer(X_tr, Y_tr, X_tr[:40], Y_tr[:40],
                               physics=PhysicsConstants(),
                               weights=ResidualWeights(), **kw)
    # Ablation A1 compares the loss, not the capacity. If these ever differ,
    # the comparison is measuring the wrong thing.
    assert plain.n_params == informed.n_params
    assert plain.info["physics_informed"] is False
    assert informed.info["physics_informed"] is True


def test_the_physics_term_changes_the_weights_it_is_supposed_to_change():
    from evpil.forecast.physics import PhysicsConstants, ResidualWeights

    X_tr, Y_tr = _multitarget_problem(200, 0)
    kw = dict(epochs=2, device="cpu", seed=3)
    plain = fit_transformer(X_tr, Y_tr, X_tr[:60], Y_tr[:60], **kw)
    informed = fit_transformer(X_tr, Y_tr, X_tr[:60], Y_tr[:60],
                               physics=PhysicsConstants(),
                               weights=ResidualWeights(100.0, 100.0, 100.0), **kw)
    # Same seed, same data, same architecture: any difference in the outputs
    # comes from the extra loss term and nothing else.
    assert not np.allclose(plain.pred, informed.pred)


def test_the_physics_term_reduces_the_residuals_it_penalises():
    from evpil.forecast.physics import PhysicsConstants, ResidualWeights, residual_terms

    const = PhysicsConstants()
    X_tr, Y_tr = _multitarget_problem(600, 0)
    X_ev, Y_ev = _multitarget_problem(200, 1)
    kw = dict(epochs=12, device="cpu", seed=0, lr=3e-3)

    plain = fit_transformer(X_tr, Y_tr, X_ev, Y_ev, **kw)
    informed = fit_transformer(X_tr, Y_tr, X_ev, Y_ev, physics=const,
                               weights=ResidualWeights(30.0, 30.0, 30.0), **kw)

    def worst_r1(pred: np.ndarray) -> float:
        return float(np.abs(residual_terms(pred, const)["r1"]).mean())

    # The untrained-from-scratch plain arm has no reason to keep P = V*I.
    assert worst_r1(informed.pred) < worst_r1(plain.pred)


def test_the_transformer_refuses_physics_on_a_single_channel_target():
    from evpil.forecast.physics import PhysicsConstants, ResidualWeights

    X_tr, Y_tr = _problem(80, 0)
    with pytest.raises(ValueError, match="power, current, voltage and charge"):
        fit_transformer(X_tr, Y_tr, X_tr[:20], Y_tr[:20], epochs=1, device="cpu",
                        physics=PhysicsConstants(), weights=ResidualWeights())


def test_the_transformer_accepts_a_single_channel_target_without_physics():
    X_tr, Y_tr = _problem(120, 0)
    out = fit_transformer(X_tr, Y_tr, X_tr[:40], Y_tr[:40], epochs=1, device="cpu")
    assert out.pred.shape == (40, HORIZON)


def test_the_transformer_selects_its_epoch_on_the_power_channel():
    X_tr, Y_tr = _multitarget_problem(160, 0)
    out = fit_transformer(X_tr, Y_tr, X_tr[:50], Y_tr[:50], epochs=4,
                          device="cpu", seed=0)
    assert out.info["best_epoch"] == int(np.argmin(out.info["val_rmse_curve"]))
