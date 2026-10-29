import pytest
from core.units import Dimension, UnitSystem, factor

F = UnitSystem.TONF_M
T = UnitSystem.N_MM
# F_f=9806.65, L_f=1000 ; F_t=1.0, L_t=1.0

def approx(a, b, rel=1e-9):
    return abs(a - b) <= rel * max(abs(a), abs(b), 1.0)

def test_length():
    assert approx(factor(Dimension.LENGTH, F, T), 1000.0)

def test_force():
    assert approx(factor(Dimension.FORCE, F, T), 9806.65)

def test_stress():
    assert approx(factor(Dimension.STRESS, F, T), 9806.65 / 1000**2)

def test_area():
    assert approx(factor(Dimension.AREA, F, T), 1000.0**2)

def test_i3():
    assert approx(factor(Dimension.I3, F, T), 1000.0**3)

def test_i4():
    assert approx(factor(Dimension.I4, F, T), 1000.0**4)

def test_moment():
    assert approx(factor(Dimension.MOMENT, F, T), 9806.65 * 1000.0)

def test_mass():
    assert approx(factor(Dimension.MASS, F, T), 9806.65 / 1000.0)

def test_mass_inertia():
    assert approx(factor(Dimension.MASS_INERTIA, F, T), 9806.65 * 1000.0)

def test_mass_density():
    assert approx(factor(Dimension.MASS_DENSITY, F, T), 9806.65 / 1000.0**4)

def test_weight_density():
    assert approx(factor(Dimension.WEIGHT_DENSITY, F, T), 9806.65 / 1000.0**3)

def test_line_load():
    assert approx(factor(Dimension.LINE_LOAD, F, T), 9806.65 / 1000.0)

def test_area_load():
    assert approx(factor(Dimension.AREA_LOAD, F, T), 9806.65 / 1000.0**2)

def test_accel():
    assert approx(factor(Dimension.ACCEL, F, T), 1000.0)


def test_thermal_exp():
    assert approx(factor(Dimension.THERMAL_EXP, F, T), 1.0)

def test_temp_same_unit():
    """İki sistem de °C ise TEMP factor = 1.0 (delta)."""
    assert factor(Dimension.TEMP, UnitSystem.N_MM, UnitSystem.KN_M) == 1.0
    assert factor(Dimension.TEMP, UnitSystem.TONF_M, UnitSystem.KGF_CM) == 1.0

def test_temp_delta_c_to_f():
    """Delta: 1 °C farkı = 1.8 °F farkı."""
    assert approx(factor(Dimension.TEMP, UnitSystem.N_MM, UnitSystem.LB_IN), 9.0 / 5.0)

def test_temp_delta_f_to_c():
    """Delta: 1 °F farkı = 5/9 °C farkı."""
    assert approx(factor(Dimension.TEMP, UnitSystem.LB_IN, UnitSystem.N_MM), 5.0 / 9.0)

def test_roundtrip():
    for d in Dimension:
        f1 = factor(d, F, T)
        f2 = factor(d, T, F)
        assert approx(f1 * f2, 1.0, rel=1e-12)

def test_temp_delta():
    assert approx(factor(Dimension.TEMP, UnitSystem.N_MM, UnitSystem.LB_IN), 9.0 / 5.0)
    assert approx(factor(Dimension.TEMP, UnitSystem.LB_IN, UnitSystem.N_MM), 5.0 / 9.0)

