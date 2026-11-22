# app/commands/analysis\mass_assembly.py
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy import sparse
from app.commands.analysis.frame_resolver import resolve_frame_kinematics, resolve_section
from app.commands.analysis.stiffness_assembly import transformation_matrix
from core.units import G_M_S2, MEGAGRAM
from domain.definition import LoadDirection
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
    M_global: sparse.csc_matrix
    node_masses: dict[str, float]
    contributions: list[MassContribution] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
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

def _frame_consistent_mass_local(
    mass_per_len: float,
    A: float,
    I22: float,
    I33: float,
    J: float,
    kin,
) -> np.ndarray:
    L = kin.L_clear
    m_tot = mass_per_len * L
    m = np.zeros((12, 12), dtype=float)

    m[0, 0] = m[6, 6] = m_tot / 3.0
    m[0, 6] = m[6, 0] = m_tot / 6.0

    Ip = (I22 + I33) if (I22 + I33) > 0.0 else J
    rx_sq = (Ip / A) if A > 0.0 else 0.0
    m_rot = m_tot * rx_sq
    m[3, 3] = m[9, 9] = m_rot / 3.0
    m[3, 9] = m[9, 3] = m_rot / 6.0

    c_b = m_tot / 420.0
    for idx_u, idx_r, sgn in ((1, 5, 1.0), (2, 4, -1.0)):
        iu, ir, ju, jr = idx_u, idx_r, 6 + idx_u, 6 + idx_r
        m[iu, iu] = m[ju, ju] = 156.0 * c_b
        m[iu, ju] = m[ju, iu] = 54.0 * c_b
        m[iu, ir] = m[ir, iu] = sgn * 22.0 * L * c_b
        m[ju, jr] = m[jr, ju] = -sgn * 22.0 * L * c_b
        m[iu, jr] = m[jr, iu] = -sgn * 13.0 * L * c_b
        m[ju, ir] = m[ir, ju] = sgn * 13.0 * L * c_b
        m[ir, ir] = m[jr, jr] = 4.0 * (L * L) * c_b
        m[ir, jr] = m[jr, ir] = -3.0 * (L * L) * c_b

    m_node_loc = kin.T_ecc.T @ (kin.H.T @ m @ kin.H) @ kin.T_ecc
    return 0.5 * (m_node_loc + m_node_loc.T)

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


def _node_key_map(scene) -> dict[object, str]:
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
            q1 = abs(_load_segment_value(seg, "q1", 0.0))
            q2 = abs(_load_segment_value(seg, "q2", 0.0))
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
    p_avg = 0.5 * (abs(float(p1)) + abs(float(p2)))
    return (p_avg * frame_length) / G_M_S2


def local_consistent_mass(
    A: float, L: float, rho: float, J: float, I33: float, I22: float
) -> np.ndarray:
    m = rho * A * L
    m_mat = np.zeros((12, 12), dtype=float)

    if L <= 0 or m <= 0:
        return m_mat

    c_ax = m / 6.0
    m_mat[0, 0] = 2.0 * c_ax
    m_mat[0, 6] = c_ax
    m_mat[6, 0] = c_ax
    m_mat[6, 6] = 2.0 * c_ax

    m_t = m * (J / A) if A > 0 else m
    c_t = m_t / 6.0
    m_mat[3, 3] = 2.0 * c_t
    m_mat[3, 9] = c_t
    m_mat[9, 3] = c_t
    m_mat[9, 9] = 2.0 * c_t

    c_b = m / 420.0
    L2 = L * L
    beam_m1 = c_b * np.array([
        [156.0, 22.0 * L, 54.0, -13.0 * L],
        [22.0 * L, 4.0 * L2, 13.0 * L, -3.0 * L2],
        [54.0, 13.0 * L, 156.0, -22.0 * L],
        [-13.0 * L, -3.0 * L2, -22.0 * L, 4.0 * L2],
    ])
    idx1 = np.array([1, 5, 7, 11], dtype=np.intp)
    m_mat[np.ix_(idx1, idx1)] += beam_m1

    beam_m2 = c_b * np.array([
        [156.0, -22.0 * L, 54.0, 13.0 * L],
        [-22.0 * L, 4.0 * L2, -13.0 * L, -3.0 * L2],
        [54.0, -13.0 * L, 156.0, 22.0 * L],
        [13.0 * L, -3.0 * L2, 22.0 * L, 4.0 * L2],
    ])
    idx2 = np.array([2, 4, 8, 10], dtype=np.intp)
    m_mat[np.ix_(idx2, idx2)] += beam_m2

    return 0.5 * (m_mat + m_mat.T)


def triangle_consistent_mass_3d(nodes: list, thickness: float, material) -> np.ndarray:
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

    sub_m = (m_tot / 12.0) * np.array([
        [2.0, 1.0, 1.0],
        [1.0, 2.0, 1.0],
        [1.0, 1.0, 2.0],
    ])

    for dof_off in range(3):
        idx = np.array([dof_off, 6 + dof_off, 12 + dof_off], dtype=np.intp)
        m_loc[np.ix_(idx, idx)] = sub_m

    e3 = normal / np.linalg.norm(normal)
    e1 = v1 / np.linalg.norm(v1)
    e2 = np.cross(e3, e1)
    e2_norm = float(np.linalg.norm(e2))
    e2 = (e2 / e2_norm) if e2_norm > 1e-9 else np.array([0.0, 1.0, 0.0], dtype=float)

    R = np.vstack([e1, e2, e3])
    T = np.kron(np.eye(6), R)

    m_glob = T.T @ m_loc @ T
    return 0.5 * (m_glob + m_glob.T)


def _node_translation_dofs(node, num_dofs: int) -> list[int]:
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
    lumped_diag: np.ndarray,
    node,
    mass_kg: float,
    num_dofs: int,
) -> None:
    if mass_kg <= 0:
        return
    m_ton = mass_kg / MEGAGRAM
    for d in _node_translation_dofs(node, num_dofs):
        lumped_diag[d] += m_ton


def _push_block(
    rows: list[np.ndarray],
    cols: list[np.ndarray],
    vals: list[np.ndarray],
    dofs: list[int],
    mat: np.ndarray,
) -> None:
    d_arr = np.asarray(dofs, dtype=np.int32)
    n = d_arr.size
    rows.append(np.repeat(d_arr, n))
    cols.append(np.tile(d_arr, n))
    vals.append(mat.ravel())


def build_mass(
    scene,
    project,
    n_live: float = 0.3,
    *,
    validate: bool = True,
) -> MassAssembly:
    from app.commands.analysis.stiffness_assembly import ensure_dof_indices

    num_dofs = len(scene.nodes) * 6
    ensure_dof_indices(scene)
    node_key_map = _node_key_map(scene)

    patterns = getattr(project, "load_patterns", {}) or {}
    pattern_kind: dict[str, str] = {}
    pattern_factor: dict[str, float] = {}
    for name, lp in patterns.items():
        k = _pattern_kind(getattr(lp, "design_type", "Dead"))
        pattern_kind[name] = k
        pattern_factor[name] = (
            1.0 if k == "dead" else (n_live if k == "live" else 0.0)
        )

    node_masses: dict[str, float] = {k: 0.0 for k in scene.nodes.keys()}
    contributions: list[MassContribution] = []
    warnings: list[str] = []

    rows: list[np.ndarray] = []
    cols: list[np.ndarray] = []
    vals: list[np.ndarray] = []
    lumped_diag = np.zeros(num_dofs, dtype=float)

    def _add(key: str | None, mass_kg: float) -> None:
        if key is None or mass_kg <= 0 or not math.isfinite(mass_kg):
            return
        node_masses[key] += mass_kg

    def _contrib(source_type: str, elem_id, elem_label: str,
                 pattern: str, mass_kg: float) -> None:
        contributions.append(
            MassContribution(source_type, elem_id, elem_label, pattern, mass_kg)
        )

    for frame in scene.frames.values():
        sec = getattr(frame, "section", None)
        mat = getattr(sec, "material", None) if sec else None
        if mat is None:
            continue

        params = sec.profile_params or {}
        A = float(params.get("Area", 0.0))
        J = float(params.get("J", 0.0))
        I33 = float(params.get("I33", 0.0))
        I22 = float(params.get("I22", 0.0))

        L = frame.get_length()
        rho = float(getattr(mat, "density", 0.0))
        if A <= 0 or L <= 0 or rho <= 0:
            continue

        m_ton = A * L * rho
        m_kg = m_ton * MEGAGRAM

        ki = node_key_map.get(getattr(frame.node_i, "unique_id", None))
        kj = node_key_map.get(getattr(frame.node_j, "unique_id", None))
        _add(ki, m_kg / 2.0)
        _add(kj, m_kg / 2.0)
        _contrib("frame_self", frame.unique_id, frame.label, "", m_kg)

        dofs_i = getattr(frame.node_i, "dof_indices", None)
        dofs_j = getattr(frame.node_j, "dof_indices", None)
        if not dofs_i or not dofs_j:
            continue

        p1 = (frame.node_i.x, frame.node_i.y, frame.node_i.z)
        p2 = (frame.node_j.x, frame.node_j.y, frame.node_j.z)
        T, _ = transformation_matrix(
            p1, p2, getattr(frame, "rotation_deg", 0.0) or 0.0
        )
        m_loc = local_consistent_mass(
            A=A, L=L, rho=rho, J=J, I33=I33, I22=I22
        )
        m_glob_ton = T.T @ m_loc @ T
        dofs = list(dofs_i) + list(dofs_j)
        _push_block(rows, cols, vals, dofs, m_glob_ton)

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

            _lump_to_node(lumped_diag, frame.node_i, half, num_dofs)
            _lump_to_node(lumped_diag, frame.node_j, half, num_dofs)

    for area in scene.areas.values():
        nodes = getattr(area, "nodes", [])
        n_nodes = len(nodes)
        if n_nodes < 3:
            continue
        area_sec = getattr(area, "area_section", None)
        thickness = float(getattr(area, "thickness", 0.0) or 0.0)
        if thickness == 0.0 and area_sec is not None:
            thickness = float(getattr(area_sec, "thickness", 0.0) or 0.0)
        if thickness <= 0:
            continue
        mat = getattr(area, "material", None) or (getattr(area_sec, "material", None) if area_sec else None)
        if mat is None:
            continue

        geom_A = _polygon_area_3d(nodes)
        rho = float(getattr(mat, "density", 0.0))
        if geom_A <= 0 or rho <= 0:
            continue

        m_ton = geom_A * thickness * rho
        m_kg = m_ton * MEGAGRAM
        per_node = m_kg / n_nodes
        for nd in nodes:
            _add(node_key_map.get(getattr(nd, "unique_id", None)), per_node)
        _contrib("area_self", area.unique_id, area.label, "", m_kg)

        for i in range(1, n_nodes - 1):
            tri_nodes = [nodes[0], nodes[i], nodes[i + 1]]
            m_tri_ton = triangle_consistent_mass_3d(tri_nodes, thickness, mat)
            if m_tri_ton.size == 0:
                continue

            tri_dofs: list[int] = []
            ok = True
            for nd in tri_nodes:
                dofs = getattr(nd, "dof_indices", None)
                if not dofs:
                    ok = False
                    break
                tri_dofs.extend(dofs)
            if not ok or len(tri_dofs) != 18:
                continue

            _push_block(rows, cols, vals, tri_dofs, m_tri_ton)

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
            val = abs(float(getattr(load, "value", 0.0)))
            if val <= 0:
                continue

            mass_kg = (val * geom_A) / G_M_S2
            contrib_kg = mass_kg * factor
            per_node = contrib_kg / n

            for nd in area.nodes:
                _add(node_key_map.get(getattr(nd, "unique_id", None)), per_node)
                _lump_to_node(lumped_diag, nd, per_node, num_dofs)
            _contrib("area_uniform", area.unique_id, area.label, pat, mass_kg)

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
            val = abs(float(getattr(load, "value", 0.0)))
            if val <= 0:
                continue

            mass_kg = (val * geom_A) / G_M_S2
            contrib_kg = mass_kg * factor
            per_node = contrib_kg / n

            for nd in area.nodes:
                _add(node_key_map.get(getattr(nd, "unique_id", None)), per_node)
                _lump_to_node(lumped_diag, nd, per_node, num_dofs)
            _contrib("area_to_frame", area.unique_id, area.label, pat, mass_kg)

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
            _lump_to_node(lumped_diag, node, contrib_kg, num_dofs)

    nz = np.flatnonzero(lumped_diag > 0.0).astype(np.int32)
    if nz.size > 0:
        rows.append(nz)
        cols.append(nz)
        vals.append(lumped_diag[nz])

    if rows:
        M = sparse.coo_matrix(
            (np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
            shape=(num_dofs, num_dofs),
        ).tocsc()
        M = 0.5 * (M + M.T)
    else:
        M = sparse.csc_matrix((num_dofs, num_dofs), dtype=float)

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
        from app.commands.analysis.validation import validate_mass
        for e in validate_mass(asm, is_consistent=True):
            asm.warnings.append(e)
            logger.error("[Mass] %s", e)

    return asm