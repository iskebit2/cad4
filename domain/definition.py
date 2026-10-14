# domain/definition.py
"""
SAP2000 uyumlu tanım sınıfları
- Material, Section, LinkProp, LoadPattern, LoadCase, Combo, Restraint
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field, asdict, fields
from enum import Enum, IntEnum
from typing import Optional, Dict, Any, List, Tuple, Union
import typing
import uuid

import glm


# ============================================================================
# SERIALIZABLE BASE
# ============================================================================
class SerializableData:
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        if not data:
            return cls()

        fields_map = {f.name: f for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in fields_map}

        for name, f in fields_map.items():
            if name not in filtered:
                continue
            val = filtered[name]
            if val is None:
                continue

            # Alan tipini çöz (str ise modülden getir)
            ftype = f.type
            if isinstance(ftype, str):
                import sys
                mod = sys.modules.get(cls.__module__)
                # typing.Optional[X] vs X
                ftype = _resolve_type(ftype, mod) if mod else None

            # Enum koersiyonu
            if isinstance(ftype, type) and issubclass(ftype, Enum):
                if not isinstance(val, ftype):
                    try:
                        if isinstance(val, str):
                            filtered[name] = ftype[val]
                        else:
                            filtered[name] = ftype(val)
                    except (KeyError, ValueError):
                        pass
                continue

            # Nested dataclass koersiyonu
            if isinstance(ftype, type) and dataclasses.is_dataclass(ftype):
                if isinstance(val, dict) and not isinstance(val, ftype):
                    filtered[name] = ftype.from_dict(val)
                continue

            # List[...] içinde dataclass varsa
            origin = typing.get_origin(ftype)
            args = typing.get_args(ftype)
            if origin in (list, typing.List) and args:
                inner = args[0]
                if isinstance(inner, str):
                    import sys
                    mod = sys.modules.get(cls.__module__)
                    inner = getattr(mod, inner, None) if mod else None
                if (isinstance(inner, type)
                        and dataclasses.is_dataclass(inner)
                        and isinstance(val, list)):
                    filtered[name] = [
                        inner.from_dict(x) if isinstance(x, dict) else x
                        for x in val
                    ]
                elif (isinstance(inner, type)
                        and issubclass(inner, Enum)
                        and isinstance(val, list)):
                    filtered[name] = [
                        inner[x] if isinstance(x, str) else inner(x)
                        for x in val
                    ]

        return cls(**filtered)


def _resolve_type(type_str: str, mod):
    """'WindConfig' veya 'Optional[WindConfig]' gibi string'leri çöz."""
    type_str = type_str.strip()
    # Optional[X] / Union[X, None] → X
    if type_str.startswith("Optional["):
        inner = type_str[9:-1]
        return _resolve_type(inner, mod)
    if type_str.startswith("Union[") and "None" in type_str:
        # Union[X, None] → X
        parts = type_str[6:-1].split(",")
        for p in parts:
            p = p.strip()
            if p != "None" and not p.startswith("None"):
                return _resolve_type(p, mod)
    # Doğrudan sınıf adı
    return getattr(mod, type_str, None)


# ============================================================================
# CONFIG DATACLASSES
# ============================================================================
@dataclass
class WindConfig(SerializableData):
    # TS EN 1991-1-4
    vb0: float = 28.0
    terrain_category: str = "III"
    z0: float = 0.0
    z1: float = 5.27
    z2: float = 6.92
    cpi_positive: float = 0.2
    cpi_negative: float = -0.3


@dataclass
class SnowConfig(SerializableData):
    # TS EN 1991-1-3
    sk: float = 0.75
    exposure_coefficient: float = 1.0
    thermal_coefficient: float = 1.0
    shape_coefficient: float = 0.8


@dataclass
class SeismicConfig(SerializableData):
    # TBDY 2018
    ss: float = 0.0
    s1: float = 0.0
    soil_class: str = "ZD"
    importance_factor: float = 1.0
    building_height_class: str = ""
    behavior_factor: float = 8.0
    overstrength_factor: float = 3.0


@dataclass
class ProjectConfig(SerializableData):
    wind: WindConfig = field(default_factory=WindConfig)
    snow: SnowConfig = field(default_factory=SnowConfig)
    seismic: SeismicConfig = field(default_factory=SeismicConfig)


@dataclass
class ProjectInfo(SerializableData):
    name: str = "Untitled"
    description: str = ""
    author: str = ""


@dataclass
class LoadManager(SerializableData):
    pass


@dataclass
class WindDirectionResult(SerializableData):
    w_dir: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    q_p: float = 0.0
    q_b: float = 0.0
    z_ref: float = 0.0
    e: float = 0.0
    geometry: Dict[str, Any] = field(default_factory=dict)
    zones_data: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class WindAnalysisResult(SerializableData):
    directions: Dict[str, WindDirectionResult] = field(default_factory=dict)
    active_direction: Optional[Tuple[float, float, float]] = None


@dataclass
class AnalysisManager(SerializableData):
    wind: WindAnalysisResult = field(default_factory=WindAnalysisResult)
    snow: Any = None
    seismic: Any = None


@dataclass
class ReportManager(SerializableData):
    pass


# ============================================================================
# TBDY 2018 DEPREM TABLOLARI VE KATSAYILARI (LOOKUP TABLES)
# ============================================================================
TSC_2018_FS_TABLE = {
    "ZA": [(0.25, 0.8), (0.50, 0.8), (0.75, 0.8), (1.00, 0.8), (1.25, 0.8), (1.50, 0.8)],
    "ZB": [(0.25, 0.9), (0.50, 0.9), (0.75, 0.9), (1.00, 0.9), (1.25, 0.9), (1.50, 0.9)],
    "ZC": [(0.25, 1.3), (0.50, 1.3), (0.75, 1.2), (1.00, 1.2), (1.25, 1.2), (1.50, 1.2)],
    "ZD": [(0.25, 1.6), (0.50, 1.4), (0.75, 1.2), (1.00, 1.1), (1.25, 1.0), (1.50, 1.0)],
    "ZE": [(0.25, 2.4), (0.50, 1.7), (0.75, 1.3), (1.00, 1.1), (1.25, 0.9), (1.50, 0.8)],
}

TSC_2018_F1_TABLE = {
    "ZA": [(0.10, 0.8), (0.20, 0.8), (0.30, 0.8), (0.40, 0.8), (0.50, 0.8), (0.60, 0.8)],
    "ZB": [(0.10, 0.8), (0.20, 0.8), (0.30, 0.8), (0.40, 0.8), (0.50, 0.8), (0.60, 0.8)],
    "ZC": [(0.10, 1.5), (0.20, 1.5), (0.30, 1.5), (0.40, 1.4), (0.50, 1.3), (0.60, 1.2)],
    "ZD": [(0.10, 2.4), (0.20, 2.2), (0.30, 2.0), (0.40, 1.8), (0.50, 1.6), (0.60, 1.5)],
    "ZE": [(0.10, 4.2), (0.20, 3.3), (0.30, 2.8), (0.40, 2.4), (0.50, 2.2), (0.60, 2.0)],
}


def get_tsc2018_site_coefficients(ss: float, s1: float, site_class: str) -> Tuple[float, float]:
    """
    TBDY 2018 Tablo 2.1 ve 2.2'ye göre doğrusal interpolasyon ile Fs ve F1 katsayılarını hesaplar.
    ZF sınıfında sahaya özel zemin davranışı analizi gerektiğinden varsayılan 1.0 döner.
    """
    site_class = site_class.upper()
    if site_class not in TSC_2018_FS_TABLE or site_class == "ZF":
        return 1.0, 1.0

    def interpolate(val: float, points: List[Tuple[float, float]]) -> float:
        if val <= points[0][0]:
            return points[0][1]
        if val >= points[-1][0]:
            return points[-1][1]
        for i in range(len(points) - 1):
            x0, y0 = points[i]
            x1, y1 = points[i + 1]
            if x0 <= val <= x1:
                return y0 + (y1 - y0) * (val - x0) / (x1 - x0)
        return 1.0

    fs = interpolate(ss, TSC_2018_FS_TABLE[site_class])
    f1 = interpolate(s1, TSC_2018_F1_TABLE[site_class])
    return fs, f1


# ============================================================================
# ENUMERATION'LAR
# ============================================================================
class UnitSystem(IntEnum):
    LB_IN = 1
    LB_FT = 2
    KIP_IN = 3
    KIP_FT = 4
    KN_MM = 5
    KN_M = 6
    KGF_MM = 7
    KGF_M = 8
    N_MM = 9
    N_M = 10
    TON_MM = 11
    TON_M = 12
    KN_CM = 13
    KGF_CM = 14
    N_CM = 15
    TON_CM = 16

    @property
    def force_unit(self) -> str:
        return UNIT_DEFINITIONS_MAP[self][0]

    @property
    def length_unit(self) -> str:
        return UNIT_DEFINITIONS_MAP[self][1]


UNIT_DEFINITIONS_MAP = {
    UnitSystem.LB_IN: ('lb', 'in'),
    UnitSystem.LB_FT: ('lb', 'ft'),
    UnitSystem.KIP_IN: ('kip', 'in'),
    UnitSystem.KIP_FT: ('kip', 'ft'),
    UnitSystem.KN_MM: ('kN', 'mm'),
    UnitSystem.KN_M: ('kN', 'm'),
    UnitSystem.KGF_MM: ('kgf', 'mm'),
    UnitSystem.KGF_M: ('kgf', 'm'),
    UnitSystem.N_MM: ('N', 'mm'),
    UnitSystem.N_M: ('N', 'm'),
    UnitSystem.TON_MM: ('Ton', 'mm'),
    UnitSystem.TON_M: ('Ton', 'm'),
    UnitSystem.KN_CM: ('kN', 'cm'),
    UnitSystem.KGF_CM: ('kgf', 'cm'),
    UnitSystem.N_CM: ('N', 'cm'),
    UnitSystem.TON_CM: ('Ton', 'cm'),
}


class GridPlane(IntEnum):
    XY = 1
    XZ = 2
    YZ = 3
    
UNIT_DEFINITIONS = {
    1: ('lb', 'in'),
    2: ('lb', 'ft'),
    3: ('kip', 'in'),
    4: ('kip', 'ft'),
    5: ('kN', 'mm'),
    6: ('kN', 'm'),
    7: ('kgf', 'mm'),
    8: ('kgf', 'm'),
    9: ('N', 'mm'),
    10: ('N', 'm'),
    11: ('Ton', 'mm'),
    12: ('Ton', 'm'),
    13: ('kN', 'cm'),
    14: ('kgf', 'cm'),
    15: ('N', 'cm'),
    16: ('Ton', 'cm')
}

LOAD_PATTERN_TYPES = {
    1: "DEAD", 2: "SUPERDEAD", 3: "LIVE", 4: "REDUCELIVE", 5: "QUAKE", 6: "WIND", 7: "SNOW",
    8: "OTHER", 9: "MOVE", 10: "TEMPERATURE", 11: "ROOFLIVE", 12: "NOTIONAL", 13: "PATTERNLIVE",
    14: "WAVE", 15: "BRAKING", 16: "CENTRIFUGAL", 17: "FRICTION", 18: "ICE", 19: "WINDONLIVELOAD",
    20: "HORIZONTALEARTHPRESSURE", 21: "VERTICALEARTHPRESSURE", 22: "EARTHSURCHARGE", 23: "DOWNDRAG",
    24: "VEHICLECOLLISION", 25: "VESSELCOLLISION", 26: "TEMPERATUREGRADIENT", 27: "SETTLEMENT",
    28: "SHRINKAGE", 29: "CREEP", 30: "WATERLOADPRESSURE", 31: "LIVELOADSURCHARGE",
    32: "LOCKEDINFORCES", 33: "PEDESTRIANLL", 34: "PRESTRESS", 35: "HYPERSTATIC", 36: "BOUYANCY",
    37: "STREAMFLOW", 38: "IMPACT", 39: "CONSTRUCTION"
}

LOAD_CASE_TYPES = {
    1: "LinearStatic", 2: "NonlinearStatic", 3: "Modal", 4: "ResponseSpectrum",
    5: "LinearHistory", 6: "NonlinearHistory", 7: "LinearDynamic", 8: "NonlinearDynamic",
    9: "MovingLoad", 10: "Buckling", 11: "SteadyState", 12: "PowerSpectralDensity",
    13: "LinearStaticMultistep", 14: "Hyperstatic", 15: "ExternalResults",
    16: "StagedConstruction", 17: "NonlinearStaticMultiStep"
}

LOAD_CASE_DESIGN_TYPES = {
    1: "DEAD", 2: "SUPERDEAD", 3: "LIVE", 4: "REDUCELIVE", 5: "QUAKE", 6: "WIND", 7: "SNOW",
    8: "OTHER", 9: "MOVE", 10: "TEMPERATURE", 11: "ROOFLIVE", 12: "NOTIONAL", 13: "PATTERNLIVE",
    14: "WAVE", 15: "BRAKING", 16: "CENTRIFUGAL", 17: "FRICTION", 18: "ICE", 19: "WINDONLIVELOAD",
    20: "HORIZONTALEARTHPRESSURE", 21: "VERTICALEARTHPRESSURE", 22: "EARTHSURCHARGE", 23: "DOWNDRAG",
    24: "VEHICLECOLLISION", 25: "VESSELCOLLISION", 26: "TEMPERATUREGRADIENT", 27: "SETTLEMENT",
    28: "SHRINKAGE", 29: "CREEP", 30: "WATERLOADPRESSURE", 31: "LIVELOADSURCHARGE",
    32: "LOCKEDINFORCES", 33: "PEDESTRIANLL", 34: "PRESTRESS", 35: "HYPERSTATIC", 36: "BOUYANCY",
    37: "STREAMFLOW", 38: "IMPACT", 39: "CONSTRUCTION", 40: "DEADWEARING", 41: "DEADWATER",
    42: "DEADMANUFACTURE", 43: "EARTHHYDROSTATIC", 44: "PASSIVEEARTHPRESSURE",
    45: "ACTIVEEARTHPRESSURE", 46: "PEDESTRIANLLREDUCED", 47: "SNOWHIGHALTITUDE", 48: "EUROLM1CHAR",
    49: "EUROLM1FREQ", 50: "EUROLM2", 51: "EUROLM3", 52: "EUROLM4"
}

OBJECT_TYPE_MAP = {
    1: "Point", 2: "Frame", 3: "Cable", 4: "Tendon", 5: "Area", 6: "Solid", 7: "Link"
}

COMBOTYPE = {
    0: "Linear Additive",
    1: "Envelope",
    2: "Absolute Additive",
    3: "SRSS",
    4: "Range Additive",
}


class PropAreaType(IntEnum):
    All = 0
    Shell = 1
    Plane = 2
    Asolid = 3


class PropType(IntEnum):
    I = 1
    Channel = 2
    T = 3
    Angle = 4
    DblAngle = 5
    Box = 6
    Pipe = 7
    Rectangular = 8
    Circle = 9
    General = 10
    DbChannel = 11
    Auto = 12
    SD = 13
    Variable = 14
    Joist = 15
    Bridge = 16
    Cold_C = 17
    Cold_2C = 18
    Cold_Z = 19
    Cold_L = 20
    Cold_2L = 21
    Cold_HAT = 22
    BuiltupICoverplate = 23
    PCCGIRDERI = 24
    PCCGIRDERU = 25
    BuiltupIHybrid = 26
    BuiltupUHybrid = 27
    PCCGirderSuperT = 41
    Cold_Box = 42
    Cold_I = 43
    Cold_Pipe = 44
    Cold_T = 45
    Trapezoidal = 46


class SymType(IntEnum):
    ISOTROPIC = 0
    ORTHOTROPIC = 1
    ANISOTROPIC = 2
    UNIAXIAL = 3


@dataclass
class GridPlaneDef(SerializableData):
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
class GridConfig(SerializableData):
    x_coords: List[float] = field(default_factory=lambda: [0.0, 3000.0, 8000.0, 11000.0])
    y_coords: List[float] = field(default_factory=lambda: [0.0, 3000.0, 6000.0, 12000.0])
    z_coords: List[float] = field(default_factory=lambda: [0.0, 3200.0, 6400.0])
    origin_x: float = 0.0
    origin_y: float = 0.0
    origin_z: float = 0.0
    planes_visibility: Dict[str, bool] = field(default_factory=lambda: {"XY": True, "XZ": False, "YZ": False})

@dataclass
class GeneralProjectInfo(SerializableData):
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
class SiteInformation(SerializableData):
    live_load_factor: float = 0.3
    cadastral_info: str = "102 / 14"
    date: str = ""
    soil_class: str = "ZD"
    subgrade_modulus_kn_m3: float = 15000.0
    extra_items: Dict[str, Any] = field(default_factory=dict)


# -------------------------------------------------------------------------
# LOAD PATTERNS & CASES
# -------------------------------------------------------------------------
@dataclass
class LoadPattern(SerializableData):
    """TABLE: LOAD PATTERN DEFINITIONS"""
    name: str = ""
    design_type: str = "Dead"
    self_wt_mult: float = 0.0


@dataclass
class StaticLoadAssignment(SerializableData):
    """TABLE: CASE - STATIC 1 - LOAD ASSIGNMENTS"""
    load_type: str = "Load pattern"
    load_name: str = ""
    load_sf: float = 1.0


@dataclass
class LoadCase(SerializableData):
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
class ModalCase(SerializableData):
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
class ComboItem(SerializableData):
    case_or_pattern_name: str = ""
    scale_factor: float = 1.0


@dataclass
class LoadCombination(SerializableData):
    """TABLE: COMBINATION DEFINITIONS"""
    name: str = ""
    combo_type: str = "Linear Add"
    auto_design: bool = False
    items: List[ComboItem] = field(default_factory=list)


class SpectrumSourceType(Enum):
    USER = "USER"
    FROM_FILE = "FROM_FILE"
    TSC_2018 = "TSC_2018"
    EUROCODE = "EUROCODE"
    IBC = "IBC"


@dataclass
class SpectrumFunction(SerializableData):
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
class ResponseSpectrumLoadAssignment(SerializableData):
    load_name: str = ""
    function_name: str = ""
    angle: float = 0.0
    sf: float = 9810.0


@dataclass
class ResponseSpectrumCase(SerializableData):
    name: str = ""
    modal_combo: str = "CQC"
    dir_combo: str = "SRSS"
    damping: float = 0.05
    eccentricity: float = 0.0
    assignments: List[ResponseSpectrumLoadAssignment] = field(default_factory=list)


@dataclass
class AutoSeismicTSC2018(SerializableData):
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


class LoadType(Enum):
    POINT = "POINT"
    DISTRIBUTED = "DISTRIBUTED"
    GRAVITY = "GRAVITY"
    TEMPERATURE = "TEMPERATURE"
    UNIFORM = "UNIFORM"
    SURFACE_PRESSURE = "SURFACE_PRESSURE"
    STRAIN = "STRAIN"
    WIND_PRESSURE = "WIND_PRESSURE"
    UNIFORM_TO_FRAME = "UNIFORM_TO_FRAME"


class LoadDirection(Enum):
    GLOBAL_X = "GX"
    GLOBAL_Y = "GY"
    GLOBAL_Z = "GZ"
    LOCAL_1 = "1"
    LOCAL_2 = "2"
    LOCAL_3 = "3"
    GRAVITY = "GRAV"
    PROJECTED_X = "PX"
    PROJECTED_Y = "PY"
    PROJECTED_Z = "PZ"


SAP_FRAME_LOAD_DIRECTION = {
    1: LoadDirection.LOCAL_1,
    2: LoadDirection.LOCAL_2,
    3: LoadDirection.LOCAL_3,
    4: LoadDirection.GLOBAL_X,
    5: LoadDirection.GLOBAL_Y,
    6: LoadDirection.GLOBAL_Z,
    7: LoadDirection.GRAVITY,
    8: LoadDirection.PROJECTED_X,
    9: LoadDirection.PROJECTED_Y,
    10: LoadDirection.PROJECTED_Z,
}


# -------------------------------------------------------------------------
# JOINT LOADS
# -------------------------------------------------------------------------
@dataclass
class PointLoad(SerializableData):
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
class FramePointLoad(SerializableData):
    pattern_name: str = ""
    force_or_moment: str = "Force"
    direction: LoadDirection = LoadDirection.GLOBAL_Z
    value: float = 0.0
    distance: float = 0.0
    is_relative: bool = True
    coordinate_system: str = "GLOBAL"


@dataclass
class FrameDistributedLoad(SerializableData):
    pattern_name: str = ""
    force_or_moment: str = "Force"
    direction: LoadDirection = LoadDirection.GLOBAL_Z
    p1: float = 0.0
    p2: float = 0.0
    d1: float = 0.0
    d2: float = 0.0
    is_relative: bool = True
    coordinate_system: str = "GLOBAL"


@dataclass
class FrameGravityLoad(SerializableData):
    pattern_name: str = ""
    multiplier_x: float = 0.0
    multiplier_y: float = 0.0
    multiplier_z: float = 0.0


@dataclass
class FrameTemperatureLoad(SerializableData):
    pattern_name: str = ""
    temp_type: str = "Temperature"
    val: float = 0.0


# -------------------------------------------------------------------------
# AREA LOADS
# -------------------------------------------------------------------------
@dataclass
class AreaGravityLoad(SerializableData):
    pattern_name: str = ""
    multiplier_x: float = 0.0
    multiplier_y: float = 0.0
    multiplier_z: float = 0.0


@dataclass
class AreaRefTemperatureLoad(SerializableData):
    temp: float = 0.0


@dataclass
class AreaStrainLoad(SerializableData):
    pattern_name: str = ""
    component: str = "S11"
    val: float = 0.0


@dataclass
class AreaSurfacePressureLoad(SerializableData):
    pattern_name: str = ""
    face: str = "BOTTOM"
    pressure: float = 0.0


@dataclass
class AreaTemperatureLoad(SerializableData):
    pattern_name: str = ""
    temp_type: str = "Temperature"
    val: float = 0.0


@dataclass
class AreaUniformLoad(SerializableData):
    pattern_name: str = ""
    direction: LoadDirection = LoadDirection.GLOBAL_Z
    value: float = 0.0
    coordinate_system: str = "GLOBAL"


@dataclass
class AreaUniformToFrameLoad(SerializableData):
    pattern_name: str = ""
    direction: LoadDirection = LoadDirection.GLOBAL_Z
    value: float = 0.0
    dist_type: str = "To Joints"
    coordinate_system: str = "GLOBAL"


@dataclass
class AreaWindPressureLoad(SerializableData):
    pattern_name: str = ""
    cp: float = 0.0
    windward: bool = True
    dist_type: str = "To Joints"


class MatType(Enum):
    STEEL = 1
    CONCRETE = 2
    NODESIGN = 3
    ALUMINUM = 4
    COLDFORMED = 5
    REBAR = 6
    TENDON = 7
    TIMBER = 8
    MASONRY = 9


class SectionType(Enum):
    RECT = "RECT"
    CIRCLE = "CIRCLE"
    I = "I"
    L = "L"
    T = "T"
    PIPE = "PIPE"
    TUBE = "TUBE"
    C = "C"
    BOX = "BOX"
    CHANNEL = "CHANNEL"
    CUSTOM = "CUSTOM"

    def __str__(self):
        return self.value

    def __repr__(self):
        return f"SectionType.{self.name}"


class ElementType(Enum):
    NODE = "NODE"
    FRAME = "FRAME"
    AREA = "AREA"
    LINK = "LINK"


class ObjType(Enum):
    FRAME = 2
    AREA = 5
    LINK = 7


class LoadPatternType(Enum):
    DEAD = 1
    SUPER_DEAD = 2
    LIVE = 3
    WIND = 5
    SNOW = 6
    QUAKE = 7
    USER = 18


class LoadCaseType(Enum):
    LIN_STATIC = 1
    NONLIN_STATIC = 4
    LIN_MODAL = 2


class ComboType(Enum):
    LINEAR_ADD = 1
    ENVELOPE = 2
    SRSS = 4


# ============================================================================
# MATERIAL
# ============================================================================
@dataclass
class Material(SerializableData):
    name: str = "DEFAULT"
    mat_type: MatType = MatType.STEEL
    color: Tuple[float, float, float] = (0.8, 0.8, 0.8)

    E1: float = 2.0e8
    E2: float = 2.0e8
    E3: float = 2.0e8

    G12: float = 7.7e7
    G13: float = 7.7e7
    G23: float = 7.7e7

    nu12: float = 0.3
    nu13: float = 0.3
    nu23: float = 0.3

    density: float = 7850

    @property
    def E(self) -> float:
        return self.E1

    @property
    def G(self) -> float:
        return self.G12

    @property
    def nu(self) -> float:
        return self.nu12


# ============================================================================
# SECTION
# ============================================================================
DEFAULT_MATERIAL = Material(
    name="DEFAULT_STEEL",
    mat_type=MatType.STEEL,
    E1=2.1e8,
    G12=8.1e7,
    nu12=0.3,
    density=7850
)


@dataclass
class Section(SerializableData):
    name: str = ""
    profile_type: SectionType = SectionType.RECT
    profile_params: Dict[str, float] = field(default_factory=dict)
    material: Optional[Material] = None
    color: Tuple[float, float, float] = (0.8, 0.8, 0.8)

    def __post_init__(self):
        if self.material is None:
            self.material = DEFAULT_MATERIAL

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["material_name"] = self.material.name if self.material else None
        d["profile_type"] = self.profile_type.name if hasattr(self.profile_type, "name") else str(self.profile_type)
        d.pop("material", None)   # nested Material yazma
        return d


@dataclass
class AreaSection(SerializableData):
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
    
    def to_dict(self) -> dict:
        d = super().to_dict()
        d["material_name"] = self.material.name if self.material else None
        d["prop_type"] = self.prop_type.name if hasattr(self.prop_type, "name") else str(self.prop_type)
        d.pop("material", None)
        return d

# ============================================================================
# LINK PROPERTIES
# ============================================================================
class LinkPropType(IntEnum):
    LINEAR = 1
    DAMPER = 2
    GAP = 3
    HOOK = 4
    PLASTIC_WEN = 5
    ISOLATOR1 = 6
    ISOLATOR2 = 7
    MULTILINEAR_ELASTIC = 8
    MULTILINEAR_PLASTIC = 9
    ISOLATOR3 = 10

    @classmethod
    def from_sap(cls, sap_str: str) -> "LinkPropType":
        if not sap_str:
            return cls.LINEAR
        mapping = {
            "LINEAR": cls.LINEAR, "LIN": cls.LINEAR,
            "DAMPER": cls.DAMPER,
            "GAP": cls.GAP,
            "HOOK": cls.HOOK,
            "PLASTIC": cls.PLASTIC_WEN, "PLASTICWEN": cls.PLASTIC_WEN,
            "ISOLATOR1": cls.ISOLATOR1,
            "ISOLATOR2": cls.ISOLATOR2,
            "MULTILINEARELASTIC": cls.MULTILINEAR_ELASTIC,
            "MULTILINEARPLASTIC": cls.MULTILINEAR_PLASTIC,
            "ISOLATOR3": cls.ISOLATOR3,
        }
        key = sap_str.strip().upper().replace(" ", "").replace("_", "")
        return mapping.get(key, cls.LINEAR)


@dataclass
class LinkProperty(SerializableData):
    name: str = ""
    prop_type: LinkPropType = LinkPropType.LINEAR

    dof: Tuple[bool, ...] = ()
    fixed: Tuple[bool, ...] = ()

    ke: Tuple[float, ...] = ()
    ce: Tuple[float, ...] = ()

    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LinkProp(SerializableData):
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
class Restraint(SerializableData):
    ux: bool = False
    uy: bool = False
    uz: bool = False
    rx: bool = False
    ry: bool = False
    rz: bool = False

    DOF_ORDER = ('ux', 'uy', 'uz', 'rx', 'ry', 'rz')

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            ux=data.get("ux", False),
            uy=data.get("uy", False),
            uz=data.get("uz", False),
            rx=data.get("rx", False),
            ry=data.get("ry", False),
            rz=data.get("rz", False),
        )

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

    def __repr__(self):
        fixed = self.fixed_dofs()
        if not fixed:
            return "<Restraint: FREE>"
        return f"<Restraint fixed={fixed}>"


class SectionCutDefinedBy(str, Enum):
    GROUP = "Group"
    QUAD = "Quad"
    COORDINATE = "Coordinate"


class SectionCutResultType(str, Enum):
    ANALYSIS = "Analysis"
    DESIGN = "Design"


@dataclass
class QuadDefinition(SerializableData):
    points: List[Tuple[float, float, float]] = field(default_factory=list)


@dataclass
class SectionCut(SerializableData):
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