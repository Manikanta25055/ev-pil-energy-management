"""The sensor arms the registered evaluation can run, by name.

One place, so that the evaluation, the tuning and the architecture study all
build an arm the same way.
"""

from __future__ import annotations

from pathlib import Path

from evpil.control.speed_estimators import (
    BiasAwareFaultKalman, BiasAwareSettings, KinematicFaultKalman,
)


def _b6(nominal, q, q_d, settings):
    return KinematicFaultKalman(nominal, q_mps=q, q_d_mps2=q_d)


def _b7(nominal, q, q_d, settings):
    return BiasAwareFaultKalman(nominal, q_mps=q, q_d_mps2=q_d,
                                settings=BiasAwareSettings(**(settings or {})))


ARMS = {"b6": _b6, "b7": _b7}


def make_arm(name: str, nominal, q: float, q_d: float, settings=None):
    return ARMS[name](nominal, q, q_d, settings)


def reviewer(name: str):
    """A reviewer by name: `monitor`, `healthy`, or a trained model's file
    stem (`gru16v3`, `fastgrnn16v3`, `gru64v3`)."""
    from evpil.control.supervisor import FixedReviewer, RuleMonitor
    from evpil.control.tiny_rnn import TinyReviewer

    if name == "monitor":
        return RuleMonitor()
    if name == "healthy":
        return FixedReviewer(name="healthy")
    # The committed reviewers first; a freshly trained one, not yet copied
    # there, is found under data/reviewer.
    for root in ("models/reviewer", "data/reviewer"):
        path = Path(root) / f"{name}.npz"
        if path.exists():
            return TinyReviewer.load(path, name)
    raise FileNotFoundError(f"no trained reviewer named {name!r}")


def _sup(nominal, q, q_d, settings):
    """B7 with a reviewer around it. `settings`:

      fast, slow     reviewer names; either may be absent
      delay_s        of the slow path (the fast path has none)
      jitter_s, loss, outages, seed   of the slow path
      policy         overrides of `supervisor.Policy`
      b7             overrides of `BiasAwareSettings`
    """
    from evpil.control.supervisor import Channel, Policy, Supervisor

    s = dict(settings or {})
    base = _b7(nominal, q, q_d, s.get("b7"))
    fast = (reviewer(s["fast"]), Channel()) if s.get("fast") else None
    slow = None
    if s.get("slow"):
        slow = (reviewer(s["slow"]), Channel(
            delay_s=s.get("delay_s", 0.15), jitter_s=s.get("jitter_s", 0.0),
            loss=s.get("loss", 0.0),
            outages=tuple(tuple(o) for o in s.get("outages", ())),
            seed=s.get("seed", 0)))
    return Supervisor(base, fast=fast, slow=slow,
                      policy=Policy(**s.get("policy", {})))


ARMS["sup"] = _sup
