# data/unit_enums.py


from dataclasses import dataclass
from enum import IntEnum
from typing import Dict

# ---------------------------------------------------------------------------
# BİRİM TANIMLARI
# ---------------------------------------------------------------------------
# SAP2000 CurrUnits kodlaması: 1..16
# Kuvvet birimleri: lb, kip, N, kN, kgf, tonf
# Uzunluk birimleri: in, ft, mm, cm, m
# Sıcaklık: C veya F (SAP2000 varsayılan C)
#
# Dönüşüm faktörleri:
#   1 in  = 25.4 mm
#   1 ft  = 304.8 mm
#   1 cm  = 10 mm
#   1 m   = 1000 mm
#   1 lb  = 4.4482216152605 N
#   1 kip = 4448.2216152605 N
#   1 kgf = 9.80665 N
#   1 tonf= 9806.65 N
#   1 N   = 1 N
#   1 kN  = 1000 N
#
# Kütle: F = m * g, g = 9.80665 m/s² = 9806.65 mm/s²
#   m [kg] = F [N] / 9.80665
#   m [kg] = F [tonf] * 1000 / 9.80665  (tonf → N → kg)
# SAP2000'de "UnitMass" genellikle kuvvet birimi / (uzunluk birimi)²
# veya kütle/uzunluk³ olarak verilir; import'ta dikkat.
# ---------------------------------------------------------------------------

# Kuvvet → N
FORCE_TO_N: Dict[str, float] = {
    "N":    1.0,
    "kN":   1000.0,
    "kgf":  9.80665,
    "kg":   9.80665,      # alias
    "tonf": 9806.65,
    "ton":  9806.65,      # SAP "Ton" = tonf
    "lb":   4.4482216152605,
    "lbf":  4.4482216152605,
    "kip":  4448.2216152605,
    "kipf": 4448.2216152605,
}

# Uzunluk → mm
LENGTH_TO_MM: Dict[str, float] = {
    "mm": 1.0,
    "cm": 10.0,
    "m":  1000.0,
    "in": 25.4,
    "ft": 304.8,
}

# Sıcaklık birimi
TEMP_UNITS = {"C", "F"}

# Yerçekimi ivmesi (mm/s²)
G_MM_S2 = 9806.65


@dataclass(frozen=True)
class UnitDef:
    """Bir SAP2000 birim sisteminin tam tanımı."""
    force: str
    length: str
    temperature: str = "C"

    @property
    def force_to_N(self) -> float:
        return FORCE_TO_N[self.force]

    @property
    def length_to_mm(self) -> float:
        return LENGTH_TO_MM[self.length]

    @property
    def moment_to_Nmm(self) -> float:
        """Moment: F * L → N * mm."""
        return self.force_to_N * self.length_to_mm

    @property
    def stress_to_MPa(self) -> float:
        """Gerilme: F / L² → N / mm² (MPa)."""
        return self.force_to_N / (self.length_to_mm ** 2)

    @property
    def line_load_to_N_per_mm(self) -> float:
        """Yayılı yük: F / L → N / mm."""
        return self.force_to_N / self.length_to_mm

    @property
    def area_load_to_N_per_mm2(self) -> float:
        """Alan yükü: F / L² → N / mm² (MPa)."""
        return self.force_to_N / (self.length_to_mm ** 2)

    @property
    def density_to_kg_per_mm3(self) -> float:
        """Yoğunluk: F / L³ → kg / mm³.
        SAP2000 'UnitMass' genellikle F/L³ olarak verir;
        kg/mm³ = (F_to_N / g_m_s2) / (L_to_mm)³ * 1000³ ... dikkat!
        Aşağıdaki formül: (F_to_N / 9.80665) kg / (L_to_mm)³ mm³.
        """
        return (self.force_to_N / 9.80665) / (self.length_to_mm ** 3)

    @property
    def mass_to_kg(self) -> float:
        """Kütle: F → kg. SAP2000 'Mass' genellikle F/g olarak verir."""
        return self.force_to_N / 9.80665

    def temp_abs_to_C(self, v: float) -> float:
        """Mutlak sıcaklık → °C."""
        if self.temperature == "F":
            return (v - 32.0) * 5.0 / 9.0
        return v

    def temp_diff_to_C(self, v: float) -> float:
        """Sıcaklık farkı → °C farkı."""
        if self.temperature == "F":
            return v * 5.0 / 9.0
        return v


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
    def unit_def(self) -> UnitDef:
        return UNIT_DEFINITIONS_MAP[self]

    @property
    def force_unit(self) -> str:
        return self.unit_def.force

    @property
    def length_unit(self) -> str:
        return self.unit_def.length

    @property
    def temperature_unit(self) -> str:
        return self.unit_def.temperature


UNIT_DEFINITIONS_MAP: Dict[UnitSystem, UnitDef] = {
    UnitSystem.LB_IN:  UnitDef("lb",  "in"),
    UnitSystem.LB_FT:  UnitDef("lb",  "ft"),
    UnitSystem.KIP_IN: UnitDef("kip", "in"),
    UnitSystem.KIP_FT: UnitDef("kip", "ft"),
    UnitSystem.KN_MM:  UnitDef("kN",  "mm"),
    UnitSystem.KN_M:   UnitDef("kN",  "m"),
    UnitSystem.KGF_MM: UnitDef("kgf", "mm"),
    UnitSystem.KGF_M:  UnitDef("kgf", "m"),
    UnitSystem.N_MM:   UnitDef("N",   "mm"),
    UnitSystem.N_M:    UnitDef("N",   "m"),
    UnitSystem.TON_MM: UnitDef("tonf","mm"),
    UnitSystem.TON_M:  UnitDef("tonf","m"),
    UnitSystem.KN_CM:  UnitDef("kN",  "cm"),
    UnitSystem.KGF_CM: UnitDef("kgf", "cm"),
    UnitSystem.N_CM:   UnitDef("N",   "cm"),
    UnitSystem.TON_CM: UnitDef("tonf","cm"),
}


def unit_system_from_sap_string(s: str) -> UnitSystem:
    """SAP2000 'CurrUnits' string'ini UnitSystem'e çevir.
    Örnek: 'N, mm, C' → UnitSystem.N_MM
           'Tonf, m, C' → UnitSystem.TON_M
           'Kip, in, F' → UnitSystem.KIP_IN
    """
    if not s:
        return UnitSystem.N_MM
    parts = [p.strip() for p in s.split(",")]
    force = parts[0].lower() if len(parts) > 0 else "n"
    length = parts[1].lower() if len(parts) > 1 else "mm"
    temp = parts[2].upper() if len(parts) > 2 else "C"

    # Alias'lar
    force_aliases = {
        "n": "N", "kn": "kN", "kgf": "kgf", "kg": "kgf",
        "tonf": "tonf", "ton": "tonf", "tf": "tonf",
        "lb": "lb", "lbf": "lb", "kip": "kip", "kipf": "kip",
    }
    length_aliases = {
        "mm": "mm", "cm": "cm", "m": "m", "in": "in", "ft": "ft",
    }
    force_norm = force_aliases.get(force, "N")
    length_norm = length_aliases.get(length, "mm")

    mapping = {
        ("lb",  "in"): UnitSystem.LB_IN,
        ("lb",  "ft"): UnitSystem.LB_FT,
        ("kip", "in"): UnitSystem.KIP_IN,
        ("kip", "ft"): UnitSystem.KIP_FT,
        ("kN",  "mm"): UnitSystem.KN_MM,
        ("kN",  "m"):  UnitSystem.KN_M,
        ("kgf", "mm"): UnitSystem.KGF_MM,
        ("kgf", "m"):  UnitSystem.KGF_M,
        ("N",   "mm"): UnitSystem.N_MM,
        ("N",   "m"):  UnitSystem.N_M,
        ("tonf","mm"): UnitSystem.TON_MM,
        ("tonf","m"):  UnitSystem.TON_M,
        ("kN",  "cm"): UnitSystem.KN_CM,
        ("kgf", "cm"): UnitSystem.KGF_CM,
        ("N",   "cm"): UnitSystem.N_CM,
        ("tonf","cm"): UnitSystem.TON_CM,
    }
    sys_enum = mapping.get((force_norm, length_norm), UnitSystem.N_MM)
    # Sıcaklık F ise UnitDef'i override etmek gerekir; ama enum immutable.
    # Pratik çözüm: UnitConverter içinde temp_unit'i ayrıca sakla.
    return sys_enum