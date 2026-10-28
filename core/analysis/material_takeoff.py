# core/analysis/material_takeoff.py
"""
Malzeme metrajı — ElementWeight ve özet tablolar.

Birim sözleşmesi: units.py (kg, mm, N, MPa, kg/mm³).
"""
from dataclasses import dataclass, field

import pandas as pd

from core.units import G_M_S2, KG_PER_TON
from domain.element import Area, Frame
from domain.scene import Scene
from logging_config import CadLogger

logger = CadLogger.get(__name__)


# ============================================================================
@dataclass
class ElementWeight:
    unique_id: int
    element_type: str
    label: str
    material_name: str
    section_name: str

    length: float = 0.0         # mm (kanonik)
    area: float = 0.0           # mm²
    volume: float = 0.0         # mm³
    density: float = 0.0        # kg/mm³
    mass_kg: float = 0.0
    weight_N: float = 0.0       # ← SI, N

    @property
    def mass_ton(self) -> float:
        return self.mass_kg / 1000.0

    @property
    def weight_kN(self) -> float:
        return self.weight_N / 1000.0


@dataclass
class MaterialSummary:
    material_name: str
    total_mass_kg: float = 0.0
    total_weight_kN: float = 0.0
    total_volume: float = 0.0
    element_count: int = 0
    elements: list[ElementWeight] = field(default_factory=list)


@dataclass
class TakeoffResult:
    elements: list[ElementWeight] = field(default_factory=list)
    by_material: dict[str, MaterialSummary] = field(default_factory=dict)
    by_type: dict[str, dict] = field(default_factory=dict)

    @property
    def total_mass_kg(self) -> float:
        return sum(e.mass_kg for e in self.elements)

    @property
    def total_mass_ton(self) -> float:
        return self.total_mass_kg / KG_PER_TON

    @property
    def total_weight_kN(self) -> float:
        return sum(e.weight_kN for e in self.elements)


# ============================================================================
# HESAP
# ============================================================================
def _polygon_area_3d(points) -> float:
    """Newell — mm²."""
    import numpy as np
    pts = np.array(points, dtype=float)
    n = len(pts)
    if n < 3:
        return 0.0
    normal = np.zeros(3)
    for i in range(n):
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        normal[0] += (p1[1] - p2[1]) * (p1[2] + p2[2])
        normal[1] += (p1[2] - p2[2]) * (p1[0] + p2[0])
        normal[2] += (p1[0] - p2[0]) * (p1[1] + p2[1])
    return float(np.linalg.norm(normal) / 2.0)


def _frame_weight(frame: Frame) -> ElementWeight | None:
    sec = getattr(frame, "section", None)
    if sec is None:
        return None
    mat = getattr(sec, "material", None)
    if mat is None:
        return None
    A = (sec.profile_params or {}).get("Area", 0.0)
    if A <= 0:
        return None
    L = frame.get_length()
    if L <= 0:
        return None
    rho = getattr(mat, "density", 0.0)
    if rho <= 0:
        return None

    volume = A * L                     # mm³
    mass_kg = volume * rho             # kg
    weight_N = mass_kg * G_M_S2

    return ElementWeight(
        unique_id=frame.unique_id,
        element_type="Frame",
        label=str(getattr(frame, "label", "")),
        material_name=getattr(mat, "name", "(tanımsız)"),
        section_name=getattr(sec, "name", "(tanımsız)"),
        length=L, area=A, volume=volume, density=rho,
        mass_kg=mass_kg, weight_N=weight_N,
    )


def _area_weight(area: Area) -> ElementWeight | None:
    mat = getattr(area, "material", None)
    if mat is None:
        return None
    th = getattr(area, "thickness", 0.0)
    if th <= 0:
        return None
    geom_A = _polygon_area_3d([(n.x, n.y, n.z) for n in area.nodes])
    if geom_A <= 0:
        return None
    rho = getattr(mat, "density", 0.0)
    if rho <= 0:
        return None

    volume = geom_A * th
    mass_kg = volume * rho
    weight_N = mass_kg * G_M_S2

    return ElementWeight(
        unique_id=area.unique_id,
        element_type="Area",
        label=str(getattr(area, "label", "")),
        material_name=getattr(mat, "name", "(tanımsız)"),
        section_name=str(getattr(area, "section_name", "") or f"t={th:.1f}"),
        length=0.0, area=geom_A, volume=volume, density=rho,
        mass_kg=mass_kg, weight_N=weight_N,
    )


def compute_takeoff(scene: Scene) -> TakeoffResult:
    result = TakeoffResult()

    for f in scene.frames.values():
        w = _frame_weight(f)
        if w:
            result.elements.append(w)

    for a in scene.areas.values():
        w = _area_weight(a)
        if w:
            result.elements.append(w)

    # Özet
    for e in result.elements:
        mat = e.material_name or "(tanımsız)"
        if mat not in result.by_material:
            result.by_material[mat] = MaterialSummary(material_name=mat)
        s = result.by_material[mat]
        s.total_mass_kg += e.mass_kg
        s.total_weight_kN += e.weight_kN
        s.total_volume += e.volume
        s.element_count += 1
        s.elements.append(e)

    for e in result.elements:
        if e.element_type not in result.by_type:
            result.by_type[e.element_type] = {
                "count": 0, "mass_kg": 0.0, "weight_N": 0.0,
            }
        t = result.by_type[e.element_type]
        t["count"] += 1
        t["mass_kg"] += e.mass_kg
        t["weight_N"] += e.weight_N

    logger.info(
        f"[Takeoff] {len(result.elements)} eleman, "
        f"toplam {result.total_mass_kg:.3f} kg "
        f"({result.total_mass_ton:.4f} ton)"
    )
    return result


# ============================================================================
# DATAFRAME ÇIKIŞI
# ============================================================================
def takeoff_to_dataframes(result: TakeoffResult):
    summary_df = pd.DataFrame([{
        "Eleman Sayısı": len(result.elements),
        "Kütle (kg)": round(result.total_mass_kg, 2),
        "Kütle (ton)": round(result.total_mass_ton, 4),
        "Ağırlık (kN)": round(result.total_weight_kN, 2),
    }])

    by_material_data = []
    for name, s in sorted(result.by_material.items()):
        by_material_data.append({
            "Malzeme": name,
            "Eleman": s.element_count,
            "Kütle (kg)": round(s.total_mass_kg, 2),
            "Kütle (ton)": round(s.total_mass_kg / KG_PER_TON, 4),
            "Ağırlık (kN)": round(s.total_weight_kN, 2),
            "Hacim (m³)": round(s.total_volume / 1e9, 6),
        })
    by_material_df = pd.DataFrame(by_material_data)

    elements_data = []
    for e in result.elements:
        elements_data.append({
            "Tip": e.element_type,
            "Label": e.label,
            "Malzeme": e.material_name,
            "Kesit": e.section_name,
            "L (mm)": round(e.length, 1),
            "A (mm²)": round(e.area, 1),
            "V (mm³)": round(e.volume, 0),
            "Kütle (kg)": round(e.mass_kg, 3),
            "Ağırlık (kN)": round(e.weight_kN, 5),
        })
    elements_df = pd.DataFrame(elements_data)

    return summary_df, by_material_df, elements_df