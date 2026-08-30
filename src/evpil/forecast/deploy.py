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

# Storage per decision-tree node: feature index, threshold and a child offset.
# Deliberately optimistic, so that a footprint judged to exceed the budget here
# exceeds it on any real encoding too.
TREE_BYTES_PER_NODE = 8


@dataclass(frozen=True)
class DeployCost:
    """One arm's cost against the G5 budget."""

    macs: int | None            # None where the arm is not a MAC workload
    int8_bytes: int
    latency_ms: float | None    # None where no MAC-based estimate applies
    footprint_estimated: bool   # True when int8_bytes is an estimate, not arithmetic

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


def constant_cost() -> DeployCost:
    """Persistence and drift: a multiply and a repeat, below the noise floor."""
    return DeployCost(macs=0, int8_bytes=0, latency_ms=0.0, footprint_estimated=False)


def ridge_cost(seq_len: int, n_features: int, horizon: int) -> DeployCost:
    """A dense matrix-vector product from the flattened window to the horizon."""
    n_in = seq_len * n_features
    weights = (n_in + 1) * horizon
    macs = n_in * horizon
    return DeployCost(macs=macs, int8_bytes=weights, latency_ms=_latency(macs),
                      footprint_estimated=False)


def lstm_cost(seq_len: int, n_features: int, hidden: int, layers: int,
              horizon: int) -> DeployCost:
    """Recurrence unrolled over the window, plus a dense output head.

    Per timestep a layer computes four gates over both its input and its own
    previous hidden state, so the cost is `4 * (in*hidden + hidden*hidden)`,
    paid `seq_len` times. The elementwise sigmoid and tanh are excluded: they
    are not MACs, and on the S3 they are a lookup, not the binding cost.
    """
    macs = 0
    params = 0
    for layer in range(layers):
        n_in = n_features if layer == 0 else hidden
        per_step = 4 * (n_in * hidden + hidden * hidden)
        macs += per_step * seq_len
        params += per_step + 4 * 2 * hidden        # weights plus the two bias vectors
    macs += hidden * horizon
    params += hidden * horizon + horizon
    return DeployCost(macs=macs, int8_bytes=params, latency_ms=_latency(macs),
                      footprint_estimated=False)


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
                      latency_ms=None, footprint_estimated=True)


def transformer_cost(seq_len: int, d_model: int, layers: int) -> DeployCost:
    """The G1 config table's encoder stack, for comparison against the ladder.

    Attention projections, the attention product itself and a feed-forward of
    width `2 * d_model`. Input embedding and output head are excluded, exactly
    as in `docs/g1-compute-budget.md`, so the numbers line up with the G1 table.
    """
    per_layer = (
        4 * seq_len * d_model * d_model          # q, k, v and output projections
        + 2 * seq_len * seq_len * d_model        # scores and the weighted sum
        + 2 * seq_len * d_model * (2 * d_model)  # feed-forward, both directions
    )
    macs = per_layer * layers
    params = layers * (4 * d_model * d_model + 4 * d_model * d_model)
    return DeployCost(macs=macs, int8_bytes=params, latency_ms=_latency(macs),
                      footprint_estimated=False)
