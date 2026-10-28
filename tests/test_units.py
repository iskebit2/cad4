"""Aşama 1 — core.units temel testler."""
from core.units import (
    Dimension,
    UnitSystem,
    convert_project_units,
    convert_value,
)


def test_length():
    assert convert_value(Dimension.LENGTH, 1.0, UnitSystem.KN_M, UnitSystem.N_MM) == 1000.0
    assert convert_value(Dimension.LENGTH, 1000.0, UnitSystem.N_MM, UnitSystem.KN_M) == 1.0


def test_force():
    assert convert_value(Dimension.FORCE, 1.0, UnitSystem.KN_M, UnitSystem.N_MM) == 1000.0
    assert convert_value(Dimension.FORCE, 1000.0, UnitSystem.N_MM, UnitSystem.KN_M) == 1.0


def test_stress():
    v = convert_value(Dimension.STRESS, 210000, UnitSystem.N_MM, UnitSystem.KN_M)
    # 210000 N/mm² = 210000000 kN/m²
    assert abs(v - 210000000) < 1e-3
    back = convert_value(Dimension.STRESS, v, UnitSystem.KN_M, UnitSystem.N_MM)
    assert abs(back - 210000) < 1e-6


def test_roundtrip_length():
    """N_MM → KN_M → N_MM"""
    v0 = 6000.0
    v1 = convert_value(Dimension.LENGTH, v0, UnitSystem.N_MM, UnitSystem.KN_M)
    v2 = convert_value(Dimension.LENGTH, v1, UnitSystem.KN_M, UnitSystem.N_MM)
    assert abs(v2 - v0) < 1e-9


def test_convert_project_units():
    """Basit proje — Material + Section."""
    from domain.definition import Material, Section

    class FakeProject:
        unit_system = UnitSystem.N_MM
        ui_dirty = False
        materials = {"S235": Material(name="S235", E1=210000, G12=80769, density=7.85e-6)}
        sections = {"HE220B": Section(
            name="HE220B",
            profile_params={"Area": 9100.0, "I33": 8.09e7, "I22": 2.84e7, "J": 7.7e5,
                            "h": 220.0, "b": 220.0},
        )}

    p = FakeProject()
    E1_orig = p.materials["S235"].E1
    Area_orig = p.sections["HE220B"].profile_params["Area"]

    convert_project_units(p, UnitSystem.KN_M)
    assert p.unit_system == UnitSystem.KN_M
    assert p.ui_dirty is True

    convert_project_units(p, UnitSystem.N_MM)
    assert abs(p.materials["S235"].E1 - E1_orig) / E1_orig < 1e-9
    assert abs(p.sections["HE220B"].profile_params["Area"] - Area_orig) / Area_orig < 1e-9


if __name__ == "__main__":
    test_length()
    test_force()
    test_stress()
    test_roundtrip_length()
    test_convert_project_units()
    print("✅ Aşama 1 testleri geçti")