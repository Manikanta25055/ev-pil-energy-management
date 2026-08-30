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
    assert c.n_params == pytest.approx(16_384, rel=0.05)
    assert c.latency_ms == pytest.approx(22.0, abs=0.1)


def test_transformer_parameter_count_agrees_with_pytorch():
    torch = pytest.importorskip("torch")
    from torch import nn

    seq_len, d_model, layers, n_feat, horizon, n_out = 32, 32, 2, 8, 30, 4
    layer = nn.TransformerEncoderLayer(
        d_model=d_model, nhead=4, dim_feedforward=2 * d_model,
        dropout=0.0, batch_first=True, norm_first=True,
    )
    encoder = nn.TransformerEncoder(layer, num_layers=layers,
                                    enable_nested_tensor=False)
    embed = nn.Linear(n_feat, d_model)
    head = nn.Linear(d_model, horizon * n_out)
    actual = sum(
        p.numel()
        for m in (encoder, embed, head)
        for p in m.parameters()
    )
    predicted = transformer_cost(seq_len, d_model, layers, n_features=n_feat,
                                 n_outputs=n_out, horizon=horizon)
    # Biases and layer norms are 4% of the parameter count at this width. A
    # memory gate is the wrong place to be 4% optimistic.
    assert predicted.n_params == actual


def test_the_deployed_graph_costs_more_than_the_encoder_g1_measured():
    encoder_only = transformer_cost(32, 32, 2)
    deployed = transformer_cost(32, 32, 2, n_features=8, n_outputs=4, horizon=30)
    assert deployed.macs > encoder_only.macs
    assert deployed.int8_bytes > encoder_only.int8_bytes
    # The encoder still dominates, which is what made G1's exclusion defensible.
    assert deployed.macs / encoder_only.macs < 1.05


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
    assert lstm_cost(seq_len, n_feat, hidden, 1, horizon).n_params == actual


def test_latency_is_macs_divided_by_the_measured_throughput():
    c = ridge_cost(seq_len=32, n_features=8, horizon=30)
    assert c.macs == 32 * 8 * 30
    assert c.latency_ms == pytest.approx(c.macs / (MEASURED_MMAC_PER_S * 1e6) * 1e3)


def test_ridge_carries_one_bias_per_output():
    c = ridge_cost(seq_len=4, n_features=2, horizon=3)
    assert c.n_params == (4 * 2 + 1) * 3


def test_biases_are_charged_four_bytes_not_one():
    # They are added into a 32-bit accumulator on the device, so quantising
    # them costs accuracy and saves nothing. Charging them one byte understated
    # the Transformer's footprint by 12%.
    c = ridge_cost(seq_len=4, n_features=2, horizon=3)
    assert c.int8_bytes == 4 * 2 * 3 * 1 + 3 * 4


def test_the_footprint_matches_what_a_real_quantised_model_occupies():
    torch = pytest.importorskip("torch")
    from torch import nn

    from evpil.forecast.quantise import deployed_bytes

    seq_len, d_model, layers, n_feat, horizon, n_out = 32, 32, 2, 8, 30, 1
    layer = nn.TransformerEncoderLayer(
        d_model=d_model, nhead=4, dim_feedforward=2 * d_model,
        dropout=0.0, batch_first=True, norm_first=True,
    )

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.embed = nn.Linear(n_feat, d_model)
            self.encoder = nn.TransformerEncoder(layer, num_layers=layers,
                                                 enable_nested_tensor=False)
            self.head = nn.Linear(d_model, horizon * n_out)

    predicted = transformer_cost(seq_len, d_model, layers, n_features=n_feat,
                                 n_outputs=n_out, horizon=horizon).int8_bytes
    assert predicted == deployed_bytes(Net())


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


def test_the_measured_encoder_latency_still_fits_the_g5_budget():
    from evpil.forecast.deploy import MEASURED_ENCODER_US

    # Measured, not divided. 36.5 ms against a 40 ms budget leaves 9% of
    # margin, and this is the slowest plausible implementation: scalar C with
    # no ESP-NN vector kernels and a floating-point exponential in the softmax.
    assert MEASURED_ENCODER_US / 1000.0 < BUDGET_LATENCY_MS
    assert MEASURED_ENCODER_US / 1000.0 / BUDGET_LATENCY_MS > 0.85


def test_the_mac_count_estimate_understates_the_measurement():
    from evpil.forecast.deploy import ESTIMATED_ENCODER_US, MEASURED_ENCODER_US

    # This is the finding, not a tolerance. A MAC count cannot see softmax or
    # normalisation, and on this graph those are most of the difference. The
    # assertion exists so that a future change to the cost model which quietly
    # closes the gap has to say so.
    ratio = MEASURED_ENCODER_US / ESTIMATED_ENCODER_US
    assert ratio > 1.5

    estimate = transformer_cost(32, 32, 2, n_features=8, n_outputs=1,
                                horizon=30)
    assert estimate.latency_ms == pytest.approx(ESTIMATED_ENCODER_US / 1000.0,
                                                rel=0.01)
