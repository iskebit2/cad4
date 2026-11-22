# app/commands/analysis\solve_static.py
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from app.commands.analysis.mesher import SolverMesh, build_solver_mesh
from app.commands.analysis.stiffness_assembly import transformation_matrix
from app.commands.analysis.validation import validate_model
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

_GRAVITY_MM_S2 = 9806.65


@dataclass
class StaticCaseResult:
    case_name: str
    displacements: np.ndarray
    reactions: np.ndarray
    applied_forces: np.ndarray
    node_displacements: dict[str, np.ndarray] = field(default_factory=dict)
    node_reactions: dict[str, np.ndarray] = field(default_factory=dict)


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


def _direction_vector(
    frame: Frame,
    R: np.ndarray,
    coord_sys: str,
    load_dir: str,
    direction: LoadDirection | None,
) -> tuple[np.ndarray, float]:
    L = frame.get_length()
    if L <= 1e-12:
        return np.zeros(3, dtype=float), 0.0

    e1 = R[0]
    e2 = R[1]
    e3 = R[2]
    proj_xy = math.hypot(float(e1[0]), float(e1[1]))
    proj_xz = math.hypot(float(e1[0]), float(e1[2]))
    proj_yz = math.hypot(float(e1[1]), float(e1[2]))

    if direction is not None:
        if direction == LoadDirection.LOCAL_1:
            return e1, 1.0
        if direction == LoadDirection.LOCAL_2:
            return e2, 1.0
        if direction == LoadDirection.LOCAL_3:
            return e3, 1.0
        if direction == LoadDirection.GLOBAL_X:
            return np.array([1.0, 0.0, 0.0]), 1.0
        if direction == LoadDirection.GLOBAL_Y:
            return np.array([0.0, 1.0, 0.0]), 1.0
        if direction == LoadDirection.GLOBAL_Z:
            return np.array([0.0, 0.0, 1.0]), 1.0
        if direction == LoadDirection.PROJECTED_X:
            return np.array([1.0, 0.0, 0.0]), proj_yz
        if direction == LoadDirection.PROJECTED_Y:
            return np.array([0.0, 1.0, 0.0]), proj_xz
        if direction == LoadDirection.PROJECTED_Z:
            return np.array([0.0, 0.0, 1.0]), proj_xy

    cs = str(coord_sys or "GLOBAL").strip().upper()
    ld = str(load_dir or "").strip().upper()

    if cs == "LOCAL":
        if ld in ("1", "X"):
            return e1, 1.0
        if ld in ("2", "Y"):
            return e2, 1.0
        if ld in ("3", "Z"):
            return e3, 1.0
        return e2, 1.0

    if ld in ("1", "4", "X", "UX", "FX"):
        return np.array([1.0, 0.0, 0.0]), 1.0
    if ld in ("2", "5", "Y", "UY", "FY"):
        return np.array([0.0, 1.0, 0.0]), 1.0
    if ld in ("3", "6", "Z", "UZ", "FZ"):
        return np.array([0.0, 0.0, 1.0]), 1.0
    if ld in ("7", "PX"):
        return np.array([1.0, 0.0, 0.0]), proj_yz
    if ld in ("8", "PY"):
        return np.array([0.0, 1.0, 0.0]), proj_xz
    if ld in ("9", "PZ"):
        return np.array([0.0, 0.0, 1.0]), proj_xy
    if ld in ("10", "GRAV", "GRAVITY"):
        return np.array([0.0, 0.0, -1.0]), 1.0

    return np.array([0.0, 0.0, -1.0]), 1.0


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
    f_loc: np.ndarray,
    frame: Frame,
    R: np.ndarray,
    L: float,
    dload: FrameDistributedLoad,
    scale: float,
) -> None:
    if L <= 1e-12 or not dload.segments:
        return

    dir_vec, proj_factor = _direction_vector(
        frame, R, dload.coord_sys, dload.load_dir, dload.direction
    )
    if proj_factor == 0.0:
        return

    local_dir = R @ (dir_vec * proj_factor)
    is_moment = str(dload.force_or_moment or "Force").strip().lower().startswith("m")

    for seg in dload.segments:
        x1 = float(seg.x1) * L if dload.is_relative else float(seg.x1)
        x2 = float(seg.x2) * L if dload.is_relative else float(seg.x2)
        a = max(0.0, min(L, x1))
        b = max(0.0, min(L, x2))
        if b <= a + 1e-12:
            continue

        q1 = float(seg.q1) * scale
        q2 = float(seg.q2) * scale

        if is_moment:
            for comp in range(3):
                qc1 = q1 * float(local_dir[comp])
                qc2 = q2 * float(local_dir[comp])
                if abs(qc1) <= 1e-15 and abs(qc2) <= 1e-15:
                    continue
                mi, mj = _trapezoidal_fef_axial(a, b, qc1, qc2, L)
                f_loc[3 + comp] += mi
                f_loc[9 + comp] += mj
        else:
            qx1, qx2 = q1 * float(local_dir[0]), q2 * float(local_dir[0])
            if abs(qx1) > 1e-15 or abs(qx2) > 1e-15:
                fi1, fj1 = _trapezoidal_fef_axial(a, b, qx1, qx2, L)
                f_loc[0] += fi1
                f_loc[6] += fj1

            qy1, qy2 = q1 * float(local_dir[1]), q2 * float(local_dir[1])
            if abs(qy1) > 1e-15 or abs(qy2) > 1e-15:
                ri2, mi3, rj2, mj3 = _trapezoidal_fef_transverse(a, b, qy1, qy2, L)
                f_loc[1] += ri2
                f_loc[5] += mi3
                f_loc[7] += rj2
                f_loc[11] += mj3

            qz1, qz2 = q1 * float(local_dir[2]), q2 * float(local_dir[2])
            if abs(qz1) > 1e-15 or abs(qz2) > 1e-15:
                ri3, mi2, rj3, mj2 = _trapezoidal_fef_transverse(a, b, qz1, qz2, L)
                f_loc[2] += ri3
                f_loc[4] -= mi2
                f_loc[8] += rj3
                f_loc[10] -= mj2


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
        ni, nj = frame.node_i, frame.node_j
        if ni is None or nj is None:
            continue
        base_i = _node_dof_base(dof_map, ni)
        base_j = _node_dof_base(dof_map, nj)
        if base_i is None or base_j is None:
            continue

        L = frame.get_length()
        if L <= 1e-12:
            continue

        T, L = transformation_matrix(
            (ni.x, ni.y, ni.z),
            (nj.x, nj.y, nj.z),
            getattr(frame, "rotation_deg", 0.0) or 0.0,
        )
        R = T[:3, :3]

        f_loc = np.zeros(12, dtype=float)

        for dload in frame.dist_loads:
            if dload.pattern_name == pattern_name:
                _assemble_frame_distributed_load(f_loc, frame, R, L, dload, scale)

        sec = getattr(frame, "section", None)
        mat = getattr(sec, "material", None) if sec is not None else None
        area_val = float(sec.profile_params.get("Area", 0.0)) if sec is not None else 0.0
        density = float(getattr(mat, "density", 0.0)) if mat is not None else 0.0
        w_line = density * area_val * _GRAVITY_MM_S2

        for gload in getattr(frame, "gravity_loads", None) or []:
            if gload.pattern_name == pattern_name and w_line > 0.0:
                g_glob = np.array(
                    [float(gload.multiplier_x), float(gload.multiplier_y), float(gload.multiplier_z)],
                    dtype=float,
                )
                q_loc = (scale * w_line) * (R @ g_glob)
                _add_uniform_local_vector_fef(f_loc, q_loc, L)

        if sw_mult != 0.0 and w_line > 0.0:
            q_loc = (scale * sw_mult * w_line) * (R @ np.array([0.0, 0.0, -1.0]))
            _add_uniform_local_vector_fef(f_loc, q_loc, L)

        if np.any(f_loc != 0.0):
            _apply_release_mask(f_loc, frame.release_i, frame.release_j)
            f_glob = T.T @ f_loc
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


def assemble_load_case_vector(
    project,
    mesh: SolverMesh,
    dof_map: dict[str, int],
    num_dofs: int,
    load_case: LoadCase,
    M_global: np.ndarray | None = None,
) -> np.ndarray:
    F = np.zeros(num_dofs, dtype=float)
    patterns = getattr(project, "load_patterns", None) or {}

    assignments: list[StaticLoadAssignment] = getattr(load_case, "static_assignments", None) or []
    for item in assignments:
        ltype = str(item.load_type or "Load pattern").strip().lower()
        sf = float(item.load_sf)
        if sf == 0.0:
            continue

        if ltype in ("load pattern", "pattern", "load"):
            pat = patterns.get(item.load_name)
            F += assemble_pattern_load_vector(
                mesh=mesh,
                dof_map=dof_map,
                num_dofs=num_dofs,
                pattern_name=item.load_name,
                pattern=pat,
                scale=sf,
            )
        elif ltype in ("accel", "acceleration") and M_global is not None:
            F += _assemble_accel_load_vector(
                M_global=M_global,
                num_dofs=num_dofs,
                accel_dir=item.load_name,
                scale=sf,
            )

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

    U, R = solver.static_solve(F)

    node_disp: dict[str, np.ndarray] = {}
    node_reac: dict[str, np.ndarray] = {}
    for n_key, base in dof_map.items():
        node_disp[n_key] = U[base : base + 6].copy()
        node_reac[n_key] = R[base : base + 6].copy()

    return StaticCaseResult(
        case_name=case_name,
        displacements=U,
        reactions=R,
        applied_forces=F,
        node_displacements=node_disp,
        node_reactions=node_reac,
    )


def run_static_analysis(
    project,
    case_names: list[str] | None = None,
    *,
    n_live: float = 0.3,
    validate: bool = True,
    use_shear_deform: bool = True,
) -> dict[str, StaticCaseResult]:
    from app.commands.analysis.mass_assembly import build_mass
    from app.commands.analysis.solver import StructuralSolver
    from app.commands.analysis.stiffness_assembly import build_stiffness

    convert_project_units(project, UnitSystem.N_MM, reason="static_analysis")
    model = project.math_model
    if validate:
        validate_model(model, project, strict=True)

    mesh = build_solver_mesh(model)
    mass_asm = build_mass(mesh, project, n_live=n_live, validate=validate)
    stiff_asm = build_stiffness(
        mesh,
        project,
        validate=validate,
        use_shear_deform=use_shear_deform,
    )

    dof_map = {
        n_key: int(node.dof_indices[0])
        for n_key, node in mesh.nodes.items()
        if getattr(node, "dof_indices", None)
    }

    solver = StructuralSolver(
        K_global=stiff_asm.K_global,
        M_global=mass_asm.M_global,
        num_dofs=mass_asm.num_dofs,
        dof_map=dof_map,
        nodes=mesh.nodes,
    )

    all_cases = getattr(project, "load_cases", None) or {}
    targets = case_names if case_names is not None else [
        cname for cname, lc in all_cases.items()
        if getattr(lc, "run_case", True)
        and str(getattr(lc, "case_type", "LinStatic")).lower() in ("linstatic", "linearstatic")
    ]

    results: dict[str, StaticCaseResult] = {}
    for cname in targets:
        results[cname] = solve_static_case(project, solver, mesh, cname)
    return results