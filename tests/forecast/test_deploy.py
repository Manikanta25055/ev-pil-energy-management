"""Cost arithmetic, checked against figures that were measured elsewhere.

The value of this module is that a number here can be trusted before G5 runs,
so two of these tests are cross-checks rather than unit tests: the Transformer
cost has to reproduce the G1 table it will be compared against, and the LSTM
parameter count has to agree with what PyTorch reports for the same shapes. A
cost model that disagrees with either is worse than no cost model.
"""

from __future__ import annotations

import pytest

from evpil.forecast.deploy import (
    BUDGET_BYTES,
    BUDGET_LATENCY_MS,
    MEASURED_MMAC_PER_S,
    constant_cost,
    lstm_cost,
    ridge_cost,
    transformer_cost,
    tree_ensemble_cost,
)


def test_transformer_cost_reproduces_the_g1_config_table():
    # docs/g1-compute-budget.md: seq 32, d_model 32, 2 layers -> 655,360 MACs,
    # 16.4 k params, 22.0 ms. Measured throughput, not an assumed one.
    c = transformer_cost(seq_len=32, d_model=32, layers=2)
    assert c.macs == 655_360
    assert c.int8_bytes == pytest.approx(16_384, rel=0.01)
    assert c.latency_ms == pytest.approx(22.0, abs=0.1)


def test_transformer_cost_reproduces_the_plan_implied_row_too():
    # The row G1 rejected: 5,242,880 MACs and 175.8 ms.
    c = transformer_cost(seq_len=64, d_model=64, layers=2)
    assert c.macs == 5_242_880
    assert c.latency_ms == pytest.approx(175.8, abs=0.5)
    assert not c.fits


def test_lstm_parameter_count_agrees_with_pytorch():
    torch = pytest.importorskip("torch")
    from torch import nn

    seq_len, n_feat, hidden, horizon = 32, 8, 64, 30
    net = nn.Sequential()
    rnn = nn.LSTM(n_feat, hidden, 1, batch_first=True)
    head = nn.Linear(hidden, horizon)
    actual = sum(p.numel() for p in rnn.parameters()) + sum(
        p.numel() for p in head.parameters()
    )
    assert lstm_cost(seq_len, n_feat, hidden, 1, horizon).int8_bytes == actual


def test_latency_is_macs_divided_by_the_measured_throughput():
    c = ridge_cost(seq_len=32, n_features=8, horizon=30)
    assert c.macs == 32 * 8 * 30
    assert c.latency_ms == pytest.approx(c.macs / (MEASURED_MMAC_PER_S * 1e6) * 1e3)


def test_ridge_carries_one_bias_per_output():
    c = ridge_cost(seq_len=4, n_features=2, horizon=3)
    assert c.int8_bytes == (4 * 2 + 1) * 3


def test_a_recurrent_layer_pays_its_cost_once_per_input_sample():
    one = lstm_cost(16, 8, 32, 1, 10)
    two = lstm_cost(32, 8, 32, 1, 10)
    # Doubling the window doubles the recurrent work but not the output head,
    # so the ratio sits just under two.
    assert 1.95 < (two.macs / one.macs) < 2.0
    assert two.int8_bytes == one.int8_bytes


def test_the_tree_ensemble_reports_no_latency_because_it_has_no_macs():
    c = tree_ensemble_cost(n_trees=1000, max_depth=4)
    assert c.macs is None
    assert c.latency_ms is None
    assert c.latency_fraction is None
    assert c.footprint_estimated


def test_a_tree_ensemble_over_the_memory_budget_does_not_fit():
    # 15,103 trees is what the ladder's XGBoost arm actually produced.
    c = tree_ensemble_cost(n_trees=15_103, max_depth=4)
    assert c.int8_bytes > BUDGET_BYTES
    assert not c.fits


def test_a_small_ensemble_is_not_rejected_on_memory_alone():
    c = tree_ensemble_cost(n_trees=200, max_depth=4)
    assert c.int8_bytes < BUDGET_BYTES
    assert c.fits


def test_persistence_costs_nothing_and_fits():
    c = constant_cost()
    assert c.macs == 0 and c.int8_bytes == 0
    assert c.fits and c.latency_fraction == 0.0


def test_fractions_are_reported_against_the_g5_limits():
    c = ridge_cost(32, 8, 30)
    assert c.latency_fraction == pytest.approx(c.latency_ms / BUDGET_LATENCY_MS)
    assert c.memory_fraction == pytest.approx(c.int8_bytes / BUDGET_BYTES)
