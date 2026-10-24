# core/units.py
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

# ============================================================================
# BOYUTLAR ve TEMEL BİRİMLER
# ============================================================================
class Dimension(Enum):
    LENGTH = "L"
    FORCE = "F"
    MASS = "M"
    TIME = "T"
    STRESS = "F/L²"        # MPa
    MOMENT = "F·L"         # N·mm
    DENSITY = "M/L³"       # kg/mm³
    LINE_LOAD = "F/L"      # N/mm
    AREA_LOAD = "F/L²"     # MPa
    ACCEL = "L/T²"         # mm/s²
    TEMP = "Θ"

# İç modelin kanonik birimleri (ASLA değişmez)
CANONICAL = {
    Dimension.LENGTH:    "mm",
    Dimension.FORCE:     "N",
    Dimension.MASS:      "kg",
    Dimension.TIME:      "s",
    Dimension.STRESS:    "MPa",
    Dimension.MOMENT:    "N·mm",
    Dimension.DENSITY:   "kg/mm³",
    Dimension.LINE_LOAD: "N/mm",
    Dimension.AREA_LOAD: "MPa",
    Dimension.ACCEL:     "mm/s²",
    Dimension.TEMP:      "°C",
}

# ============================================================================
# DÖNÜŞÜM TABLOLARI (tek yer)
# ============================================================================
FORCE_TO_N = {
    "N": 1.0, "kN": 1e3, "kgf": 9.80665, "tonf": 9806.65,
    "lb": 4.4482216152605, "kip": 4448.2216152605,
}
LENGTH_TO_MM = {
    "mm": 1.0, "cm": 10.0, "m": 1000.0,
    "in": 25.4, "ft": 304.8,
}
MASS_TO_KG = {
    "kg": 1.0, "t": 1000.0, "g": 1e-3,
    "lb": 0.45359237, "slug": 14.59390294,
}
TIME_TO_S = {"s": 1.0, "ms": 1e-3}
TEMP_FACTOR = {"C": (1.0, 0.0), "F": (5.0/9.0, -32.0*5.0/9.0)}

G_M_S2 = 9.80665  # m/s²
G_MM_S2 = 9806.65  # mm/s²
KG_PER_TON = 1000.0

# ============================================================================
# UNIT SYSTEM (giriş/çıkış)
# ============================================================================
class UnitSystem(Enum):
    N_MM    = "N, mm, C"
    N_M     = "N, m, C"
    KN_MM   = "kN, mm, C"
    KN_M    = "kN, m, C"
    KGF_MM  = "kgf, mm, C"
    KGF_M   = "kgf, m, C"
    TONF_MM = "tonf, mm, C"
    TONF_M  = "tonf, m, C"
    LB_IN   = "lb, in, F"
    KIP_IN  = "kip, in, F"
    KIP_FT  = "kip, ft, F"

    @classmethod
    def from_sap(cls, s: str) -> "UnitSystem":
        s = (s or "N, mm, C").strip()
        for us in cls:
            if us.value.lower() == s.lower():
                return us
        # Bilinmeyen → varsayılan
        return cls.N_MM

    @property
    def force_unit(self) -> str:  return self.value.split(",")[0].strip()
    @property
    def length_unit(self) -> str: return self.value.split(",")[1].strip()
    @property
    def temp_unit(self) -> str:   return self.value.split(",")[2].strip()


# ============================================================================
# UNIT REGISTRY — tüm dönüşümler
# ============================================================================
class UnitRegistry:
    """
    Tek doğruluk kaynağı. Tüm dönüşümler buradan geçer.

    İç model her zaman kanonik birimlerde (mm, N, MPa, kg, ...).
    UnitRegistry sadece giriş/çıkış dönüşümü yapar.
    """

    # --- Temel dönüşüm ---
    @staticmethod
    def length_to_mm(v: float, unit: str) -> float:
        return float(v) * LENGTH_TO_MM[unit]

    @staticmethod
    def force_to_N(v: float, unit: str) -> float:
        return float(v) * FORCE_TO_N[unit]

    @staticmethod
    def mass_to_kg(v: float, unit: str) -> float:
        return float(v) * MASS_TO_KG[unit]

    @staticmethod
    def stress_to_MPa(v: float, force_unit: str, length_unit: str) -> float:
        f = FORCE_TO_N[force_unit]
        l = LENGTH_TO_MM[length_unit]
        return float(v) * f / (l * l)

    @staticmethod
    def moment_to_Nmm(v: float, force_unit: str, length_unit: str) -> float:
        return float(v) * FORCE_TO_N[force_unit] * LENGTH_TO_MM[length_unit]

    @staticmethod
    def density_to_kg_mm3(v: float, force_unit: str, length_unit: str) -> float:
        """
        SAP2000 UnitMass = F·s²/L⁴ (kütle/uzunluk³).
        N·s²/mm⁴ = kg/mm³.
        → kg/mm³ = v * (force_to_N) / (length_to_mm)^4
        """
        f = FORCE_TO_N[force_unit]
        l = LENGTH_TO_MM[length_unit]
        return float(v) * f / (l ** 4)

    @staticmethod
    def line_load_to_N_mm(v: float, force_unit: str, length_unit: str) -> float:
        return float(v) * FORCE_TO_N[force_unit] / LENGTH_TO_MM[length_unit]

    @staticmethod
    def area_load_to_MPa(v: float, force_unit: str, length_unit: str) -> float:
        return float(v) * FORCE_TO_N[force_unit] / (LENGTH_TO_MM[length_unit] ** 2)

    @staticmethod
    def accel_to_mm_s2(v: float, length_unit: str) -> float:
        return float(v) * LENGTH_TO_MM[length_unit]

    @staticmethod
    def temp_to_C(v: float, unit: str, absolute: bool = False) -> float:
        a, b = TEMP_FACTOR[unit]
        return float(v) * a + (b if absolute else 0.0)

    # --- Vektör/matris dönüşümü (kesit özellikleri için) ---
    @staticmethod
    def length_pow_to_mm_pow(v: float, unit: str, power: int) -> float:
        """mm^power cinsine çevir (alan=2, atalet=4, kesit modülü=3)."""
        return float(v) * (LENGTH_TO_MM[unit] ** power)


# ============================================================================
# UNIT CONVERTER — UnitSystem bağlı, pratik API
# ============================================================================
@dataclass
class UnitConverter:
    """
    Bir UnitSystem'e bağlı converter. S2K import sırasında
    CurrUnits'ten üretilir, tüm handler'lara geçirilir.

    Kullanım:
        uc = UnitConverter(UnitSystem.TONF_M)
        uc.L(3.0)          # 3000.0 mm
        uc.F(1.0)          # 9806.65 N
        uc.E(1.0)          # 9.80665e-3 MPa
        uc.I(1.0)          # 1e12 mm⁴
        uc.density(1.0)    # 9.80665e-12 kg/mm³
    """
    system: UnitSystem = UnitSystem.N_MM

    @classmethod
    def from_sap(cls, s: str) -> "UnitConverter":
        return cls(UnitSystem.from_sap(s))

    @property
    def force(self) -> str:  return self.system.force_unit
    @property
    def length(self) -> str: return self.system.length_unit
    @property
    def temp(self) -> str:   return self.system.temp_unit

    # --- Skaler dönüşümler ---
    def L(self, v):         return UnitRegistry.length_to_mm(v, self.length)
    def L2(self, v):        return UnitRegistry.length_pow_to_mm_pow(v, self.length, 2)
    def L3(self, v):        return UnitRegistry.length_pow_to_mm_pow(v, self.length, 3)
    def L4(self, v):        return UnitRegistry.length_pow_to_mm_pow(v, self.length, 4)
    def F(self, v):         return UnitRegistry.force_to_N(v, self.force)
    def M(self, v):         return UnitRegistry.moment_to_Nmm(v, self.force, self.length)
    def E(self, v):         return UnitRegistry.stress_to_MPa(v, self.force, self.length)
    def w(self, v):         return UnitRegistry.line_load_to_N_mm(v, self.force, self.length)
    def area_w(self, v):    return UnitRegistry.area_load_to_MPa(v, self.force, self.length)
    def density(self, v):   return UnitRegistry.density_to_kg_mm3(v, self.force, self.length)
    def acc(self, v):       return UnitRegistry.accel_to_mm_s2(v, self.length)
    def temp_abs(self, v):  return UnitRegistry.temp_to_C(v, self.temp, absolute=True)
    def temp_diff(self, v): return UnitRegistry.temp_to_C(v, self.temp, absolute=False)

    # --- Kütle (SAP `Mass` = F·s²/L → kg) ---
    def mass(self, v):
        # F·s²/L → kg:  N·s²/mm = kg
        return float(v) * FORCE_TO_N[self.force] / LENGTH_TO_MM[self.length]

    def mmi(self, v):
        # F·L·s² → kg·mm²:  N·mm·s² = kg·mm²
        return float(v) * FORCE_TO_N[self.force] * (LENGTH_TO_MM[self.length] ** 2) / LENGTH_TO_MM[self.length]
        # = v * F * L  (kütle atalet momenti F·L²·s²/L = F·L·s²)


# ============================================================================
# DOĞRULAMA — kesit özellikleri
# ============================================================================
def validate_section_properties(section, *, strict: bool = False) -> list[str]:
    """
    Kesit özelliklerini analitik olarak doğrula.

    Dönen: uyarı/hata listesi (boş = OK).

    Kontroller:
      - Area > 0, I33 > 0, I22 > 0, J > 0
      - Paralel eksen teoremi: I33 ≥ I22 + ... (gevşek sınır)
      - Torsiyon: J ≤ I33 + I22 (genel sınır)
      - Atalet yarıçapı: r33 = sqrt(I33/A), r22 = sqrt(I22/A) — makul aralık
    """
    errs = []
    p = section.profile_params or {}
    A  = float(p.get("Area", 0) or 0)
    I33 = float(p.get("I33", 0) or 0)
    I22 = float(p.get("I22", 0) or 0)
    J  = float(p.get("J", 0) or 0)

    if A <= 0:
        errs.append(f"Section {section.name}: Area={A} <= 0")
    if I33 <= 0:
        errs.append(f"Section {section.name}: I33={I33} <= 0")
    if I22 <= 0:
        errs.append(f"Section {section.name}: I22={I22} <= 0")
    if J <= 0:
        errs.append(f"Section {section.name}: J={J} <= 0")
    if A > 0:
        r33 = (I33 / A) ** 0.5
        r22 = (I22 / A) ** 0.5
        # Atalet yarıçapı kesit boyutunun mertebesinde olmalı (1..500 mm)
        if not (0.5 <= r33 <= 500.0):
            errs.append(f"Section {section.name}: r33={r33:.2f} mm makul değil")
        if not (0.5 <= r22 <= 500.0):
            errs.append(f"Section {section.name}: r22={r22:.2f} mm makul değil")
    # Torsiyon sınırı (kaba): J <= I33 + I22
    if J > (I33 + I22) * 1.5:
        errs.append(f"Section {section.name}: J={J:.2e} > 1.5*(I33+I22)")

    return errs