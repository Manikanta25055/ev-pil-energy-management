"""What each forecasting arm costs on the ESP32-S3, alongside what it scores.

Spec 7.1 is budget first, then model, and G1 measured the budget: **29.82
MMAC/s** int8 on one core at 240 MHz. G5 asks for the deployed forecaster
within **40 ms on core 1** with model plus tensor arena at most **300 KB**.

Accuracy reported without cost is how a project discovers in Week 10 that its
best model does not fit. Every arm in the ladder is costed here at the moment
it is scored, so the Pareto front is a running record rather than a Week 6
surprise.

Two different kinds of number live in this module and they are not
interchangeable:

  - MAC counts for the linear and recurrent arms are **arithmetic**. Given the
    shapes they are exact, and dividing by a measured throughput gives a
    latency estimate whose only uncertainty is framework overhead.
  - The tree-ensemble footprint is an **estimate** from node counts and a
    stated bytes-per-node. Tree traversal is branches and loads, not MACs, so
    there is no throughput figure to divide by and no latency is claimed.

G5 measures the real figures on silicon. These size the decision beforehand.
"""

from __future__ import annotations

from dataclasses import dataclass

# Measured at G1, n=1024 row, scalar int8 loop on one core. See
# docs/g1-compute-budget.md. A lower bound: no ESP-NN vector kernels were used.
MEASURED_MMAC_PER_S = 29.82

# Spec 8.2, gate G5.
BUDGET_LATENCY_MS = 40.0
BUDGET_BYTES = 300 * 1024

# Measured on silicon 2026-08-31, scalar int8 C, one core at 240 MHz, for the
# deployed encoder shape (seq 32, d_model 32, 2 layers, 4 heads, horizon 30).
# Repeatable to 0.1 us across resets. See docs/g5-latency.md.
MEASURED_ENCODER_US = 36_457.2

# What the MAC-count estimate gave for the same graph. The gap is the point:
# dividing multiply-accumulates by a measured MAC rate ignores softmax, layer
# normalisation, requantisation and memory traffic, and on this graph that is
# 64% of the real time.
ESTIMATED_ENCODER_US = 22_284.0

# The LSTM at hidden 64, one layer, measured the same way on the same silicon.
# It is here because it settles what the Transformer's gap was evidence of. The
# LSTM has no softmax, so if attention were the explanation its estimate would
# have been close. It is 77% low, worse than the Transformer's 64%: four gates
# per timestep over 32 timesteps is 8,192 sigmoid and tanh evaluations, the
# same order of nonlinear work by a different name.
#
# The estimating method was optimistic, not the architecture. What the two
# measurements also do is close the gap between the arms: estimated, the LSTM
# looked 11% faster than the Transformer; measured, it is 4% faster. Estimates
# remain useful for ranking arms and must not be quoted as latencies once a
# measurement exists.
MEASURED_LSTM_US = 35_070.8
ESTIMATED_LSTM_US = 19_844.0

# Storage per decision-tree node: feature index, threshold and a child offset.
# Deliberately optimistic, so that a footprint judged to exceed the budget here
# exceeds it on any real encoding too.
TREE_BYTES_PER_NODE = 8


@dataclass(frozen=True)
class DeployCost:
    """One arm's cost against the G5 budget.

    `int8_bytes` charges one byte per weight and four per bias. Biases are
    added into a 32-bit accumulator on the device, so quantising them costs
    accuracy and saves almost no memory. Charging them one byte, as an earlier
    version did, understated the footprint of the Transformer by 12%, and
    memory is one of the two things G5 gates on.
    """

    macs: int | None            # None where the arm is not a MAC workload
    int8_bytes: int
    latency_ms: float | None    # None where no MAC-based estimate applies
    footprint_estimated: bool   # True when int8_bytes is an estimate, not arithmetic
    n_params: int = 0           # element count, for cross-checks against PyTorch

    @property
    def latency_fraction(self) -> float | None:
        if self.latency_ms is None:
            return None
        return self.latency_ms / BUDGET_LATENCY_MS

    @property
    def memory_fraction(self) -> float:
        return self.int8_bytes / BUDGET_BYTES

    @property
    def fits(self) -> bool:
        """Whether both G5 limits are met.

        An arm with no latency estimate is judged on memory alone, which is
        the charitable reading: if it already fails on memory the latency
        question never arises.
        """
        if self.int8_bytes > BUDGET_BYTES:
            return False
        return self.latency_ms is None or self.latency_ms <= BUDGET_LATENCY_MS


def _latency(macs: int) -> float:
    return macs / (MEASURED_MMAC_PER_S * 1e6) * 1000.0


BIAS_BYTES = 4
WEIGHT_BYTES = 1


def _footprint(weights: int, biases: int) -> int:
    return weights * WEIGHT_BYTES + biases * BIAS_BYTES


def constant_cost() -> DeployCost:
    """Persistence and drift: a multiply and a repeat, below the noise floor."""
    return DeployCost(macs=0, int8_bytes=0, latency_ms=0.0,
                      footprint_estimated=False, n_params=0)


def ridge_cost(seq_len: int, n_features: int, horizon: int) -> DeployCost:
    """A dense matrix-vector product from the flattened window to the horizon."""
    n_in = seq_len * n_features
    weights = n_in * horizon
    biases = horizon
    macs = n_in * horizon
    return DeployCost(macs=macs, int8_bytes=_footprint(weights, biases),
                      latency_ms=_latency(macs), footprint_estimated=False,
                      n_params=weights + biases)


def lstm_cost(seq_len: int, n_features: int, hidden: int, layers: int,
              horizon: int) -> DeployCost:
    """Recurrence unrolled over the window, plus a dense output head.

    Per timestep a layer computes four gates over both its input and its own
    previous hidden state, so the cost is `4 * (in*hidden + hidden*hidden)`,
    paid `seq_len` times. The elementwise sigmoid and tanh are excluded: they
    are not MACs, and on the S3 they are a lookup, not the binding cost.
    """
    macs = 0
    weights = 0
    biases = 0
    for layer in range(layers):
        n_in = n_features if layer == 0 else hidden
        per_step = 4 * (n_in * hidden + hidden * hidden)
        macs += per_step * seq_len
        weights += per_step
        biases += 4 * 2 * hidden                   # PyTorch keeps two bias vectors
    macs += hidden * horizon
    weights += hidden * horizon
    biases += horizon
    return DeployCost(macs=macs, int8_bytes=_footprint(weights, biases),
                      latency_ms=_latency(macs), footprint_estimated=False,
                      n_params=weights + biases)


def tree_ensemble_cost(n_trees: int, max_depth: int) -> DeployCost:
    """Footprint of a boosted ensemble, estimated from a full-depth node count.

    A tree of depth d holds at most `2^(d+1) - 1` nodes. Real trees are
    pruned below that, so this is an upper bound on a per-tree basis and the
    result is labelled an estimate. No latency is returned: traversal is
    branch-and-load work with no MAC equivalent, and inventing a throughput
    figure for it would be dressing a guess as a measurement.
    """
    nodes = n_trees * (2 ** (max_depth + 1) - 1)
    return DeployCost(macs=None, int8_bytes=nodes * TREE_BYTES_PER_NODE,
                      latency_ms=None, footprint_estimated=True,
                      n_params=nodes)


def transformer_cost(
    seq_len: int,
    d_model: int,
    layers: int,
    n_features: int | None = None,
    n_outputs: int | None = None,
    horizon: int | None = None,
) -> DeployCost:
    """A Transformer encoder's cost, with or without the parts G1 excluded.

    Attention projections, the attention product itself and a feed-forward of
    width `2 * d_model`. Called with three arguments this is the encoder stack
    alone, exactly as in `docs/g1-compute-budget.md`, so it reproduces the G1
    table. Supply `n_features`, `n_outputs` and `horizon` as well to add the
    input embedding and the output head, which is what actually gets deployed.

    The gap between the two is the point of offering both. G1 sized the budget
    on the encoder, and a report that quietly compared a full graph against
    that number would be flattering itself by the difference.

    Positional encoding is sinusoidal, so it costs no parameters and no MACs:
    on the device it is a constant table added to the embedded input.
    """
    per_layer = (
        4 * seq_len * d_model * d_model          # q, k, v and output projections
        + 2 * seq_len * seq_len * d_model        # scores and the weighted sum
        + 2 * seq_len * d_model * (2 * d_model)  # feed-forward, both directions
    )
    macs = per_layer * layers
    # 8*d^2 of weights (four attention projections, two feed-forward layers),
    # 7*d of biases across them, and 4*d for the two layer norms.
    weights = layers * 8 * d_model * d_model
    biases = layers * 11 * d_model

    if n_features is not None:
        macs += seq_len * n_features * d_model
        weights += n_features * d_model
        biases += d_model
    if n_outputs is not None and horizon is not None:
        # The head reads the final token only, so it is paid once per
        # inference rather than once per input sample.
        macs += d_model * horizon * n_outputs
        weights += d_model * horizon * n_outputs
        biases += horizon * n_outputs

    return DeployCost(macs=macs, int8_bytes=_footprint(weights, biases),
                      latency_ms=_latency(macs), footprint_estimated=False,
                      n_params=weights + biases)
