"""Does the ranking of the two energy managers depend on uncertain plant
parameters? (plan docs/2026-10-14-measurement-plan.md, item H3)

The identified model has a rolling coefficient 2.2 times a published coastdown
value, a rotational factor that absorbs other losses, an assumed regeneration
ceiling and an assumed drivetrain efficiency. Each is changed alone, the
rule-based manager and the deployed learned policy (corrected retraining, seed
3, no forecast) drive the varied vehicle, and the sign of learned minus rule
energy on the comparable scale is recorded.

Only the simulated vehicle changes. The controllers keep the nominal model in
their feedforward and observations, as they would on a real car whose
parameters were misidentified. No sensor noise; the host loop is
deterministic. SIMULATED.

    PYTHONPATH="src:." python3 scripts/plant_sensitivity.py
"""

from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path

from evpil.forecast import _openmp        # noqa: F401  (import-order guard)

from evpil.control.actor import Actor
from evpil.control.cycles import load_cycle
from evpil.control.rule_ems import RuleParams, rule_action
from evpil.control.sac_policy import actor_policy
from evpil.control.sim import simulate
from scripts.identify_params import params_from_json

PUBLISHED_C_RR = 0.00878   # 2013 Nissan Leaf coastdown, cited in Section IV


def variants(p):
    rp = p.regen
    return [
        ("nominal", p),
        ("c_rr published 0.00878", dataclasses.replace(p, c_rr=PUBLISHED_C_RR)),
        ("rotational factor 0", dataclasses.replace(p, rot_mass_factor=0.0)),
        ("regen ceiling x0.8", dataclasses.replace(
            p, regen=dataclasses.replace(rp, power_limit_w=0.8 * rp.power_limit_w))),
        ("regen ceiling x1.2", dataclasses.replace(
            p, regen=dataclasses.replace(rp, power_limit_w=1.2 * rp.power_limit_w))),
        ("drivetrain eta -0.03", dataclasses.replace(
            p, drivetrain_eta=p.drivetrain_eta - 0.03)),
        ("drivetrain eta +0.03", dataclasses.replace(
            p, drivetrain_eta=min(1.0, p.drivetrain_eta + 0.03))),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default="data/i3_params.json")
    ap.add_argument("--actor", default="data/actors-corrected/sac-without-forecast-seed3.npz")
    ap.add_argument("--cycles", nargs="+", default=["us06", "hwfet"])
    ap.add_argument("--soc0", type=float, default=0.80)
    ap.add_argument("--t-ambient", type=float, default=12.0)
    ap.add_argument("--out-json", default="docs/2026-10-14-plant-sensitivity.json")
    args = ap.parse_args()

    nominal = params_from_json(args.params)
    actor = Actor.load(args.actor)
    rules = RuleParams()
    rows = []
    for cname in args.cycles:
        cycle = load_cycle(cname)
        for label, plant in variants(nominal):
            rule = simulate(plant, cycle,
                            lambda o: rule_action(rules, soc_frac=o.soc_frac,
                                                  v_mps=o.v_mps),
                            soc0=args.soc0, t_ambient_c=args.t_ambient,
                            ff_params=nominal)
            learned = simulate(plant, cycle,
                               actor_policy(actor, cycle, nominal,
                                            use_forecast=False),
                               soc0=args.soc0, t_ambient_c=args.t_ambient,
                               ff_params=nominal)
            diff = 100.0 * (learned.equivalent_wh_per_km
                            / rule.equivalent_wh_per_km - 1.0)
            rows.append({"cycle": cname, "variant": label,
                         "rule_wh_per_km": rule.equivalent_wh_per_km,
                         "learned_wh_per_km": learned.equivalent_wh_per_km,
                         "diff_pct": diff})
            print(f"{cname:6s} {label:24s} rule {rule.equivalent_wh_per_km:7.2f}"
                  f"  learned {learned.equivalent_wh_per_km:7.2f}  {diff:+.2f}%",
                  flush=True)

    signs = {r["diff_pct"] > 0 for r in rows}
    Path(args.out_json).write_text(json.dumps({
        "provenance": "SIMULATED on the host; plant varied, controllers keep "
                      "the nominal model; plan item H3",
        "actor": args.actor, "rows": rows,
        "sign_unchanged": len(signs) == 1,
        "learned_higher_everywhere": signs == {True}}, indent=1) + "\n")
    print(f"sign unchanged in every variant: {len(signs) == 1}")
    print(f"wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
