# domain/definition.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pyglm import glm
import numpy as np

from core.units import DENSITY_STEEL, Dimension
from data.enums import (
    DistType, LinkPropType, LoadDirection, MatType, PropAreaType,
    SectionCutDefinedBy, SectionCutResultType, SectionType,
    SpectrumSourceType, ConstraintType,
)
from data.seismic import get_tsc2018_site_coefficients


@dataclass
class Material:
    name: str = "DEFAULT"
    mat_type: MatType = MatType.STEEL
    color: tuple[float, float, float] = (0.8, 0.8, 0.8)
    grade: str = ""
    sym_type: str = "Isotropic"
    temp_depend: bool = False
    design_type: str = ""
    notes: str = ""

    E1: float = 2.1e5
    E2: float = 2.1e5
    E3: float = 2.1e5
    G12: float = 8.1e4
    G13: float = 8.1e4
    G23: float = 8.1e4
    nu12: float = 0.3
    nu13: float = 0.3
    nu23: float = 0.3
    density: float = DENSITY_STEEL

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

    fc: float = 0.0
    efc: float = 0.0
    ltwt_conc: bool = False
    sfc: float = 0.0
    s_cap: float = 0.0
    f_angle: float = 0.0
    d_angle: float = 0.0

    rebar_fy: float = 0.0
    rebar_fys: float = 0.0
    ltwt_fact: float = 1.0

    rebar_ss_curve_opt: str = "Simple"
    rebar_ss_hys_type: str = "Kinematic"
    rebar_s_hard: float = 0.0
    rebar_s_cap: float = 0.0
    rebar_use_ct_def: bool = False

    tendon_ss_curve_opt: str = ""
    tendon_ss_hys_type: str = "Kinematic"

    modal_ratio: float = 0.0
    vis_mass: float = 0.0
    vis_stiff: float = 0.0
    hys_mass: float = 0.0
    hys_stiff: float = 0.0

    io_tens: float = 0.0
    ls_tens: float = 0.0
    cp_tens: float = 0.0
    io_comp: float = 0.0
    ls_comp: float = 0.0
    cp_comp: float = 0.0
    ignore_tens: bool = False

    yield_stress: float = 0.0
    lin_iso_hard: bool = False
    lin_kin_hard: bool = False
    nl_iso_sa_hard: bool = False

    __unit_schema__ = {
        "E1": Dimension.STRESS, "E2": Dimension.STRESS, "E3": Dimension.STRESS,
        "G12": Dimension.STRESS, "G13": Dimension.STRESS, "G23": Dimension.STRESS,
        "density": Dimension.MASS_DENSITY,
        "fy": Dimension.STRESS, "fu": Dimension.STRESS,
        "eff_fy": Dimension.STRESS, "eff_fu": Dimension.STRESS,
        "s_hard": Dimension.STRESS, "s_max": Dimension.STRESS, "s_rup": Dimension.STRESS,
        "fc": Dimension.STRESS, "efc": Dimension.STRESS,
        "sfc": Dimension.STRESS, "s_cap": Dimension.STRESS,
        "rebar_fy": Dimension.STRESS, "rebar_fys": Dimension.STRESS,
        "rebar_s_hard": Dimension.STRESS, "rebar_s_cap": Dimension.STRESS,
        "yield_stress": Dimension.STRESS,
    }

    @property
    def E(self) -> float: return self.E1

    @property
    def G(self) -> float: return self.G12

    @property
    def nu(self) -> float: return self.nu12

    def is_concrete(self) -> bool: return self.mat_type == MatType.CONCRETE

    def is_steel(self) -> bool: return self.mat_type == MatType.STEEL


DEFAULT_MATERIAL = Material(
    name="DEFAULT_STEEL", mat_type=MatType.STEEL,
    E1=2.1e5, G12=8.1e4, nu12=0.3, density=DENSITY_STEEL,
)


@dataclass
class Section:
    name: str = ""
    profile_type: SectionType = SectionType.RECT
    profile_params: dict[str, float] = field(default_factory=dict)
    material: Material | None = None
    color: tuple[float, float, float] = (0.8, 0.8, 0.8)
    catalog_props: dict[str, float] = field(default_factory=dict)
    catalog_source: str = ""
    sd_section: "SDSection | None" = None
    cg_offset3: float = 0.0
    cg_offset2: float = 0.0
    ecc_v2: float = 0.0
    ecc_v3: float = 0.0
    from_file: bool = False
    notes: str = ""
    rebar_column: dict[str, Any] = field(default_factory=dict)
    rebar_beam: dict[str, Any] = field(default_factory=dict)
    time_dependent: dict[str, Any] = field(default_factory=dict)

    __unit_schema__ = {
        "profile_params.Area": Dimension.AREA,
        "profile_params.I33": Dimension.I4,
        "profile_params.I22": Dimension.I4,
        "profile_params.J": Dimension.I4,
        "profile_params.h": Dimension.LENGTH,
        "profile_params.b": Dimension.LENGTH,
        "cg_offset3": Dimension.LENGTH,
        "cg_offset2": Dimension.LENGTH,
        "ecc_v2": Dimension.LENGTH,
        "ecc_v3": Dimension.LENGTH,
    }

    def __post_init__(self):
        if self.material is None:
            self.material = DEFAULT_MATERIAL

    def is_concrete(self) -> bool:
        return bool(self.rebar_column or self.rebar_beam)


@dataclass
class AreaSection:
    name: str = ""
    prop_type: PropAreaType = PropAreaType.Shell
    area_type: str = "Shell-Thin"
    material: Material | None = None
    mat_angle: float = 0.0
    thickness: float = 0.0
    bend_thick: float | None = None
    drill_dof: bool = False
    color: tuple[float, float, float] = (0.8, 0.8, 0.8)
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
    rebar_mat: str = ""
    rebar_opt: str = "Default"
    type_size: str = "Auto"
    auto_sf_size: float = 1.0
    params: dict = field(default_factory=dict)

    __unit_schema__ = {
        "thickness": Dimension.LENGTH,
        "bend_thick": Dimension.LENGTH,
    }

    @property
    def effective_bend_thick(self) -> float:
        return self.bend_thick if self.bend_thick is not None else self.thickness


@dataclass
class LinkProp:
    name: str = "LINK1"
    prop_type: LinkPropType = LinkPropType.LINEAR


@dataclass
class LinkPropLinear(LinkProp):
    DOF: dict[str, bool] = field(default_factory=lambda: {
        "U1": True, "U2": True, "U3": True, "R1": True, "R2": True, "R3": True,
    })
    Fixed: dict[str, bool] = field(default_factory=dict)
    Ke: dict[str, float] = field(default_factory=lambda: {k: 0.0 for k in ("U1", "U2", "U3", "R1", "R2", "R3")})
    Ce: dict[str, float] = field(default_factory=lambda: {k: 0.0 for k in ("U1", "U2", "U3", "R1", "R2", "R3")})

    __unit_schema__ = {
        "Ke.U1": Dimension.FORCE, "Ke.U2": Dimension.FORCE, "Ke.U3": Dimension.FORCE,
        "Ke.R1": Dimension.MOMENT, "Ke.R2": Dimension.MOMENT, "Ke.R3": Dimension.MOMENT,
    }


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
        return sum(1 << i for i, d in enumerate(self.DOF_ORDER) if getattr(self, d))


@dataclass
class WindConfig:
    v_b0: float = 28.0
    terrain: str = "Kategori III"
    rho: float = 1.25
    ct: float = 1.0
    kI: float = 1.0
    z0: float = 0.0
    z1: float = 5.27
    z2: float = 6.92
    cpi_positive: float = 0.2
    cpi_negative: float = -0.3

    @property
    def vb0(self) -> float: return self.v_b0
    @vb0.setter
    def vb0(self, val: float): self.v_b0 = val

    @property
    def terrain_category(self) -> str: return self.terrain
    @terrain_category.setter
    def terrain_category(self, val: str): self.terrain = val

    __unit_schema__ = {
        "v_b0": Dimension.ACCEL, "vb0": Dimension.ACCEL,
        "z0": Dimension.LENGTH, "z1": Dimension.LENGTH, "z2": Dimension.LENGTH
    }


@dataclass
class SnowConfig:
    slope: float = 15.0
    snow_region: int = 2
    altitude: float = 50.0
    sk: float = 0.75
    Ce: float = 1.0
    Ct: float = 1.0
    shape_coefficient: float = 0.8

    @property
    def exposure_coefficient(self) -> float: return self.Ce
    @exposure_coefficient.setter
    def exposure_coefficient(self, val: float): self.Ce = val

    @property
    def thermal_coefficient(self) -> float: return self.Ct
    @thermal_coefficient.setter
    def thermal_coefficient(self, val: float): self.Ct = val

    __unit_schema__ = {"sk": Dimension.AREA_LOAD}


@dataclass
class SeismicConfig:
    R: float = 2.5
    D: float = 2.5
    I: float = 1.2
    kappa: float = 0.5
    Hn: float = 10.1
    gamma_E: float = 0.9
    n: float = 0.30
    e: str = "±0.05"
    ee: str = "Dbi= (η_bi/1.2)², Ek dış merkezlik= %5 + Dbi"
    zemin_sinifi: str = "ZC"
    limit_raw: float = 0.008
    load_cases: list[str] = field(default_factory=lambda: ["EQX", "EQY", "QUAKEX", "QUAKEY"])
    drift_combo_names: list[str] = field(default_factory=lambda: ["EXP", "EXM", "EYP", "EYM"])
    has_irregularity: bool = True
    dd2: dict[str, float] = field(default_factory=lambda: {
        "Ss": 0.329, "S1": 0.128, "PGA": 0.143, "PGV": 10.653,
        "Fs": 1.300, "F1": 1.500, "Sds": 0.428, "Sd1": 0.192,
    })
    dd3: dict[str, float] = field(default_factory=lambda: {
        "Ss": 0.130, "S1": 0.054, "PGA": 0.058, "PGV": 4.540,
        "Fs": 1.300, "F1": 1.500, "Sds": 0.169, "Sd1": 0.081,
    })
    
    # Geriye dönük uyumluluk property'leri
    @property
    def ss(self) -> float: return self.dd2.get("Ss", 0.0)
    @property
    def s1(self) -> float: return self.dd2.get("S1", 0.0)
    @property
    def soil_class(self) -> str: return self.zemin_sinifi
    @property
    def importance_factor(self) -> float: return self.I
    @property
    def behavior_factor(self) -> float: return self.R
    @property
    def overstrength_factor(self) -> float: return self.D


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
class WindResult:
    direction: tuple[float, float, float] = (0.0, 0.0, 0.0)
    q_p: float = 0.0
    q_b: float = 0.0
    z_ref: float = 0.0
    e: float = 0.0
    zones_cpe10: list[dict] = field(default_factory=list)
    zones_cpe1: list[dict] = field(default_factory=list)


@dataclass
class LoadManager:
    wind_zones: dict[str, list[Any]] = field(default_factory=dict)
    wind_results: dict[str, WindResult] = field(default_factory=dict)
    snow_loads: list[dict] = field(default_factory=list)
    area_load_transfers: list[dict] = field(default_factory=list)
    area_frame_transfers: list[dict] = field(default_factory=list)
    area_frame_base_loads: list[dict] = field(default_factory=list)

    def add_area_load_transfer(
        self,
        polygon,
        load: "AreaUniformLoad",
        *,
        analysis_data: Any | None = None,
        transfer_target: str = "frames",
        dist_type: DistType = DistType.ONE_WAY_U1,
    ) -> dict:
        if polygon is None or not hasattr(polygon, "unique_id"):
            raise TypeError("polygon gerekli")
        if not isinstance(load, AreaUniformLoad):
            raise TypeError("AreaUniformLoad gerekli")
        if analysis_data is None:
            raise ValueError("PolygonAnalysisData gerekli")
        if transfer_target not in ("frames", "areas"):
            raise ValueError("transfer_target geçersiz")

        dist = DistType.from_input(dist_type)
        stored = AreaUniformLoad(
            pattern_name=load.pattern_name, direction=load.direction,
            value=float(load.value), coordinate_system=load.coordinate_system,
            source_name=load.source_name,
        )
        analysis_data.assigned_loads.append(stored)
        analysis_data.transfer_target = transfer_target
        if hasattr(polygon, "set_dist_type"):
            polygon.set_dist_type(dist)
        analysis_data.transfer_dist_type = dist.value
        analysis_data.is_load_area = True

        record = {
            "polygon_id": int(polygon.unique_id), "source_type": "uniform",
            "transfer_target": transfer_target, "dist_type": dist.value,
            "load": stored, "source_key": f"polygon:{int(polygon.unique_id)}",
        }
        self.area_load_transfers.append(record)
        return record

    def area_load_transfers_for_polygon(self, polygon_id: int) -> list[dict]:
        return [t for t in self.area_load_transfers
                if int(t.get("polygon_id", -1)) == int(polygon_id)]


@dataclass
class ReportManager:
    reports: list[Any] = field(default_factory=list)

    def add_report(self, report) -> None:
        """Aynı rapor nesnesi listede yoksa güvenli bir şekilde ekler."""
        if not any(r is report for r in self.reports):
            self.reports.append(report)

    def clear(self) -> None:
        self.reports.clear()


@dataclass
class AnalysisManager:
    wind: Any = None
    snow: Any = None
    seismic: Any = None


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

    __unit_schema__ = {"global_x": Dimension.LENGTH, "global_y": Dimension.LENGTH, "global_z": Dimension.LENGTH}


@dataclass
class LoadPattern:
    name: str = ""
    design_type: str = "Dead"
    self_wt_mult: float = 0.0


@dataclass
class StaticLoadAssignment:
    load_type: str = "Load pattern"
    load_name: str = ""
    load_sf: float = 1.0


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


@dataclass
class LoadCombination:
    name: str = ""
    combo_type: str = "Linear Add"
    auto_design: bool = False
    items: list[ComboItem] = field(default_factory=list)


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
class LoadSegment:
    x1: float = 0.0
    x2: float = 1.0
    q1: float = 0.0
    q2: float = 0.0

    __unit_schema__ = {"q1": Dimension.LINE_LOAD, "q2": Dimension.LINE_LOAD}

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

    def add_segment(self, x1, x2, q1, q2):
        self.segments.append(LoadSegment(x1, x2, q1, q2))
        self.segments.sort(key=lambda s: s.x1)

    def clear(self):
        self.segments.clear()

    def to_sap_loads(self):
        return [
            FrameDistributedLoad(
                pattern_name=self.pattern_name, coord_sys=self.coord_sys,
                load_dir=self.load_dir, mode=self.mode,
                force_or_moment=self.force_or_moment, direction=self.direction,
                is_relative=self.is_relative, coordinate_system=self.coordinate_system,
                dist_type=self.dist_type, segments=[seg],
            )
            for seg in self.segments
        ]


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
    source_name: str = ""

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

    def __post_init__(self):
        if self.source_type == SpectrumSourceType.TSC_2018 and not self.points:
            self.generate_tbdy2018_points()

    def generate_tbdy2018_points(self, num_points: int = 200):
        self.fs, self.f1 = get_tsc2018_site_coefficients(self.ss, self.s1, self.site_class)
        sds, sd1 = self.ss * self.fs, self.s1 * self.f1
        ta = 0.2 * (sd1 / sds) if sds > 0 else 0.0
        tb = (sd1 / sds) if sds > 0 else 0.0
        self.points.clear()
        dt = max(self.tl + 2.0, 8.0) / num_points
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
            ra = ((self.d_coeff + (self.r_coeff / self.i_coeff - self.d_coeff) * (t / tb))
                  if t < tb and tb > 0 else self.r_coeff / self.i_coeff)
            self.points.append((round(t, 4), round(sae / ra if ra > 0 else sae, 6)))

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
                return sa0 if t1 == t0 else sa0 + (sa1 - sa0) * (period - t0) / (t1 - t0)
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
    reinforcing: bool = False


@dataclass
class SDSection:
    name: str = ""
    design_type: str = "No Check/Design"
    base_material: str = ""
    axis_angle: float = 90.0
    mesh_sz_abs: float = 0.0
    mesh_sz_rel: float = 0.05
    dsgn_or_chck: str = "Check"
    include_v_str: bool = False
    n_polygon: int = 0
    shapes: list[SDShape] = field(default_factory=list)
    edge_rebars: list[dict] = field(default_factory=list)
    corner_rebars: list[dict] = field(default_factory=list)
    line_rebars: list[dict] = field(default_factory=list)
    rect_rebars: list[dict] = field(default_factory=list)
    fiber: dict = field(default_factory=dict)

    __unit_schema__ = {"mesh_sz_abs": Dimension.LENGTH}


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
class ConstraintDefinition:
    name: str = ""
    constraint_type: ConstraintType | None = None
    coord_sys: str = "GLOBAL"
    axis: str = "Z"
    ux: bool = False
    uy: bool = False
    uz: bool = False
    rx: bool = False
    ry: bool = False
    rz: bool = False
    u1: bool = False
    u2: bool = False
    u3: bool = False
    r1: bool = False
    r2: bool = False
    r3: bool = False
    multi_level: bool = False
    tolerance: float = 0.0

    __unit_schema__ = {"tolerance": Dimension.LENGTH}

@dataclass
class WindDirectionResult:
    w_dir: tuple[float, float, float] = (0.0, 0.0, 0.0)
    q_p: float = 0.0
    q_b: float = 0.0
    z_ref: float = 0.0
    e: float = 0.0
    geometry: dict[str, Any] = field(default_factory=dict)
    zones_data: list[dict[str, Any]] = field(default_factory=list)