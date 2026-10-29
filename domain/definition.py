# domain/definition.py
"""
SAP2000 uyumlu tanım sınıfları.

Birim sözleşmesi (core.units):
    Model her zaman project.unit_system'de.
    convert_project_units(project, target) __unit_schema__ ile dönüştürür.
    __unit_schema__: {field_path: Dimension} — boyutsuz alanlar None.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pyglm import glm
import numpy as np

from core.units import DENSITY_STEEL, Dimension
from data.enums import (
    DistType,
    LinkPropType,
    LoadDirection,
    MatType,
    PropAreaType,
    SectionCutDefinedBy,
    SectionCutResultType,
    SectionType,
    SpectrumSourceType,
)
from data.seismic import get_tsc2018_site_coefficients

__all__ = [
    # enums (re-export)
    "DistType", "LinkPropType", "LoadDirection", "MatType",
    "PropAreaType", "SectionCutDefinedBy", "SectionCutResultType",
    "SectionType", "SpectrumSourceType",
    # sınıflar
    "AreaUniformLoad", "AreaUniformToFrameLoad", "AreaWindPressureLoad",
    "AutoSeismicTSC2018", "ComboItem", "FrameDistributedLoad",
    "FrameGravityLoad", "GeneralProjectInfo", "LinkProp", "LinkPropLinear",
    "LoadCase", "LoadCombination", "LoadPattern", "Material", "ModalCase",
    "PointLoad", "QuadDefinition", "ResponseSpectrumCase",
    "ResponseSpectrumLoadAssignment", "Section", "SectionCut",
    "SiteInformation", "SpectrumFunction", "StaticLoadAssignment",
]


# ============================================================================
# MATERIAL
# ============================================================================
@dataclass
class Material:
    """S2K material — tüm 01/02/03x/06/09 (v25) ve 01/04 (v10) alanları.

    Birim sözleşmesi: S2K CurrUnits → convert_project_units N_MM'ye çevirir.
    """
    name: str = "DEFAULT"
    mat_type: MatType = MatType.STEEL
    color: tuple[float, float, float] = (0.8, 0.8, 0.8)

    # --- MATERIAL PROPERTIES 01 - GENERAL ---
    grade: str = ""
    sym_type: str = "Isotropic"          # Isotropic / Orthotropic / Uniaxial
    temp_depend: bool = False
    design_type: str = ""                # v10: Concrete / Steel / ...
    notes: str = ""

    # --- 02 - BASIC MECHANICAL PROPERTIES ---
    E1: float = 2.1e5
    E2: float = 2.1e5
    E3: float = 2.1e5
    G12: float = 8.1e4
    G13: float = 8.1e4
    G23: float = 8.1e4
    nu12: float = 0.3
    nu13: float = 0.3
    nu23: float = 0.3
    density: float = DENSITY_STEEL   # kg/mm³

    # --- 03A - STEEL DATA ---
    fy: float = 235.0
    fu: float = 360.0
    eff_fy: float = 0.0
    eff_fu: float = 0.0
    ss_curve_opt: str = "Simple"
    ss_hys_type: str = "Kinematic"
    s_hard: float = 0.0
    s_max: float = 0.0
    s_rup: float = 0.0
    final_slope: float = -0.1
    coup_mod_type: str = "Von Mises"

    # --- 03B - CONCRETE DATA ---
    fc: float = 0.0
    efc: float = 0.0
    ltwt_conc: bool = False
    sfc: float = 0.0
    s_cap: float = 0.0
    f_angle: float = 0.0
    d_angle: float = 0.0

    # --- 04 - DESIGN CONCRETE (v10) ---
    rebar_fy: float = 0.0
    rebar_fys: float = 0.0
    ltwt_fact: float = 1.0

    # --- 03E - REBAR DATA ---
    rebar_ss_curve_opt: str = "Simple"
    rebar_ss_hys_type: str = "Kinematic"
    rebar_s_hard: float = 0.0
    rebar_s_cap: float = 0.0
    rebar_use_ct_def: bool = False

    # --- 03F - TENDON DATA ---
    tendon_ss_curve_opt: str = ""
    tendon_ss_hys_type: str = "Kinematic"

    # --- 06 - DAMPING PARAMETERS ---
    modal_ratio: float = 0.0
    vis_mass: float = 0.0
    vis_stiff: float = 0.0
    hys_mass: float = 0.0
    hys_stiff: float = 0.0

    # --- 09 - ACCEPTANCE CRITERIA ---
    io_tens: float = 0.0
    ls_tens: float = 0.0
    cp_tens: float = 0.0
    io_comp: float = 0.0
    ls_comp: float = 0.0
    cp_comp: float = 0.0
    ignore_tens: bool = False

    # --- 03J - COUPLED NONLINEAR VON MISES ---
    yield_stress: float = 0.0
    lin_iso_hard: bool = False
    lin_kin_hard: bool = False
    nl_iso_sa_hard: bool = False

    __unit_schema__ = {
        # 02 - basic mech
        "E1": Dimension.STRESS, "E2": Dimension.STRESS, "E3": Dimension.STRESS,
        "G12": Dimension.STRESS, "G13": Dimension.STRESS, "G23": Dimension.STRESS,
        "density": Dimension.MASS_DENSITY,
        "nu12": None, "nu13": None, "nu23": None,
        # 03A - steel
        "fy": Dimension.STRESS, "fu": Dimension.STRESS,
        "eff_fy": Dimension.STRESS, "eff_fu": Dimension.STRESS,
        "s_hard": Dimension.STRESS, "s_max": Dimension.STRESS,
        "s_rup": Dimension.STRESS,
        # 03B - concrete
        "fc": Dimension.STRESS, "efc": Dimension.STRESS,
        "sfc": Dimension.STRESS, "s_cap": Dimension.STRESS,
        # 04 - v10 design concrete
        "rebar_fy": Dimension.STRESS, "rebar_fys": Dimension.STRESS,
        # 03E - rebar
        "rebar_s_hard": Dimension.STRESS, "rebar_s_cap": Dimension.STRESS,
        # 03J
        "yield_stress": Dimension.STRESS,
        # 06 - damping (boyutsuz)
        "modal_ratio": None, "vis_mass": None, "vis_stiff": None,
        "hys_mass": None, "hys_stiff": None,
        # 09 - acceptance (boyutsuz)
        "io_tens": None, "ls_tens": None, "cp_tens": None,
        "io_comp": None, "ls_comp": None, "cp_comp": None,
    }

    @property
    def E(self) -> float: return self.E1

    @property
    def G(self) -> float: return self.G12

    @property
    def nu(self) -> float: return self.nu12

    def is_concrete(self) -> bool:
        return self.mat_type == MatType.CONCRETE

    def is_steel(self) -> bool:
        return self.mat_type == MatType.STEEL


DEFAULT_MATERIAL = Material(
    name="DEFAULT_STEEL",
    mat_type=MatType.STEEL,
    E1=2.1e5,
    G12=8.1e4,
    nu12=0.3,
    density=DENSITY_STEEL,
)


# ============================================================================
# SECTION
# ============================================================================
@dataclass
class Section:
    """S2K frame section — geometri + analitik + betonarme + SD.

    Birim sözleşmesi: profile_params/catalog_props S2K biriminde;
    convert_project_units __unit_schema__ ile N_MM'ye çevirir.
    """
    name: str = ""
    profile_type: SectionType = SectionType.RECT
    profile_params: dict[str, float] = field(default_factory=dict)
    material: Material | None = None
    color: tuple[float, float, float] = (0.8, 0.8, 0.8)

    catalog_props: dict[str, float] = field(default_factory=dict)
    catalog_source: str = ""
    sd_section: SDSection | None = None

    # --- FRAME SECTION PROPERTIES 01 - GENERAL (ek alanlar) ---
    cg_offset3: float = 0.0
    cg_offset2: float = 0.0
    ecc_v2: float = 0.0
    ecc_v3: float = 0.0
    from_file: bool = False
    notes: str = ""

    # --- FRAME SECTION PROPERTIES 02 - CONCRETE COLUMN (v25) ---
    # {rebar_mat_l, rebar_mat_c, reinf_config, lat_reinf, cover,
    #  num_bars3_dir, num_bars2_dir, bar_size_l, bar_size_c,
    #  spacing_c, num_cbars2, num_cbars3, reinf_type}
    rebar_column: dict[str, Any] = field(default_factory=dict)

    # --- FRAME SECTION PROPERTIES 03 - CONCRETE BEAM (v25) ---
    # {rebar_mat_l, rebar_mat_c, top_cover, bot_cover,
    #  top_left_area, top_rght_area, bot_left_area, bot_rght_area}
    rebar_beam: dict[str, Any] = field(default_factory=dict)

    # --- FRAME SECTION PROPERTIES 13 - TIME DEPENDENT ---
    # {type_size, auto_sf_size}
    time_dependent: dict[str, Any] = field(default_factory=dict)

    __unit_schema__ = {
        # profile_params
        "profile_params.Area": Dimension.AREA,
        "profile_params.I33": Dimension.I4,
        "profile_params.I22": Dimension.I4,
        "profile_params.J": Dimension.I4,
        "profile_params.I23": Dimension.I4,
        "profile_params.AS2": Dimension.AREA,
        "profile_params.AS3": Dimension.AREA,
        "profile_params.h": Dimension.LENGTH,
        "profile_params.b": Dimension.LENGTH,
        "profile_params.tw": Dimension.LENGTH,
        "profile_params.tf": Dimension.LENGTH,
        "profile_params.t": Dimension.LENGTH,
        "profile_params.ro": Dimension.LENGTH,
        "profile_params.ri": Dimension.LENGTH,
        "profile_params.d": Dimension.LENGTH,
        "profile_params.t2b": Dimension.LENGTH,
        "profile_params.tfb": Dimension.LENGTH,
        "profile_params.S33Top": Dimension.I3,
        "profile_params.S33Bot": Dimension.I3,
        "profile_params.S22Left": Dimension.I3,
        "profile_params.S22Right": Dimension.I3,
        "profile_params.Z33": Dimension.I3,
        "profile_params.Z22": Dimension.I3,
        "profile_params.R33": Dimension.I3,
        "profile_params.R22": Dimension.I3,
        "profile_params.Cw": Dimension.I4,
        "profile_params.n": None,
        # catalog_props
        "catalog_props.Area": Dimension.AREA,
        "catalog_props.I33": Dimension.I4,
        "catalog_props.I22": Dimension.I4,
        "catalog_props.J": Dimension.I4,
        "catalog_props.h": Dimension.LENGTH,
        "catalog_props.b": Dimension.LENGTH,
        "catalog_props.tw": Dimension.LENGTH,
        "catalog_props.tf": Dimension.LENGTH,
        # 01 - general ek alanlar
        "cg_offset3": Dimension.LENGTH,
        "cg_offset2": Dimension.LENGTH,
        "ecc_v2": Dimension.LENGTH,
        "ecc_v3": Dimension.LENGTH,
    }

    def __post_init__(self):
        if self.material is None:
            self.material = DEFAULT_MATERIAL

    # --- yardımcılar ---
    def is_concrete(self) -> bool:
        return bool(self.rebar_column or self.rebar_beam)

    def get_rebar_mat_l(self) -> str:
        return str(self.rebar_column.get("rebar_mat_l")
                   or self.rebar_beam.get("rebar_mat_l") or "")

    def get_rebar_mat_c(self) -> str:
        return str(self.rebar_column.get("rebar_mat_c")
                   or self.rebar_beam.get("rebar_mat_c") or "")


# ============================================================================
# AREA SECTION
# ============================================================================
@dataclass
class AreaSection:
    """AREA SECTION PROPERTIES — shell/membrane/plate.

    S2K tablosu: Section, Material, MatAngle, AreaType, Type, DrillDOF,
                 Thickness, BendThick, Color, F11Mod, F22Mod, F12Mod,
                 M11Mod, M22Mod, M12Mod, V13Mod, V23Mod, MMod, WMod
    """
    name: str = ""
    prop_type: PropAreaType = PropAreaType.Shell   # Shell / Plane / Asolid
    area_type: str = "Shell-Thin"                  # Shell-Thin / Shell-Thick / Membrane / Plate-Thin / Plate-Thick
    material: Material | None = None
    mat_angle: float = 0.0

    thickness: float = 0.0
    bend_thick: float | None = None                # None → thickness kullan
    drill_dof: bool = False
    color: tuple[float, float, float] = (0.8, 0.8, 0.8)

    # --- modifiers (boyutsuz) ---
    membrane_f11: float = 1.0
    membrane_f22: float = 1.0
    membrane_f12: float = 1.0

    bending_m11: float = 1.0
    bending_m22: float = 1.0
    bending_m12: float = 1.0

    shear_v13: float = 1.0
    shear_v23: float = 1.0

    mass: float = 1.0
    weight: float = 1.0

    # --- AREA SECTION PROPERTY DESIGN PARAMETERS ---
    rebar_mat: str = ""
    rebar_opt: str = "Default"

    # --- AREA SECTION PROPERTY - TIME DEPENDENT ---
    type_size: str = "Auto"
    auto_sf_size: float = 1.0

    params: dict = field(default_factory=dict)

    __unit_schema__ = {
        "thickness": Dimension.LENGTH,
        "bend_thick": Dimension.LENGTH,
        "mat_angle": None,   # açı — boyutsuz
    }

    @property
    def modifiers(self):
        return (
            self.membrane_f11, self.membrane_f22, self.membrane_f12,
            self.bending_m11, self.bending_m22, self.bending_m12,
            self.shear_v13, self.shear_v23, self.mass, self.weight,
        )

    @property
    def effective_bend_thick(self) -> float:
        return self.bend_thick if self.bend_thick is not None else self.thickness


# ============================================================================
# LINK PROPERTIES
# ============================================================================
@dataclass
class LinkProp:
    name: str = "LINK1"
    prop_type: LinkPropType = LinkPropType.LINEAR


@dataclass
class LinkPropLinear(LinkProp):
    prop_type: LinkPropType = LinkPropType.LINEAR
    DOF: dict[str, bool] = field(default_factory=lambda: {
        "U1": True, "U2": True, "U3": True,
        "R1": True, "R2": True, "R3": True,
    })
    Fixed: dict[str, bool] = field(default_factory=dict)
    Ke: dict[str, float] = field(default_factory=lambda: {
        "U1": 0.0, "U2": 0.0, "U3": 0.0,
        "R1": 0.0, "R2": 0.0, "R3": 0.0,
    })
    Ce: dict[str, float] = field(default_factory=lambda: {
        "U1": 0.0, "U2": 0.0, "U3": 0.0,
        "R1": 0.0, "R2": 0.0, "R3": 0.0,
    })

    __unit_schema__ = {
        "Ke.U1": Dimension.FORCE,
        "Ke.U2": Dimension.FORCE,
        "Ke.U3": Dimension.FORCE,
        "Ke.R1": Dimension.MOMENT,
        "Ke.R2": Dimension.MOMENT,
        "Ke.R3": Dimension.MOMENT,
    }

    def __post_init__(self):
        self.DOF = self.DOF or {"U1": True, "U2": True, "U3": True,
                                "R1": True, "R2": True, "R3": True}
        self.Fixed = self.Fixed or {}
        self.Ke = self.Ke or {"U1": 0, "U2": 0, "U3": 0, "R1": 0, "R2": 0, "R3": 0}
        self.Ce = self.Ce or {"U1": 0, "U2": 0, "U3": 0, "R1": 0, "R2": 0, "R3": 0}


# ============================================================================
# RESTRAINT
# ============================================================================
@dataclass
class Restraint:
    ux: bool = False
    uy: bool = False
    uz: bool = False
    rx: bool = False
    ry: bool = False
    rz: bool = False

    DOF_ORDER = ("ux", "uy", "uz", "rx", "ry", "rz")

    @classmethod
    def from_list(cls, values): return cls(*values)

    def is_free(self): return not any(self.as_list())

    def is_fully_fixed(self): return all(self.as_list())

    def fixed_dofs(self): return [n for n in self.DOF_ORDER if getattr(self, n)]

    def free_dofs(self): return [n for n in self.DOF_ORDER if not getattr(self, n)]

    def as_list(self): return [getattr(self, d) for d in self.DOF_ORDER]

    def as_dict(self): return {d: getattr(self, d) for d in self.DOF_ORDER}

    def as_int_mask(self):
        mask = 0
        for i, d in enumerate(self.DOF_ORDER):
            if getattr(self, d):
                mask |= (1 << i)
        return mask


# ============================================================================
# CONFIG
# ============================================================================
@dataclass
class WindConfig:
    vb0: float = 28.0
    terrain_category: str = "III"
    z0: float = 0.0
    z1: float = 5.27
    z2: float = 6.92
    cpi_positive: float = 0.2
    cpi_negative: float = -0.3

    __unit_schema__ = {"vb0": Dimension.ACCEL, "z0": Dimension.LENGTH, "z1": Dimension.LENGTH, "z2": Dimension.LENGTH}


@dataclass
class SnowConfig:
    sk: float = 0.75
    exposure_coefficient: float = 1.0
    thermal_coefficient: float = 1.0
    shape_coefficient: float = 0.8

    __unit_schema__ = {"sk": Dimension.AREA_LOAD}


@dataclass
class SeismicConfig:
    ss: float = 0.0
    s1: float = 0.0
    soil_class: str = "ZD"
    importance_factor: float = 1.0
    building_height_class: str = ""
    behavior_factor: float = 8.0
    overstrength_factor: float = 3.0

    __unit_schema__ = {}


@dataclass
class ProjectConfig:
    wind: WindConfig = field(default_factory=WindConfig)
    snow: SnowConfig = field(default_factory=SnowConfig)
    seismic: SeismicConfig = field(default_factory=SeismicConfig)


@dataclass
class GeneralProjectInfo:
    company_name: str = ""
    client_name: str = ""
    project_name: str = "Test Yapısı"
    project_number: str = ""
    model_name: str = ""
    model_description: str = ""
    revision_number: str = "R0"
    frame_type: str = ""
    engineer: str = "Engineer"
    checker: str = ""
    supervisor: str = ""
    issue_code: str = ""
    design_code: str = ""


@dataclass
class SiteInformation:
    live_load_factor: float = 0.3
    cadastral_info: str = "102 / 14"
    date: str = ""
    soil_class: str = "ZD"
    subgrade_modulus_kn_m3: float = 15000.0
    extra_items: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectInfo:
    name: str = "Untitled"
    description: str = ""
    author: str = ""


@dataclass
class LoadManager:
    wind_zones: dict[str, list[Any]] = field(default_factory=dict)

@dataclass
class ReportManager: pass


@dataclass
class AnalysisManager:
    wind: Any = None
    snow: Any = None
    seismic: Any = None


@dataclass
class GridPlaneDef:
    name: str = ""
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    normal: tuple[float, float, float] = (0.0, 0.0, 1.0)
    u_axis: tuple[float, float, float] = (1.0, 0.0, 0.0)
    spacing_u: float = 1000.0
    spacing_v: float = 1000.0
    count_u: int = 20
    count_v: int = 20
    visible: bool = True
    color: tuple[float, float, float] = (0.55, 0.55, 0.60)
    locked: bool = False

    def get_uv_frame(self):
        n = glm.normalize(glm.vec3(*self.normal))
        u = glm.vec3(*self.u_axis)
        u = u - n * glm.dot(u, n)
        if glm.length(u) < 1e-6:
            u = glm.vec3(1, 0, 0) - n * n.x
        u = glm.normalize(u)
        v = glm.cross(n, u)
        return glm.vec3(*self.origin), u, v, n


@dataclass
class GridConfig:
    __unit_schema__ = {
        "x_coords": Dimension.LENGTH,
        "y_coords": Dimension.LENGTH,
        "z_coords": Dimension.LENGTH,
        "origin_x": Dimension.LENGTH,
        "origin_y": Dimension.LENGTH,
        "origin_z": Dimension.LENGTH,
    }

    x_coords: list[float] = field(default_factory=lambda: [0.0, 1000.0])
    y_coords: list[float] = field(default_factory=lambda: [0.0, 1000.0])
    z_coords: list[float] = field(default_factory=lambda: [0.0, 1000.0])
    origin_x: float = 0.0
    origin_y: float = 0.0
    origin_z: float = 0.0
    planes_visibility: dict[str, bool] = field(default_factory=lambda: {
        "XY": True, "XZ": False, "YZ": False,
    })


@dataclass
class QuadDefinition:
    points: list[tuple[float, float, float]] = field(default_factory=list)

    __unit_schema__ = {"points": Dimension.LENGTH}


@dataclass
class SectionCut:
    name: str = "DEFAULT"
    defined_by: SectionCutDefinedBy = SectionCutDefinedBy.QUAD
    group: str = "All"
    result_type: SectionCutResultType = SectionCutResultType.ANALYSIS
    default_loc: bool = True
    global_x: float = 0.0
    global_y: float = 0.0
    global_z: float = 0.0
    angle_a: float = 0.0
    angle_b: float = 0.0
    angle_c: float = 0.0
    elem_side: str = "Positive"
    quad: QuadDefinition | None = None

    __unit_schema__ = {
        "global_x": Dimension.LENGTH,
        "global_y": Dimension.LENGTH,
        "global_z": Dimension.LENGTH,
    }


# ============================================================================
# LOAD PATTERN / CASE / COMBO
# ============================================================================
@dataclass
class LoadPattern:
    name: str = ""
    design_type: str = "Dead"
    self_wt_mult: float = 0.0

    __unit_schema__ = {"self_wt_mult": None}   # boyutsuz


@dataclass
class StaticLoadAssignment:
    load_type: str = "Load pattern"
    load_name: str = ""
    load_sf: float = 1.0

    __unit_schema__ = {"load_sf": None}


@dataclass
class LoadCase:
    name: str = ""
    case_type: str = "LinStatic"
    initial_cond: str = "Zero"
    design_type: str = "Dead"
    design_act: str = "Non-Composite"
    auto_type: str = "None"
    run_case: bool = True
    static_assignments: list[StaticLoadAssignment] = field(default_factory=list)

    __unit_schema__ = {"static_assignments.load_sf": None}


@dataclass
class ModalCase:
    name: str = ""
    mode_type: str = "Eigen"
    max_num_modes: int = 12
    min_num_modes: int = 1
    eigen_shift: float = 0.0
    eigen_cutoff: float = 0.0
    eigen_tol: float = 1e-9
    auto_shift: bool = True


@dataclass
class ComboItem:
    case_or_pattern_name: str = ""
    scale_factor: float = 1.0

    __unit_schema__ = {"scale_factor": None}


@dataclass
class LoadCombination:
    name: str = ""
    combo_type: str = "Linear Add"
    auto_design: bool = False
    items: list[ComboItem] = field(default_factory=list)


# ============================================================================
# JOINT / FRAME / AREA LOADS
# ============================================================================
@dataclass
class PointLoad:
    pattern_name: str = ""
    fx: float = 0.0
    fy: float = 0.0
    fz: float = 0.0
    mx: float = 0.0
    my: float = 0.0
    mz: float = 0.0

    __unit_schema__ = {
        "fx": Dimension.FORCE, "fy": Dimension.FORCE, "fz": Dimension.FORCE,
        "mx": Dimension.MOMENT, "my": Dimension.MOMENT, "mz": Dimension.MOMENT,
    }


@dataclass
class FramePointLoad:
    pattern_name: str = ""
    force_or_moment: str = "Force"
    direction: LoadDirection = LoadDirection.GLOBAL_Z
    value: float = 0.0
    distance: float = 0.0
    is_relative: bool = True
    coordinate_system: str = "GLOBAL"

    __unit_schema__ = {
        "value": Dimension.FORCE,   # veya MOMENT — force_or_moment'a göre
        "distance": Dimension.LENGTH,
    }


@dataclass
class LoadSegment:
    x1: float = 0.0
    x2: float = 1.0
    q1: float = 0.0
    q2: float = 0.0

    __unit_schema__ = {
        "q1": Dimension.LINE_LOAD,
        "q2": Dimension.LINE_LOAD,
        "x1": None, "x2": None,   # relative
    }

    def to_points(self):
        return [(self.x1, self.q1), (self.x2, self.q2)]


@dataclass
class FrameDistributedLoad:
    pattern_name: str = ""
    coord_sys: str = "Local"
    load_dir: str = "2"
    mode: str = "REPLACE"
    force_or_moment: str = "Force"
    direction: LoadDirection = LoadDirection.GLOBAL_Z
    is_relative: bool = True
    coordinate_system: str = "GLOBAL"
    dist_type: str = "one_way"
    segments: list[LoadSegment] = field(default_factory=list)

    def add_segment(self, x1: float, x2: float, q1: float, q2: float):
        self.segments.append(LoadSegment(x1, x2, q1, q2))
        self.segments.sort(key=lambda s: s.x1)

    def clear(self):
        self.segments.clear()

    def to_sap_loads(self):
        return [
            FrameDistributedLoad(
                pattern_name=self.pattern_name,
                coord_sys=self.coord_sys,
                load_dir=self.load_dir,
                mode=self.mode,
                force_or_moment=self.force_or_moment,
                direction=self.direction,
                is_relative=self.is_relative,
                coordinate_system=self.coordinate_system,
                dist_type=self.dist_type,
                segments=[seg],
            )
            for seg in self.segments
        ]


@dataclass
class FrameGravityLoad:
    pattern_name: str = ""
    multiplier_x: float = 0.0
    multiplier_y: float = 0.0
    multiplier_z: float = 0.0

    __unit_schema__ = {
        "multiplier_x": None, "multiplier_y": None, "multiplier_z": None,
    }


@dataclass
class FrameTemperatureLoad:
    pattern_name: str = ""
    temp_type: str = "Temperature"
    val: float = 0.0

    __unit_schema__ = {"val": Dimension.TEMP}


@dataclass
class AreaGravityLoad:
    pattern_name: str = ""
    multiplier_x: float = 0.0
    multiplier_y: float = 0.0
    multiplier_z: float = 0.0


@dataclass
class AreaRefTemperatureLoad:
    temp: float = 0.0

    __unit_schema__ = {"temp": Dimension.TEMP}


@dataclass
class AreaStrainLoad:
    pattern_name: str = ""
    component: str = "S11"
    val: float = 0.0

    __unit_schema__ = {"val": None}


@dataclass
class AreaSurfacePressureLoad:
    pattern_name: str = ""
    face: str = "BOTTOM"
    pressure: float = 0.0

    __unit_schema__ = {"pressure": Dimension.AREA_LOAD}


@dataclass
class AreaTemperatureLoad:
    pattern_name: str = ""
    temp_type: str = "Temperature"
    val: float = 0.0

    __unit_schema__ = {"val": Dimension.TEMP}


@dataclass
class AreaUniformLoad:
    pattern_name: str = ""
    direction: LoadDirection = LoadDirection.GLOBAL_Z
    value: float = 0.0
    coordinate_system: str = "GLOBAL"

    __unit_schema__ = {"value": Dimension.AREA_LOAD}


@dataclass
class AreaUniformToFrameLoad:
    pattern_name: str = ""
    direction: LoadDirection = LoadDirection.GLOBAL_Z
    value: float = 0.0
    dist_type: DistType = DistType.ONE_WAY
    coordinate_system: str = "GLOBAL"

    __unit_schema__ = {"value": Dimension.AREA_LOAD}


@dataclass
class AreaWindPressureLoad:
    pattern_name: str = ""
    cp: float = 0.0
    windward: bool = True
    dist_type: str = "To Joints"

    __unit_schema__ = {"cp": None}


# ============================================================================
# SEISMIC / SPECTRUM
# ============================================================================
@dataclass
class SpectrumFunction:
    name: str = ""
    source_type: SpectrumSourceType = SpectrumSourceType.USER
    damp: float = 0.05
    ss: float = 0.0
    s1: float = 0.0
    tl: float = 6.0
    site_class: str = "ZC"
    fs: float = 1.0
    f1: float = 1.0
    r_coeff: float = 1.0
    d_coeff: float = 1.0
    i_coeff: float = 1.0
    spec_dir: str = "Horizontal"
    file_path: str | None = None
    data_type: str = "Period vs Accel"
    points: list[tuple[float, float]] = field(default_factory=list)

    __unit_schema__ = {}   # spektrum değerleri boyutsuz (g), periyot s

    def __post_init__(self):
        if self.source_type == SpectrumSourceType.TSC_2018 and not self.points:
            self.generate_tbdy2018_points()

    def generate_tbdy2018_points(self, num_points: int = 200):
        self.fs, self.f1 = get_tsc2018_site_coefficients(self.ss, self.s1, self.site_class)
        sds = self.ss * self.fs
        sd1 = self.s1 * self.f1
        ta = 0.2 * (sd1 / sds) if sds > 0 else 0.0
        tb = (sd1 / sds) if sds > 0 else 0.0
        self.points.clear()
        max_t = max(self.tl + 2.0, 8.0)
        dt = max_t / num_points
        for i in range(num_points + 1):
            t = i * dt
            if 0 <= t < ta:
                sae = (0.4 + 0.6 * (t / ta)) * sds if ta > 0 else sds
            elif ta <= t <= tb:
                sae = sds
            elif tb < t <= self.tl:
                sae = sd1 / t
            else:
                sae = (sd1 * self.tl) / (t ** 2)
            if t < tb:
                ra = (self.d_coeff + (self.r_coeff / self.i_coeff - self.d_coeff) * (t / tb)
                      if tb > 0 else self.r_coeff / self.i_coeff)
            else:
                ra = self.r_coeff / self.i_coeff
            sa_design = sae / ra if ra > 0 else sae
            self.points.append((round(t, 4), round(sa_design, 6)))

    def get_sa(self, period: float) -> float:
        if not self.points:
            return 0.0
        if period <= self.points[0][0]:
            return self.points[0][1]
        if period >= self.points[-1][0]:
            return self.points[-1][1]
        for i in range(len(self.points) - 1):
            t0, sa0 = self.points[i]
            t1, sa1 = self.points[i + 1]
            if t0 <= period <= t1:
                if t1 == t0:
                    return sa0
                return sa0 + (sa1 - sa0) * (period - t0) / (t1 - t0)
        return 0.0


@dataclass
class ResponseSpectrumLoadAssignment:
    load_name: str = ""
    function_name: str = ""
    angle: float = 0.0
    sf: float = 9810.0

    __unit_schema__ = {"sf": None}


@dataclass
class ResponseSpectrumCase:
    name: str = ""
    modal_combo: str = "CQC"
    dir_combo: str = "SRSS"
    damping: float = 0.05
    eccentricity: float = 0.0
    assignments: list[ResponseSpectrumLoadAssignment] = field(default_factory=list)


@dataclass
class AutoSeismicTSC2018:
    load_pattern: str = ""
    direction: str = "X"
    percent_ecc: float = 0.05
    period_calc: str = "Prog Calc"
    ct_and_x: str = "0.10m, 0.75"
    r_coeff: float = 2.5
    d_coeff: float = 2.5
    i_coeff: float = 1.2
    ss: float = 0.329
    s1: float = 0.128
    tl: float = 8.0
    site_class: str = "ZC"
    fs: float = 1.3
    f1: float = 1.5


# ============================================================================
# SD SECTION
# ============================================================================
@dataclass
class SDPolygonPoint:
    x: float = 0.0
    y: float = 0.0
    radius: float = 0.0

    __unit_schema__ = {"x": Dimension.LENGTH, "y": Dimension.LENGTH, "radius": Dimension.LENGTH}


@dataclass
class SDShape:
    name: str = ""
    shape_kind: str = "Polygon"
    material: str = ""
    z_order: int = 1
    fill_color: tuple[float, float, float] = (0.8, 0.8, 0.8)
    points: list[SDPolygonPoint] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class SDSection:
    name: str = ""
    design_type: str = "No Check/Design"
    base_material: str = ""
    axis_angle: float = 90.0
    mesh_sz_abs: float = 0.0            # SECTION DESIGNER 01
    mesh_sz_rel: float = 0.05
    dsgn_or_chck: str = "Check"
    include_v_str: bool = False
    n_polygon: int = 0                  # v10
    shapes: list[SDShape] = field(default_factory=list)
    edge_rebars: list[dict] = field(default_factory=list)
    corner_rebars: list[dict] = field(default_factory=list)
    line_rebars: list[dict] = field(default_factory=list)
    rect_rebars: list[dict] = field(default_factory=list)
    fiber: dict = field(default_factory=dict)   # 30 - FIBER GENERAL

    __unit_schema__ = {
        "axis_angle": None,
        "mesh_sz_abs": Dimension.LENGTH,
        "mesh_sz_rel": None,
    }


# ============================================================================
# MASS ASSEMBLY (analiz çıktısı — birim dönüşümü YOK, her zaman kg/N)
# ============================================================================
@dataclass
class MassContribution:
    source_type: str
    element_id: int
    element_label: str
    pattern: str
    mass_kg: float


@dataclass
class MassAssembly:
    num_dofs: int
    M_global: np.ndarray
    node_masses: dict[str, float]
    contributions: list[MassContribution]
    total_self_kg: float = 0.0
    total_dead_kg: float = 0.0
    total_live_kg: float = 0.0
    n_live: float = 0.3

@dataclass
class WindDirectionResult:
    w_dir: tuple[float, float, float] = (0.0, 0.0, 0.0)
    q_p: float = 0.0
    q_b: float = 0.0
    z_ref: float = 0.0
    e: float = 0.0
    geometry: dict[str, Any] = field(default_factory=dict)
    zones_data: list[dict[str, Any]] = field(default_factory=list)