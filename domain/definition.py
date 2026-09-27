# domain/definition.py
"""
SAP2000 uyumlu tanım sınıfları
- Material, Section, LinkProp, LoadPattern, LoadCase, Combo, Restraint
"""
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple, Union
from dataclasses import dataclass, field
import uuid

# ============================================================================
# ENUMERATION'LAR
# ============================================================================

class MatType(Enum):
    STEEL = 1
    CONCRETE = 2
    NODESIGN = 3
    ALUMINUM = 4
    COLDFORMED = 5
    REBAR = 6
    TENDON = 7

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
    E: float = 2.0e8
    G: float = 7.7e7
    nu: float = 0.3
    density: float = 7850
    guid: str = field(default_factory=lambda: str(uuid.uuid4()))

# ============================================================================
# SECTION (element.py'deki Section ile uyumlu)
# ============================================================================

class Section:
    def __init__(self, name: str, profile_type: SectionType,
                 profile_params: Dict[str, float],
                 material: Optional[Material] = None,
                 color: Tuple[float, float, float] = (0.8, 0.8, 0.8)):
        self.name = name
        self.profile_type = profile_type
        self.profile_params = profile_params
        self.material = material
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
        self.load_combos: Dict[str, LoadCombination] = {}
    
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