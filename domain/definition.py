# domain/definition.py
"""
SAP2000 uyumlu tanım sınıfları
- Material, Section, LinkProp, LoadPattern, LoadCase, Combo, Restraint
"""
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple, Union
from dataclasses import dataclass, field
import uuid

from domain.sap_enums import (
    LOAD_PATTERN_TYPES,
    LOAD_CASE_TYPES,
    LOAD_CASE_DESIGN_TYPES,
    COMBOTYPE
)

# ============================================================================
# TBDY 2018 DEPREM TABLOLARI VE KATSAYILARI (LOOKUP TABLES)
# ============================================================================

# Tablo 2.1 – Kısa periyot bölgesi için Yerel Zemin Etki Katsayıları (Fs)
TSC_2018_FS_TABLE = {
    # Zemin Sınıfı: [(Ss_sınırı, Fs_değeri), ...] -> İnterpolasyon için
    "ZA": [(0.25, 0.8), (0.50, 0.8), (0.75, 0.8), (1.00, 0.8), (1.25, 0.8), (1.50, 0.8)],
    "ZB": [(0.25, 0.9), (0.50, 0.9), (0.75, 0.9), (1.00, 0.9), (1.25, 0.9), (1.50, 0.9)],
    "ZC": [(0.25, 1.3), (0.50, 1.3), (0.75, 1.2), (1.00, 1.2), (1.25, 1.2), (1.50, 1.2)],
    "ZD": [(0.25, 1.6), (0.50, 1.4), (0.75, 1.2), (1.00, 1.1), (1.25, 1.0), (1.50, 1.0)],
    "ZE": [(0.25, 2.4), (0.50, 1.7), (0.75, 1.3), (1.00, 1.1), (1.25, 0.9), (1.50, 0.8)],
}

# Tablo 2.2 – 1.0 saniye periyot için Yerel Zemin Etki Katsayıları (F1)
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

    
# -------------------------------------------------------------------------
# LOAD PATTERNS & CASES
# -------------------------------------------------------------------------

@dataclass
class LoadPattern:
    """TABLE: LOAD PATTERN DEFINITIONS"""
    name: str
    design_type: str = "Dead"
    self_wt_mult: float = 0.0
    guid: Optional[str] = None

@dataclass
class StaticLoadAssignment:
    """TABLE: CASE - STATIC 1 - LOAD ASSIGNMENTS"""
    load_type: str      # 'Load pattern', 'Accel' vb.
    load_name: str      # Pattern adı
    load_sf: float = 1.0  # Ölçek çarpanı

@dataclass
class LoadCase:
    """TABLE: LOAD CASE DEFINITIONS"""
    name: str
    case_type: str = "LinStatic"
    initial_cond: str = "Zero"
    design_type: str = "Dead"
    design_act: str = "Non-Composite"
    auto_type: str = "None"
    run_case: bool = True
    guid: Optional[str] = None
    # Statik yük atamaları listesi
    static_assignments: List[StaticLoadAssignment] = field(default_factory=list)

@dataclass
class ModalCase:
    """TABLE: CASE - MODAL 1 - GENERAL"""
    name: str
    mode_type: str = "Eigen"    # Eigen / Ritz
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
    """Kombinasyon İçindeki Her Bir Eleman/Yükleme"""
    case_or_pattern_name: str
    scale_factor: float = 1.0

@dataclass
class LoadCombination:
    """TABLE: COMBINATION DEFINITIONS"""
    name: str
    combo_type: str = "Linear Add"  # Linear Add, Envelope, Absolute Add, SRSS, Range Add
    auto_design: bool = False
    items: List[ComboItem] = field(default_factory=list)
    guid: Optional[str] = None


class SpectrumSourceType(Enum):
    USER = "USER"
    FROM_FILE = "FROM_FILE"
    TSC_2018 = "TSC_2018"  # TBDY 2018
    EUROCODE = "EUROCODE"
    IBC = "IBC"

@dataclass
class SpectrumFunction:
    """Tepki Spektrumu Fonksiyon Tanımları"""
    name: str
    source_type: SpectrumSourceType
    damp: float = 0.05
    # TBDY 2018 veya Kod Parametreleri
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
    # Dosyadan okuma / Kullanıcı tanımlı veri
    file_path: Optional[str] = None
    data_type: str = "Period vs Accel"
    points: List[Tuple[float, float]] = field(default_factory=list) # (Periyot, İvme)

    def __post_init__(self):
        """Eğer TBDY 2018 seçilmişse ve points dizisi henüz boşsa noktaları üretir."""
        if self.source_type == SpectrumSourceType.TSC_2018 and not self.points:
            self.generate_tbdy2018_points()

    def generate_tbdy2018_points(self, num_points: int = 200):
        """TBDY 2018 parametrelerinden T-Sa eğri noktalarını hesaplar."""
        # Fs ve F1 zemin katsayılarını hesapla
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
            # TBDY 2018 Denklem (2.2) - Sae(T)
            if 0 <= t < ta:
                sae = (0.4 + 0.6 * (t / ta)) * sds if ta > 0 else sds
            elif ta <= t <= tb:
                sae = sds
            elif tb < t <= self.tl:
                sae = sd1 / t
            else:
                sae = (sd1 * self.tl) / (t ** 2)

            # Azaltma Katsayısı Ra(T) - Denklem (4.1)
            if t < tb:
                ra = self.d_coeff + (self.r_coeff / self.i_coeff - self.d_coeff) * (t / tb) if tb > 0 else self.r_coeff / self.i_coeff
            else:
                ra = self.r_coeff / self.i_coeff

            sa_design = sae / ra if ra > 0 else sae
            self.points.append((round(t, 4), round(sa_design, 6)))

    def get_sa(self, period: float) -> float:
        """
        Verilen T periyodu için points (T, Sa) listesinden doğrusal interpolasyon ile Sa değerini döndürür.
        """
        if not self.points:
            return 0.0
        
        # Periyot dizinin en başından küçükse ilk değeri dön
        if period <= self.points[0][0]:
            return self.points[0][1]
        
        # Periyot dizinin en sonundan büyükse son değeri dön
        if period >= self.points[-1][0]:
            return self.points[-1][1]
        
        # İki nokta arasında doğrusal interpolasyon (Linear Interpolation)
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
    """CASE - RESPONSE SPECTRUM 2 - LOAD ASSIGNMENTS"""
    load_name: str       # U1, U2, U3 vb.
    function_name: str   # İlgili SpectrumFunction adı
    angle: float = 0.0
    sf: float = 9810.0   # Ölçek Katsayısı (TransAccSF - mm/s2)

@dataclass
class ResponseSpectrumCase:
    """CASE - RESPONSE SPECTRUM 1 & 2"""
    name: str
    modal_combo: str = "CQC"
    dir_combo: str = "SRSS"
    damping: float = 0.05
    eccentricity: float = 0.0
    assignments: List[ResponseSpectrumLoadAssignment] = field(default_factory=list)

@dataclass
class AutoSeismicTSC2018:
    """AUTO SEISMIC - TSC-2018 (Eşdeğer Deprem Yükü)"""
    load_pattern: str
    direction: str          # X, Y, X+EccY vb.
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

# -------------------------------------------------------------------------
# JOINT LOADS
# -------------------------------------------------------------------------

@dataclass
class PointLoad:
    """JOINT LOADS - FORCE"""
    pattern_name: str
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
    """FRAME LOADS - POINTS"""
    pattern_name: str
    force_or_moment: str  # 'FORCE' veya 'MOMENT'
    direction: LoadDirection
    value: float          # N veya N*mm
    distance: float       # Bağıl veya Mutlak
    is_relative: bool = True

@dataclass
class FrameDistributedLoad:
    """FRAME LOADS - DISTRIBUTED"""
    pattern_name: str
    force_or_moment: str  # 'FORCE' veya 'MOMENT'
    direction: LoadDirection
    p1: float             # N/mm
    p2: float             # N/mm
    d1: float             # Mesafe A
    d2: float             # Mesafe B
    is_relative: bool = True

@dataclass
class FrameGravityLoad:
    """FRAME LOADS - GRAVITY"""
    pattern_name: str
    multiplier_x: float = 0.0
    multiplier_y: float = 0.0
    multiplier_z: float = 0.0

@dataclass
class FrameTemperatureLoad:
    """FRAME LOADS - TEMPERATURE"""
    pattern_name: str
    temp_type: str        # 'Temperature' veya 'Gradient'
    val: float            # °C veya °C/mm


# -------------------------------------------------------------------------
# AREA LOADS
# -------------------------------------------------------------------------

@dataclass
class AreaGravityLoad:
    """AREA LOADS - GRAVITY"""
    pattern_name: str
    multiplier_x: float = 0.0
    multiplier_y: float = 0.0
    multiplier_z: float = 0.0

@dataclass
class AreaRefTemperatureLoad:
    """AREA LOADS - REFERENCE TEMPERATURE"""
    temp: float           # °C

@dataclass
class AreaStrainLoad:
    """AREA LOADS - STRAIN"""
    pattern_name: str
    component: str        # 'S11', 'S22', 'S12'
    val: float

@dataclass
class AreaSurfacePressureLoad:
    """AREA LOADS - SURFACE PRESSURE"""
    pattern_name: str
    face: str             # 'BOTTOM', 'TOP'
    pressure: float       # N/mm2

@dataclass
class AreaTemperatureLoad:
    """AREA LOADS - TEMPERATURE"""
    pattern_name: str
    temp_type: str
    val: float

@dataclass
class AreaUniformLoad:
    """AREA LOADS - UNIFORM"""
    pattern_name: str
    direction: LoadDirection
    value: float          # N/mm2

@dataclass
class AreaUniformToFrameLoad:
    """AREA LOADS - UNIFORM TO FRAME (Tributary Area / Bir-İki Yönlü Aktarım)"""
    pattern_name: str
    direction: LoadDirection
    value: float          # N/mm2
    dist_type: str        # 'One way', 'Two way'

@dataclass
class AreaWindPressureLoad:
    """AREA LOADS - WIND PRESSURE COEFFICIENTS"""
    pattern_name: str
    cp: float             # Cp katsayısı
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
    TIMBER = 8        # Ahşap
    MASONRY = 9       # Yığma duvar

class SectionType(Enum):
    """FEA çubuk kesit tipleri"""
    RECT = "RECT"
    CIRCLE = "CIRCLE"
    I = "I"
    L = "L"
    T = "T"
    PIPE = "PIPE"
    TUBE = "TUBE"
    C = "C"
    BOX = "BOX"
    CHANNEL = "CHANNEL"  # C ile aynı
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

class LinkPropType(Enum):
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
class Material:
    name: str = "DEFAULT"
    mat_type: MatType = MatType.STEEL
    color: Tuple[float, float, float] = (0.8, 0.8, 0.8)
    
    # 3 Lokal eksen elastisite modülleri (Ortotropik destekli)
    E1: float = 2.0e8
    E2: float = 2.0e8
    E3: float = 2.0e8
    
    # 3 Düzlem kayma modülleri
    G12: float = 7.7e7
    G13: float = 7.7e7
    G23: float = 7.7e7
    
    # Poisson oranları (U12, U13, U23)
    nu12: float = 0.3
    nu13: float = 0.3
    nu23: float = 0.3
    
    density: float = 7850
    guid: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Çubuk eleman analizlerinde (1 ekseni boyunca) geriye dönük uyumluluk için
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
# SECTION (element.py'deki Section ile uyumlu)
# ============================================================================
# Varsayılan Malzeme Nesnesi
DEFAULT_MATERIAL = Material(
    name="DEFAULT_STEEL",
    mat_type=MatType.STEEL,
    E1=2.1e8,       # kN/m² veya N/mm² ölçeğine göre
    G12=8.1e7,
    nu12=0.3,
    density=7850
)

class Section:
    def __init__(self, name: str, profile_type: SectionType,
                 profile_params: Dict[str, float],
                 material: Optional[Material] = None,
                 color: Tuple[float, float, float] = (0.8, 0.8, 0.8)):
        self.name = name
        self.profile_type = profile_type
        self.profile_params = profile_params
        self.material = material if material is not None else DEFAULT_MATERIAL
        self.color = color
        self.guid = str(uuid.uuid4())

# ============================================================================
# LINK PROPERTIES
# ============================================================================

@dataclass
class LinkProp:
    name: str = "LINK1"
    prop_type: LinkPropType = LinkPropType.LINEAR
    guid: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class LinkPropLinear(LinkProp):
    """Linear link property - DOF bazlı stiffness ve damping"""
    prop_type: LinkPropType = LinkPropType.LINEAR
    DOF: Dict[str, bool] = None
    Fixed: Dict[str, bool] = None
    Ke: Dict[str, float] = None  # Stiffness
    Ce: Dict[str, float] = None  # Damping
    
    def __post_init__(self):
        self.DOF = self.DOF or {"U1": True, "U2": True, "U3": True,
                                 "R1": True, "R2": True, "R3": True}
        self.Fixed = self.Fixed or {}
        self.Ke = self.Ke or {"U1": 0, "U2": 0, "U3": 0,
                               "R1": 0, "R2": 0, "R3": 0}
        self.Ce = self.Ce or {"U1": 0, "U2": 0, "U3": 0,
                               "R1": 0, "R2": 0, "R3": 0}


class Restraint:
    DOF_ORDER = ('ux', 'uy', 'uz', 'rx', 'ry', 'rz')

    def __init__(self, ux=False, uy=False, uz=False,
                 rx=False, ry=False, rz=False):
        self.ux = ux
        self.uy = uy
        self.uz = uz
        self.rx = rx
        self.ry = ry
        self.rz = rz
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
    # ----------------------------
    # Temel durum kontrolleri
    # ----------------------------
    def is_free(self):
        return not any(self.as_list())

    def is_fully_fixed(self):
        return all(self.as_list())

    def fixed_dofs(self):
        return [name for name in self.DOF_ORDER if getattr(self, name)]

    def free_dofs(self):
        return [name for name in self.DOF_ORDER if not getattr(self, name)]

    # ----------------------------
    # Veri dönüşümleri
    # ----------------------------
    def as_list(self):
        return [getattr(self, dof) for dof in self.DOF_ORDER]

    def as_dict(self):
        return {dof: getattr(self, dof) for dof in self.DOF_ORDER}

    def as_int_mask(self):
        """Solver için bit mask (performanslı)"""
        mask = 0
        for i, dof in enumerate(self.DOF_ORDER):
            if getattr(self, dof):
                mask |= (1 << i)
        return mask

    # ----------------------------
    # String gösterim
    # ----------------------------
    def __repr__(self):
        fixed = self.fixed_dofs()
        if not fixed:
            return "<Restraint: FREE>"
        return f"<Restraint fixed={fixed}>"

# ============================================================================
# MANAGER
# ============================================================================

class DefinitionManager:
    def __init__(self):
        self.materials: Dict[str, Material] = {}
        self.sections: Dict[str, Section] = {}
        self.link_props: Dict[str, LinkProp] = {}

        self.load_patterns: Dict[str, LoadPattern] = {}
        self.load_cases: Dict[str, LoadCase] = {}
        self.modal_cases: Dict[str, ModalCase] = {}
        self.combinations: Dict[str, LoadCombination] = {}

        self.spectrum_functions: Dict[str, SpectrumFunction] = {}
        self.response_spectrum_cases: Dict[str, ResponseSpectrumCase] = {}
        self.auto_seismics: Dict[str, AutoSeismicTSC2018] = {}
        self.mass_source_map: Dict[str, float] = {}
        self.project_info: Dict[str, GeneralProjectInfo | SiteInformation] = {
            "gen": GeneralProjectInfo(),
            "site": SiteInformation(),
        }

    # --- ESKİ METOTLARIN ---
    def add_material(self, m: Material):
        self.materials[m.guid] = m

    def add_section(self, s: Section):
        self.sections[s.guid] = s

    def add_link_prop(self, p: LinkProp):
        self.link_props[p.guid] = p

    def get_section_by_name(self, name: str) -> Optional[Section]:
        for s in self.sections.values():
            if s.name == name:
                return s
        return None

    # =========================================================================
    # SPEKTRUM VE DEPREM YÖNETİM METOTLARI (YENİ EKLENENLER)
    # =========================================================================

    def add_spectrum_function(self, spec: SpectrumFunction):
        """Spektrum fonksiyonunu hafızaya kaydeder."""
        self.spectrum_functions[spec.name] = spec

    def add_response_spectrum_case(self, rs_case: ResponseSpectrumCase):
        """Response Spectrum analiz yük durumunu kaydeder."""
        self.response_spectrum_cases[rs_case.name] = rs_case

    def add_auto_seismic(self, auto_seismic: AutoSeismicTSC2018):
        """Eşdeğer Deprem Yükü tanımını kaydeder."""
        self.auto_seismics[auto_seismic.load_pattern] = auto_seismic

    def create_tbdy2018_spectrum(
        self,
        name: str,
        ss: float,
        s1: float,
        site_class: str = "ZC",
        r_coeff: float = 1.0,
        d_coeff: float = 1.0,
        i_coeff: float = 1.0,
        tl: float = 6.0,
        num_points: int = 200
    ) -> SpectrumFunction:
        """
        TBDY 2018 parametrelerinden Fs, F1, Sds, Sd1, Ta, Tb değerlerini türetip
        otomatik olarak (T, Sae) spektrum eğri noktalarını hesaplar ve SpectrumFunction döndürür.
        """
        fs, f1 = get_tsc2018_site_coefficients(ss, s1, site_class)
        sds = ss * fs
        sd1 = s1 * f1

        ta = 0.2 * (sd1 / sds) if sds > 0 else 0.0
        tb = (sd1 / sds) if sds > 0 else 0.0

        # Spektrum eğrisi nokta matrisini üret (T = 0'dan T = T_L + 2.0 saniyeye kadar)
        points: List[Tuple[float, float]] = []
        max_t = max(tl + 2.0, 8.0)
        dt = max_t / num_points

        # R, D, I katsayılarına göre azaltılmış/elastik spektral ivme hesabı (Sae / Ra)
        # Eğer elastik spektrum isteniyorsa r_coeff=1.0, d_coeff=1.0 bırakılır.
        for i in range(num_points + 1):
            t = i * dt
            
            # TBDY 2018 Denklem (2.2) - Yatay Elastik Deprem İvmesi Sae(T)
            if 0 <= t < ta:
                sae = (0.4 + 0.6 * (t / ta)) * sds if ta > 0 else sds
            elif ta <= t <= tb:
                sae = sds
            elif tb < t <= tl:
                sae = sd1 / t
            else:
                sae = (sd1 * tl) / (t ** 2)

            # Azaltma Katsayısı Ra(T) Hesabı - TBDY 2018 Denklem (4.1)
            if t < tb:
                ra = d_coeff + (r_coeff / i_coeff - d_coeff) * (t / tb) if tb > 0 else r_coeff / i_coeff
            else:
                ra = r_coeff / i_coeff

            # İvme spektrumu Sa(T) = Sae(T) / Ra(T)
            sa_design = sae / ra if ra > 0 else sae
            points.append((round(t, 4), round(sa_design, 6)))

        # SpectrumFunction nesnesi oluştur ve kaydet
        spec_func = SpectrumFunction(
            name=name,
            source_type=SpectrumSourceType.TSC_2018,
            ss=ss,
            s1=s1,
            tl=tl,
            site_class=site_class,
            fs=fs,
            f1=f1,
            r_coeff=r_coeff,
            d_coeff=d_coeff,
            i_coeff=i_coeff,
            points=points
        )
        self.add_spectrum_function(spec_func)
        return spec_func

    def __inspector_tree__(self) -> dict:
        """
        GUI Inspector için iç yapının kategorize edilmiş görünümü.
        Eleman sayıları 0 olsa dahi alt kategoriler ağaçta görünür.
        """
        return {
            "Materials": self.materials,
            "Sections": self.sections,
            "Link Properties": self.link_props,
            "Load Patterns": self.load_patterns,
            "Load Cases": self.load_cases,
            "Modal Cases": self.modal_cases,
            "Load Combinations": self.combinations,
            "Spectrum Functions": self.spectrum_functions,
            "Response Spectrum Cases": self.response_spectrum_cases,
            "Auto Seismics (TBDY 2018)": self.auto_seismics,
            "Project Information": self.project_info or "Tanımlanmadı"
        }