# core/analysis/material_takeoff.py
"""
Malzeme metrajı — element ağırlıkları ve özet tablo.

Bağımsız modül: UI'dan çağrılır, sadece Scene alır.
"""
from dataclasses import dataclass, field
from typing import Dict, List

import pandas as pd

from logging_config import CadLogger
logger = CadLogger.get(__name__)

from domain.scene import Scene
from domain.element import Frame, Area, Link


# ============================================================
# SONUÇ SINIFLARI
# ============================================================

@dataclass
class ElementWeight:
    """Tek bir elemanın ağırlık bilgisi."""
    element_id: str
    element_type: str       # "Frame" | "Area" | "Link"
    label: str
    material_name: str
    section_name: str
    
    # Geometri
    length: float = 0.0     # mm
    area: float = 0.0       # mm² (kesit alanı)
    volume: float = 0.0     # mm³
    
    # Ağırlık
    density: float = 0.0    # t/mm³
    mass: float = 0.0       # ton
    weight: float = 0.0     # kN
    
    @property
    def mass_kg(self) -> float:
        return self.mass * 1000.0


@dataclass
class MaterialSummary:
    """Bir malzeme için özet."""
    material_name: str
    total_mass: float = 0.0       # ton
    total_weight: float = 0.0     # kN
    total_volume: float = 0.0     # mm³
    element_count: int = 0
    elements: List[ElementWeight] = field(default_factory=list)
    
    @property
    def total_mass_kg(self) -> float:
        return self.total_mass * 1000.0


@dataclass
class TakeoffResult:
    """Metraj sonucu."""
    elements: List[ElementWeight] = field(default_factory=list)
    by_material: Dict[str, MaterialSummary] = field(default_factory=dict)
    by_type: Dict[str, Dict] = field(default_factory=dict)
    
    @property
    def total_mass(self) -> float:
        return sum(e.mass for e in self.elements)
    
    @property
    def total_weight(self) -> float:
        return sum(e.weight for e in self.elements)


# ============================================================
# HESAP
# ============================================================

G_MM_S2 = 9810.0   # mm/s²


def compute_takeoff(scene: Scene) -> TakeoffResult:
    """
    Scene'deki tüm elemanların ağırlığını hesapla.
    
    Frame + Area + Link desteği.
    """
    result = TakeoffResult()
    
    # Frame'ler
    for frame in scene.frames.values():
        w = _frame_weight(frame)
        if w:
            result.elements.append(w)
    
    # Area'lar
    for area in scene.areas.values():
        w = _area_weight(area)
        if w:
            result.elements.append(w)
    
    # Link'ler (şimdilik atla — propname'den ağırlık çıkmaz)
    # for link in scene.links.values():
    #     ...
    
    # Malzeme bazlı özet
    for e in result.elements:
        mat_name = e.material_name or "(tanımsız)"
        
        if mat_name not in result.by_material:
            result.by_material[mat_name] = MaterialSummary(material_name=mat_name)
        
        s = result.by_material[mat_name]
        s.total_mass += e.mass
        s.total_weight += e.weight
        s.total_volume += e.volume
        s.element_count += 1
        s.elements.append(e)
    
    # Tip bazlı özet
    for e in result.elements:
        if e.element_type not in result.by_type:
            result.by_type[e.element_type] = {
                'count': 0, 'mass': 0.0, 'weight': 0.0,
            }
        t = result.by_type[e.element_type]
        t['count'] += 1
        t['mass'] += e.mass
        t['weight'] += e.weight
    
    logger.info(
        f"[Takeoff] {len(result.elements)} eleman, "
        f"toplam {result.total_mass:.3f} ton"
    )
    
    return result


# ============================================================
# ELEMAN BAZLI HESAP
# ============================================================

def _frame_weight(frame: Frame) -> ElementWeight:
    """Frame ağırlığı."""
    if not frame.section:
        return None
    
    mat = frame.section.material
    if not mat:
        return None
    
    # Kesit alanı
    A = frame.section.profile_params.get('Area', 0.0)
    if A <= 0:
        return None
    
    L = frame.get_length()
    if L <= 0:
        return None
    
    rho = mat.density  # t/mm³
    
    volume = A * L         # mm³
    mass = volume * rho    # t
    weight = mass * G_MM_S2 / 1e6   # kN (t·mm/s² → N × 1e-3 → kN)
    
    return ElementWeight(
        element_id=frame.element_id,
        element_type="Frame",
        label=frame.label,
        material_name=mat.name,
        section_name=frame.section.name,
        length=L,
        area=A,
        volume=volume,
        density=rho,
        mass=mass,
        weight=weight,
    )


def _area_weight(area: Area) -> ElementWeight:
    """Area ağırlığı (thickness × alan)."""
    mat = None
    # Area'nın malzemesi — Area'da material attribute'u yok
    # thickness ve boyutlardan hesap gerekir
    # Şimdilik: sadece thickness var, material yok → geçici
    # İleride: area.section veya benzeri eklenirse
    
    # Alan hesabı — poligon alanı (shoelace)
    if len(area.nodes) < 3:
        return None
    
    area_mm2 = _polygon_area_3d([(n.x, n.y, n.z) for n in area.nodes])
    
    thickness = area.thickness
    volume = area_mm2 * thickness   # mm³
    
    # Malzeme bilgisi yok → beton varsayımı (2.5 t/m³ = 2.5e-9 t/mm³)
    rho = 2.5e-9
    mat_name = "(beton varsayımı)"
    
    mass = volume * rho
    weight = mass * G_MM_S2 / 1e6
    
    return ElementWeight(
        element_id=area.element_id,
        element_type="Area",
        label=area.label,
        material_name=mat_name,
        section_name=f"t={thickness}",
        length=0.0,
        area=area_mm2,
        volume=volume,
        density=rho,
        mass=mass,
        weight=weight,
    )


def _polygon_area_3d(points) -> float:
    """3D poligon alanı (Newell metodu)."""
    import numpy as np
    pts = np.array(points, dtype=float)
    n = len(pts)
    if n < 3:
        return 0.0
    
    # Newell normali
    normal = np.zeros(3)
    for i in range(n):
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        normal[0] += (p1[1] - p2[1]) * (p1[2] + p2[2])
        normal[1] += (p1[2] - p2[2]) * (p1[0] + p2[0])
        normal[2] += (p1[0] - p2[0]) * (p1[1] + p2[1])
    
    area = np.linalg.norm(normal) / 2.0
    return float(area)


def takeoff_to_dataframes(result: TakeoffResult):
    """
    Takeoff sonucunu DataFrame'lere çevir.
    
    Returns
    -------
    (summary_df, elements_df, by_material_df) : tuple
    """
    # 1. Genel özet
    summary_data = [{
        "Toplam Eleman": len(result.elements),
        "Toplam Kütle (ton)": round(result.total_mass, 3),
        "Toplam Kütle (kg)": round(result.total_mass * 1000, 1),
        "Toplam Ağırlık (kN)": round(result.total_weight, 2),
    }]
    summary_df = pd.DataFrame(summary_data)
    
    # 2. Malzeme bazlı özet
    by_material_data = []
    for mat_name, s in sorted(result.by_material.items()):
        by_material_data.append({
            "Malzeme": mat_name,
            "Eleman Sayısı": s.element_count,
            "Kütle (ton)": round(s.total_mass, 4),
            "Kütle (kg)": round(s.total_mass * 1000, 1),
            "Ağırlık (kN)": round(s.total_weight, 2),
            "Hacim (m³)": round(s.total_volume / 1e9, 4),
        })
    by_material_df = pd.DataFrame(by_material_data)
    
    # 3. Eleman detayları
    elements_data = []
    for e in result.elements:
        elements_data.append({
            "Tip": e.element_type,
            "Label": e.label,
            "Malzeme": e.material_name,
            "Kesit": e.section_name,
            "Uzunluk (mm)": round(e.length, 1),
            "Alan (mm²)": round(e.area, 1),
            "Hacim (mm³)": round(e.volume, 0),
            "Kütle (kg)": round(e.mass * 1000, 2),
            "Ağırlık (kN)": round(e.weight, 4),
        })
    elements_df = pd.DataFrame(elements_data)
    
    return summary_df, by_material_df, elements_df