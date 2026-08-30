import pytest
from evpil.plant.battery import (
    BatteryParams, BatteryState, battery_step, clamp_current, current_for_power,
    emf_v, max_power_w, ocv_v, r0_at, terminal_voltage_v,
)

P = BatteryParams(
    capacity_ah=60.0,
    ocv_soc_points=(0.0, 0.5, 1.0),
    ocv_volts=(300.0, 350.0, 400.0),
    r0_ohm=0.05,
    r1_ohm=0.01,
    c1_farad=2000.0,
    i_discharge_max_a=400.0,
    i_charge_max_a=150.0,
    soc_min=0.05,
    soc_max=0.98,
    r0_temp_coeff_per_c=-0.004,
    t_ref_c=25.0,
)


def test_ocv_at_table_points():
    assert ocv_v(P, 0.0) == pytest.approx(300.0)
    assert ocv_v(P, 0.5) == pytest.approx(350.0)
    assert ocv_v(P, 1.0) == pytest.approx(400.0)


def test_ocv_interpolates_linearly_between_points():
    assert ocv_v(P, 0.25) == pytest.approx(325.0)
    assert ocv_v(P, 0.75) == pytest.approx(375.0)


def test_ocv_clamps_outside_the_table():
    assert ocv_v(P, -0.2) == pytest.approx(300.0)
    assert ocv_v(P, 1.5) == pytest.approx(400.0)


def test_r0_at_reference_temperature():
    assert r0_at(P, 25.0) == pytest.approx(0.05)


def test_r0_rises_as_the_cell_gets_colder():
    cold = r0_at(P, 0.0)
    hot = r0_at(P, 45.0)
    assert cold > 0.05 > hot
    # 0.05 * (1 + -0.004 * (0 - 25)) == 0.05 * 1.1
    assert cold == pytest.approx(0.055, rel=1e-9)


def test_r0_never_goes_non_positive_at_extreme_heat():
    assert r0_at(P, 500.0) > 0.0


def test_terminal_voltage_drops_under_discharge():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    assert terminal_voltage_v(P, st, i_a=0.0) == pytest.approx(350.0)
    assert terminal_voltage_v(P, st, i_a=100.0) == pytest.approx(345.0)


def test_terminal_voltage_rises_under_charge():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    assert terminal_voltage_v(P, st, i_a=-100.0) == pytest.approx(355.0)


def test_terminal_voltage_includes_the_rc_branch():
    st = BatteryState(soc_frac=0.5, v_rc_v=2.0, t_batt_c=25.0)
    assert terminal_voltage_v(P, st, i_a=100.0) == pytest.approx(343.0)


def test_coulomb_counting_over_one_step():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    out = battery_step(P, st, i_a=100.0, dt_s=0.1)
    # 100 A for 0.1 s out of 60 Ah is 10 / 216000 of full charge.
    assert out.soc_frac == pytest.approx(0.5 - 4.6296296296e-5, rel=1e-9)


def test_one_c_discharge_drops_soc_at_the_expected_rate():
    # 60 A from a 60 Ah pack is 1C: 30 minutes removes half the charge.
    # Start at 0.9 so the result stays clear of soc_max and soc_min and the
    # test measures the discharge rate rather than the clamp.
    st = BatteryState(soc_frac=0.9, v_rc_v=0.0, t_batt_c=25.0)
    for _ in range(1800):
        st = battery_step(P, st, i_a=60.0, dt_s=1.0)
    assert st.soc_frac == pytest.approx(0.4, rel=1e-9)


def test_rc_branch_charges_toward_its_steady_state():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    out = battery_step(P, st, i_a=100.0, dt_s=0.1)
    # dv_rc = dt * (i/c1 - v_rc/(r1*c1)) = 0.1 * (100/2000 - 0) = 0.005
    assert out.v_rc_v == pytest.approx(0.005, rel=1e-9)

    for _ in range(100000):
        out = battery_step(P, out, i_a=100.0, dt_s=0.1)
    assert out.v_rc_v == pytest.approx(100.0 * P.r1_ohm, rel=1e-3)


def test_soc_is_clamped_to_its_bounds():
    st = BatteryState(soc_frac=P.soc_min, v_rc_v=0.0, t_batt_c=25.0)
    assert battery_step(P, st, i_a=400.0, dt_s=10.0).soc_frac == pytest.approx(P.soc_min)

    st = BatteryState(soc_frac=P.soc_max, v_rc_v=0.0, t_batt_c=25.0)
    assert battery_step(P, st, i_a=-400.0, dt_s=10.0).soc_frac == pytest.approx(P.soc_max)


def test_current_is_clamped_to_the_rated_limits():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    assert clamp_current(P, st, 1000.0) == pytest.approx(400.0)
    assert clamp_current(P, st, -1000.0) == pytest.approx(-150.0)
    assert clamp_current(P, st, 50.0) == pytest.approx(50.0)


def test_charging_is_blocked_at_full_and_discharge_at_empty():
    full = BatteryState(soc_frac=P.soc_max, v_rc_v=0.0, t_batt_c=25.0)
    assert clamp_current(P, full, -100.0) == pytest.approx(0.0)

    empty = BatteryState(soc_frac=P.soc_min, v_rc_v=0.0, t_batt_c=25.0)
    assert clamp_current(P, empty, 100.0) == pytest.approx(0.0)


def test_emf_is_ocv_less_the_rc_drop():
    st = BatteryState(soc_frac=0.5, v_rc_v=2.0, t_batt_c=25.0)
    assert emf_v(P, st) == pytest.approx(348.0)


def test_current_for_power_is_zero_at_zero_power():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    assert current_for_power(P, st, 0.0) == pytest.approx(0.0, abs=1e-12)


def test_current_for_power_round_trips_through_terminal_voltage():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    for target in (5000.0, 20000.0, 50000.0):
        i = current_for_power(P, st, target)
        assert terminal_voltage_v(P, st, i) * i == pytest.approx(target, rel=1e-9)


def test_current_for_power_handles_charging():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    i = current_for_power(P, st, -20000.0)
    assert i < 0.0
    assert terminal_voltage_v(P, st, i) * i == pytest.approx(-20000.0, rel=1e-9)


def test_current_for_power_clamps_at_the_matched_load_point():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    # Peak power is E^2 / (4 r0) = 350^2 / 0.2 = 612500 W.
    assert max_power_w(P, st) == pytest.approx(612500.0, rel=1e-9)

    i = current_for_power(P, st, 1e9)          # far beyond what is deliverable
    assert i == pytest.approx(350.0 / (2 * 0.05), rel=1e-9)


def test_lower_root_is_chosen_not_the_upper():
    st = BatteryState(soc_frac=0.5, v_rc_v=0.0, t_batt_c=25.0)
    i = current_for_power(P, st, 100000.0)
    assert i < 350.0 / (2 * 0.05), "must stay on the physical side of peak power"
