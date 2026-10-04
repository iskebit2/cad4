# core/analysis/mass_source.py
"""
Deprem kütlesi — sabit formül.

    m = G + n × Q

G = self_weight + Dead pattern yükleri
Q = Live pattern yükleri

MASS SOURCE tablosu import edilir ama hesaba KARŞILMAZ.
n parametresi ProjectInformation'dan gelir.
"""
from dataclasses import dataclass, field
from typing import Dict, List

from logging_config import CadLogger
logger = CadLogger.get(__name__)

from domain.scene import Scene
from domain.definition import LoadDirection


# ============================================================
# SABİTLER
# ============================================================

G_MM_S2 = 9810.0   # mm/s²


# Kütleye katılan düşey yönler
VERTICAL_DIRECTIONS = {
    LoadDirection.GRAVITY,
    LoadDirection.GLOBAL_Z,
    LoadDirection.PROJECTED_Z,
    LoadDirection.LOCAL_3,
}


def is_vertical(direction) -> bool:
    """Yük düşey mi?"""
    return direction in VERTICAL_DIRECTIONS


def get_pattern_kind(design_type: str) -> str:
    """DesignType → 'dead' | 'live' | 'other'."""
    t = str(design_type).upper().strip()
    if "DEAD" in t:
        return "dead"
    if "LIVE" in t:
        return "live"
    return "other"


# ============================================================
# SONUÇ
# ============================================================

@dataclass
class MassBreakdown:
    """Kütle hesabı detayı."""

    self_weight: float = 0.0
    dead_loads: float = 0.0
    live_loads: float = 0.0

    n: float = 0.3

    dead_patterns: Dict[str, float] = field(default_factory=dict)
    live_patterns: Dict[str, float] = field(default_factory=dict)

    @property
    def G(self) -> float:
        """Toplam sabit yük kütlesi."""
        return self.self_weight + self.dead_loads

    @property
    def Q(self) -> float:
        """Toplam hareketli yük kütlesi."""
        return self.live_loads

    @property
    def total(self) -> float:
        """m = G + n·Q"""
        return self.G + self.n * self.Q

    @property
    def total_kg(self) -> float:
        return self.total * 1000.0

    @property
    def total_weight_kn(self) -> float:
        return self.total * G_MM_S2 / 1e6

    def __inspector_tree__(self):
        return {
            "G — Dead Mass": {
                "Self Weight": f"{self.self_weight:.3f} ton",
                "Dead Loads": f"{self.dead_loads:.3f} ton",
                "G": f"{self.G:.3f} ton",
            },

            "Q — Live Mass": {
                "Live Loads": f"{self.live_loads:.3f} ton",
                "Q": f"{self.Q:.3f} ton",
                "n": f"{self.n:.2f}",
            },

            "Seismic Mass": {
                "m = G + n·Q": f"{self.total:.3f} ton",
                "Mass": f"{self.total_kg:.1f} kg",
                "Weight": f"{self.total_weight_kn:.3f} kN",
            },

            "Load Patterns": {
                "Dead": self.dead_patterns,
                "Live": self.live_patterns,
            },
        }


# ============================================================
# ANA HESAP
# ============================================================

def compute_seismic_mass(scene: Scene, n: float = 0.3) -> MassBreakdown:
    """
    Deprem kütlesi hesapla.
    
    Parameters
    ----------
    scene : Scene
        CAD sahnesi
    n : float
        Live load katsayısı (yönetmelikten, varsayılan 0.3)
    
    Returns
    -------
    MassBreakdown
        G, Q, n, total ve detaylar
    """
    result = MassBreakdown(n=n)
    
    # ---- 1. Self weight ----
    result.self_weight = _compute_self_weight(scene)
    logger.info(f"[Mass] Self weight: {result.self_weight:.3f} ton")
    
    # ---- 2. Pattern'leri sınıflandır ----
    patterns = scene.def_mgr.load_patterns
    dead_names: List[str] = []
    live_names: List[str] = []
    
    for name, pat in patterns.items():
        kind = get_pattern_kind(pat.design_type)
        if kind == "dead":
            dead_names.append(name)
        elif kind == "live":
            live_names.append(name)
    
    logger.info(f"[Mass] Dead patterns: {dead_names}")
    logger.info(f"[Mass] Live patterns: {live_names}")
    
    # ---- 3. Dead pattern yükleri (G) ----
    for name in dead_names:
        m = _pattern_vertical_loads(scene, name)
        if m > 0:
            result.dead_patterns[name] = m
            result.dead_loads += m
    
    # ---- 4. Live pattern yükleri (Q) ----
    for name in live_names:
        m = _pattern_vertical_loads(scene, name)
        if m > 0:
            result.live_patterns[name] = m
            result.live_loads += m
    
    logger.info(
        f"[Mass] G = {result.G:.3f} ton "
        f"(self={result.self_weight:.3f} + dead={result.dead_loads:.3f})"
    )
    logger.info(f"[Mass] Q = {result.Q:.3f} ton")
    logger.info(f"[Mass] n = {result.n}")
    logger.info(f"[Mass] m = G + n·Q = {result.total:.3f} ton")
    
    return result


# ============================================================
# SELF WEIGHT — ELEMAN AĞIRLIKLARI
# ============================================================

def _compute_self_weight(scene: Scene) -> float:
    """
    Tüm elemanların öz kütlesi (ton).
    
    Frame + Area + Link
    """
    total = 0.0
    
    # ---- Frame'ler ----
    for frame in scene.frames.values():
        total += _frame_mass(frame)
    
    # ---- Area'lar ----
    for area in scene.areas.values():
        total += _area_mass(area)
    
    # ---- Link'ler ----
    # Şimdilik atla — Link'in propname'i kesit değil
    # for link in scene.links.values():
    #     total += _link_mass(link)
    
    return total


def _frame_mass(frame) -> float:
    """Frame öz kütlesi (ton)."""
    if not frame.section or not frame.section.material:
        return 0.0
    
    A = frame.section.profile_params.get('Area', 0.0)   # mm²
    if A <= 0:
        return 0.0
    
    L = frame.get_length()   # mm
    if L <= 0:
        return 0.0
    
    rho = frame.section.material.density   # t/mm³
    
    return A * L * rho


def _area_mass(area) -> float:
    """Area öz kütlesi (ton)."""
    mat = getattr(area, 'material', None)
    if not mat:
        return 0.0
    
    thickness = area.thickness   # mm
    if thickness <= 0:
        return 0.0
    
    # Poligon alanı (mm²)
    poly_area = _polygon_area_3d(area.nodes)
    if poly_area <= 0:
        return 0.0
    
    rho = mat.density   # t/mm³
    
    return poly_area * thickness * rho


def _polygon_area_3d(nodes) -> float:
    """3D poligon alanı (Newell metodu)."""
    import numpy as np
    
    if len(nodes) < 3:
        return 0.0
    
    pts = np.array([[n.x, n.y, n.z] for n in nodes], dtype=float)
    n = len(pts)
    
    # Newell normal vektörü
    normal = np.zeros(3)
    for i in range(n):
        p1 = pts[i]
        p2 = pts[(i + 1) % n]
        normal[0] += (p1[1] - p2[1]) * (p1[2] + p2[2])
        normal[1] += (p1[2] - p2[2]) * (p1[0] + p2[0])
        normal[2] += (p1[0] - p2[0]) * (p1[1] + p2[1])
    
    return float(np.linalg.norm(normal) / 2.0)


# ============================================================
# PATTERN YÜKLERİ — DÜŞEY TOPLAMI
# ============================================================

def _pattern_vertical_loads(scene: Scene, pattern_name: str) -> float:
    """
    Bir pattern için düşey yüklerin toplam kütlesi (ton).
    
    Kaynaklar:
        - Frame yayılı yükler
        - Frame gravity loads
        - Area uniform yükler
        - Area uniform to frame
        - Node point loads
    """
    total_force = 0.0   # N (veya pattern biriminde)
    
    # ---- 1. Frame yayılı yükler ----
    for frame in scene.frames.values():
        L = frame.get_length()
        if L <= 0:
            continue
        
        for load in frame.dist_loads:
            if load.pattern_name != pattern_name:
                continue
            if not is_vertical(load.direction):
                continue
            
            # Ortalama yayılı yük × uzunluk
            # p1, p2 → N/mm
            # L → mm
            # sonuç → N
            p_avg = (load.p1 + load.p2) / 2
            total_force += p_avg * L
    
    # ---- 2. Frame gravity loads (çarpanlı) ----
    for frame in scene.frames.values():
        for load in frame.gravity_loads:
            if load.pattern_name != pattern_name:
                continue
            
            # Frame'in kendi ağırlığı × çarpan
            m_elem = _frame_mass(frame)   # ton
            if m_elem <= 0:
                continue
            
            # MultiplierZ → düşey çarpan (0-1 arası, yüzde)
            # Kuvvet = m × g × çarpan
            # N = ton × mm/s² × ...
            # 1 ton × 1 mm/s² = 1e6 N·mm/s²/... = karışık
            #
            # Basitleştirme:
            # m_elem ton
            # g = 9810 mm/s²
            # Force (N) = m_elem × g × 1e-3 (çünkü 1 ton = 1000 kg)
            # Aslında: kg × mm/s² = 1e-3 N
            # ton × mm/s² = 1 N
            total_force += m_elem * G_MM_S2 * load.multiplier_z
    
    # ---- 3. Area uniform yükler ----
    for area in scene.areas.values():
        poly_area = _polygon_area_3d(area.nodes)   # mm²
        if poly_area <= 0:
            continue
        
        for load in area.uniform_loads:
            if load.pattern_name != pattern_name:
                continue
            if not is_vertical(load.direction):
                continue
            
            # N/mm² × mm² = N
            total_force += load.value * poly_area
    
    # ---- 4. Area uniform to frame ----
    # Bu yükler SAP2000'de frame'lere otomatik dağıtılır.
    # Frame loads tablosunda görünmez ama ayrı tablodadır.
    for area in scene.areas.values():
        poly_area = _polygon_area_3d(area.nodes)
        if poly_area <= 0:
            continue
        
        for load in area.uniform_to_frame_loads:
            if load.pattern_name != pattern_name:
                continue
            if not is_vertical(load.direction):
                continue
            
            total_force += load.value * poly_area
    
    # ---- 5. Node point loads ----
    for node in scene.nodes.values():
        for load in node.loads:
            if load.pattern_name != pattern_name:
                continue
            
            # Sadece düşey bileşen (Fz)
            total_force += abs(load.fz)
    
    # ---- Kuvvet → kütle (ton) ----
    # N / (mm/s²) = kg·mm/s² / (mm/s²) = kg
    # kg → ton: / 1000
    # Ancak tüm birimler ton-mm-sisteminde:
    # 1 N = 1 kg·m/s² = 1e3 kg·mm/s² = 1e-3 ton·mm/s²... hayır
    # 
    # Doğru dönüşüm:
    # ton·mm/s² = 1e3 kg · mm/s² = 1e3 N·mm/s²/(m/s²)... 
    #
    # Basit:
    # 1 N = 1 kg·m/s² = 1000 kg·mm/s² · 1e-3 = 1 kg·mm/s² × 1e-3 ... 
    # 
    # En net: F (N) = m (kg) × a (m/s²)
    # CAD'de a = 9810 mm/s² = 9.81 m/s²
    # m (kg) = F (N) / 9.81
    # m (ton) = F / 9810
    #
    # Yani: m_ton = total_force_N / 9810
    # Aslında bu: total_force / G_MM_S2 (çünkü tüm birimler mm bazlı)
    
    return total_force / G_MM_S2


# ============================================================
# YARDIMCI — KULLANIM İÇİN
# ============================================================

def get_seismic_mass(scene: Scene, n: float = None) -> float:
    """
    Sadece toplam deprem kütlesini döndür (ton).
    
    Kısayol.
    """
    if n is None:
        # ProjectInformation'dan oku
        info = getattr(scene.def_mgr, 'project_info', None)
        n = getattr(info, 'live_load_factor', 0.3) if info else 0.3
    
    result = compute_seismic_mass(scene, n=n)
    return result.total


def mass_summary_text(result: MassBreakdown) -> str:
    """Özet metin (konsol/log için)."""
    lines = [
        "═══ Deprem Kütlesi ═══",
        f"  m = G + n·Q",
        "",
        f"  G (sabit yükler): {result.G:.3f} ton",
        f"    ├─ Self weight: {result.self_weight:.3f} ton",
    ]
    for name, m in result.dead_patterns.items():
        lines.append(f"    ├─ {name}: {m:.3f} ton")
    
    lines.append(f"  Q (hareketli yükler): {result.Q:.3f} ton")
    for name, m in result.live_patterns.items():
        lines.append(f"    ├─ {name}: {m:.3f} ton")
    
    lines += [
        "",
        f"  n = {result.n}",
        f"  n · Q = {result.n * result.Q:.3f} ton",
        "",
        f"  ➜ m = {result.total:.3f} ton",
        f"  ➜ m = {result.total_kg:.0f} kg",
        f"  ➜ W = {result.total_weight_kn:.2f} kN",
    ]
    return "\n".join(lines)

import numpy as np


def build_global_mass_matrix(scene: Scene, num_dofs: int, n: float = 0.3):
    """
    Tüm elemanların (Frame, Area) öz ağırlıklarından ve üzerindeki yüklerden
    m = G + n·Q formülüne göre kütleleri türetir ve düğüm noktalarının
    serbestlik derecelerine (UX, UY, UZ) köşegen (lumped) olarak atar.

    Parameters
    ----------
    scene : Scene
        CAD sahnesi (nodes, frames, areas, def_mgr içerir)
    num_dofs : int
        Sistemin serbestlik derecesi sayısı (M_global boyutu)
    n : float
        Hareketli yük katılım katsayısı (varsayılan 0.3)

    Returns
    -------
    M_global : np.ndarray (num_dofs, num_dofs) veya (num_dofs,)
        Global kütle matrisi (Köşegen matris)
    report : dict
        Düğüm bazlı ve eleman bazlı kütle dağılım raporu
    """
    M_global = np.zeros((num_dofs, num_dofs), dtype=float)
    
    # Raporlama yapısı
    report = {
        "node_masses": {},  # node_id -> float (ton)
        "breakdown": MassBreakdown(n=n)
    }

    # 1. Load Pattern Sınıflandırması
    patterns = scene.def_mgr.load_patterns
    pattern_factors = {}
    for name, pat in patterns.items():
        kind = get_pattern_kind(pat.design_type)
        if kind == "dead":
            pattern_factors[name] = 1.0  # G için katsayı 1.0
        elif kind == "live":
            pattern_factors[name] = n    # Q için katsayı n
        else:
            pattern_factors[name] = 0.0

    node_mass_map = {node_id: 0.0 for node_id in scene.nodes.keys()}

    # =========================================================
    # A. FRAME ELEMANLARI (Kendi Ağırlığı + Yayılı Yükler)
    # =========================================================
    for f_id, frame in scene.frames.items():
        if not frame.node_i or not frame.node_j:
            continue
        
        # A1. Frame Öz Kütlesi (ton)
        m_frame_self = _frame_mass(frame)
        m_total_frame = m_frame_self  # Dead kabul edilir (katsayı 1.0)
        report["breakdown"].self_weight += m_frame_self

        # A2. Frame Yayılı Yükleri
        L = frame.get_length()
        if L > 0:
            for load in getattr(frame, 'dist_loads', []):
                factor = pattern_factors.get(load.pattern_name, 0.0)
                if factor <= 0 or not is_vertical(load.direction):
                    continue
                
                # N -> Ton dönüşümü: (N / 9810)
                p_avg = (load.p1 + load.p2) / 2.0
                force = p_avg * L
                m_load = force / G_MM_S2
                
                m_total_frame += m_load * factor

                if pattern_factors.get(load.pattern_name) == 1.0:
                    report["breakdown"].dead_loads += m_load
                else:
                    report["breakdown"].live_loads += m_load

        # A3. Düğümlere Dağıt (I ve J uçlarına yarı yarıya)
        m_half = m_total_frame / 2.0
        node_mass_map[frame.node_i.unique_id] += m_half
        node_mass_map[frame.node_j.unique_id] += m_half

    # =========================================================
    # B. AREA ELEMANLARI (Kendi Ağırlığı + Uniform Yükler)
    # =========================================================
    for a_id, area in scene.areas.items():
        nodes = area.nodes
        num_nodes = len(nodes)
        if num_nodes < 3:
            continue

        poly_area = _polygon_area_3d(nodes)
        if poly_area <= 0:
            continue

        # B1. Area Öz Kütlesi (ton)
        m_area_self = _area_mass(area)
        m_total_area = m_area_self
        report["breakdown"].self_weight += m_area_self

        # B2. Area Uniform Yükleri
        for load in getattr(area, 'uniform_loads', []):
            factor = pattern_factors.get(load.pattern_name, 0.0)
            if factor <= 0 or not is_vertical(load.direction):
                continue

            force = load.value * poly_area
            m_load = force / G_MM_S2
            m_total_area += m_load * factor

            if pattern_factors.get(load.pattern_name) == 1.0:
                report["breakdown"].dead_loads += m_load
            else:
                report["breakdown"].live_loads += m_load

        # B3. Area Uniform To Frame Yükleri
        for load in getattr(area, 'uniform_to_frame_loads', []):
            factor = pattern_factors.get(load.pattern_name, 0.0)
            if factor <= 0 or not is_vertical(load.direction):
                continue

            force = load.value * poly_area
            m_load = force / G_MM_S2
            m_total_area += m_load * factor

            if pattern_factors.get(load.pattern_name) == 1.0:
                report["breakdown"].dead_loads += m_load
            else:
                report["breakdown"].live_loads += m_load

        # B4. Düğümlere Dağıt (Tributary Area / Köşe Düğümlerine Eşit)
        m_per_node = m_total_area / num_nodes
        for node in nodes:
            node_mass_map[node.id] += m_per_node

    # =========================================================
    # C. NOKTASAL DÜĞÜM YÜKLERİ (Node Point Loads)
    # =========================================================
    for node_id, node in scene.nodes.items():
        for load in getattr(node, 'loads', []):
            factor = pattern_factors.get(load.pattern_name, 0.0)
            if factor <= 0:
                continue

            # Sadece düşey kuvvet kütleye dönüşür (Fz)
            fz = abs(getattr(load, 'fz', 0.0))
            if fz > 0:
                m_load = fz / G_MM_S2
                node_mass_map[node_id] += m_load * factor

                if pattern_factors.get(load.pattern_name) == 1.0:
                    report["breakdown"].dead_loads += m_load
                else:
                    report["breakdown"].live_loads += m_load

    # =========================================================
    # D. GLOBAL KÜTLE MATRİSİNE İŞLEME (M_global)
    # =========================================================
    for node_id, node in scene.nodes.items():
        m_node = node_mass_map.get(node_id, 0.0)
        report["node_masses"][node_id] = m_node

        if m_node <= 0 or not hasattr(node, 'dof_indices') or node.dof_indices is None:
            continue

        # Serbestlik Dereceleri: UX, UY, UZ (0, 1, 2)
        for offset in (0, 1, 2):
            if offset < len(node.dof_indices):
                idx = node.dof_indices[offset]
                # Sınır koşulu / mesnet kontrolleri (idx >= 0 olmalı)
                if 0 <= idx < num_dofs:
                    M_global[idx, idx] += m_node

    return M_global, report