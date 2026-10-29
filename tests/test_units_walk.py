import pytest

from core.units import UnitSystem, convert_project_units


def test_grid_lines_converted_via_sync(make_project):
    """grid_lines sync sonrası grid dönüşür; grid_lines dönüşmez (artık kullanılmıyor)."""
    p = make_project(UnitSystem.N_MM)
    p.grid_lines = [{"ordinate": 3000.0, "axis_dir": "X"}]
    p.sync_grid_from_s2k_lines()
    p.grid_lines.clear()
    convert_project_units(p, UnitSystem.TONF_M)
    assert p.grid.x_coords == [3.0]


def test_no_double_conversion_area_thickness(make_project):
    p = make_project(UnitSystem.N_MM)
    a = next(iter(p.scene.areas.values()))

    # conftest'te thick_over=10.0, area_section.thickness=150.0
    t0_section = a.area_section.thickness   # 150.0
    t0_over = a.thick_over                   # 10.0

    convert_project_units(p, UnitSystem.TONF_M)

    # area_section.thickness tek kez dönüştü
    assert a.area_section.thickness == pytest.approx(t0_section / 1000.0)  # 0.15
    # thick_over de tek kez dönüştü
    assert a.thick_over == pytest.approx(t0_over / 1000.0)                  # 0.01
    # effective_thickness = thick_over (öncelikli)
    assert a.effective_thickness == pytest.approx(t0_over / 1000.0)         # 0.01


def test_no_double_conversion_dist_loads(make_project):
    p = make_project(UnitSystem.N_MM)
    f = next(iter(p.scene.frames.values()))
    q0 = f.dist_load_sets["DEAD"].segments[0].q1    # 10.0 N/mm

    convert_project_units(p, UnitSystem.TONF_M)

    q1 = f.dist_load_sets["DEAD"].segments[0].q1
    expected = q0 / 9806.65 * 1000.0                 # tonf/m
    assert q1 == pytest.approx(expected, rel=1e-9)

    # property türetilmiş → aynı değer
    assert f.dist_loads[0].segments[0].q1 == pytest.approx(q1, rel=1e-9)