import pytest
from core.units import UnitSystem, convert_project_units
from tests.conftest import snapshot


ALL_SYSTEMS = [
    UnitSystem.N_MM, UnitSystem.N_M,
    UnitSystem.KN_MM, UnitSystem.KN_M,
    UnitSystem.KGF_M, UnitSystem.TONF_M,
    UnitSystem.LB_IN, UnitSystem.KIP_IN,
]


# --- 1. Roundtrip: herhangi bir sistemden herhangi birine gidiş-dönüş ---
@pytest.mark.parametrize("target", ALL_SYSTEMS)
def test_roundtrip_nmm_to_target_to_nmm(make_project, target):
    p = make_project(UnitSystem.N_MM)
    original = snapshot(p)

    convert_project_units(p, target, reason="test")
    assert p.unit_system == target

    convert_project_units(p, UnitSystem.N_MM, reason="test")
    assert p.unit_system == UnitSystem.N_MM

    for key, val in snapshot(p).items():
        assert val == pytest.approx(original[key], rel=1e-9), f"{key} bozuldu"


# --- 2. Aynı sistem → no-op, 0 dönüş ---
def test_same_system_noop(make_project):
    p = make_project(UnitSystem.N_MM)
    before = snapshot(p)
    n = convert_project_units(p, UnitSystem.N_MM)
    assert n == 0
    assert snapshot(p) == before


# --- 3. Boyut doğruluğu: TONF_M → N_MM ---
def test_tonf_m_to_n_mm_values(make_project):
    p = make_project(UnitSystem.TONF_M)
    original = snapshot(p)

    convert_project_units(p, UnitSystem.N_MM)

    s = snapshot(p)
    # Uzunluk × 1000
    assert s["node_x"] == pytest.approx(original["node_x"] * 1000.0)
    # Kuvvet × 9806.65
    assert s["node_fx"] == pytest.approx(original["node_fx"] * 9806.65)
    # Moment × 9806.65 × 1000
    assert s["node_mx"] == pytest.approx(original["node_mx"] * 9806.65 * 1000.0)
    # Gerilme × 9806.65 / 1e6
    assert s["fy"] == pytest.approx(original["fy"] * 9806.65 / 1e6)
    # Alan × 1e6
    assert s["sec_Area"] == pytest.approx(original["sec_Area"] * 1e6)


# --- 4. Çift dönüşüm YOK: dist_loads ve dist_load_sets ---
def test_no_double_conversion_dist_loads(make_project):
    """dist_loads ve dist_load_sets aynı yükü iki kez dönüştürmemeli."""
    p = make_project(UnitSystem.N_MM)
    f = next(iter(p.scene.frames.values()))
    q0_sets = f.dist_load_sets["DEAD"].segments[0].q1
    q0_loads = f.dist_loads[0].segments[0].q1

    convert_project_units(p, UnitSystem.TONF_M)

    q1_sets = f.dist_load_sets["DEAD"].segments[0].q1
    q1_loads = f.dist_loads[0].segments[0].q1

    # Beklenen: bir kez dönüşmüş
    expected = q0_sets * (1.0 / 9806.65 * 1000.0)  # N/mm → tonf/m
    assert q1_sets == pytest.approx(expected, rel=1e-9)
    # İki form aynı olmalı (referans veya eşit dönüşüm)
    assert q1_loads == pytest.approx(q1_sets, rel=1e-9), \
        "dist_loads ve dist_load_sets aynı değil — çift dönüşüm var"


# --- 5. Çift dönüşüm YOK: Area.thickness + AreaSection.thickness ---
def test_no_double_conversion_area_thickness(make_project):
    p = make_project(UnitSystem.N_MM)
    a = next(iter(p.scene.areas.values()))
    t0 = a.area_section.thickness
    thick_over0 = a.thick_over

    convert_project_units(p, UnitSystem.TONF_M)

    t1 = a.area_section.thickness
    assert t1 == pytest.approx(t0 / 1000.0, rel=1e-9)
    assert a.thick_over == pytest.approx(thick_over0 / 1000.0, rel=1e-9)
    assert a.effective_thickness == pytest.approx(a.thick_over)


# --- 6. SectionCut quad points ---
def test_section_cut_quad(make_project):
    p = make_project(UnitSystem.N_MM)
    sc = p.section_cuts["SC1"]
    x0 = sc.quad.points[0][0]

    convert_project_units(p, UnitSystem.TONF_M)
    assert sc.quad.points[0][0] == pytest.approx(x0 / 1000.0)


# --- 7. ResponseSpectrum sf boyutsuz ---
def test_response_sf_dimensionless(make_project):
    from domain.definition import ResponseSpectrumCase, ResponseSpectrumLoadAssignment
    p = make_project(UnitSystem.N_MM)
    p.response_spectrum_cases["RS"] = ResponseSpectrumCase(name="RS")
    p.response_spectrum_cases["RS"].assignments.append(
        ResponseSpectrumLoadAssignment(load_name="U1", sf=0.700478)
    )
    convert_project_units(p, UnitSystem.TONF_M)
    sf = p.response_spectrum_cases["RS"].assignments[0].sf
    assert sf == pytest.approx(0.700478), "sf boyutsuz olmalı, dönüşmemeli"


# --- 8. grid_lines ---
def test_grid_lines(make_project):
    p = make_project(UnitSystem.N_MM)
    p.grid_lines.append({"ordinate": 3000.0, "axis_dir": "X"})
    convert_project_units(p, UnitSystem.TONF_M)
    assert p.grid_lines[0]["ordinate"] == pytest.approx(3.0)


# --- 9. LinkPropLinear Ke ---
def test_link_ke(make_project):
    p = make_project(UnitSystem.N_MM)
    lp = p.link_props["L1"]
    assert lp.Ke["U1"] == 1000.0
    convert_project_units(p, UnitSystem.TONF_M)
    assert lp.Ke["U1"] == pytest.approx(1000.0 / 9806.65)
    # Rotasyonel: N·mm → tonf·m
    assert lp.Ke["R1"] == pytest.approx(1e6 / (9806.65 * 1000.0))


# --- 10. Material stress fields ---
def test_material_stress_fields(make_project):
    p = make_project(UnitSystem.N_MM)
    m = p.materials["STEEL"]
    convert_project_units(p, UnitSystem.TONF_M)
    # s_max: mm/mm boyutsuz? Hayır — stress (F/L²)
    # Ama schema'da STRESS ise dönüşür
    assert m.s_max == pytest.approx(0.11 / 9806.65 * 1e6)  # N/mm² → tonf/m²