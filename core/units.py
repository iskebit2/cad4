# core/units.py
"""
Birim sistemi — tek doğruluk kaynağı.

Model her zaman `project.unit_system`'de. `convert_project_units` ile dönüşür.
Builder `float` — birim bilmez. Render `render_scale` ile kanonik mm'ye çevirir.

Import stratejisi:
    S2K import sırasında DEĞER DEĞİŞTİRİLMEZ. `project.unit_system` S2K'nın
    CurrUnits'ine ayarlanır; dönüşüm gerektiğinde (solver öncesi, UI birim
    değişimi) `convert_project_units` ayrıca çağrılır.
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
G_M_S2 = 9.80665
G_MM_S2 = 9806.65
KG_PER_TON = 1000.0
MEGAGRAM = 1000.0

DENSITY_STEEL = 7.85e-6
DENSITY_CONCRETE = 2.50e-6
DENSITY_ALUMINUM = 2.70e-6
DENSITY_TIMBER = 0.60e-6


# ============================================================================
# BİRİM TABLOLARI
# ============================================================================
FORCE_TO_N: dict[str, float] = {
    "N": 1.0, "kN": 1e3, "kgf": 9.80665, "tonf": 9806.65,
    "lb": 4.4482216152605, "kip": 4448.2216152605,
}

LENGTH_TO_MM: dict[str, float] = {
    "mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8,
}

MASS_TO_KG: dict[str, float] = {
    "kg": 1.0, "t": 1000.0, "tonf": 1000.0, "ton": 1000.0,
    "g": 1e-3, "lb": 0.45359237, "kip": 453.59237,
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
    STRESS = "F/L²"
    AREA = "L²"
    I3 = "L³"
    I4 = "L⁴"
    MOMENT = "F·L"
    MASS = "M"
    MASS_INERTIA = "M·L²"
    MASS_DENSITY = "M/L³"
    WEIGHT_DENSITY = "F/L³"
    LINE_LOAD = "F/L"
    AREA_LOAD = "F/L²"
    ACCEL = "L/T²"
    TEMP = "Θ"
    THERMAL_EXP = "1/Θ"


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
        """SAP2000 CurrUnits string → UnitSystem.

        v25:  "Tonf, m, C"
        v10:  "Ton. m. C"   (nokta + boşluk ayraç; "Ton" = "tonf")
        """
        raw = (s or "N, mm, C").strip()
        if not raw:
            return cls.N_MM

        low = raw.lower()
        for us in cls:
            if us.value.lower() == low:
                return us

        normalized = cls._normalize_v10(raw)
        low_n = normalized.lower()
        for us in cls:
            if us.value.lower() == low_n:
                return us

        parts = [p.strip().lower() for p in normalized.split(",") if p.strip()]
        if len(parts) >= 2:
            force = parts[0]
            length = parts[1]
            if force == "ton":
                force = "tonf"
            for us in cls:
                if us.force_unit.lower() == force and us.length_unit.lower() == length:
                    return us

        logger.debug("[Units] Tanınmayan CurrUnits=%r → N_MM", raw)
        return cls.N_MM

    @staticmethod
    def _normalize_v10(raw: str) -> str:
        """v10 `Ton. m. C` → `Tonf, m, C`."""
        s = raw.strip()
        if "." in s and "," not in s:
            s = ", ".join(p.strip() for p in s.split(".") if p.strip())
        tokens = [t.strip() for t in s.split(",")]
        out = []
        for t in tokens:
            out.append("tonf" if t.lower() == "ton" else t)
        return ", ".join(out)

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
    """Boyut ve iki sistem için dönüşüm faktörü (F^a · L^b modeli)."""
    if from_sys == to_sys:
        return 1.0

    F_f = FORCE_TO_N[from_sys.force_unit]
    F_t = FORCE_TO_N[to_sys.force_unit]
    L_f = LENGTH_TO_MM[from_sys.length_unit]
    L_t = LENGTH_TO_MM[to_sys.length_unit]

    if dim == Dimension.TEMP:
        a_f, _ = TEMP_FACTOR[from_sys.temp_unit]
        a_t, _ = TEMP_FACTOR[to_sys.temp_unit]
        return a_f / a_t
    if dim == Dimension.THERMAL_EXP:
        return 1.0

    force_ratio = F_f / F_t
    length_ratio = L_f / L_t

    if dim == Dimension.LENGTH or dim == Dimension.ACCEL:
        return length_ratio
    if dim == Dimension.FORCE:
        return force_ratio
    if dim == Dimension.STRESS or dim == Dimension.AREA_LOAD:
        return force_ratio / length_ratio**2
    if dim == Dimension.AREA:
        return length_ratio**2
    if dim == Dimension.I3:
        return length_ratio**3
    if dim == Dimension.I4:
        return length_ratio**4
    if dim == Dimension.MOMENT or dim == Dimension.MASS_INERTIA:
        return force_ratio * length_ratio
    if dim == Dimension.MASS or dim == Dimension.LINE_LOAD:
        return force_ratio / length_ratio
    if dim == Dimension.MASS_DENSITY:
        return force_ratio / length_ratio**4
    if dim == Dimension.WEIGHT_DENSITY:
        return force_ratio / length_ratio**3

    logger.debug("[Units] Bilinmeyen Dimension: %r → factor=1.0", dim)
    return 1.0


def convert_value(dim, value, from_sys, to_sys):
    if dim is None or value is None or from_sys == to_sys:
        return value
    if isinstance(value, (tuple, list)):
        return type(value)(convert_value(dim, v, from_sys, to_sys) for v in value)
    try:
        return float(value) * factor(dim, from_sys, to_sys)
    except (TypeError, ValueError):
        logger.debug("[Units] convert_value(%s, %r) → dönüştürülemedi", dim, value)
        return value


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

def _convert_grid_lines(project, from_sys, to_sys) -> int:
    count = 0
    for gl in getattr(project, "grid_lines", []):
        if isinstance(gl, dict) and "ordinate" in gl and gl["ordinate"] is not None:
            gl["ordinate"] = convert_value(
                Dimension.LENGTH, gl["ordinate"], from_sys, to_sys,
            )
            count += 1
    return count

# ============================================================================
# PROJE DÖNÜŞÜMÜ
# ============================================================================
def convert_project_units(
    project, target: UnitSystem, *, reason: str = "",
) -> int:
    """Proje ağacındaki tüm birimli alanları hedef sisteme çevir."""
    from_sys = getattr(project, "unit_system", UnitSystem.N_MM)
    if from_sys == target:
        return 0

    n = _walk_convert(project, from_sys, target)
    n += _convert_grid_lines(project, from_sys, target)
    project.unit_system = target
    project.ui_dirty = True

    unit_change_event.emit(from_sys, target, reason)
    logger.info(
        "[Units] %s → %s (reason=%s, %d alan)",
        from_sys.value, target.value, reason, n,
    )
    return n


def _collect_schema(cls) -> dict[str, Dimension | None]:
    """MRO boyunca `__unit_schema__`'ları birleştir (alt sınıf kazanır)."""
    merged: dict[str, Dimension | None] = {}
    for c in reversed(cls.__mro__):
        sch = getattr(c, "__unit_schema__", None)
        if sch:
            merged.update(sch)
    return merged


def _walk_convert(root: Any, from_sys: UnitSystem, to_sys: UnitSystem) -> int:
    """Ağacı derinlemesine gez, __unit_schema__ olan her nesneyi dönüştür."""
    seen: set[int] = set()
    count = 0

    def visit(obj):
        nonlocal count
        if obj is None:
            return
        if isinstance(obj, (int, float, str, bool, bytes)):
            return
        oid = id(obj)
        if oid in seen:
            return
        seen.add(oid)

        schema = _collect_schema(type(obj))
        if schema:
            for field_path, dim in schema.items():
                count += _convert_field(obj, field_path, dim, from_sys, to_sys)

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
    obj, field_path: str, dim: Dimension | None,
    from_sys: UnitSystem, to_sys: UnitSystem,
) -> int:
    """obj.field_path (nested, a.b.c) alanını dönüştür.

    __dict__ doğrudan yaz → @property setter (mark_dirty) tetiklenmez.
    dict path'i desteklenir. Tuple/list değerler convert_value'da ele alınır.
    """
    if dim is None:
        return 0

    parts = field_path.split(".")
    target = obj
    for part in parts[:-1]:
        try:
            if isinstance(target, dict):
                target = target.get(part)
            elif hasattr(target, "__dict__"):
                target = target.__dict__.get(part)
            else:
                target = getattr(target, part, None)
        except Exception:
            return 0
        if target is None:
            return 0

    key = parts[-1]
    try:
        if isinstance(target, dict):
            if key not in target:
                return 0
            target[key] = convert_value(dim, target[key], from_sys, to_sys)
            return 1
        if hasattr(target, "__dict__") and key in target.__dict__:
            target.__dict__[key] = convert_value(
                dim, target.__dict__[key], from_sys, to_sys,
            )
            return 1
    except Exception as e:
        logger.debug("[Units] %s dönüştürülemedi: %s", field_path, e)
    return 0


# ============================================================================
# DOĞRULAMA (opsiyonel)
# ============================================================================
def validate_project_units(project, original_system: UnitSystem) -> list[str]:
    """Roundtrip doğrulaması için stub."""
    return []