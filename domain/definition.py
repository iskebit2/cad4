# domain/definition.py
"""
SAP2000 uyumlu tanım sınıfları
- Material, Section, LinkProp, LoadPattern, LoadCase, Combo, Restraint
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field, asdict

from typing import Optional, Dict, Any, List, Tuple, Type
import typing

import glm
import numpy as np
from data.seismic import get_tsc2018_site_coefficients
# ============================================================================
# RE-EXPORT (s2k_utils.py'nin beklediği tüm isimler)
# ============================================================================
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
from data.unit_enums import DENSITY_STEEL

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

# domain/definition.py (başına)

# ============================================================================
# BİRİM SÖZLEŞMESİ (tek doğruluk kaynağı)
# ============================================================================
# Uzunluk      : mm
# Kuvvet       : N
# Gerilme      : MPa (= N/mm²)
# Moment       : N·mm
# Kütle        : kg   (yoğunluk kg/mm³ ise hacim mm³ → kg)
# Yoğunluk     : kg/mm³
# Yerçekimi ivmesi g : 9810 mm/s²
#
# Material.density [kg/mm³] — çelik 7.85e-6, beton 2.5e-6
# Section.profile_params['Area'] [mm²]
# Section.profile_params['I33','I22','J'] [mm⁴]
# MassSource katkıları kg cinsinden; rapor ton'a çevirirken /1000.
# ============================================================================



# ============================================================================
# MATERIAL
# ============================================================================
@dataclass
class Material:
    name: str = "DEFAULT"
    mat_type: MatType = MatType.STEEL
    color: Tuple[float, float, float] = (0.8, 0.8, 0.8)
    E1: float = 2.1e5     # MPa (çelik 210 GPa)
    E2: float = 2.1e5
    E3: float = 2.1e5
    G12: float = 8.1e4    # MPa (G = E / (2(1+ν)))
    G13: float = 8.1e4
    G23: float = 8.1e4
    nu12: float = 0.3
    nu13: float = 0.3
    nu23: float = 0.3
    density: float = DENSITY_STEEL   # kg/mm³

    @property
    def E(self) -> float:
        return self.E1
    @property
    def G(self) -> float:
        return self.G12
    @property
    def nu(self) -> float:
        return self.nu12

DEFAULT_MATERIAL = Material(
    name="DEFAULT_STEEL",
    mat_type=MatType.STEEL,
    E1=2.1e8,
    G12=8.1e7,
    nu12=0.3,
    density=DENSITY_STEEL   # kg/mm³

)
# ============================================================================
# SECTION
# ============================================================================
@dataclass
class Section:
    name: str = ""
    profile_type: SectionType = SectionType.RECT
    profile_params: Dict[str, float] = field(default_factory=dict)
    material: Optional[Material] = None
    color: Tuple[float, float, float] = (0.8, 0.8, 0.8)

    # YENİ: Katalogdan gelen hesaplanmış özellikler (analiz için)
    catalog_props: Dict[str, float] = field(default_factory=dict)
    catalog_source: str = ""    # "CSI Euro - W" gibi

    sd_section: Optional["SDSection"] = None   # ileri referans
    
    def __post_init__(self):
        if self.material is None:
            self.material = DEFAULT_MATERIAL



@dataclass
class AreaSection:
    name: str = ""
    prop_type: PropAreaType = PropAreaType.Shell
    material: Optional[Material] = None
    thickness: float = 0.0

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

    params: Dict = field(default_factory=dict)

    @property
    def modifiers(self):
        return (
            self.membrane_f11,
            self.membrane_f22,
            self.membrane_f12,
            self.bending_m11,
            self.bending_m22,
            self.bending_m12,
            self.shear_v13,
            self.shear_v23,
            self.mass,
            self.weight,
        )
    

# ============================================================================
# LINK PROPERTIES
# ============================================================================
@dataclass
class LinkProperty:
    name: str = ""
    prop_type: LinkPropType = LinkPropType.LINEAR

    dof: Tuple[bool, ...] = ()
    fixed: Tuple[bool, ...] = ()

    ke: Tuple[float, ...] = ()
    ce: Tuple[float, ...] = ()

    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LinkProp:
    name: str = "LINK1"
    prop_type: LinkPropType = LinkPropType.LINEAR

@dataclass
class LinkPropLinear(LinkProp):
    """Linear link property - DOF bazlı stiffness ve damping"""
    prop_type: LinkPropType = LinkPropType.LINEAR
    DOF: Dict[str, bool] = field(default_factory=lambda: {
        "U1": True, "U2": True, "U3": True,
        "R1": True, "R2": True, "R3": True
    })

    Fixed: Dict[str, bool] = field(default_factory=dict)

    Ke: Dict[str, float] = field(default_factory=lambda: {
        "U1": 0.0, "U2": 0.0, "U3": 0.0,
        "R1": 0.0, "R2": 0.0, "R3": 0.0
    })

    Ce: Dict[str, float] = field(default_factory=lambda: {
        "U1": 0.0, "U2": 0.0, "U3": 0.0,
        "R1": 0.0, "R2": 0.0, "R3": 0.0
    })

    def __post_init__(self):
        self.DOF = self.DOF or {"U1": True, "U2": True, "U3": True,
                                "R1": True, "R2": True, "R3": True}
        self.Fixed = self.Fixed or {}
        self.Ke = self.Ke or {"U1": 0, "U2": 0, "U3": 0,
                              "R1": 0, "R2": 0, "R3": 0}
        self.Ce = self.Ce or {"U1": 0, "U2": 0, "U3": 0,
                              "R1": 0, "R2": 0, "R3": 0}


@dataclass
class Restraint:
    ux: bool = False
    uy: bool = False
    uz: bool = False
    rx: bool = False
    ry: bool = False
    rz: bool = False

    DOF_ORDER = ('ux', 'uy', 'uz', 'rx', 'ry', 'rz')

    @classmethod
    def from_list(cls, values):
        return cls(*values)

    def is_free(self):
        return not any(self.as_list())

    def is_fully_fixed(self):
        return all(self.as_list())

    def fixed_dofs(self):
        return [name for name in self.DOF_ORDER if getattr(self, name)]

    def free_dofs(self):
        return [name for name in self.DOF_ORDER if not getattr(self, name)]

    def as_list(self):
        return [getattr(self, dof) for dof in self.DOF_ORDER]

    def as_dict(self):
        return {dof: getattr(self, dof) for dof in self.DOF_ORDER}

    def as_int_mask(self):
        mask = 0
        for i, dof in enumerate(self.DOF_ORDER):
            if getattr(self, dof):
                mask |= (1 << i)
        return mask

# ============================================================================
# CONFIG DATACLASSES
# ============================================================================
@dataclass
class WindConfig:
    # TS EN 1991-1-4
    vb0: float = 28.0
    terrain_category: str = "III"
    z0: float = 0.0
    z1: float = 5.27
    z2: float = 6.92
    cpi_positive: float = 0.2
    cpi_negative: float = -0.3

@dataclass
class SnowConfig:
    # TS EN 1991-1-3
    sk: float = 0.75
    exposure_coefficient: float = 1.0
    thermal_coefficient: float = 1.0
    shape_coefficient: float = 0.8

@dataclass
class SeismicConfig:
    # TBDY 2018
    ss: float = 0.0
    s1: float = 0.0
    soil_class: str = "ZD"
    importance_factor: float = 1.0
    building_height_class: str = ""
    behavior_factor: float = 8.0
    overstrength_factor: float = 3.0

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
    extra_items: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ProjectInfo:
    name: str = "Untitled"
    description: str = ""
    author: str = ""

@dataclass
class LoadManager:
    pass

@dataclass
class WindDirectionResult:
    w_dir: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    q_p: float = 0.0
    q_b: float = 0.0
    z_ref: float = 0.0
    e: float = 0.0
    geometry: Dict[str, Any] = field(default_factory=dict)
    zones_data: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class WindAnalysisResult:
    directions: Dict[str, WindDirectionResult] = field(default_factory=dict)
    active_direction: Optional[Tuple[float, float, float]] = None

@dataclass
class AnalysisManager:
    wind: WindAnalysisResult = field(default_factory=WindAnalysisResult)
    snow: Any = None
    seismic: Any = None

@dataclass
class ReportManager:
    pass

@dataclass
class GridPlaneDef:
    """Kullanıcı tanımlı eğik grid düzlemi."""
    name: str = ""
    origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    # Düzlemin normal vektörü (birim, otomatik normalize)
    normal: Tuple[float, float, float] = (0.0, 0.0, 1.0)
    # Yerel U ekseni (normal'e dik, otomatik ortonormalize)
    u_axis: Tuple[float, float, float] = (1.0, 0.0, 0.0)
    # U ve V yönünde grid aralığı (yerel birim)
    spacing_u: float = 1000.0
    spacing_v: float = 1000.0
    # Kaç çizgi çizilecek (her yönde)
    count_u: int = 20
    count_v: int = 20
    # Görsel
    visible: bool = True
    color: Tuple[float, float, float] = (0.55, 0.55, 0.60)
    locked: bool = False

    def get_uv_frame(self):
        """Ortonormal (origin, U, V, N) frame döner."""
        n = glm.normalize(glm.vec3(*self.normal))
        u = glm.vec3(*self.u_axis)
        # U'yu N'e dik hale getir
        u = u - n * glm.dot(u, n)
        if glm.length(u) < 1e-6:
            # Dejenere — dünya X kullan
            u = glm.vec3(1, 0, 0) - n * n.x
        u = glm.normalize(u)
        v = glm.cross(n, u)
        return glm.vec3(*self.origin), u, v, n
    
@dataclass
class GridConfig:
    x_coords: List[float] = field(default_factory=lambda: [0.0, 1000.0])
    y_coords: List[float] = field(default_factory=lambda: [0.0, 1000.0])
    z_coords: List[float] = field(default_factory=lambda: [0.0, 1000.0])
    origin_x: float = 0.0
    origin_y: float = 0.0
    origin_z: float = 0.0
    planes_visibility: Dict[str, bool] = field(default_factory=lambda: {"XY": True, "XZ": False, "YZ": False})

@dataclass
class QuadDefinition:
    points: List[Tuple[float, float, float]] = field(default_factory=list)

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

    quad: Optional[QuadDefinition] = None

# -------------------------------------------------------------------------
# LOAD PATTERNS & CASES
# -------------------------------------------------------------------------
@dataclass
class LoadPattern:
    """TABLE: LOAD PATTERN DEFINITIONS"""
    name: str = ""
    design_type: str = "Dead"
    self_wt_mult: float = 0.0

@dataclass
class StaticLoadAssignment:
    """TABLE: CASE - STATIC 1 - LOAD ASSIGNMENTS"""
    load_type: str = "Load pattern"
    load_name: str = ""
    load_sf: float = 1.0

@dataclass
class LoadCase:
    """TABLE: LOAD CASE DEFINITIONS"""
    name: str = ""
    case_type: str = "LinStatic"
    initial_cond: str = "Zero"
    design_type: str = "Dead"
    design_act: str = "Non-Composite"
    auto_type: str = "None"
    run_case: bool = True
    static_assignments: List[StaticLoadAssignment] = field(default_factory=list)

@dataclass
class ModalCase:
    """TABLE: CASE - MODAL 1 - GENERAL"""
    name: str = ""
    mode_type: str = "Eigen"
    max_num_modes: int = 12
    min_num_modes: int = 1
    eigen_shift: float = 0.0
    eigen_cutoff: float = 0.0
    eigen_tol: float = 1e-9
    auto_shift: bool = True

# -------------------------------------------------------------------------
# COMBINATIONS
# -------------------------------------------------------------------------
@dataclass
class ComboItem:
    case_or_pattern_name: str = ""
    scale_factor: float = 1.0

@dataclass
class LoadCombination:
    name: str = ""
    combo_type: str = "Linear Add"
    auto_design: bool = False
    items: List[ComboItem] = field(default_factory=list)

    
# -------------------------------------------------------------------------
# JOINT LOADS
# -------------------------------------------------------------------------
@dataclass
class PointLoad:
    pattern_name: str = ""
    fx: float = 0.0
    fy: float = 0.0
    fz: float = 0.0
    mx: float = 0.0
    my: float = 0.0
    mz: float = 0.0

# -------------------------------------------------------------------------
# FRAME LOADS
# -------------------------------------------------------------------------
@dataclass
class FramePointLoad:
    pattern_name: str = ""
    force_or_moment: str = "Force"
    direction: LoadDirection = LoadDirection.GLOBAL_Z
    value: float = 0.0
    distance: float = 0.0
    is_relative: bool = True
    coordinate_system: str = "GLOBAL"

@dataclass
class LoadSegment:
    x1: float = 0.0
    x2: float = 1.0
    q1: float = 0.0
    q2: float = 0.0

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
    dist_type: str = "one_way"      # ← YENİ: "one_way" veya "two_way"
    segments: List[LoadSegment] = field(default_factory=list)

    def add_segment(self, x1: float, x2: float, q1: float, q2: float):
        self.segments.append(LoadSegment(x1, x2, q1, q2))
        self.segments.sort(key=lambda s: s.x1)

    def clear(self):
        self.segments.clear()

    def to_sap_loads(self):
        out = []
        for seg in self.segments:
            out.append(FrameDistributedLoad(
                pattern_name=self.pattern_name,
                coord_sys=self.coord_sys,
                load_dir=self.load_dir,
                mode=self.mode,
                force_or_moment=self.force_or_moment,
                direction=self.direction,           # ← EKLENDİ
                is_relative=self.is_relative,
                coordinate_system=self.coordinate_system,
                dist_type=self.dist_type,
                segments=[seg],
            ))
        return out

    @classmethod
    def from_sap_loads(cls, loads):
        if not loads:
            return cls()
        first = loads[0]
        s = cls(
            pattern_name=first.pattern_name,
            coord_sys=first.coord_sys,
            load_dir=first.load_dir,
            mode=first.mode,
            is_relative=getattr(first, "is_relative", True),
            coordinate_system=getattr(first, "coordinate_system", "GLOBAL"),
            dist_type=getattr(first, "dist_type", "one_way"),   # ← YENİ
        )
        for ld in loads:
            for seg in ld.segments:
                s.add_segment(seg.x1, seg.x2, seg.q1, seg.q2)
        return s


@dataclass
class FrameGravityLoad:
    pattern_name: str = ""
    multiplier_x: float = 0.0
    multiplier_y: float = 0.0
    multiplier_z: float = 0.0


@dataclass
class FrameTemperatureLoad:
    pattern_name: str = ""
    temp_type: str = "Temperature"
    val: float = 0.0

# -------------------------------------------------------------------------
# AREA LOADS
# -------------------------------------------------------------------------
@dataclass
class AreaGravityLoad:
    pattern_name: str = ""
    multiplier_x: float = 0.0
    multiplier_y: float = 0.0
    multiplier_z: float = 0.0

@dataclass
class AreaRefTemperatureLoad:
    temp: float = 0.0

@dataclass
class AreaStrainLoad:
    pattern_name: str = ""
    component: str = "S11"
    val: float = 0.0

@dataclass
class AreaSurfacePressureLoad:
    pattern_name: str = ""
    face: str = "BOTTOM"
    pressure: float = 0.0

@dataclass
class AreaTemperatureLoad:
    pattern_name: str = ""
    temp_type: str = "Temperature"
    val: float = 0.0

@dataclass
class AreaUniformLoad:
    pattern_name: str = ""
    direction: LoadDirection = LoadDirection.GLOBAL_Z
    value: float = 0.0
    coordinate_system: str = "GLOBAL"

@dataclass
class AreaUniformToFrameLoad:
    pattern_name: str = ""
    direction: LoadDirection = LoadDirection.GLOBAL_Z
    value: float = 0.0
    dist_type: DistType = DistType.ONE_WAY
    coordinate_system: str = "GLOBAL"

@dataclass
class AreaWindPressureLoad:
    pattern_name: str = ""
    cp: float = 0.0
    windward: bool = True
    dist_type: str = "To Joints"

# -------------------------------------------------------------------------
# SEISMIC
# -------------------------------------------------------------------------
@dataclass
class SpectrumFunction:
    """Tepki Spektrumu Fonksiyon Tanımları"""
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
    file_path: Optional[str] = None
    data_type: str = "Period vs Accel"
    points: List[Tuple[float, float]] = field(default_factory=list)

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
                ra = self.d_coeff + (self.r_coeff / self.i_coeff - self.d_coeff) * (t / tb) if tb > 0 else self.r_coeff / self.i_coeff
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

@dataclass
class ResponseSpectrumCase:
    name: str = ""
    modal_combo: str = "CQC"
    dir_combo: str = "SRSS"
    damping: float = 0.05
    eccentricity: float = 0.0
    assignments: List[ResponseSpectrumLoadAssignment] = field(default_factory=list)

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

@dataclass
class SDPolygonPoint:
    x: float = 0.0
    y: float = 0.0
    radius: float = 0.0

@dataclass
class SDShape:
    name: str = ""
    shape_kind: str = "Polygon"        # "Polygon" | "SolidRect" | "Pipe" | ...
    material: str = ""
    z_order: int = 1
    fill_color: Tuple[float,float,float] = (0.8,0.8,0.8)
    # polygon için
    points: List[SDPolygonPoint] = field(default_factory=list)
    # diğer shape'ler için ham parametreler
    params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SDSection:
    name: str = ""
    design_type: str = "No Check/Design"
    base_material: str = ""
    axis_angle: float = 90.0
    shapes: List[SDShape] = field(default_factory=list)
    # donatı (opsiyonel, tablo 02/03/18/19)
    edge_rebars: List[dict] = field(default_factory=list)
    corner_rebars: List[dict] = field(default_factory=list)
    line_rebars: List[dict] = field(default_factory=list)
    rect_rebars: List[dict] = field(default_factory=list)
    fiber: dict = field(default_factory=dict)

@dataclass
class MassContribution:
    """Tek bir kütle kaynağı. Rapor ve debug için."""
    source_type: str      # "frame_self" | "frame_load" | "area_self" | ...
    element_id: int
    element_label: str
    pattern: str          # "" self için
    mass_kg: float

@dataclass
class MassAssembly:
    """Kütle toplamanın tek çıkışı."""
    num_dofs: int
    M_global: np.ndarray              # köşegen, kg
    node_masses: Dict[str, float]     # kg, key = scene.nodes anahtarı
    contributions: List[MassContribution]
    # Özet
    total_self_kg: float = 0.0
    total_dead_kg: float = 0.0
    total_live_kg: float = 0.0
    n_live: float = 0.3
