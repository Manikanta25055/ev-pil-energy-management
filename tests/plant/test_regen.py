import pytest
from evpil.plant.battery import BatteryParams, BatteryState
from evpil.plant.regen import RegenParams, split_braking

BP = BatteryParams(
    capacity_ah=60.0, ocv_soc_points=(0.0, 0.5, 1.0), ocv_volts=(300.0, 350.0, 400.0),
    r0_ohm=0.05, r1_ohm=0.01, c1_farad=2000.0,
    i_discharge_max_a=400.0, i_charge_max_a=150.0, soc_min=0.05, soc_max=0.98,
)
RP = RegenParams(power_limit_w=50000.0, blend_min=0.0, blend_max=1.0)
ST = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)


def test_driving_produces_no_braking_split():
    regen, friction = split_braking(30000.0, 0.8, regen_params=RP, batt_params=BP,
                                    batt_state=ST, v_term_v=350.0)
    assert regen == pytest.approx(0.0)
    assert friction == pytest.approx(0.0)


def test_blend_sets_the_regenerated_fraction():
    regen, friction = split_braking(-20000.0, 0.75, regen_params=RP, batt_params=BP,
                                    batt_state=ST, v_term_v=350.0)
    assert regen == pytest.approx(-15000.0)
    assert friction == pytest.approx(-5000.0)


def test_regen_and_friction_always_sum_to_the_demand():
    regen, friction = split_braking(-40000.0, 0.6, regen_params=RP, batt_params=BP,
                                    batt_state=ST, v_term_v=350.0)
    assert regen + friction == pytest.approx(-40000.0)


def test_regen_capped_by_the_declared_power_limit():
    regen, friction = split_braking(-90000.0, 1.0, regen_params=RP, batt_params=BP,
                                    batt_state=ST, v_term_v=350.0)
    assert regen == pytest.approx(-50000.0)
    assert friction == pytest.approx(-40000.0)


def test_regen_capped_by_the_battery_charge_current_limit():
    # 150 A charge limit at 350 V terminal is 52.5 kW, above the 50 kW power
    # limit, so lower the terminal voltage to make current the binding constraint.
    regen, friction = split_braking(-90000.0, 1.0, regen_params=RP, batt_params=BP,
                                    batt_state=ST, v_term_v=200.0)
    assert regen == pytest.approx(-30000.0)     # 150 A * 200 V
    assert friction == pytest.approx(-60000.0)


def test_no_regen_when_the_battery_is_full():
    full = BatteryState(soc_frac=BP.soc_max, v_rc_v=0.0, t_batt_c=25.0)
    regen, friction = split_braking(-30000.0, 1.0, regen_params=RP, batt_params=BP,
                                    batt_state=full, v_term_v=350.0)
    assert regen == pytest.approx(0.0)
    assert friction == pytest.approx(-30000.0)


def test_blend_is_clamped_to_its_declared_range():
    a, _ = split_braking(-20000.0, 5.0, regen_params=RP, batt_params=BP,
                         batt_state=ST, v_term_v=350.0)
    b, _ = split_braking(-20000.0, 1.0, regen_params=RP, batt_params=BP,
                         batt_state=ST, v_term_v=350.0)
    assert a == pytest.approx(b)

    c, d = split_braking(-20000.0, -3.0, regen_params=RP, batt_params=BP,
                         batt_state=ST, v_term_v=350.0)
    assert c == pytest.approx(0.0)
    assert d == pytest.approx(-20000.0)
