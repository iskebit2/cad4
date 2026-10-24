# core/analysis/mass_assembly.py

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from core.units import G_M_S2, KG_PER_TON
from domain.definition import LoadDirection
from logging_config import CadLogger

logger = CadLogger.get(__name__)

VERTICAL_DIRECTIONS = {
    LoadDirection.GRAVITY, LoadDirection.GLOBAL_Z,
    LoadDirection.PROJECTED_Z, LoadDirection.LOCAL_3,
}

# SAP2000 Dir kodları → düşey mi?
_VERTICAL_DIR_CODES = {"6", "7", "10"}  # Global Z, Gravity, Proj Z


@dataclass
class MassContribution:
    source_type: str
    element_id: int
    element_label: str
    pattern: str
    mass_kg: float


@dataclass
class MassAssembly:
    num_dofs: int
    M_global: np.ndarray
    node_masses: Dict[str, float]
    contributions: List[MassContribution] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    total_self_kg: float = 0.0
    total_dead_kg: float = 0.0
    total_live_kg: float = 0.0
    n_live: float = 0.3

    @property
    def total_kg(self) -> float:
        return self.total_self_kg + self.total_dead_kg + self.n_live * self.total_live_kg

    @property
    def total_ton(self) -> float:
        return self.total_kg / KG_PER_TON


# ============================================================================
# YARDIMCILAR
# ============================================================================
def _is_vertical_load_set(load) -> bool:
    ld = str(getattr(load, "load_dir", "") or "").strip()
    if ld:
        if ld in _VERTICAL_DIR_CODES:
            return True
        if ld == "3":
            cs = str(getattr(load, "coord_sys", "Local")).lower()
            return cs == "local"
        return False
    d = getattr(load, "direction", None)
    return d in VERTICAL_DIRECTIONS


def _pattern_kind(design_type: str) -> str:
    t = str(design_type or "").upper().strip()
    if "DEAD" in t or "SUPERDEAD" in t:
        return "dead"
    if "LIVE" in t or "ROOFLIVE" in t or "PATTERNLIVE" in t:
        return "live"
    return "other"


def _node_key_map(scene) -> Dict[object, str]:
    out = {}
    for key, node in scene.nodes.items():
        out[key] = key
        uid = getattr(node, "unique_id", None)
        if uid is not None:
            out[uid] = key
    return out


def _polygon_area_3d(nodes) -> float:
    if len(nodes) < 3:
        return 0.0
    pts = np.array([[n.x, n.y, n.z] for n in nodes], dtype=float)
    normal = np.zeros(3)
    for i in range(len(pts)):
        p1, p2 = pts[i], pts[(i + 1) % len(pts)]
        normal[0] += (p1[1] - p2[1]) * (p1[2] + p2[2])
        normal[1] += (p1[2] - p2[2]) * (p1[0] + p2[0])
        normal[2] += (p1[0] - p2[0]) * (p1[1] + p2[1])
    return float(np.linalg.norm(normal) / 2.0)


def _frame_self_mass_kg(frame) -> Tuple[float, Optional[str]]:
    sec = getattr(frame, "section", None)
    if sec is None:
        return 0.0, "section yok"
    mat = getattr(sec, "material", None)
    if mat is None:
        return 0.0, "material yok"
    A = (sec.profile_params or {}).get("Area", 0.0)
    if A <= 0:
        return 0.0, "Area<=0"
    L = frame.get_length()
    if L <= 0:
        return 0.0, "L<=0"
    rho = getattr(mat, "density", 0.0)
    if rho <= 0:
        return 0.0, "density<=0"
    return A * L * rho, None


def _area_self_mass_kg(area) -> Tuple[float, Optional[str]]:
    mat = getattr(area, "material", None)
    if mat is None:
        return 0.0, "material yok"
    th = getattr(area, "thickness", 0.0)
    if th <= 0:
        return 0.0, "thickness<=0"
    geom_A = _polygon_area_3d(area.nodes)
    if geom_A <= 0:
        return 0.0, "geometry area<=0"
    rho = getattr(mat, "density", 0.0)
    if rho <= 0:
        return 0.0, "density<=0"
    return geom_A * th * rho, None


def _load_segment_value(seg, key: str, default=0.0) -> float:
    if isinstance(seg, dict):
        return float(seg.get(key, default))
    return float(getattr(seg, key, default))


def _distributed_load_mass_kg(load, frame_length: float) -> float:
    """Yayılı yükün toplam kütlesi (kg). Segment veya p1/p2 destekler."""
    segs = getattr(load, "segments", None)
    if segs:
        is_rel = bool(getattr(load, "is_relative", True))
        total_force_N = 0.0
        for seg in segs:
            x1 = _load_segment_value(seg, "x1", 0.0)
            x2 = _load_segment_value(seg, "x2", 1.0)
            q1 = _load_segment_value(seg, "q1", 0.0)
            q2 = _load_segment_value(seg, "q2", 0.0)
            dx = x2 - x1
            if dx <= 0:
                continue
            seg_len_mm = dx * frame_length if is_rel else dx
            total_force_N += 0.5 * (q1 + q2) * seg_len_mm
        return total_force_N / G_M_S2

    p1 = getattr(load, "p1", None)
    p2 = getattr(load, "p2", None)
    if p1 is None or p2 is None:
        return 0.0
    p_avg = 0.5 * (float(p1) + float(p2))
    return (p_avg * frame_length) / G_M_S2


# ============================================================================
# ANA FONKSİYON
# ============================================================================
def build_mass(scene, project, n_live: float = 0.3, *, validate: bool = True) -> MassAssembly:
    num_dofs = len(scene.nodes) * 6

    for i, node in enumerate(scene.nodes.values()):
        node.dof_indices = list(range(i * 6, i * 6 + 6))

    node_key_map = _node_key_map(scene)

    patterns = getattr(project, "load_patterns", {}) or {}
    pattern_kind: Dict[str, str] = {}
    pattern_factor: Dict[str, float] = {}
    for name, lp in patterns.items():
        k = _pattern_kind(getattr(lp, "design_type", "Dead"))
        pattern_kind[name] = k
        pattern_factor[name] = 1.0 if k == "dead" else (n_live if k == "live" else 0.0)

    node_masses: Dict[str, float] = {k: 0.0 for k in scene.nodes.keys()}
    contributions: List[MassContribution] = []
    warnings: List[str] = []

    def _add(key: Optional[str], mass_kg: float):
        if key is None or mass_kg <= 0 or not math.isfinite(mass_kg):
            return
        node_masses[key] += mass_kg

    def _contrib(source_type: str, elem_id: int, elem_label: str,
                 pattern: str, mass_kg: float):
        contributions.append(MassContribution(source_type, elem_id, elem_label, pattern, mass_kg))

    # 1. FRAME öz kütle
    for frame in scene.frames.values():
        m_kg, err = _frame_self_mass_kg(frame)
        if err:
            warnings.append(f"Frame {frame.label}: öz kütle atlandı ({err})")
            continue
        if m_kg <= 0:
            continue
        ki = node_key_map.get(getattr(frame.node_i, "unique_id", None))
        kj = node_key_map.get(getattr(frame.node_j, "unique_id", None))
        _add(ki, m_kg / 2.0)
        _add(kj, m_kg / 2.0)
        _contrib("frame_self", frame.unique_id, frame.label, "", m_kg)

    # 2. FRAME yayılı yükler (düşey) — TEK döngü, çift sayım yok
    for frame in scene.frames.values():
        L = frame.get_length()
        if L <= 0:
            continue
        ki = node_key_map.get(getattr(frame.node_i, "unique_id", None))
        kj = node_key_map.get(getattr(frame.node_j, "unique_id", None))

        for load in getattr(frame, "dist_loads", []) or []:
            if not _is_vertical_load_set(load):
                continue
            pat = getattr(load, "pattern_name", "")
            factor = pattern_factor.get(pat, 0.0)
            if factor <= 0:
                continue
            mass_kg = _distributed_load_mass_kg(load, L)
            if mass_kg <= 0:
                continue
            contrib_kg = mass_kg * factor
            _add(ki, contrib_kg / 2.0)
            _add(kj, contrib_kg / 2.0)
            _contrib("frame_load", frame.unique_id, frame.label, pat, mass_kg)

    # 3. AREA öz kütle
    for area in scene.areas.values():
        m_kg, err = _area_self_mass_kg(area)
        if err:
            warnings.append(f"Area {area.label}: öz kütle atlandı ({err})")
            continue
        if m_kg <= 0:
            continue
        n = len(area.nodes)
        if n == 0:
            continue
        per_node = m_kg / n
        for nd in area.nodes:
            _add(node_key_map.get(getattr(nd, "unique_id", None)), per_node)
        _contrib("area_self", area.unique_id, area.label, "", m_kg)

    # 4. AREA uniform yük
    for area in scene.areas.values():
        geom_A = _polygon_area_3d(area.nodes)
        if geom_A <= 0:
            continue
        n = len(area.nodes)
        if n == 0:
            continue
        for load in getattr(area, "uniform_loads", []) or []:
            if getattr(load, "direction", None) not in VERTICAL_DIRECTIONS:
                continue
            pat = getattr(load, "pattern_name", "")
            factor = pattern_factor.get(pat, 0.0)
            if factor <= 0:
                continue
            val = getattr(load, "value", 0.0)
            if val <= 0:
                continue
            mass_kg = (val * geom_A) / G_M_S2
            contrib_kg = mass_kg * factor
            for nd in area.nodes:
                _add(node_key_map.get(getattr(nd, "unique_id", None)), contrib_kg / n)
            _contrib("area_uniform", area.unique_id, area.label, pat, mass_kg)

    # 5. AREA uniform to frame
    for area in scene.areas.values():
        geom_A = _polygon_area_3d(area.nodes)
        if geom_A <= 0:
            continue
        n = len(area.nodes)
        if n == 0:
            continue
        for load in getattr(area, "uniform_to_frame_loads", []) or []:
            ld = str(getattr(load, "load_dir", "") or "").strip()
            d = getattr(load, "direction", None)
            if ld not in _VERTICAL_DIR_CODES and d not in VERTICAL_DIRECTIONS:
                continue
            pat = getattr(load, "pattern_name", "")
            factor = pattern_factor.get(pat, 0.0)
            if factor <= 0:
                continue
            val = getattr(load, "value", 0.0)
            if val <= 0:
                continue
            mass_kg = (val * geom_A) / G_M_S2
            contrib_kg = mass_kg * factor
            for nd in area.nodes:
                _add(node_key_map.get(getattr(nd, "unique_id", None)), contrib_kg / n)
            _contrib("area_to_frame", area.unique_id, area.label, pat, mass_kg)

    # 6. NODE nokta yükü (fz)
    for key, node in scene.nodes.items():
        for load in getattr(node, "loads", []) or []:
            pat = getattr(load, "pattern_name", "")
            factor = pattern_factor.get(pat, 0.0)
            if factor <= 0:
                continue
            fz = abs(getattr(load, "fz", 0.0))
            if fz <= 0:
                continue
            mass_kg = fz / G_M_S2
            _add(key, mass_kg * factor)
            _contrib("node_point", node.unique_id, node.label, pat, mass_kg)

    # 7. Özet
    total_self = sum(c.mass_kg for c in contributions if c.source_type.endswith("_self"))
    total_dead = sum(c.mass_kg for c in contributions if c.pattern and pattern_kind.get(c.pattern) == "dead")
    total_live = sum(c.mass_kg for c in contributions if c.pattern and pattern_kind.get(c.pattern) == "live")

    # 8. M_global (lumped, sadece UX/UY/UZ) -> kg cinsinden gelen kütleyi ton (N·s²/mm) cinsine çevirmek için 1000'e bölüyoruz
    M = np.zeros((num_dofs, num_dofs), dtype=float)
    for key, node in scene.nodes.items():
        m_kg = node_masses.get(key, 0.0)
        if m_kg <= 0:
            continue
        dofs = getattr(node, "dof_indices", None)
        if not dofs:
            continue
        m_ton = m_kg / KG_PER_TON  # kg -> ton (N·s²/mm)
        for off in (0, 1, 2):
            if off < len(dofs) and dofs[off] is not None:
                d = dofs[off]
                if 0 <= d < num_dofs:
                    M[d, d] = m_ton

    asm = MassAssembly(
        num_dofs=num_dofs,
        M_global=M,
        node_masses=node_masses,
        contributions=contributions,
        warnings=warnings,
        total_self_kg=total_self,
        total_dead_kg=total_dead,
        total_live_kg=total_live,
        n_live=n_live,
    )

    if validate:
        from core.analysis.validation import validate_mass
        for e in validate_mass(asm):
            asm.warnings.append(e)
            logger.error("[Mass] %s", e)

    return asm