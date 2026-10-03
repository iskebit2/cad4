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
# ENUMERATION'LAR
# ============================================================================

from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class ProjectInformation:
    # SAP2000 Standart Alanları
    company_name: str = ""
    client_name: str = ""
    project_name: str = "Endüstriyel Depo Yapısı"
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
    
    # Özel / Yerel Alanlar (İngilizce attribute ismiyle)
    cadastral_info: str = "102 / 14"       # Ada / Parsel
    date: str = ""                          # Tarih
    soil_class: str = "ZD"                  # Zemin Sınıfı
    subgrade_modulus_kn_m3: float = 15000.0 # Yatak Katsayısı
    
    extra_items: Dict[str, Any] = field(default_factory=dict)

    def to_s2k_dict(self) -> Dict[str, str]:
        data = {
            "Company Name": self.company_name,
            "Client Name": self.client_name,
            "Project Name": self.project_name,
            "Project Number": self.project_number,
            "Model Name": self.model_name,
            "Model Description": self.model_description,
            "Revision Number": self.revision_number,
            "Frame Type": self.frame_type,
            "Engineer": self.engineer,
            "Checker": self.checker,
            "Supervisor": self.supervisor,
            "Issue Code": self.issue_code,
            "Design Code": self.design_code,
            # SAP2000 tablosuna basılacak etiketler
            "Cadastral Info": self.cadastral_info,
            "Date": self.date,
            "Soil Class": self.soil_class,
            "Subgrade Modulus (kN/m3)": str(self.subgrade_modulus_kn_m3),
        }
        
        for key, val in self.extra_items.items():
            data[key] = str(val)

        return data

    def to_s2k(self) -> str:
        lines = ['TABLE:  "PROJECT INFORMATION"']
        for item, val in self.to_s2k_dict().items():
            if val:
                lines.append(f'   Item="{item}"   Data="{val}"')
            else:
                lines.append(f'   Item="{item}"')
        lines.append("")
        return "\n".join(lines)
    
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

# ============================================================================
# LOAD DEFINITIONS
# ============================================================================

@dataclass
class LoadPattern:
    name: str
    pattern_type: LoadPatternType = LoadPatternType.DEAD
    self_weight_multiplier: float = 1.0
    guid: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class LoadCase:
    name: str
    case_type: LoadCaseType = LoadCaseType.LIN_STATIC
    patterns: List[Tuple[LoadPattern, float]] = field(default_factory=list)
    guid: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class LoadCombination:
    name: str
    combo_type: ComboType = ComboType.LINEAR_ADD
    cases: List[Tuple[LoadCase, float]] = field(default_factory=list)
    guid: str = field(default_factory=lambda: str(uuid.uuid4()))

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