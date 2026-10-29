# tests/conftest.py
import math
import pytest
from core.units import UnitSystem, Dimension, DENSITY_STEEL,convert_value, convert_project_units, factor

from domain.project import Project
from domain.definition import (
    Material, Section, AreaSection, LinkPropLinear,
    LoadPattern, LoadCase, LoadCombination,
    PointLoad, FrameGravityLoad, FrameDistributedLoad, LoadSegment,
    AreaUniformLoad, AreaUniformToFrameLoad,
    SectionCut, QuadDefinition,
    SDSection, SDShape, SDPolygonPoint,
)
from domain.element import Node, Frame, Area, Link
from data.enums import SectionType, MatType, PropAreaType


# ---------------------------------------------------------------------------
# Temel proje fabrikası — N_MM biriminde
# ---------------------------------------------------------------------------
@pytest.fixture
def make_project():
    def _make(unit_system=UnitSystem.N_MM):
        p = Project()
        p.unit_system = unit_system

        # --- Material ---
        mat = Material(
            name="STEEL",
            mat_type=MatType.STEEL,
            E1=210000.0, E2=210000.0, E3=210000.0,
            G12=81000.0, G13=81000.0, G23=81000.0,
            nu12=0.3, nu13=0.3, nu23=0.3,
            density=DENSITY_STEEL,
            fy=235.0, fu=360.0,
            eff_fy=260.0, eff_fu=400.0,
            fc=30.0, efc=30.0, sfc=0.002,
            s_max=0.11, s_rup=0.17, s_cap=0.05,
            rebar_fy=420.0, rebar_fys=420.0,
            rebar_s_hard=0.01, rebar_s_cap=0.09,
        )
        p.materials[mat.name] = mat

        # --- Section ---
        sec = Section(
            name="R1",
            profile_type=SectionType.RECT,
            profile_params={
                "h": 300.0, "b": 200.0,
                "Area": 60000.0, "I33": 4.5e8, "I22": 2.0e8,
                "J": 3.0e8, "AS2": 50000.0, "AS3": 50000.0,
            },
            material=mat,
            rebar_column={"cover": 40.0, "spacing_c": 150.0},
            rebar_beam={"top_cover": 40.0, "bot_cover": 40.0,
                        "top_left_area": 100.0, "top_rght_area": 100.0,
                        "bot_left_area": 100.0, "bot_rght_area": 100.0},
            cg_offset2=5.0, cg_offset3=7.0,
            ecc_v2=2.0, ecc_v3=3.0,
            time_dependent={"type_size": "Auto", "auto_sf_size": 1.0},
        )
        p.sections[sec.name] = sec

        # --- AreaSection ---
        asec = AreaSection(
            name="SHELL1",
            prop_type=PropAreaType.Shell,
            area_type="Shell-Thin",
            material=mat,
            thickness=150.0,
            bend_thick=150.0,
            mat_angle=0.0,
        )
        p.area_sections[asec.name] = asec

        # --- LinkPropLinear ---
        lp = LinkPropLinear(name="L1")
        lp.Ke = {"U1": 1000.0, "U2": 2000.0, "U3": 3000.0,
                 "R1": 1e6, "R2": 2e6, "R3": 3e6}
        p.link_props[lp.name] = lp

        # --- Load pattern/case/combo ---
        p.load_patterns["DEAD"] = LoadPattern(name="DEAD", design_type="Dead", self_wt_mult=1.0)
        p.load_cases["C1"] = LoadCase(name="C1", case_type="LinStatic")
        p.combinations["COMB1"] = LoadCombination(name="COMB1")

        # --- Node + Frame ---
        n1 = Node(0.0, 0.0, 0.0, label="N1")
        n2 = Node(1000.0, 0.0, 0.0, label="N2")
        p.scene.add_node(n1)
        p.scene.add_node(n2)
        f = Frame(n1, n2, sec, label="F1")
        f.jt_offset_i = (10.0, 20.0, 30.0)
        f.jt_offset_j = (40.0, 50.0, 60.0)
        f.offset_length_i = 50.0
        f.offset_length_j = 60.0
        f.mesh_max_length = 500.0
        f.max_sta_spcg = 250.0
        f.modifiers = {"amod": 1.0, "i33mod": 1.0}
        p.scene.add_frame(f)

        # --- Yükler ---
        n1.loads.append(PointLoad(pattern_name="DEAD",
                                  fx=1000.0, fy=2000.0, fz=-3000.0,
                                  mx=1e5, my=2e5, mz=3e5))
        f.dist_load_sets["DEAD"] = FrameDistributedLoad(
            pattern_name="DEAD", is_relative=True,
            segments=[LoadSegment(x1=0.0, x2=1.0, q1=10.0, q2=10.0)],
        )
        f.dist_loads.extend(f.dist_load_sets["DEAD"].to_sap_loads())

        # --- Area ---
        n3 = Node(0.0, 1000.0, 0.0, label="N3")
        p.scene.add_node(n3)
        a = Area([n1, n2, n3], thickness=asec.thickness, label="A1")
        a.area_section = asec
        a.thick_over = 10.0
        a.offset_over = -5.0
        a.uniform_loads.append(AreaUniformLoad(
            pattern_name="DEAD", value=5e-3))   # N/mm²
        a.uniform_to_frame_loads.append(AreaUniformToFrameLoad(
            pattern_name="DEAD", value=3e-3))
        p.scene.add_area(a)

        # --- SectionCut ---
        sc = SectionCut(
            name="SC1",
            global_x=100.0, global_y=200.0, global_z=300.0,
            quad=QuadDefinition(points=[(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]),
        )
        p.section_cuts[sc.name] = sc

        # --- SD ---
        sd = SDSection(name="SD1", axis_angle=90.0, mesh_sz_abs=20.0)
        sd.shapes.append(SDShape(
            name="SH1",
            points=[SDPolygonPoint(x=10.0, y=20.0, radius=1.0)],
        ))
        sec.sd_section = sd

        return p
    return _make

# tests/conftest.py (devam)

def snapshot(p):
    """Tüm birimli değerleri dict olarak topla — roundtrip testleri için."""
    mat = p.materials["STEEL"]
    sec = p.sections["R1"]
    asec = p.area_sections["SHELL1"]
    lp = p.link_props["L1"]
    sc = p.section_cuts["SC1"]
    sd = sec.sd_section

    f = next(iter(p.scene.frames.values()))
    a = next(iter(p.scene.areas.values()))
    n1 = next(iter(p.scene.nodes.values()))

    return {
        # Node
        "node_x": n1.x, "node_y": n1.y, "node_z": n1.z,
        # Frame
        "jt_off_i_x": f.jt_offset_i[0],
        "jt_off_i_y": f.jt_offset_i[1],
        "jt_off_i_z": f.jt_offset_i[2],
        "offset_length_i": f.offset_length_i,
        "mesh_max_length": f.mesh_max_length,
        "max_sta_spcg": f.max_sta_spcg,
        # Material
        "E1": mat.E1, "G12": mat.G12,
        "fy": mat.fy, "fu": mat.fu,
        "fc": mat.fc, "s_max": mat.s_max,
        # Section
        "sec_Area": sec.profile_params["Area"],
        "sec_I33": sec.profile_params["I33"],
        "sec_cover_col": sec.rebar_column["cover"],
        "sec_top_cover_beam": sec.rebar_beam["top_cover"],
        "sec_cg2": sec.cg_offset2,
        # AreaSection
        "asec_thick": asec.thickness,
        "asec_bend": asec.bend_thick,
        # Area
        "area_thick_over": a.thick_over,
        "area_offset_over": a.offset_over,
        # Link
        "link_Ke_U1": lp.Ke["U1"],
        "link_Ke_R1": lp.Ke["R1"],
        # Loads
        "node_fx": n1.loads[0].fx,
        "node_mx": n1.loads[0].mx,
        "dist_q1": f.dist_load_sets["DEAD"].segments[0].q1,
        "area_uniform": a.uniform_loads[0].value,
        "area_to_frame": a.uniform_to_frame_loads[0].value,
        # SectionCut
        "sc_gx": sc.global_x,
        "sc_quad_0_x": sc.quad.points[0][0],
        # SD
        "sd_mesh": sd.mesh_sz_abs,
        "sd_point_x": sd.shapes[0].points[0].x,
    }