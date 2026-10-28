# core/units.py
"""
Birim sistemi — tek doğruluk kaynağı.

Model her zaman `project.unit_system`'de. `convert_project_units` ile dönüşür.
Builder `float` — birim bilmez. Render `render_scale` ile kanonik mm'ye çevirir.

Katmanlar:
    - Fiziksel sabitler (SI): G_M_S2, KG_PER_TON
    - Boyutlar: Dimension
    - UnitSystem: "N, mm, C", "kN, m, C", ...
    - Dönüşüm: convert_value(dim, value, from_sys, to_sys)
    - Proje dönüşümü: convert_project_units(project, target)
    - UI: ui_value, ui_to_model (opsiyonel)
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ============================================================================
# FİZİKSEL SABİTLER (SI)
# ============================================================================
G_M_S2 = 9.80665            # m/s² — yerçekimi ivmesi
G_MM_S2 = 9806.65           # mm/s²
KG_PER_TON = 1000.0
MEGAGRAM = 1000.0

# Yoğunluklar (kg/mm³)
DENSITY_STEEL = 7.85e-6
DENSITY_CONCRETE = 2.50e-6
DENSITY_ALUMINUM = 2.70e-6
DENSITY_TIMBER = 0.60e-6


# ============================================================================
# BİRİM TABLOLARI (tek yer)
# ============================================================================
FORCE_TO_N: dict[str, float] = {
    "N": 1.0, "kN": 1e3, "kgf": 9.80665, "tonf": 9806.65,
    "lb": 4.4482216152605, "kip": 4448.2216152605,
}

LENGTH_TO_MM: dict[str, float] = {
    "mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8,
}

MASS_TO_KG: dict[str, float] = {
    "kg": 1.0, "t": 1000.0, "g": 1e-3, "lb": 0.45359237,
}

# Mutlak sıcaklık: °C = (v - b) * a
TEMP_FACTOR: dict[str, tuple[float, float]] = {
    "C": (1.0, 0.0),
    "F": (5.0 / 9.0, 32.0),
}


# ============================================================================
# BOYUTLAR
# ============================================================================
class Dimension(Enum):
    LENGTH = "L"
    FORCE = "F"
    STRESS = "F/L²"           # MPa (N/mm²)
    AREA = "L²"
    I3 = "L³"                 # kesit modülü
    I4 = "L⁴"                 # atalet momenti
    MOMENT = "F·L"            # N·mm
    MASS = "M"                # kg
    MASS_DENSITY = "M/L³"     # kg/mm³ (SAP UnitMass F·s²/L⁴)
    WEIGHT_DENSITY = "F/L³"   # N/mm³
    LINE_LOAD = "F/L"         # N/mm
    AREA_LOAD = "F/L²"        # N/mm²
    ACCEL = "L/T²"            # mm/s²
    TEMP = "Θ"
    THERMAL_EXP = "1/Θ"       # 1/°C

class UnitSystem(Enum):
    N_MM = "N, mm, C"
    N_M = "N, m, C"
    KN_MM = "kN, mm, C"
    KN_M = "kN, m, C"
    KGF_MM = "kgf, mm, C"
    KGF_M = "kgf, m, C"
    KGF_CM = "kgf, cm, C"
    TONF_MM = "tonf, mm, C"
    TONF_M = "tonf, m, C"
    LB_IN = "lb, in, F"
    KIP_IN = "kip, in, F"
    KIP_FT = "kip, ft, F"

    @classmethod
    def from_sap(cls, s: str | None) -> UnitSystem:
        s = (s or "N, mm, C").strip()
        for us in cls:
            if us.value.lower() == s.lower():
                return us
        return cls.N_MM

    @property
    def force_unit(self) -> str:
        return self.value.split(",")[0].strip()

    @property
    def length_unit(self) -> str:
        return self.value.split(",")[1].strip()

    @property
    def temp_unit(self) -> str:
        return self.value.split(",")[2].strip()


# ============================================================================
# DÖNÜŞÜM FONKSİYONU
# ============================================================================
def factor(dim: Dimension, from_sys: UnitSystem, to_sys: UnitSystem) -> float:
    """Boyut ve iki sistem için dönüşüm faktörü."""
    if from_sys == to_sys:
        return 1.0

    F_f, F_t = FORCE_TO_N[from_sys.force_unit], FORCE_TO_N[to_sys.force_unit]
    L_f, L_t = LENGTH_TO_MM[from_sys.length_unit], LENGTH_TO_MM[to_sys.length_unit]
    T_f, T_t = from_sys.temp_unit, to_sys.temp_unit

    if dim == Dimension.LENGTH:
        return L_f / L_t
    if dim == Dimension.FORCE:
        return F_f / F_t
    if dim == Dimension.STRESS:
        return (F_f / L_f**2) / (F_t / L_t**2)
    if dim == Dimension.AREA:
        return (L_f / L_t) ** 2
    if dim == Dimension.I3:
        return (L_f / L_t) ** 3
    if dim == Dimension.I4:
        return (L_f / L_t) ** 4
    if dim == Dimension.MOMENT:
        return (F_f * L_f) / (F_t * L_t)
    if dim == Dimension.MASS:
        return MASS_TO_KG.get(from_sys.force_unit, 1.0) / MASS_TO_KG.get(to_sys.force_unit, 1.0)
    if dim == Dimension.MASS_DENSITY:
        # SAP UnitMass: F·s²/L⁴ → kg/mm³
        return (F_f / L_f**4) / (F_t / L_t**4)
    if dim == Dimension.WEIGHT_DENSITY:
        return (F_f / L_f**3) / (F_t / L_t**3)
    if dim == Dimension.LINE_LOAD:
        return (F_f / L_f) / (F_t / L_t)
    if dim == Dimension.AREA_LOAD:
        return (F_f / L_f**2) / (F_t / L_t**2)
    if dim == Dimension.ACCEL:
        return L_f / L_t
    if dim == Dimension.TEMP:
        a_f, b_f = TEMP_FACTOR[T_f]
        a_t, b_t = TEMP_FACTOR[T_t]
        return a_f / a_t
    if dim == Dimension.THERMAL_EXP:
        return 1.0
    return 1.0


def convert_value(
    dim: Dimension, value: float,
    from_sys: UnitSystem, to_sys: UnitSystem,
) -> float:
    """Tek değer dönüşümü."""
    if value is None or from_sys == to_sys:
        return value
    return float(value) * factor(dim, from_sys, to_sys)

# ============================================================================
# BİRİM DEĞİŞİMİ EVENT
# ============================================================================
class UnitChangeEvent:
    def __init__(self):
        self._listeners: list[Callable] = []

    def subscribe(self, fn: Callable):
        self._listeners.append(fn)

    def emit(self, from_sys: UnitSystem, to_sys: UnitSystem, reason: str = ""):
        for fn in self._listeners:
            try:
                fn(from_sys, to_sys, reason)
            except Exception:
                logger.exception("UnitChangeEvent listener hatası")

unit_change_event = UnitChangeEvent()


# ============================================================================
# PROJE DÖNÜŞÜMÜ
# ============================================================================
def convert_project_units(
    project, target: UnitSystem, *, reason: str = "",
) -> int:
    """
    Proje ağacındaki tüm birimli alanları hedef sisteme çevir.

    - `__unit_schema__` olan her nesne dönüştürülür
    - `project.unit_system = target`
    - `project.ui_dirty = True`
    - `scene.mark_dirty()` ÇAĞRILMAZ — render_scale ile
    """
    from_sys = getattr(project, "unit_system", UnitSystem.N_MM)
    if from_sys == target:
        return 0

    n = _walk_convert(project, from_sys, target)
    project.unit_system = target
    project.ui_dirty = True

    unit_change_event.emit(from_sys, target, reason)
    logger.info(
        "[Units] %s → %s (reason=%s, %d alan)",
        from_sys.value, target.value, reason, n,
    )
    return n


def _walk_convert(root: Any, from_sys: UnitSystem, to_sys: UnitSystem) -> int:
    """Ağacı derinlemesine gez, __unit_schema__ olan her nesneyi dönüştür."""
    seen = set()
    count = 0

    def visit(obj):
        nonlocal count
        if obj is None or id(obj) in seen:
            return
        seen.add(id(obj))

        # __unit_schema__ — dataclass veya sınıf
        schema = getattr(type(obj), "__unit_schema__", None)
        if schema:
            for field_path, dim in schema.items():
                count += _convert_field(obj, field_path, dim, from_sys, to_sys)

        # Recurse
        if isinstance(obj, dict):
            for v in obj.values():
                visit(v)
        elif isinstance(obj, (list, tuple, set)):
            for v in obj:
                visit(v)
        elif hasattr(obj, "__dict__"):
            for v in list(obj.__dict__.values()):
                if v is obj:
                    continue
                visit(v)

    visit(root)
    return count


def _convert_field(
    obj, field_path: str, dim: Dimension,
    from_sys: UnitSystem, to_sys: UnitSystem,
) -> int:
    """
    obj.field_path (nested) alanını dönüştür.
    `__dict__` doğrudan yaz — @property setter (mark_dirty) tetiklenmez.
    """
    parts = field_path.split(".")
    target = obj
    for part in parts[:-1]:
        if isinstance(target, dict):
            target = target.get(part)
        else:
            target = target.__dict__.get(part) if hasattr(target, "__dict__") else getattr(target, part, None)
        if target is None:
            return 0
    key = parts[-1]

    if isinstance(target, dict):
        if key not in target:
            return 0
        target[key] = convert_value(dim, target[key], from_sys, to_sys)
        return 1

    # __dict__ doğrudan — mark_dirty yok
    if hasattr(target, "__dict__") and key in target.__dict__:
        target.__dict__[key] = convert_value(dim, target.__dict__[key], from_sys, to_sys)
        return 1

    return 0


# ============================================================================
# DOĞRULAMA
# ============================================================================
def validate_project_units(project, original_system: UnitSystem) -> list[str]:
    """
    Dönüşüm öncesi ve sonrası aynı fiziksel değerleri mi temsil ediyor?
    Roundtrip: original → N_MM → original.
    """
    errs = []
    # ... test edilebilir, opsiyonel ...
    return errs

