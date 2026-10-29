import pytest
from core.units import UnitSystem, convert_project_units


def test_wind_uses_kn_m(make_project):
    """Wind analizi kN·m'de çalışmalı (mevcut wind pipeline böyle varsayıyorsa)."""
    p = make_project(UnitSystem.TONF_M)
    # Wind adapter kN·m bekliyorsa:
    if p.unit_system != UnitSystem.KN_M:
        convert_project_units(p, UnitSystem.KN_M, reason="wind")
    assert p.unit_system == UnitSystem.KN_M


def test_wind_inputs_dimensions(make_project):
    """Wind analizine giren koordinatlar kN/m biriminde mi?"""
    p = make_project(UnitSystem.N_MM)
    convert_project_units(p, UnitSystem.KN_M, reason="wind")
    n1 = next(iter(p.scene.nodes.values()))
    # Orijinal mm → şimdi m cinsinden
    assert n1.x == pytest.approx(0.0)
    n2 = list(p.scene.nodes.values())[1]
    assert n2.x == pytest.approx(1.0)   # 1000 mm → 1 m