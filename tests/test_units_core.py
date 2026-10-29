import pytest
from core.units import UnitSystem, Dimension, factor, convert_value
from tests.conftest import snapshot   # opsiyonel


SYSTEMS = [
    UnitSystem.N_MM, UnitSystem.N_M,
    UnitSystem.KN_MM, UnitSystem.KN_M,
    UnitSystem.KGF_MM, UnitSystem.KGF_M, UnitSystem.KGF_CM,
    UnitSystem.TONF_MM, UnitSystem.TONF_M,
    UnitSystem.LB_IN, UnitSystem.KIP_IN, UnitSystem.KIP_FT,
]


# --- from_sap ---
@pytest.mark.parametrize("raw,expected", [
    ("N, mm, C", UnitSystem.N_MM),
    ("Tonf, m, C", UnitSystem.TONF_M),
    ("Ton. m. C", UnitSystem.TONF_M),         # v10
    ("Ton. m. C ", UnitSystem.TONF_M),
    ("kN, m, C", UnitSystem.KN_M),
    ("lb, in, F", UnitSystem.LB_IN),
    ("", UnitSystem.N_MM),
    (None, UnitSystem.N_MM),
    ("garbage", UnitSystem.N_MM),
])
def test_from_sap(raw, expected):
    assert UnitSystem.from_sap(raw) == expected


# --- factor: bilinen değerler ---
def test_factor_length_tonf_m_to_n_mm():
    assert factor(Dimension.LENGTH, UnitSystem.TONF_M, UnitSystem.N_MM) == pytest.approx(1000.0)

def test_factor_force_tonf_m_to_n_mm():
    assert factor(Dimension.FORCE, UnitSystem.TONF_M, UnitSystem.N_MM) == pytest.approx(9806.65)

def test_factor_stress_tonf_m_to_n_mm():
    assert factor(Dimension.STRESS, UnitSystem.TONF_M, UnitSystem.N_MM) == pytest.approx(9806.65 / 1e6)

def test_factor_mass_tonf_m_to_n_mm():
    assert factor(Dimension.MASS, UnitSystem.TONF_M, UnitSystem.N_MM) == pytest.approx(9806.65 / 1000.0)


# --- roundtrip: her boyut için A→B→A = 1 ---
@pytest.mark.parametrize("dim", list(Dimension))
@pytest.mark.parametrize("a", SYSTEMS)
@pytest.mark.parametrize("b", SYSTEMS)
def test_factor_roundtrip(dim, a, b):
    f1 = factor(dim, a, b)
    f2 = factor(dim, b, a)
    assert f1 * f2 == pytest.approx(1.0, rel=1e-12)


# --- same system → 1.0 ---
@pytest.mark.parametrize("dim", list(Dimension))
@pytest.mark.parametrize("sys", SYSTEMS)
def test_factor_same_system(dim, sys):
    assert factor(dim, sys, sys) == 1.0


# --- convert_value: tuple/list/None/boyutsuz ---
def test_convert_value_none():
    assert convert_value(Dimension.LENGTH, None, UnitSystem.TONF_M, UnitSystem.N_MM) is None

def test_convert_value_dimensionless():
    assert convert_value(None, 42.0, UnitSystem.TONF_M, UnitSystem.N_MM) == 42.0

def test_convert_value_tuple():
    out = convert_value(Dimension.LENGTH, (1.0, 2.0, 3.0), UnitSystem.TONF_M, UnitSystem.N_MM)
    assert out == (1000.0, 2000.0, 3000.0)

def test_convert_value_list():
    out = convert_value(Dimension.LENGTH, [1.0, 2.0], UnitSystem.TONF_M, UnitSystem.N_MM)
    assert out == [1000.0, 2000.0]

def test_convert_value_string_returns_unchanged():
    # Schema'da string olmamalı ama güvenlik
    assert convert_value(Dimension.LENGTH, "abc", UnitSystem.TONF_M, UnitSystem.N_MM) == "abc"


# --- TEMP ---
def test_temp_delta_c_to_f():
    assert factor(Dimension.TEMP, UnitSystem.N_MM, UnitSystem.LB_IN) == pytest.approx(9/5)

def test_temp_same_unit():
    assert factor(Dimension.TEMP, UnitSystem.N_MM, UnitSystem.KN_M) == 1.0