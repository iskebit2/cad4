# core/analysis/mass_assembly.py

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from core.units import G_M_S2, MEGAGRAM
from domain.definition import LoadDirection
from core.analysis.stiffness_assembly import transformation_matrix
from logging_config import CadLogger

logger = CadLogger.get(__name__)

VERTICAL_DIRECTIONS = {
    LoadDirection.GRAVITY, LoadDirection.GLOBAL_Z,
    LoadDirection.PROJECTED_Z, LoadDirection.LOCAL_3,
}

_VERTICAL_DIR_CODES = {"6", "7", "10"}


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
        return self.total_kg / MEGAGRAM


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


def _load_segment_value(seg, key: str, default=0.0) -> float:
    if isinstance(seg, dict):
        return float(seg.get(key, default))
    return float(getattr(seg, key, default))


def _distributed_load_mass_kg(load, frame_length: float) -> float:
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


def local_consistent_mass(
    A: float, L: float, rho: float, J: float, I33: float, I22: float
) -> np.ndarray:
    """3D Çubuk 12x12 Lokal Tutarlı (Consistent) Kütle Matrisi."""
    m = rho * A * L
    m_mat = np.zeros((12, 12), dtype=float)

    if L <= 0 or m <= 0:
        return m_mat

    # 1. Eksenel (UX: 0, 6)
    axial = (m / 6.0) * np.array([[2.0, 1.0], [1.0, 2.0]])
    m_mat[0, 0] = axial[0, 0]
    m_mat[0, 6] = axial[0, 1]
    m_mat[6, 0] = axial[1, 0]
    m_mat[6, 6] = axial[1, 1]

    # 2. Burulma (RX: 3, 9)
    m_t = m * (J / A) if A > 0 else m
    torsion = (m_t / 6.0) * np.array([[2.0, 1.0], [1.0, 2.0]])
    m_mat[3, 3] = torsion[0, 0]
    m_mat[3, 9] = torsion[0, 1]
    m_mat[9, 3] = torsion[1, 0]
    m_mat[9, 9] = torsion[1, 1]

    # 3. Eğilme Yönü 1 (UY: 1, RZ: 5)
    beam_m1 = (m / 420.0) * np.array([
        [156.0,  22.0 * L,   54.0, -13.0 * L],
        [22.0 * L, 4.0 * L**2, 13.0 * L, -3.0 * L**2],
        [54.0,   13.0 * L,  156.0, -22.0 * L],
        [-13.0 * L, -3.0 * L**2, -22.0 * L, 4.0 * L**2]
    ])
    idx1 = [1, 5, 7, 11]
    for r_i, ri in enumerate(idx1):
        for c_i, ci in enumerate(idx1):
            m_mat[ri, ci] += beam_m1[r_i, c_i]

    # 4. Eğilme Yönü 2 (UZ: 2, RY: 4)
    beam_m2 = (m / 420.0) * np.array([
        [156.0, -22.0 * L,   54.0,  13.0 * L],
        [-22.0 * L, 4.0 * L**2, -13.0 * L, -3.0 * L**2],
        [54.0,  -13.0 * L,  156.0,  22.0 * L],
        [13.0 * L, -3.0 * L**2,  22.0 * L, 4.0 * L**2]
    ])
    idx2 = [2, 4, 8, 10]
    for r_i, ri in enumerate(idx2):
        for c_i, ci in enumerate(idx2):
            m_mat[ri, ci] += beam_m2[r_i, c_i]

    return 0.5 * (m_mat + m_mat.T)


def triangle_consistent_mass_3d(nodes: list, thickness: float, material) -> np.ndarray:
    """3 düğümlü 3D kabuk elemanı 18x18 Consistent Kütle Matrisi."""
    n = len(nodes)
    if n < 3:
        return np.zeros((0, 0), dtype=float)

    rho = float(getattr(material, "density", 0.0))
    t = float(thickness)
    if rho <= 0 or t <= 0:
        return np.zeros((18, 18), dtype=float)

    p0 = np.array([nodes[0].x, nodes[0].y, nodes[0].z], dtype=float)
    p1 = np.array([nodes[1].x, nodes[1].y, nodes[1].z], dtype=float)
    p2 = np.array([nodes[2].x, nodes[2].y, nodes[2].z], dtype=float)

    v1 = p1 - p0
    v2 = p2 - p0
    normal = np.cross(v1, v2)
    area = 0.5 * float(np.linalg.norm(normal))
    if area < 1e-9:
        return np.zeros((18, 18), dtype=float)

    m_tot = rho * t * area
    m_loc = np.zeros((18, 18), dtype=float)

    # Öteleme serbestlik dereceleri (UX, UY, UZ) için consistent kütle dağılımı
    sub_m = (m_tot / 12.0) * np.array([
        [2.0, 1.0, 1.0],
        [1.0, 2.0, 1.0],
        [1.0, 1.0, 2.0]
    ])

    for dof_off in range(3):
        for i_node in range(3):
            for j_node in range(3):
                ri = 6 * i_node + dof_off
                ci = 6 * j_node + dof_off
                m_loc[ri, ci] = sub_m[i_node, j_node]

    e3 = normal / np.linalg.norm(normal)
    e1 = v1 / np.linalg.norm(v1)
    e2 = np.cross(e3, e1)
    if np.linalg.norm(e2) > 1e-9:
        e2 = e2 / np.linalg.norm(e2)
    else:
        e2 = np.array([0, 1, 0], dtype=float)

    R = np.vstack([e1, e2, e3])
    T = np.zeros((18, 18), dtype=float)
    for i in range(6):
        T[i*3:(i+1)*3, i*3:(i+1)*3] = R

    m_glob = T.T @ m_loc @ T
    return 0.5 * (m_glob + m_glob.T)




def _node_translation_dofs(node, num_dofs: int):
    """Düğümün UX/UY/UZ global DOF endekslerini döndürür (None'ları atar)."""
    dofs = getattr(node, "dof_indices", None)
    if not dofs or len(dofs) < 3:
        return []
    out = []
    for off in (0, 1, 2):
        d = dofs[off]
        if d is not None and 0 <= d < num_dofs:
            out.append(int(d))
    return out


def _lump_to_node(
    M: np.ndarray,
    node,
    mass_kg: float,
    num_dofs: int,
) -> None:
    """Lumped kütleyi düğümün UX/UY/UZ köşegenlerine eşit yazar."""
    if mass_kg <= 0:
        return
    m_ton = mass_kg / MEGAGRAM
    for d in _node_translation_dofs(node, num_dofs):
        M[d, d] += m_ton


def build_mass(
    scene,
    project,
    n_live: float = 0.3,
    *,
    validate: bool = True,
) -> MassAssembly:
    """
    Kütle matrisi montajı.

    Mimari:
      - Frame/Area ÖZ kütle  → consistent (12x12 / 18x18) blok montajı.
      - Dış yükler (yayılı, uniform, nokta) → lumped (köşegen) montaj.
      - node_masses: her düğümün toplam kütlesi (kg) — raporlama ve
        validation için tek doğruluk kaynağı.
      - M_global: ton (N·s²/mm) biriminde, simetrik.
    """
    num_dofs = len(scene.nodes) * 6

    # --- DOF endeksleri ---
    for i, node in enumerate(scene.nodes.values()):
        node.dof_indices = list(range(i * 6, i * 6 + 6))

    node_key_map = _node_key_map(scene)

    # --- Yük pattern'ları ---
    patterns = getattr(project, "load_patterns", {}) or {}
    pattern_kind: Dict[str, str] = {}
    pattern_factor: Dict[str, float] = {}
    for name, lp in patterns.items():
        k = _pattern_kind(getattr(lp, "design_type", "Dead"))
        pattern_kind[name] = k
        pattern_factor[name] = (
            1.0 if k == "dead" else (n_live if k == "live" else 0.0)
        )

    # --- Toplayıcılar ---
    node_masses: Dict[str, float] = {k: 0.0 for k in scene.nodes.keys()}
    contributions: List[MassContribution] = []
    warnings: List[str] = []
    M = np.zeros((num_dofs, num_dofs), dtype=float)

    def _add(key: Optional[str], mass_kg: float) -> None:
        if key is None or mass_kg <= 0 or not math.isfinite(mass_kg):
            return
        node_masses[key] += mass_kg

    def _contrib(source_type: str, elem_id, elem_label: str,
                 pattern: str, mass_kg: float) -> None:
        contributions.append(
            MassContribution(source_type, elem_id, elem_label, pattern, mass_kg)
        )

    # ==================================================================
    # 1) FRAME ÖZ KÜTLE — consistent 12x12
    # ==================================================================
    for frame in scene.frames.values():
        sec = getattr(frame, "section", None)
        mat = getattr(sec, "material", None) if sec else None
        if mat is None:
            continue

        params = sec.profile_params or {}
        try:
            A = float(params.get("Area", 0.0))
            J = float(params.get("J", 0.0))
            I33 = float(params.get("I33", 0.0))
            I22 = float(params.get("I22", 0.0))
        except (TypeError, ValueError):
            continue

        L = frame.get_length()
        rho = float(getattr(mat, "density", 0.0))
        if A <= 0 or L <= 0 or rho <= 0:
            continue

        m_kg = A * L * rho

        # node_masses'a yarı yarıya yaz
        ki = node_key_map.get(getattr(frame.node_i, "unique_id", None))
        kj = node_key_map.get(getattr(frame.node_j, "unique_id", None))
        _add(ki, m_kg / 2.0)
        _add(kj, m_kg / 2.0)
        _contrib("frame_self", frame.unique_id, frame.label, "", m_kg)

        # Consistent mass → M
        dofs_i = getattr(frame.node_i, "dof_indices", None)
        dofs_j = getattr(frame.node_j, "dof_indices", None)
        if not dofs_i or not dofs_j:
            continue

        p1 = (frame.node_i.x, frame.node_i.y, frame.node_i.z)
        p2 = (frame.node_j.x, frame.node_j.y, frame.node_j.z)
        try:
            T, _ = transformation_matrix(
                p1, p2, getattr(frame, "rotation_deg", 0.0) or 0.0
            )
            m_loc = local_consistent_mass(
                A=A, L=L, rho=rho, J=J, I33=I33, I22=I22
            )
            m_glob_ton = (T.T @ m_loc @ T) / MEGAGRAM
            dofs = list(dofs_i) + list(dofs_j)
            M[np.ix_(dofs, dofs)] += m_glob_ton
        except Exception as e:
            warnings.append(f"Frame {frame.label} consistent kütle hatası: {e}")

    # ==================================================================
    # 2) FRAME YAYILI YÜKLER — lumped
    # ==================================================================
    for frame in scene.frames.values():
        L = frame.get_length()
        if L <= 0:
            continue
        dofs_i = getattr(frame.node_i, "dof_indices", None)
        dofs_j = getattr(frame.node_j, "dof_indices", None)
        if not dofs_i or not dofs_j:
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
            half = contrib_kg / 2.0

            _add(ki, half)
            _add(kj, half)
            _contrib("frame_load", frame.unique_id, frame.label, pat, mass_kg)

            _lump_to_node(M, frame.node_i, half, num_dofs)
            _lump_to_node(M, frame.node_j, half, num_dofs)

    # ==================================================================
    # 3) AREA ÖZ KÜTLE — consistent 18x18 (üçgenleştirilmiş)
    # ==================================================================
    for area in scene.areas.values():
        nodes = getattr(area, "nodes", [])
        n_nodes = len(nodes)
        if n_nodes < 3:
            continue
        thickness = float(getattr(area, "thickness", 0.0))
        if thickness <= 0:
            continue
        mat = getattr(area, "material", None)
        if mat is None:
            continue

        geom_A = _polygon_area_3d(nodes)
        rho = float(getattr(mat, "density", 0.0))
        if geom_A <= 0 or rho <= 0:
            continue

        m_kg = geom_A * thickness * rho
        per_node = m_kg / n_nodes
        for nd in nodes:
            _add(node_key_map.get(getattr(nd, "unique_id", None)), per_node)
        _contrib("area_self", area.unique_id, area.label, "", m_kg)

        # Consistent mass → M (triangülasyon)
        for i in range(1, n_nodes - 1):
            tri_nodes = [nodes[0], nodes[i], nodes[i + 1]]
            m_tri_glob = triangle_consistent_mass_3d(tri_nodes, thickness, mat)
            if m_tri_glob.size == 0:
                continue

            tri_dofs: List[int] = []
            ok = True
            for nd in tri_nodes:
                dofs = getattr(nd, "dof_indices", None)
                if not dofs:
                    ok = False
                    break
                tri_dofs.extend(dofs)
            if not ok or len(tri_dofs) != 18:
                continue

            m_tri_ton = m_tri_glob / MEGAGRAM
            M[np.ix_(tri_dofs, tri_dofs)] += m_tri_ton

    # ==================================================================
    # 4) AREA UNIFORM YÜK — lumped
    # ==================================================================
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
            per_node = contrib_kg / n

            for nd in area.nodes:
                _add(node_key_map.get(getattr(nd, "unique_id", None)), per_node)
                _lump_to_node(M, nd, per_node, num_dofs)
            _contrib("area_uniform", area.unique_id, area.label, pat, mass_kg)

    # ==================================================================
    # 5) AREA UNIFORM TO FRAME — lumped
    # ==================================================================
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
            per_node = contrib_kg / n

            for nd in area.nodes:
                _add(node_key_map.get(getattr(nd, "unique_id", None)), per_node)
                _lump_to_node(M, nd, per_node, num_dofs)
            _contrib("area_to_frame", area.unique_id, area.label, pat, mass_kg)

    # ==================================================================
    # 6) NODE NOKTASAL YÜK — lumped
    # ==================================================================
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
            contrib_kg = mass_kg * factor
            _add(key, contrib_kg)
            _contrib("node_point", node.unique_id, node.label, pat, mass_kg)
            _lump_to_node(M, node, contrib_kg, num_dofs)

    # ==================================================================
    # 7) Simetrizasyon
    # ==================================================================
    M = 0.5 * (M + M.T)

    # ==================================================================
    # 8) Özet
    # ==================================================================
    total_self = sum(c.mass_kg for c in contributions if c.source_type.endswith("_self"))
    total_dead = sum(
        c.mass_kg for c in contributions
        if c.pattern and pattern_kind.get(c.pattern) == "dead"
    )
    total_live = sum(
        c.mass_kg for c in contributions
        if c.pattern and pattern_kind.get(c.pattern) == "live"
    )

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
        for e in validate_mass(asm, is_consistent=True):
            asm.warnings.append(e)
            logger.error("[Mass] %s", e)

    return asm