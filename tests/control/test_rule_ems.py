import numpy as np
import pytest

from evpil.control.rule_ems import RuleParams, rule_action

P = RuleParams()


def test_the_action_is_inside_its_declared_bounds_everywhere():
    """The rule manager is the fallback the control task runs when the outer
    loop goes quiet, so an out-of-range command from it has nothing downstream
    to catch it."""
    for soc in np.linspace(0.0, 1.0, 101):
        for v in np.linspace(0.0, 45.0, 46):
            a = rule_action(P, soc_frac=float(soc), v_mps=float(v))
            assert 0.0 <= a.regen_blend <= 1.0
            assert P.p_limit_min_w <= a.p_limit_w <= P.p_limit_max_w
            assert 0.0 <= a.aux_derate <= P.aux_derate_max


def test_regeneration_is_withdrawn_as_the_pack_fills():
    blends = [rule_action(P, soc_frac=s, v_mps=20.0).regen_blend
              for s in (0.50, 0.85, 0.90, 0.94, 0.99)]
    assert blends == sorted(blends, reverse=True)
    assert blends[0] == pytest.approx(1.0)
    assert blends[-1] == pytest.approx(0.0)


def test_regeneration_fades_out_before_standstill():
    assert rule_action(P, soc_frac=0.6, v_mps=0.0).regen_blend == 0.0
    assert rule_action(P, soc_frac=0.6, v_mps=1.0).regen_blend < 1.0
    assert rule_action(P, soc_frac=0.6, v_mps=5.0).regen_blend == pytest.approx(1.0)


def test_the_discharge_ceiling_falls_as_the_pack_empties():
    limits = [rule_action(P, soc_frac=s, v_mps=20.0).p_limit_w
              for s in (0.80, 0.20, 0.12, 0.07)]
    assert limits == sorted(limits, reverse=True)
    assert limits[0] == pytest.approx(P.p_limit_max_w)
    assert limits[-1] == pytest.approx(P.p_limit_min_w)


def test_the_auxiliary_load_is_shed_only_near_the_floor_and_never_fully():
    assert rule_action(P, soc_frac=0.60, v_mps=20.0).aux_derate == 0.0
    deep = rule_action(P, soc_frac=0.07, v_mps=20.0).aux_derate
    assert deep == pytest.approx(P.aux_derate_max)
    assert deep < 1.0        # a controller that switches the heater off in
                             # winter has not saved anything a driver accepts


def test_the_policy_is_memoryless():
    """No mode means no mode to get stuck in, which is what makes this arm
    trustworthy as a fallback."""
    a = rule_action(P, soc_frac=0.5, v_mps=10.0)
    rule_action(P, soc_frac=0.99, v_mps=0.0)
    b = rule_action(P, soc_frac=0.5, v_mps=10.0)
    assert a == b
