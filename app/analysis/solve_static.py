# app/analysis/solve_static.py
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from app.analysis.frame_resolver import (
    frame_load_direction_vector,
    resolve_frame_kinematics,
    resolve_section,
)

from app.analysis.mesher import SolverMesh, build_solver_mesh
from app.analysis.stiffness_assembly import transformation_matrix
from app.analysis.validation import validate_model
from core.units import UnitSystem, convert_project_units
from data.enums import LoadDirection
from domain.definition import (
    FrameDistributedLoad,
    LoadCase,
    LoadPattern,
    PointLoad,
    StaticLoadAssignment,
)
from domain.element import Area, Frame, Node

from logging_config import CadLogger
logger = CadLogger.get(__name__)


_GRAVITY_MM_S2 = 9806.65


@dataclass
class StaticCaseResult:
    case_name: str
    displacements: np.ndarray
    reactions: np.ndarray
    applied_forces: np.ndarray
    node_displacements: dict[str, np.ndarray] = field(default_factory=dict)
    node_reactions: dict[str, np.ndarray] = field(default_factory=dict)
    sum_F: np.ndarray = field(default_factory=lambda: np.zeros(6))
    sum_R: np.ndarray = field(default_factory=lambda: np.zeros(6))
    sum_M_about_origin: np.ndarray = field(default_factory=lambda: np.zeros(3))

def _node_dof_base(dof_map: dict[str, int], node: Node) -> int | None:
    return dof_map.get(f"N_{node.unique_id}")


def _add_point_load_to_dof(F: np.ndarray, base: int, load: PointLoad, scale: float) -> None:
    F[base + 0] += scale * float(load.fx)
    F[base + 1] += scale * float(load.fy)
    F[base + 2] += scale * float(load.fz)
    F[base + 3] += scale * float(load.mx)
    F[base + 4] += scale * float(load.my)
    F[base + 5] += scale * float(load.mz)


def _is_released(rel: dict | None, keys: tuple[str, ...]) -> bool:
    if not rel:
        return False
    if isinstance(rel, dict):
        return any(bool(rel.get(k, False)) for k in keys)
    return any(bool(getattr(rel, k, False)) for k in keys)


def _apply_release_mask(f_loc: np.ndarray, release_i: dict | None, release_j: dict | None) -> None:
    dof_keys = (
        ("U1", "u1", "R1"),
        ("U2", "u2"),
        ("U3", "u3"),
        ("R4", "r1"),
        ("R2", "r2"),
        ("R3", "r3"),
    )
    for idx, keys in enumerate(dof_keys):
        if _is_released(release_i, keys):
            f_loc[idx] = 0.0
        if _is_released(release_j, keys):
            f_loc[6 + idx] = 0.0


def _trapezoidal_fef_transverse(a: float, b: float, q1: float, q2: float, L: float) -> tuple[float, float, float, float]:
    seg_len = b - a
    if seg_len <= 1e-12 or L <= 1e-12:
        return 0.0, 0.0, 0.0, 0.0

    xi = np.array([0.5 - math.sqrt(3.0 / 5.0) * 0.5, 0.5, 0.5 + math.sqrt(3.0 / 5.0) * 0.5])
    wi = np.array([5.0 / 18.0, 8.0 / 18.0, 5.0 / 18.0])

    ri = 0.0
    rj = 0.0
    mi = 0.0
    mj = 0.0

    for s, w in zip(xi, wi):
        x = a + s * seg_len
        q = q1 + s * (q2 - q1)
        u = x / L
        u2 = u * u
        u3 = u2 * u

        n1 = 1.0 - 3.0 * u2 + 2.0 * u3
        n2 = L * (u - 2.0 * u2 + u3)
        n3 = 3.0 * u2 - 2.0 * u3
        n4 = L * (-u2 + u3)

        dw = q * w * seg_len
        ri += dw * n1
        mi += dw * n2
        rj += dw * n3
        mj += dw * n4

    return ri, mi, rj, mj


def _trapezoidal_fef_axial(a: float, b: float, q1: float, q2: float, L: float) -> tuple[float, float]:
    seg_len = b - a
    if seg_len <= 1e-12 or L <= 1e-12:
        return 0.0, 0.0

    xm = 0.5 * (a + b)
    qm = 0.5 * (q1 + q2)
    dq = q2 - q1
    f_total = qm * seg_len
    x_cg = xm + (dq * seg_len) / (12.0 * qm) if abs(qm) > 1e-15 else xm

    fi = f_total * (1.0 - x_cg / L)
    fj = f_total * (x_cg / L)
    return fi, fj


def _add_uniform_local_vector_fef(f_loc: np.ndarray, q_loc: np.ndarray, L: float) -> None:
    qx = float(q_loc[0])
    qy = float(q_loc[1])
    qz = float(q_loc[2])

    if abs(qx) > 1e-15:
        f_loc[0] += 0.5 * qx * L
        f_loc[6] += 0.5 * qx * L

    if abs(qy) > 1e-15:
        f_loc[1] += 0.5 * qy * L
        f_loc[5] += (qy * L * L) / 12.0
        f_loc[7] += 0.5 * qy * L
        f_loc[11] -= (qy * L * L) / 12.0

    if abs(qz) > 1e-15:
        f_loc[2] += 0.5 * qz * L
        f_loc[4] -= (qz * L * L) / 12.0
        f_loc[8] += 0.5 * qz * L
        f_loc[10] += (qz * L * L) / 12.0


def _assemble_frame_distributed_load(
    F: np.ndarray,
    frame: Frame,
    dload: FrameDistributedLoad,
    base_i: int,
    base_j: int,
    scale: float,
) -> None:
    if not dload.segments:
        return

    sec_res = resolve_section(getattr(frame, "section", None), getattr(frame, "modifiers", None))
    kin = resolve_frame_kinematics(frame, sec_res)
    if kin.L_axis <= 1e-12 or kin.L_clear <= 1e-12:
        return

    dir_vec, proj_factor = frame_load_direction_vector(
        kin.R_axis, kin.L_axis, dload.coord_sys, dload.load_dir, dload.direction
    )
    if proj_factor == 0.0:
        return

    local_dir = kin.R_axis @ (dir_vec * proj_factor)
    is_moment = str(dload.force_or_moment or "Force").strip().lower().startswith("m")

    L_axis = kin.L_axis
    L_clear = kin.L_clear
    x0_clear = kin.eff_off_i

    f_loc_clear = np.zeros(12, dtype=float)

    for seg in dload.segments:
        x1 = float(seg.x1) * L_axis if dload.is_relative else float(seg.x1)
        x2 = float(seg.x2) * L_axis if dload.is_relative else float(seg.x2)
        a_full = max(0.0, min(L_axis, x1))
        b_full = max(0.0, min(L_axis, x2))
        if b_full <= a_full + 1e-12:
            continue

        a = max(0.0, min(L_clear, a_full - x0_clear))
        b = max(0.0, min(L_clear, b_full - x0_clear))
        if b <= a + 1e-12:
            continue

        t_a = (a + x0_clear - a_full) / (b_full - a_full)
        t_b = (b + x0_clear - a_full) / (b_full - a_full)
        q1_raw = float(seg.q1) * scale
        q2_raw = float(seg.q2) * scale
        q1 = q1_raw + (q2_raw - q1_raw) * t_a
        q2 = q1_raw + (q2_raw - q1_raw) * t_b

        if is_moment:
            for comp in range(3):
                qc1 = q1 * float(local_dir[comp])
                qc2 = q2 * float(local_dir[comp])
                if abs(qc1) <= 1e-15 and abs(qc2) <= 1e-15:
                    continue
                mi, mj = _trapezoidal_fef_axial(a, b, qc1, qc2, L_clear)
                f_loc_clear[3 + comp] += mi
                f_loc_clear[9 + comp] += mj
        else:
            qx1, qx2 = q1 * float(local_dir[0]), q2 * float(local_dir[0])
            if abs(qx1) > 1e-15 or abs(qx2) > 1e-15:
                fi1, fj1 = _trapezoidal_fef_axial(a, b, qx1, qx2, L_clear)
                f_loc_clear[0] += fi1
                f_loc_clear[6] += fj1

            qy1, qy2 = q1 * float(local_dir[1]), q2 * float(local_dir[1])
            if abs(qy1) > 1e-15 or abs(qy2) > 1e-15:
                ri2, mi3, rj2, mj3 = _trapezoidal_fef_transverse(a, b, qy1, qy2, L_clear)
                f_loc_clear[1] += ri2
                f_loc_clear[5] += mi3
                f_loc_clear[7] += rj2
                f_loc_clear[11] += mj3

            qz1, qz2 = q1 * float(local_dir[2]), q2 * float(local_dir[2])
            if abs(qz1) > 1e-15 or abs(qz2) > 1e-15:
                ri3, mi2, rj3, mj2 = _trapezoidal_fef_transverse(a, b, qz1, qz2, L_clear)
                f_loc_clear[2] += ri3
                f_loc_clear[4] -= mi2
                f_loc_clear[8] += rj3
                f_loc_clear[10] -= mj2

    rel_i = frame.release_i or {}
    for idx, keys in enumerate((("R1", "u1"), ("U2", "u2"), ("U3", "u3"), ("R4", "r1"), ("R2", "r2"), ("R3", "r3"))):
        if any(rel_i.get(k, False) for k in keys):
            f_loc_clear[idx] = 0.0

    rel_j = frame.release_j or {}
    for idx, keys in enumerate((("R1", "u1"), ("U2", "u2"), ("U3", "u3"), ("R4", "r1"), ("R2", "r2"), ("R3", "r3"))):
        if any(rel_j.get(k, False) for k in keys):
            f_loc_clear[6 + idx] = 0.0

    f_node_loc = kin.T_ecc.T @ (kin.H.T @ f_loc_clear)
    f_glob = kin.T_axis.T @ f_node_loc

    F[base_i : base_i + 6] += f_glob[:6]
    F[base_j : base_j + 6] += f_glob[6:12]


def _area_local_axes(nodes: list[Node]) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    pts = np.array([[nd.x, nd.y, nd.z] for nd in nodes], dtype=float)
    n_pts = len(pts)
    if n_pts < 3:
        return np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0]), 0.0

    normal = np.zeros(3, dtype=float)
    for i in range(n_pts):
        p1, p2 = pts[i], pts[(i + 1) % n_pts]
        normal[0] += (p1[1] - p2[1]) * (p1[2] + p2[2])
        normal[1] += (p1[2] - p2[2]) * (p1[0] + p2[0])
        normal[2] += (p1[0] - p2[0]) * (p1[1] + p2[1])

    norm_len = float(np.linalg.norm(normal))
    area_val = 0.5 * norm_len
    if norm_len <= 1e-12:
        return np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0]), 0.0

    e3 = normal / norm_len
    e1 = pts[1] - pts[0]
    e1 = e1 - np.dot(e1, e3) * e3
    e1_len = float(np.linalg.norm(e1))
    if e1_len <= 1e-12:
        ref = np.array([1.0, 0.0, 0.0]) if abs(e3[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        e1 = np.cross(ref, e3)
        e1 /= np.linalg.norm(e1)
    else:
        e1 /= e1_len
    e2 = np.cross(e3, e1)
    return e1, e2, e3, area_val


def _area_load_force_vector(
    e1: np.ndarray,
    e2: np.ndarray,
    e3: np.ndarray,
    coord_sys: str,
    load_dir: str,
    value: float,
    direction: LoadDirection | None = None,
) -> np.ndarray:
    v = float(value)

    if direction is not None:
        if direction == LoadDirection.LOCAL_1:
            return v * e1
        if direction == LoadDirection.LOCAL_2:
            return v * e2
        if direction == LoadDirection.LOCAL_3:
            return v * e3
        if direction == LoadDirection.GLOBAL_X:
            return np.array([v, 0.0, 0.0])
        if direction == LoadDirection.GLOBAL_Y:
            return np.array([0.0, v, 0.0])
        if direction == LoadDirection.GLOBAL_Z:
            return np.array([0.0, 0.0, v])
        if direction == LoadDirection.PROJECTED_X:
            proj = math.hypot(float(e3[1]), float(e3[2]))
            return np.array([v * proj, 0.0, 0.0])
        if direction == LoadDirection.PROJECTED_Y:
            proj = math.hypot(float(e3[0]), float(e3[2]))
            return np.array([0.0, v * proj, 0.0])
        if direction == LoadDirection.PROJECTED_Z:
            proj = math.hypot(float(e3[0]), float(e3[1]))
            return np.array([0.0, 0.0, v * proj])
        if direction == LoadDirection.GRAVITY:
            return np.array([0.0, 0.0, -v])

    cs = str(coord_sys or "GLOBAL").strip().upper()
    ld = str(load_dir or "GRAVITY").strip().upper()

    if cs == "LOCAL":
        if ld in ("1", "X"):
            return v * e1
        if ld in ("2", "Y"):
            return v * e2
        if ld in ("3", "Z"):
            return v * e3
        return v * e3

    if ld in ("1", "4", "X"):
        return np.array([v, 0.0, 0.0])
    if ld in ("2", "5", "Y"):
        return np.array([0.0, v, 0.0])
    if ld in ("3", "6", "Z"):
        return np.array([0.0, 0.0, v])
    if ld in ("7", "PX"):
        proj = math.hypot(float(e3[1]), float(e3[2]))
        return np.array([v * proj, 0.0, 0.0])
    if ld in ("8", "PY"):
        proj = math.hypot(float(e3[0]), float(e3[2]))
        return np.array([0.0, v * proj, 0.0])
    if ld in ("9", "PZ"):
        proj = math.hypot(float(e3[0]), float(e3[1]))
        return np.array([0.0, 0.0, v * proj])
    if ld in ("10", "GRAV", "GRAVITY"):
        return np.array([0.0, 0.0, -v])

    return np.array([0.0, 0.0, -v])


def _assemble_area_loads(
    F: np.ndarray,
    dof_map: dict[str, int],
    area: Area,
    pattern_name: str,
    scale: float,
    self_weight_mult: float,
) -> None:
    nodes = getattr(area, "nodes", None) or []
    n_nodes = len(nodes)
    if n_nodes < 3:
        return

    e1, e2, e3, geom_area = _area_local_axes(nodes)
    if geom_area <= 1e-12:
        return

    bases = [_node_dof_base(dof_map, nd) for nd in nodes]
    if any(b is None for b in bases):
        return

    total_force = np.zeros(3, dtype=float)

    for uload in getattr(area, "uniform_loads", None) or []:
        if uload.pattern_name == pattern_name:
            f_vec = _area_load_force_vector(
                e1, e2, e3,
                uload.coordinate_system,
                "",
                uload.value,
                uload.direction,
            )
            total_force += scale * geom_area * f_vec

    for utfload in getattr(area, "uniform_to_frame_loads", None) or []:
        if utfload.pattern_name == pattern_name:
            f_vec = _area_load_force_vector(
                e1, e2, e3,
                utfload.coordinate_system,
                "",
                utfload.value,
                utfload.direction,
            )
            total_force += scale * geom_area * f_vec

    for gload in getattr(area, "gravity_loads", None) or []:
        if gload.pattern_name == pattern_name:
            area_sec = getattr(area, "area_section", None)
            mat = getattr(area, "material", None) or (getattr(area_sec, "material", None) if area_sec else None)
            if mat is not None:
                density = float(getattr(mat, "density", 0.0))
                thick = float(getattr(area, "thickness", 0.0))
                mass_per_area = density * thick
                if area_sec is not None and float(getattr(area_sec, "weight", 0.0)) > 0.0:
                    w_unit = float(area_sec.weight) * geom_area
                else:
                    w_unit = mass_per_area * geom_area * _GRAVITY_MM_S2
                g_vec = np.array(
                    [float(gload.multiplier_x), float(gload.multiplier_y), float(gload.multiplier_z)],
                    dtype=float,
                )
                total_force += scale * w_unit * g_vec

    if self_weight_mult != 0.0:
        area_sec = getattr(area, "area_section", None)
        mat = getattr(area, "material", None) or (getattr(area_sec, "material", None) if area_sec else None)
        if mat is not None:
            density = float(getattr(mat, "density", 0.0))
            thick = float(getattr(area, "thickness", 0.0))
            if area_sec is not None and float(getattr(area_sec, "weight", 0.0)) > 0.0:
                sw_force = float(area_sec.weight) * geom_area
            else:
                sw_force = density * thick * geom_area * _GRAVITY_MM_S2
            total_force[2] -= scale * self_weight_mult * sw_force

    if np.linalg.norm(total_force) <= 1e-15:
        return

    nodal_f = total_force / float(n_nodes)
    for base in bases:
        F[base : base + 3] += nodal_f


def assemble_pattern_load_vector(
    mesh: SolverMesh,
    dof_map: dict[str, int],
    num_dofs: int,
    pattern_name: str,
    pattern: LoadPattern | None = None,
    scale: float = 1.0,
) -> np.ndarray:
    F = np.zeros(num_dofs, dtype=float)
    if scale == 0.0:
        return F

    sw_mult = float(getattr(pattern, "self_wt_mult", 0.0)) if pattern is not None else 0.0

    for n_key, node in mesh.nodes.items():
        if n_key in mesh.internal_node_keys:
            continue
        base = dof_map.get(n_key)
        if base is None:
            continue
        for p_load in getattr(node, "loads", None) or []:
            if p_load.pattern_name == pattern_name:
                _add_point_load_to_dof(F, base, p_load, scale)

    for frame in mesh.frames.values():
        ni = getattr(frame, "node_i", None)
        nj = getattr(frame, "node_j", None)
        if ni is None or nj is None:
            continue
        base_i = _node_dof_base(dof_map, ni)
        base_j = _node_dof_base(dof_map, nj)
        if base_i is None or base_j is None:
            continue

        sec_res = resolve_section(getattr(frame, "section", None), getattr(frame, "modifiers", None))
        kin = resolve_frame_kinematics(frame, sec_res)
        if kin.L_axis <= 1e-12 or kin.L_clear <= 1e-12:
            continue

        for dload in getattr(frame, "dist_loads", None) or []:
            if dload.pattern_name == pattern_name:
                _assemble_frame_distributed_load(F, frame, dload, base_i, base_j, scale)

        if sec_res is not None and sec_res.weight_per_len > 0.0:
            w_line = sec_res.weight_per_len
            L_clear = kin.L_clear
            f_grav_clear = np.zeros(12, dtype=float)

            for gload in getattr(frame, "gravity_loads", None) or []:
                if gload.pattern_name == pattern_name:
                    g_glob = np.array(
                        [float(gload.multiplier_x), float(gload.multiplier_y), float(gload.multiplier_z)],
                        dtype=float,
                    )
                    q_loc = (scale * w_line) * (kin.R_axis @ g_glob)
                    f_grav_clear[0] += 0.5 * q_loc[0] * L_clear
                    f_grav_clear[6] += 0.5 * q_loc[0] * L_clear
                    f_grav_clear[1] += 0.5 * q_loc[1] * L_clear
                    f_grav_clear[7] += 0.5 * q_loc[1] * L_clear
                    f_grav_clear[5] += q_loc[1] * (L_clear * L_clear) / 12.0
                    f_grav_clear[11] -= q_loc[1] * (L_clear * L_clear) / 12.0
                    f_grav_clear[2] += 0.5 * q_loc[2] * L_clear
                    f_grav_clear[8] += 0.5 * q_loc[2] * L_clear
                    f_grav_clear[4] -= q_loc[2] * (L_clear * L_clear) / 12.0
                    f_grav_clear[10] += q_loc[2] * (L_clear * L_clear) / 12.0

            if sw_mult != 0.0:
                q_loc = (scale * sw_mult * w_line) * (kin.R_axis @ np.array([0.0, 0.0, -1.0]))
                f_grav_clear[0] += 0.5 * q_loc[0] * L_clear
                f_grav_clear[6] += 0.5 * q_loc[0] * L_clear
                f_grav_clear[1] += 0.5 * q_loc[1] * L_clear
                f_grav_clear[7] += 0.5 * q_loc[1] * L_clear
                f_grav_clear[5] += q_loc[1] * (L_clear * L_clear) / 12.0
                f_grav_clear[11] -= q_loc[1] * (L_clear * L_clear) / 12.0
                f_grav_clear[2] += 0.5 * q_loc[2] * L_clear
                f_grav_clear[8] += 0.5 * q_loc[2] * L_clear
                f_grav_clear[4] -= q_loc[2] * (L_clear * L_clear) / 12.0
                f_grav_clear[10] += q_loc[2] * (L_clear * L_clear) / 12.0

            if np.any(f_grav_clear != 0.0):
                rel_i = frame.release_i or {}
                for idx, keys in enumerate((("R1", "u1"), ("U2", "u2"), ("U3", "u3"), ("R4", "r1"), ("R2", "r2"), ("R3", "r3"))):
                    if any(rel_i.get(k, False) for k in keys):
                        f_grav_clear[idx] = 0.0

                rel_j = frame.release_j or {}
                for idx, keys in enumerate((("R1", "u1"), ("U2", "u2"), ("U3", "u3"), ("R4", "r1"), ("R2", "r2"), ("R3", "r3"))):
                    if any(rel_j.get(k, False) for k in keys):
                        f_grav_clear[6 + idx] = 0.0

                f_node_loc = kin.T_ecc.T @ (kin.H.T @ f_grav_clear)
                f_glob = kin.T_axis.T @ f_node_loc
                F[base_i : base_i + 6] += f_glob[:6]
                F[base_j : base_j + 6] += f_glob[6:12]

    for area in mesh.areas.values():
        _assemble_area_loads(F, dof_map, area, pattern_name, scale, sw_mult)

    return F


def _assemble_accel_load_vector(
    M_global: np.ndarray,
    num_dofs: int,
    accel_dir: str,
    scale: float,
) -> np.ndarray:
    axis_idx = {
        "UX": 0, "X": 0, "1": 0,
        "UY": 1, "Y": 1, "2": 1,
        "UZ": 2, "Z": 2, "3": 2,
        "RX": 3, "4": 3,
        "RY": 4, "5": 4,
        "RZ": 5, "6": 5,
    }.get(str(accel_dir or "").strip().upper())

    if axis_idx is None or scale == 0.0:
        return np.zeros(num_dofs, dtype=float)

    r = np.zeros(num_dofs, dtype=float)
    r[axis_idx::6] = 1.0
    return -float(scale) * (M_global @ r)


def assemble_load_case_vector(project, mesh, dof_map, num_dofs, load_case, M_global=None):
    F = np.zeros(num_dofs, dtype=float)
    patterns = getattr(project, "load_patterns", None) or {}
    logger.info("[load_case] case=%r patterns=%d dof_map=%d mesh_frames=%d",
                getattr(load_case, "name", "?"), len(patterns), len(dof_map),
                len(mesh.frames) if hasattr(mesh, "frames") else -1)
    assignments = getattr(load_case, "static_assignments", None) or []
    logger.info("[load_case] assignments=%d", len(assignments))
    for item in assignments:
        ltype = str(item.load_type or "Load pattern").strip().lower()
        sf = float(item.load_sf)
        logger.info("[load_case] item: ltype=%r sf=%.3f name=%r pat=%s",
                    ltype, sf, item.load_name,
                    patterns.get(item.load_name) is not None)
        if sf == 0.0:
            continue
        if ltype in ("load pattern", "pattern", "load"):
            pat = patterns.get(item.load_name)
            n_before = np.count_nonzero(np.abs(F) > 1e-9)
            F += assemble_pattern_load_vector(
                mesh=mesh, dof_map=dof_map, num_dofs=num_dofs,
                pattern_name=item.load_name, pattern=pat, scale=sf,
            )
            n_after = np.count_nonzero(np.abs(F) > 1e-9)
            logger.info("[load_case] after pattern: nonzero %d -> %d, |F|=%.3e",
                        n_before, n_after, np.linalg.norm(F))
    return F


def solve_static_case(
    project,
    solver,
    mesh: SolverMesh,
    case_name: str,
) -> StaticCaseResult:
    load_case = (getattr(project, "load_cases", None) or {}).get(case_name)
    if load_case is None:
        raise KeyError(f"LoadCase bulunamadı: {case_name}")

    dof_map = solver.dof_map
    num_dofs = solver.num_dofs
    M_global = getattr(solver, "M", None)

    F = assemble_load_case_vector(
        project=project,
        mesh=mesh,
        dof_map=dof_map,
        num_dofs=num_dofs,
        load_case=load_case,
        M_global=M_global,
    )
    logger.info("[solve_static_case] %s: |F|=%.6e, nonzero=%d, free_dofs=%d, num_dofs=%d",
                case_name, np.linalg.norm(F), np.count_nonzero(np.abs(F) > 1e-9),
                solver.free_dofs.size, solver.num_dofs)
    U, R = solver.static_solve(F)
    logger.info("[solve_static_case] %s: |U|=%.6e, |R|=%.6e",
                case_name, np.linalg.norm(U), np.linalg.norm(R))
    node_disp: dict[str, np.ndarray] = {}
    node_reac: dict[str, np.ndarray] = {}
    node_coords: dict[str, np.ndarray] = {}
    for n_key, base in dof_map.items():
        node_disp[n_key] = U[base : base + 6].copy()
        node_reac[n_key] = R[base : base + 6].copy()
        node = mesh.nodes.get(n_key)
        if node:
            node_coords[n_key] = (node.x, node.y, node.z)

    # GLOBAL DENGE
    sum_F = np.array([np.sum(F[i::6]) for i in range(6)])
    sum_R = np.array([np.sum(R[i::6]) for i in range(6)])

    # Moment dengesi: her düğüm için r × F ve r × R
    sum_M_about_origin = np.zeros(3)
    for n_key, base in dof_map.items():
        if n_key not in node_coords:
            continue
        x, y, z = node_coords[n_key]
        # Dış kuvvetlerin momenti
        fx, fy, fz = F[base], F[base+1], F[base+2]
        mx, my, mz = F[base+3], F[base+4], F[base+5]
        sum_M_about_origin[0] += mx + y*fz - z*fy
        sum_M_about_origin[1] += my + z*fx - x*fz
        sum_M_about_origin[2] += mz + x*fy - y*fx
        # Reaksiyonların momenti
        rx, ry, rz = R[base], R[base+1], R[base+2]
        rmx, rmy, rmz = R[base+3], R[base+4], R[base+5]
        sum_M_about_origin[0] += rmx + y*rz - z*ry
        sum_M_about_origin[1] += rmy + z*rx - x*rz
        sum_M_about_origin[2] += rmz + x*ry - y*rx
    
    return StaticCaseResult(
        case_name=case_name,
        displacements=U,
        reactions=R,
        applied_forces=F,
        node_displacements=node_disp,
        node_reactions=node_reac,
        sum_F=sum_F,
        sum_R=sum_R,
        sum_M_about_origin=sum_M_about_origin,
    )


def run_static_analysis(project, case_names=None, *, n_live=0.3, validate=True, use_shear_deform=True):
    from app.analysis.mass_assembly import build_mass
    from app.analysis.solver import StructuralSolver
    from app.analysis.stiffness_assembly import build_stiffness, ensure_dof_indices

    convert_project_units(project, UnitSystem.N_MM, reason="static_analysis")
    model = project.math_model
    if validate:
        validate_model(model, project, strict=True)

    mesh = build_solver_mesh(model)
    mass_asm = build_mass(mesh, project, n_live=n_live, validate=validate)
    stiff_asm = build_stiffness(mesh, project, validate=validate, use_shear_deform=use_shear_deform)

    # 🔥 KRİTİK DÜZELTME: dof_map'i ensure_dof_indices ile GARANTİLE
    dof_map = ensure_dof_indices(mesh)
    if len(dof_map) != len(mesh.nodes):
        raise RuntimeError(
            f"dof_map boş/eksik: mesh.nodes={len(mesh.nodes)}, dof_map={len(dof_map)}. "
            f"build_stiffness dof_indices'i siliyor olabilir."
        )

    solver = StructuralSolver(
        K_global=stiff_asm.K_global,
        M_global=mass_asm.M_global,
        num_dofs=mass_asm.num_dofs,
        dof_map=dof_map,
        nodes=mesh.nodes,
    )

    all_cases = getattr(project, "load_cases", None) or {}
    targets = case_names if case_names is not None else [...]
    results = {}
    for cname in targets:
        results[cname] = solve_static_case(project, solver, mesh, cname)
    return results