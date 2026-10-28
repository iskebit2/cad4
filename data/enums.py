# domain/enums.py

from enum import Enum, IntEnum, auto

# ============================================================================
# ENUMERATION'LAR
# ============================================================================

class MatType(IntEnum):
    STEEL     = 1
    CONCRETE  = 2
    NODESIGN  = 3
    ALUMINUM  = 4
    COLDFORMED = 5
    REBAR     = 6
    TENDON    = 7
    MASONRY   = 8
    TIMBER    = 9
    OTHER     = 10
    RHINO     = 11

    @classmethod
    def from_sap(cls, sap_value) -> "MatType":
        """S2K'dan gelen 'Steel', 'Concrete', 2, '2' vb. normalize et."""
        if isinstance(sap_value, cls):
            return sap_value
        if isinstance(sap_value, int):
            try:
                return cls(sap_value)
            except ValueError:
                return cls.NODESIGN
        s = str(sap_value).strip().lower()
        # Sayısal kod
        if s.isdigit():
            try:
                return cls(int(s))
            except ValueError:
                return cls.NODESIGN
        # İsim eşleşmesi
        name_map = {
            "steel":       cls.STEEL,
            "concrete":    cls.CONCRETE,
            "nodesign":    cls.NODESIGN,
            "no design":   cls.NODESIGN,
            "aluminum":    cls.ALUMINUM,
            "coldformed":  cls.COLDFORMED,
            "cold formed": cls.COLDFORMED,
            "rebar":       cls.REBAR,
            "tendon":      cls.TENDON,
            "masonry":     cls.MASONRY,
            "timber":      cls.TIMBER,
            "other":       cls.OTHER,
            "rhino":       cls.RHINO,
        }
        return name_map.get(s, cls.NODESIGN)

    @property
    def sap_label(self) -> str:
        """SAP'ın kullandığı etiket."""
        return {
            MatType.STEEL: "Steel",
            MatType.CONCRETE: "Concrete",
            MatType.NODESIGN: "NoDesign",
            MatType.ALUMINUM: "Aluminum",
            MatType.COLDFORMED: "ColdFormed",
            MatType.REBAR: "Rebar",
            MatType.TENDON: "Tendon",
            MatType.MASONRY: "Masonry",
            MatType.TIMBER: "Timber",
            MatType.OTHER: "Other",
            MatType.RHINO: "Rhino",
        }[self]


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

class GridPlane(IntEnum):
    XY = 1
    XZ = 2
    YZ = 3

class SectionCutDefinedBy(str, Enum):
    GROUP = "Group"
    QUAD = "Quad"
    COORDINATE = "Coordinate"


class SectionCutResultType(str, Enum):
    ANALYSIS = "Analysis"
    DESIGN = "Design"

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

class SpectrumSourceType(Enum):
    USER = "USER"
    FROM_FILE = "FROM_FILE"
    TSC_2018 = "TSC_2018"
    EUROCODE = "EUROCODE"
    IBC = "IBC"

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


# SAP2000 frame distributed load direction kodları
SAP_FRAME_LOAD_DIRECTION = {
    1:  LoadDirection.LOCAL_1,
    2:  LoadDirection.LOCAL_2,
    3:  LoadDirection.LOCAL_3,
    4:  LoadDirection.GLOBAL_X,
    5:  LoadDirection.GLOBAL_Y,
    6:  LoadDirection.GLOBAL_Z,
    7:  LoadDirection.GRAVITY,
    8:  LoadDirection.PROJECTED_X,
    9:  LoadDirection.PROJECTED_Y,
    10: LoadDirection.PROJECTED_Z,
}

# Panel ve export için görünen isimler
SAP_DIR_LABELS = {
    "1":  "1  - Local 1",
    "2":  "2  - Local 2",
    "3":  "3  - Local 3",
    "4":  "4  - Global X",
    "5":  "5  - Global Y",
    "6":  "6  - Global Z",
    "7":  "7  - Gravity (GRAV)",
    "8":  "8  - Projected X",
    "9":  "9  - Projected Y",
    "10": "10 - Projected Z",
}

# Kısa kod (s2k export için)
SAP_DIR_CODES = {
    "1": "Local1",  "2": "Local2",  "3": "Local3",
    "4": "GlobalX", "5": "GlobalY", "6": "GlobalZ",
    "7": "Gravity", "8": "ProjX",   "9": "ProjY",  "10": "ProjZ",
}

class DistType(Enum):
    """
    SAP2000 uyumlu dağıtım tipi.
    
    - SAP2000'den gelen "One way" → ONE_WAY_U1 (varsayılan)
    - SAP2000'den gelen "Two way" → TWO_WAY
    - Bizim eklediklerimiz: ONE_WAY_U1, ONE_WAY_U2
      SAP2000 UI'da "One-Way Distribution" + "Span Direction" kombinasyonuna
      karşılık gelir. Enum'da birleştirdik.
    """
    ONE_WAY    = "One way"           # SAP uyumlu geri kalan (U1 gibi davranır)
    TWO_WAY    = "Two way"           # SAP uyumlu
    ONE_WAY_U1 = "One way (U1)"      # yeni — U1 yönünde taşınır
    ONE_WAY_U2 = "One way (U2)"      # yeni — U2 yönünde taşınır

    @classmethod
    def from_input(cls, value):
        """Esnek parse: string/enum/int/None hepsini kabul eder."""
        if value is None:
            return cls.ONE_WAY_U1

        # Zaten enum ise
        if isinstance(value, cls):
            return value

        # Int
        if isinstance(value, int):
            return cls.ONE_WAY_U1 if value == 1 else cls.TWO_WAY

        val_str = str(value).strip().lower()

        # Özel değerler (bizim eklediklerimiz)
        if "u1" in val_str:
            return cls.ONE_WAY_U1
        if "u2" in val_str:
            return cls.ONE_WAY_U2

        # SAP uyumlu iki ana değer
        if "two" in val_str or val_str == "2":
            return cls.TWO_WAY
        if "one" in val_str or val_str == "1":
            return cls.ONE_WAY   # SAP'tan "One way" geldiyse orijinal enum

        # Bilinmeyen → varsayılan
        return cls.ONE_WAY_U1

    @property
    def is_one_way(self) -> bool:
        return self in (DistType.ONE_WAY, DistType.ONE_WAY_U1, DistType.ONE_WAY_U2)

    @property
    def is_two_way(self) -> bool:
        return self == DistType.TWO_WAY

    @property
    def span_direction(self) -> str:
        """'U1' | 'U2' | 'BOTH' — hangi yönde yük akıyor."""
        if self == DistType.ONE_WAY_U2:
            return "U2"
        if self == DistType.ONE_WAY_U1:
            return "U1"
        if self == DistType.ONE_WAY:
            # SAP'tan gelen saf "One way" — U1 gibi davranır
            return "U1"
        return "BOTH"

class PolygonType(Enum):
    GENERIC = auto()
    SURFACE_ONEWAY = auto()
    SURFACE_TWOWAY = auto()
    ZONE = auto()
    SECTION_CUT = auto()
    LOAD_AREA = auto()

ENUM_REGISTRY: dict[str, type[Enum]] = {
    "MatType": MatType,
    "SectionType": SectionType,
    "LinkPropType": LinkPropType,
    "ElementType": ElementType,
    "ObjType": ObjType,
    "LoadType": LoadType,
    "LoadDirection": LoadDirection,
    "SpectrumSourceType": SpectrumSourceType,
    "LoadPatternType": LoadPatternType,
    "LoadCaseType": LoadCaseType,
    "ComboType": ComboType,
    "DistType": DistType,
    "PolygonType": PolygonType
}