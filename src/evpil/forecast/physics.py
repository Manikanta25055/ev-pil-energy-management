"""The physics residuals of spec 4.2, as functions of a model's own outputs.

A forecaster that predicts battery power alone has nothing to be consistent
with. These residuals only mean something once the model also predicts the
current, voltage and charge that produce that power, which is why
`TARGET_COLUMNS` carries four channels and why the plain and physics-informed
arms share the same head: at matched parameter count the only difference
between them is the loss, which is what ablation A1 asks.

Every function here is written in operations that behave identically on a NumPy
array and a Torch tensor, so the training loss and the reported violation rate
run the same code. A physics metric computed by a second implementation is a
metric that can disagree with the loss it is supposed to describe.

## The three residuals

    r1 = P - V*I                                     electrical consistency
    r2 = (SoC_end - SoC_start) + integral(I dt)/(3600*Q)   charge conservation
    r3 = V - (OCV(SoC) - I*r0)                       terminal-voltage consistency

r1 is spec 4.2 verbatim. **r2 and r3 are both changed, and both reasons are
recorded here.**

r2 is spec 4.2's charge conservation applied across the horizon instead of
step by step, and **it is switched off by default. The reason is a property of
the dataset, not of the residual.**

The logged charge channel holds its value across 95.8% of consecutive 10 Hz
samples, and it moves in bursts rather than evenly: the gap between updates is
one sample when it moves and 75 or more when it does not, up to 59 seconds.
The consequence is measured rather than inferred. **The median 3.0 s horizon
in this archive contains exactly one distinct SoC value.** Logged charge change
over such a horizon is 0.00, against a coulomb-implied 2.2e-4.

That defeats both forms. The pointwise derivative is zero on 94.5% of samples
against a coulomb term of 1.4e-4 per second, so it measures the stepping and
not the current. The horizon-integral form is better conditioned but has no
signal to condition on: over three seconds the channel usually does not move.

Switching it off is the conservative choice rather than the convenient one.
r2 constrains the model's own outputs, so with a weight on it the residual
pushes predicted charge to fall by the predicted current's integral while the
data loss pushes it to stay flat, because flat is what the channel logs. The
two disagree, and the disagreement is caused by the logging rate. A model
trained through that conflict would be made to contradict its own target in
order to satisfy a law the data cannot see. `run_transformer.py` runs one arm
with r2 enabled so the cost of doing so is measured and not merely asserted.

Charge conservation is a real constraint and it is not being dismissed. It is
testable on this archive over minutes, which is the trip-energy check G2
already makes, and it is not testable over three seconds.
`r2_charge_pointwise` keeps spec 4.2's literal form so the measurement can be
reproduced. The spec writes r3 as a power-balance inequality,
`relu(P_mech/eta_max + I^2*R - P)`, which needs future mechanical power.
`P_mech` is not a channel of the canonical schema, it is not available at
inference, and reconstructing it would put the plant inside the training loop
and make the forecaster depend on the very model G2 validated separately. What
replaces it is the Thevenin relation the project already built and validated:
terminal voltage must equal open-circuit voltage at the predicted charge, less
the ohmic drop at the predicted current. It constrains the same three channels,
it is computable from model outputs alone, and it is an equality the logged data
can actually support.

The substitution carries one assumption with it. The OCV curve is a
representative 96s NCA characteristic rather than an i3 measurement (CAVEATS
note 5 in `scripts/identify_params.py`), so r3 imports that assumption into the
loss. Its weight is validation-tuned like the others, and setting it to zero is
the sub-ablation that says what it was worth.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Channel order of the multi-target head, matching windows.TARGET_COLUMNS.
P, I, V, SOC = 0, 1, 2, 3


@dataclass(frozen=True)
class PhysicsConstants:
    """Everything the residuals need, in one place with its provenance.

    Defaults are the identified i3 set. `capacity_ah` is measured by Coulomb
    counting; `r0_ohm` is identified; the OCV table is an assumption.
    """

    capacity_ah: float = 61.7
    r0_ohm: float = 0.01
    ocv_soc_points: tuple[float, ...] = (0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0)
    ocv_volts: tuple[float, ...] = (307.2, 336.0, 348.5, 357.1, 371.5, 388.8, 398.4)
    dt_s: float = 0.1

    @classmethod
    def from_params(cls, params: dict, dt_s: float = 0.1) -> PhysicsConstants:
        """Read what is available out of a `data/i3_params.json` payload."""
        return cls(
            capacity_ah=float(params["published"]["capacity_ah"]),
            r0_ohm=float(params["identified"]["r0_ohm"]),
            dt_s=dt_s,
        )


def _relu(x):
    """Elementwise max(x, 0), in arithmetic both NumPy and Torch agree on."""
    return (x + abs(x)) * 0.5


def ocv_v(soc, const: PhysicsConstants):
    """Open-circuit voltage, piecewise linear, clamped at the table ends.

    Written as a cumulative sum of clipped segment weights rather than as an
    interpolation call, so that the same expression runs on a NumPy array and
    on a Torch tensor that has to stay differentiable.
    """
    pts, volts = const.ocv_soc_points, const.ocv_volts
    out = soc * 0.0 + volts[0]
    for k in range(len(pts) - 1):
        width = pts[k + 1] - pts[k]
        # clip((soc - p_k) / width, 0, 1) without a backend-specific clip
        t = (soc - pts[k]) / width
        t = _relu(t) - _relu(t - 1.0)
        out = out + t * (volts[k + 1] - volts[k])
    return out


def r1_electrical(y):
    """`P - V*I`. Zero when the predicted power matches its own factors."""
    return y[..., P] - y[..., V] * y[..., I]


def r2_charge_pointwise(y, const: PhysicsConstants):
    """`dSoC/dt + I/(3600*Q)` step by step, using a centred difference.

    Spec 4.2 verbatim, and **not what this project uses**. Measured on the i3
    archive, the logged charge channel holds its value across 95.8% of
    consecutive 10 Hz samples: it steps roughly every 2.4 s rather than every
    0.1 s. Differentiating it at 0.1 s therefore returns a train of zeros
    punctuated by spikes, which is the shape of the logging behaviour and not
    of the current. Fitted against that, this residual is unsatisfiable by
    construction, and its violation rate sits near 1.0 for any weight.

    Kept because the measurement is worth being able to reproduce, and because
    a reader comparing against spec 4.2 should be able to run the literal form
    and see why it was replaced. `r2_charge` is the one that trains.
    """
    soc = y[..., SOC]
    if soc.shape[-1] < 3:
        raise ValueError(
            f"a centred difference needs at least 3 horizon steps, got "
            f"{soc.shape[-1]}. A shorter horizon returns an empty residual, "
            f"whose mean is NaN and whose gradient is silently zero."
        )
    d_soc = (soc[..., 2:] - soc[..., :-2]) / (2.0 * const.dt_s)
    i_mid = y[..., 1:-1, I]
    return d_soc + i_mid / (3600.0 * const.capacity_ah)


def r2_charge(y, const: PhysicsConstants):
    """Charge conservation across the whole horizon rather than step by step.

    `(SoC_end - SoC_start) + integral(I dt) / (3600*Q)`, trapezoidal.

    The same conservation law as the pointwise form, applied over an interval
    the charge channel can actually resolve. Over 3.0 s the logged SoC moves
    once or twice, and a change measured across the full horizon is a real
    measurement; the same change divided into thirty 0.1 s differences is
    mostly quantisation. Integrating the current instead of differentiating the
    charge also puts the noisy operation on the smooth channel.

    Returns one residual per window, not one per step, which is the honest
    resolution: there is one independent charge measurement in this horizon,
    not thirty.
    """
    soc = y[..., SOC]
    if soc.shape[-1] < 2:
        raise ValueError(
            f"charge conservation needs at least 2 horizon steps, got "
            f"{soc.shape[-1]}"
        )
    current = y[..., I]
    # Trapezoidal rule: interior samples full weight, endpoints half.
    integral = (
        current.sum(-1) - 0.5 * (current[..., 0] + current[..., -1])
    ) * const.dt_s
    return (soc[..., -1] - soc[..., 0]) + integral / (3600.0 * const.capacity_ah)


def r3_terminal(y, const: PhysicsConstants):
    """`V - (OCV(SoC) - I*r0)`, the Thevenin relation on the predicted state.

    See the module docstring for why this stands in for spec 4.2's power-balance
    inequality.
    """
    return y[..., V] - (ocv_v(y[..., SOC], const) - y[..., I] * const.r0_ohm)


@dataclass(frozen=True)
class ResidualWeights:
    """Loss weights, one per residual. Validation-tuned, per spec 4.2.

    The training loss divides each residual by the natural scale of the channel
    it constrains before applying its weight, so these three numbers are
    comparable to each other. Without that they would not be: r1 is in watts
    and r2 is a charge fraction.

    **lambda_2 defaults to zero**, because the logged charge channel does not
    move within a 3.0 s horizon on this archive and a weight on r2 would train
    the model to contradict its own target. The measurement is in the module
    docstring. This default is a claim about this dataset at this horizon, not
    about charge conservation, and it is the one default here that should be
    revisited if either changes.
    """

    lambda_1: float = 1.0
    lambda_2: float = 0.0
    lambda_3: float = 1.0


def residual_terms(y, const: PhysicsConstants) -> dict:
    """All three residuals for a prediction tensor `(..., horizon, 4)`."""
    return {
        "r1": r1_electrical(y),
        "r2": r2_charge(y, const),
        "r3": r3_terminal(y, const),
    }


def residual_terms_pointwise(y, const: PhysicsConstants) -> dict:
    """As `residual_terms`, with spec 4.2's literal step-by-step r2.

    For reproducing the measurement that motivated replacing it. Not used in
    training.
    """
    return {
        "r1": r1_electrical(y),
        "r2": r2_charge_pointwise(y, const),
        "r3": r3_terminal(y, const),
    }


def violation_rate(y, const: PhysicsConstants, tol: dict[str, float]) -> dict[str, float]:
    """Fraction of predicted steps whose residual exceeds a stated tolerance.

    Spec 6.2 asks for the physics-violation rate as a metric in its own right,
    independent of accuracy, and a rate needs a threshold. The tolerances are
    supplied by the caller rather than defaulted here, because a number that
    decides whether a model "violates physics" should be visible at the call
    site and recorded in the report, not buried in a library.
    """
    res = residual_terms(np.asarray(y, dtype=np.float64), const)
    out = {}
    for name, value in res.items():
        if name not in tol:
            raise KeyError(f"no tolerance given for residual {name!r}")
        out[name] = float(np.mean(np.abs(value) > tol[name]))
    return out
