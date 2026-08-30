"""Quantisation, checked where it is easy to be quietly wrong.

Two of these tests exist because the first version of the module was wrong in
exactly the way they now catch: it selected tensors by module type, which
missed `MultiheadAttention`'s input projection entirely, and it hooked
`out_proj`, whose forward never runs because attention applies it functionally.
Between them that left 35% of the weights and both attention outputs in float,
which would have reported a quantisation cost far lower than the real one.
"""

from __future__ import annotations

import numpy as np
import pytest

from evpil.forecast.quantise import (
    INT8_MAX,
    INT8_MIN,
    ActivationObserver,
    QuantRange,
    deployed_bytes,
)

torch = pytest.importorskip("torch")


# --- the grid ---------------------------------------------------------------

def test_a_symmetric_grid_represents_its_own_peak_exactly():
    values = np.array([-3.0, 0.25, 7.0])
    rng = QuantRange.symmetric_from(values)
    assert rng.fake_quantise(np.array([7.0]))[0] == pytest.approx(7.0)
    assert rng.zero_point == 0


def test_a_symmetric_grid_has_no_zero_point_to_carry():
    # The device accumulates without one, so a non-zero value here would mean
    # the simulation and the hardware were computing different things.
    assert QuantRange.symmetric_from(np.array([-1.0, 2.0])).zero_point == 0


def test_an_affine_grid_always_represents_zero_exactly():
    # Padding and residual paths produce exact zeros. A grid that rounds zero
    # to something else adds a bias everywhere one appears.
    for lo, hi in ((-0.1, 3.0), (0.5, 9.0), (-4.0, -0.2)):
        rng = QuantRange.affine_from(lo, hi)
        assert rng.fake_quantise(np.array([0.0]))[0] == pytest.approx(0.0, abs=1e-12)


def test_codes_stay_inside_the_int8_range_even_for_outliers():
    rng = QuantRange.affine_from(-1.0, 1.0)
    codes = rng.quantise(np.array([-50.0, 50.0]))
    assert codes.min() >= INT8_MIN and codes.max() <= INT8_MAX


def test_quantisation_error_never_exceeds_half_a_step():
    rng = QuantRange.symmetric_from(np.array([-2.0, 2.0]))
    values = np.linspace(-2.0, 2.0, 500)
    assert np.abs(rng.fake_quantise(values) - values).max() <= rng.scale / 2 + 1e-12


def test_a_constant_tensor_does_not_produce_a_zero_scale():
    rng = QuantRange.symmetric_from(np.zeros(5))
    assert rng.scale > 0.0
    assert np.isfinite(rng.fake_quantise(np.zeros(5))).all()


# --- the observer -----------------------------------------------------------

def test_the_observer_tracks_the_extremes_it_is_shown():
    obs = ActivationObserver()
    obs.observe(np.array([-1.0, 4.0]))
    obs.observe(np.array([0.0, 9.0]))
    rng = obs.to_range()
    assert rng.fake_quantise(np.array([9.0]))[0] == pytest.approx(9.0, abs=rng.scale)


def test_an_unobserved_activation_refuses_to_invent_a_range():
    with pytest.raises(ValueError, match="no data observed"):
        ActivationObserver().to_range()


# --- coverage over a real encoder -------------------------------------------

def _encoder(d_model: int = 32, layers: int = 2, n_feat: int = 8,
             horizon: int = 30, n_out: int = 1):
    from torch import nn

    layer = nn.TransformerEncoderLayer(
        d_model=d_model, nhead=4, dim_feedforward=2 * d_model, dropout=0.0,
        batch_first=True, norm_first=True,
    )

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.embed = nn.Linear(n_feat, d_model)
            self.encoder = nn.TransformerEncoder(layer, num_layers=layers,
                                                 enable_nested_tensor=False)
            self.head = nn.Linear(d_model, horizon * n_out)

        def forward(self, x):
            return self.head(self.encoder(self.embed(x))[:, -1])

    return Net()


def test_every_two_dimensional_weight_is_selected_for_quantisation():
    from evpil.forecast.quantise import quantisable_parameters

    net = _encoder()
    selected = {name for name, _ in quantisable_parameters(net)}
    every = {name for name, p in net.named_parameters() if p.ndim >= 2}
    assert selected == every

    # The specific tensor a module-based sweep misses. It is 3,072 weights per
    # layer, 35% of the model, and it is not an nn.Linear.
    assert "encoder.layers.0.self_attn.in_proj_weight" in selected


def test_biases_and_layer_norms_are_left_out_of_quantisation():
    from evpil.forecast.quantise import quantisable_parameters

    net = _encoder()
    selected = {name for name, _ in quantisable_parameters(net)}
    assert not any(name.endswith("bias") for name in selected)
    assert not any("norm" in name and name.endswith("weight") for name in selected)


def test_attention_output_is_an_activation_point_and_out_proj_is_not():
    from evpil.forecast.quantise import observed_modules

    names = {name for name, _ in observed_modules(_encoder())}
    assert "encoder.layers.0.self_attn" in names
    # Hooking out_proj instead would never fire: attention applies it
    # functionally rather than by calling the module.
    assert not any(name.endswith("out_proj") for name in names)


def test_every_activation_point_is_actually_observed():
    from evpil.forecast.models import Standardiser, TrainedNet
    from evpil.forecast.quantise import calibrate_activations, observed_modules

    net = _encoder()
    X = np.random.default_rng(0).normal(size=(64, 32, 8)).astype(np.float32)
    trained = TrainedNet(net=net, scaler=Standardiser.fit(X),
                         y_mu=np.zeros(1), y_sd=np.ones(1), device="cpu")

    ranges = calibrate_activations(trained, X)
    assert set(ranges) == {name for name, _ in observed_modules(net)}


def test_calibration_refuses_an_empty_set():
    from evpil.forecast.models import Standardiser, TrainedNet
    from evpil.forecast.quantise import calibrate_activations

    X = np.random.default_rng(0).normal(size=(8, 32, 8)).astype(np.float32)
    trained = TrainedNet(net=_encoder(), scaler=Standardiser.fit(X),
                         y_mu=np.zeros(1), y_sd=np.ones(1), device="cpu")
    with pytest.raises(ValueError, match="calibration set is empty"):
        calibrate_activations(trained, X[:0])


def test_quantised_inference_restores_the_float_weights_afterwards():
    from evpil.forecast.models import Standardiser, TrainedNet
    from evpil.forecast.quantise import calibrate_activations, predict_int8

    net = _encoder()
    X = np.random.default_rng(0).normal(size=(64, 32, 8)).astype(np.float32)
    trained = TrainedNet(net=net, scaler=Standardiser.fit(X),
                         y_mu=np.zeros(1), y_sd=np.ones(1), device="cpu")

    before = {n: p.detach().clone() for n, p in net.named_parameters()}
    predict_int8(trained, X, calibrate_activations(trained, X))
    for name, param in net.named_parameters():
        assert torch.equal(param, before[name]), f"{name} was left quantised"


def test_the_deployed_size_charges_weights_one_byte_and_biases_four():
    net = _encoder()
    weights = sum(p.numel() for p in net.parameters() if p.ndim >= 2)
    biases = sum(p.numel() for p in net.parameters() if p.ndim < 2)
    assert deployed_bytes(net) == weights + biases * 4
