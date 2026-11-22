# app/commands/analysis/force_recovery.py
from __future__ import annotations

import json
import math
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from app.commands.analysis.mesher import SolverMesh
from app.commands.analysis.solve_static import (
    _GRAVITY_MM_S2,
    _add_uniform_local_vector_fef,
    _apply_release_mask,
    _assemble_frame_distributed_load,
)
from app.commands.analysis.stiffness_assembly import (
    _rigid_offset_matrix,
    ensure_dof_indices,
    local_stiffness,
    transformation_matrix,
)
from domain.definition import LoadPattern
from domain.element import Frame

if TYPE_CHECKING:
    from app.commands.analysis.solve_static import StaticCaseResult
    from app.commands.analysis.structuralanalysis import StructuralAnalysisResult


@dataclass
class FrameStationForce:
    ratio: float
    x: float
    N: float
    V2: float
    V3: float
    T: float
    M2: float
    M3: float


@dataclass
class FrameForceResult:
    frame_id: int
    label: str
    case_name: str
    length: float
    end_i: np.ndarray
    end_j: np.ndarray
    stations: list[FrameStationForce] = field(default_factory=list)


def _frame_local_equivalent_nodal_loads(
    project,
    frame: Frame,
    R: np.ndarray,
    L: float,
    case_name: str,
) -> tuple[np.ndarray, list[tuple[float, float, np.ndarray, np.ndarray, bool]]]:
    f_eq = np.zeros(12, dtype=float)
    span_loads: list[tuple[float, float, np.ndarray, np.ndarray, bool]] = []

    load_case = (getattr(project, "load_cases", None) or {}).get(case_name)
    if load_case is None:
        return f_eq, span_loads

    patterns: dict[str, LoadPattern] = getattr(project, "load_patterns", None) or {}
    sec = getattr(frame, "section", None)
    mat = getattr(sec, "material", None) if sec is not None else None
    area_val = float(sec.profile_params.get("Area", 0.0)) if sec is not None else 0.0
    density = float(getattr(mat, "density", 0.0)) if mat is not None else 0.0
    w_line = density * area_val * _GRAVITY_MM_S2

    from app.commands.analysis.solve_static import _direction_vector

    for item in getattr(load_case, "static_assignments", None) or []:
        ltype = str(item.load_type or "Load pattern").strip().lower()
        if ltype not in ("load pattern", "pattern", "load"):
            continue
        sf = float(item.load_sf)
        if sf == 0.0:
            continue

        pat_name = item.load_name
        pat = patterns.get(pat_name)
        sw_mult = float(getattr(pat, "self_wt_mult", 0.0)) if pat is not None else 0.0

        for dload in frame.dist_loads:
            if dload.pattern_name != pat_name or not dload.segments:
                continue
            _assemble_frame_distributed_load(f_eq, frame, R, L, dload, sf)

            dir_vec, proj_factor = _direction_vector(
                frame, R, dload.coord_sys, dload.load_dir, dload.direction
            )
            if proj_factor == 0.0:
                continue
            local_dir = R @ (dir_vec * proj_factor)
            is_moment = str(dload.force_or_moment or "Force").strip().lower().startswith("m")

            for seg in dload.segments:
                x1 = float(seg.x1) * L if dload.is_relative else float(seg.x1)
                x2 = float(seg.x2) * L if dload.is_relative else float(seg.x2)
                a = max(0.0, min(L, x1))
                b = max(0.0, min(L, x2))
                if b <= a + 1e-12:
                    continue
                q1_vec = (float(seg.q1) * sf) * local_dir
                q2_vec = (float(seg.q2) * sf) * local_dir
                span_loads.append((a, b, q1_vec, q2_vec, is_moment))

        for gload in getattr(frame, "gravity_loads", None) or []:
            if gload.pattern_name == pat_name and w_line > 0.0:
                g_glob = np.array(
                    [float(gload.multiplier_x), float(gload.multiplier_y), float(gload.multiplier_z)],
                    dtype=float,
                )
                q_loc = (sf * w_line) * (R @ g_glob)
                span_loads.append((0.0, L, q_loc, q_loc, False))
                _add_uniform_local_vector_fef(f_eq, q_loc, L)

        if sw_mult != 0.0 and w_line > 0.0:
            q_loc = (sf * sw_mult * w_line) * (R @ np.array([0.0, 0.0, -1.0]))
            span_loads.append((0.0, L, q_loc, q_loc, False))
            _add_uniform_local_vector_fef(f_eq, q_loc, L)

    _apply_release_mask(f_eq, frame.release_i, frame.release_j)
    return f_eq, span_loads


def _integrate_trapezoid(a: float, b: float, q1: float, q2: float, x: float) -> tuple[float, float]:
    if x <= a or b <= a:
        return 0.0, 0.0
    upper = min(x, b)
    dx = upper - a
    q_upper = q1 + (q2 - q1) * (dx / (b - a))
    force_int = 0.5 * (q1 + q_upper) * dx
    x_bar = dx * (q1 + 2.0 * q_upper) / (3.0 * (q1 + q_upper)) if abs(q1 + q_upper) > 1e-15 else 0.5 * dx
    arm = (x - a) - x_bar
    moment_int = force_int * arm
    return force_int, moment_int


def _recover_subframe_forces(
    project,
    frame: Frame,
    U: np.ndarray,
    case_name: str,
    dof_map: dict[str, int],
    use_shear_deform: bool = True,
) -> tuple[np.ndarray, np.ndarray, float, list[tuple[float, float, np.ndarray, np.ndarray, bool]]]:
    ni, nj = frame.node_i, frame.node_j
    if ni is None or nj is None:
        raise ValueError(f"Frame uç düğümleri eksik: {getattr(frame, 'label', '?')}")

    p1 = (ni.x, ni.y, ni.z)
    p2 = (nj.x, nj.y, nj.z)
    T, L = transformation_matrix(p1, p2, getattr(frame, "rotation_deg", 0.0) or 0.0)
    R = T[:3, :3]

    sec = frame.section
    mat = sec.material
    params = sec.profile_params or {}
    f_mods = getattr(frame, "modifiers", None) or {}

    a_mod = float(params.get("AMod", 1.0)) * float(f_mods.get("Area", f_mods.get("AMod", 1.0)))
    j_mod = float(params.get("JMod", 1.0)) * float(f_mods.get("J", f_mods.get("JMod", 1.0)))
    i3_mod = float(params.get("I3Mod", 1.0)) * float(f_mods.get("I33", f_mods.get("I3Mod", 1.0)))
    i2_mod = float(params.get("I2Mod", 1.0)) * float(f_mods.get("I22", f_mods.get("I2Mod", 1.0)))
    as2_mod = float(f_mods.get("AS2", 1.0))
    as3_mod = float(f_mods.get("AS3", 1.0))

    A = float(params["Area"]) * a_mod
    J = float(params.get("J", 0.0)) * j_mod
    I33 = float(params["I33"]) * i3_mod
    I22 = float(params["I22"]) * i2_mod
    AS2 = float(params.get("AS2", params["Area"])) * as2_mod
    AS3 = float(params.get("AS3", params["Area"])) * as3_mod

    off_i = float(getattr(frame, "offset_length_i", 0.0) or 0.0)
    off_j = float(getattr(frame, "offset_length_j", 0.0) or 0.0)
    rf = float(getattr(frame, "rigid_factor", 0.0) or 0.0)

    k_loc = local_stiffness(
        E=float(mat.E1),
        G=float(mat.G12),
        A=A,
        J=J,
        I33=I33,
        I22=I22,
        AS2=AS2,
        AS3=AS3,
        L=L,
        release_i=getattr(frame, "release_i", None),
        release_j=getattr(frame, "release_j", None),
        use_shear_deform=use_shear_deform,
        offset_i=off_i,
        offset_j=off_j,
        rigid_factor=rf,
    )

    dofs_i = getattr(ni, "dof_indices", None)
    if not dofs_i or any(d is None for d in dofs_i):
        base_i = dof_map[f"N_{ni.unique_id}"]
        dofs_i = [base_i + d for d in range(6)]

    dofs_j = getattr(nj, "dof_indices", None)
    if not dofs_j or any(d is None for d in dofs_j):
        base_j = dof_map[f"N_{nj.unique_id}"]
        dofs_j = [base_j + d for d in range(6)]

    dofs = np.asarray([int(d) for d in dofs_i] + [int(d) for d in dofs_j], dtype=np.intp)
    u_glob = U[dofs]
    u_loc = T @ u_glob

    f_eq, span_loads = _frame_local_equivalent_nodal_loads(project, frame, R, L, case_name)
    f_nodal = k_loc @ u_loc - f_eq

    eff_off_i = max(0.0, off_i * rf)
    eff_off_j = max(0.0, off_j * rf)
    if eff_off_i + eff_off_j >= L - 1e-6:
        eff_off_i = 0.0
        eff_off_j = 0.0
    if eff_off_i > 0.0 or eff_off_j > 0.0:
        H = _rigid_offset_matrix(eff_off_i, eff_off_j)
        f_nodal = np.linalg.solve(H.T, f_nodal)

    return f_nodal[:6], f_nodal[6:12], L, span_loads


def _evaluate_station(
    end_i: np.ndarray,
    x: float,
    span_loads: list[tuple[float, float, np.ndarray, np.ndarray, bool]],
) -> tuple[float, float, float, float, float, float]:
    N = -float(end_i[0])
    V2 = float(end_i[1])
    V3 = float(end_i[2])
    T = -float(end_i[3])
    M2 = -float(end_i[4]) + float(end_i[2]) * x
    M3 = -float(end_i[5]) + float(end_i[1]) * x

    for a, b, q1_vec, q2_vec, is_moment in span_loads:
        if x <= a:
            continue
        if is_moment:
            m1_int, _ = _integrate_trapezoid(a, b, float(q1_vec[0]), float(q2_vec[0]), x)
            m2_int, _ = _integrate_trapezoid(a, b, float(q1_vec[1]), float(q2_vec[1]), x)
            m3_int, _ = _integrate_trapezoid(a, b, float(q1_vec[2]), float(q2_vec[2]), x)
            T -= m1_int
            M2 += m2_int
            M3 += m3_int
        else:
            f1_int, _ = _integrate_trapezoid(a, b, float(q1_vec[0]), float(q2_vec[0]), x)
            f2_int, m3_int = _integrate_trapezoid(a, b, float(q1_vec[1]), float(q2_vec[1]), x)
            f3_int, m2_int = _integrate_trapezoid(a, b, float(q1_vec[2]), float(q2_vec[2]), x)
            N -= f1_int
            V2 += f2_int
            V3 += f3_int
            M2 += m2_int
            M3 += m3_int

    return N, V2, V3, T, M2, M3


def _station_count_for_segment(parent: Frame, seg_len: float, total_len: float, default_samples: int) -> int:
    if parent.station_type == "MaxStaSpcg" and parent.max_sta_spcg and parent.max_sta_spcg > 0.0:
        return max(2, math.ceil(seg_len / float(parent.max_sta_spcg)) + 1)
    min_sta = int(parent.min_num_sta) if parent.min_num_sta and parent.min_num_sta >= 2 else default_samples
    if total_len > 1e-12:
        scaled = math.ceil((min_sta - 1) * (seg_len / total_len)) + 1
        return max(2, scaled)
    return max(2, min_sta)


def recover_frame_forces(
    project,
    mesh: SolverMesh,
    static_results: dict[str, StaticCaseResult],
    *,
    use_shear_deform: bool = True,
    samples_per_segment: int = 9,
) -> dict[str, dict[int, FrameForceResult]]:
    dof_map = ensure_dof_indices(mesh)
    model = project.math_model
    raw_frames: dict[int, Frame] = getattr(model, "frames", None) or {}
    out: dict[str, dict[int, FrameForceResult]] = {}

    for case_name, case_res in static_results.items():
        U = case_res.displacements
        case_map: dict[int, FrameForceResult] = {}

        for parent_uid, child_keys in mesh.frame_children.items():
            parent = raw_frames.get(parent_uid)
            if parent is None or not child_keys:
                continue

            total_len = parent.get_length()
            if total_len <= 1e-12:
                continue

            stations: list[FrameStationForce] = []
            first_end_i = np.zeros(6, dtype=float)
            last_end_j = np.zeros(6, dtype=float)
            x_offset = 0.0

            for seg_idx, c_key in enumerate(child_keys):
                sub_frame = mesh.frames.get(c_key)
                if sub_frame is None:
                    continue

                end_i, end_j, seg_len, span_loads = _recover_subframe_forces(
                    project,
                    sub_frame,
                    U,
                    case_name,
                    dof_map=dof_map,
                    use_shear_deform=use_shear_deform,
                )
                if seg_idx == 0:
                    first_end_i = end_i.copy()
                if seg_idx == len(child_keys) - 1:
                    last_end_j = end_j.copy()

                n_pts = _station_count_for_segment(parent, seg_len, total_len, samples_per_segment)
                start_k = 0 if seg_idx == 0 else 1
                for k in range(start_k, n_pts):
                    local_x = seg_len * (k / float(n_pts - 1))
                    global_x = x_offset + local_x
                    ratio = min(1.0, max(0.0, global_x / total_len))
                    N, V2, V3, T, M2, M3 = _evaluate_station(end_i, local_x, span_loads)
                    stations.append(
                        FrameStationForce(
                            ratio=ratio,
                            x=global_x,
                            N=N,
                            V2=V2,
                            V3=V3,
                            T=T,
                            M2=M2,
                            M3=M3,
                        )
                    )

                x_offset += seg_len

            case_map[parent_uid] = FrameForceResult(
                frame_id=parent_uid,
                label=str(getattr(parent, "label", "") or f"F#{parent_uid}"),
                case_name=case_name,
                length=total_len,
                end_i=first_end_i,
                end_j=last_end_j,
                stations=stations,
            )

        out[case_name] = case_map

    return out


def save_analysis_results(
    filepath: str | Path,
    result: StructuralAnalysisResult,
    frame_forces: dict[str, dict[int, FrameForceResult]] | None = None,
) -> Path:
    path = Path(filepath)
    if path.suffix != ".cd4res":
        path = path.with_suffix(".cd4res")

    arrays: dict[str, np.ndarray] = {
        "fixed_dofs": np.asarray(result.fixed_dofs, dtype=np.int64),
    }

    static_meta: dict[str, dict] = {}
    for cname, sres in result.static_results.items():
        prefix = f"static__{cname}"
        arrays[f"{prefix}__U"] = np.asarray(sres.displacements, dtype=np.float64)
        arrays[f"{prefix}__R"] = np.asarray(sres.reactions, dtype=np.float64)
        arrays[f"{prefix}__F"] = np.asarray(sres.applied_forces, dtype=np.float64)
        static_meta[cname] = {
            "node_keys": list(sres.node_displacements.keys()),
        }
        if sres.node_displacements:
            arrays[f"{prefix}__node_U"] = np.asarray(
                list(sres.node_displacements.values()), dtype=np.float64
            )
            arrays[f"{prefix}__node_R"] = np.asarray(
                list(sres.node_reactions.values()), dtype=np.float64
            )

    modal_meta: dict | None = None
    if result.modal is not None:
        arrays["modal__frequencies"] = np.asarray(result.modal.frequencies, dtype=np.float64)
        arrays["modal__periods"] = np.asarray(result.modal.periods, dtype=np.float64)
        arrays["modal__mode_shapes"] = np.asarray(result.modal.mode_shapes, dtype=np.float64)
        modal_meta = {"n_modes": int(result.modal.n_modes)}

    forces_meta: dict[str, list[dict]] = {}
    if frame_forces:
        for cname, fmap in frame_forces.items():
            case_entries: list[dict] = []
            for fid, ff in fmap.items():
                key_base = f"ff__{cname}__{fid}"
                arrays[f"{key_base}__ends"] = np.vstack([ff.end_i, ff.end_j])
                if ff.stations:
                    st_arr = np.array(
                        [[s.ratio, s.x, s.N, s.V2, s.V3, s.T, s.M2, s.M3] for s in ff.stations],
                        dtype=np.float64,
                    )
                else:
                    st_arr = np.zeros((0, 8), dtype=np.float64)
                arrays[f"{key_base}__stations"] = st_arr
                case_entries.append(
                    {
                        "frame_id": int(ff.frame_id),
                        "label": ff.label,
                        "length": float(ff.length),
                    }
                )
            forces_meta[cname] = case_entries

    manifest = {
        "mass": {
            "total_self_kg": float(result.mass.total_self_kg),
            "total_dead_kg": float(result.mass.total_dead_kg),
            "total_live_kg": float(result.mass.total_live_kg),
            "n_live": float(result.mass.n_live),
        },
        "stiffness": {
            "num_dofs": int(result.stiffness.num_dofs),
            "frame_count": int(result.stiffness.frame_count),
            "area_count": int(result.stiffness.area_count),
            "link_count": int(result.stiffness.link_count),
        },
        "static_cases": static_meta,
        "modal": modal_meta,
        "frame_forces": forces_meta,
        "warnings": list(result.warnings),
    }

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        with zf.open("arrays.npz", "w") as f_npz:
            np.savez(f_npz, **arrays)

    return path


def load_analysis_results(filepath: str | Path) -> dict:
    path = Path(filepath)
    with zipfile.ZipFile(path, "r") as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        with zf.open("arrays.npz", "r") as f_npz:
            npz = np.load(f_npz, allow_pickle=False)
            arrays = {k: npz[k] for k in npz.files}

    static_out: dict[str, dict] = {}
    for cname, smeta in manifest.get("static_cases", {}).items():
        prefix = f"static__{cname}"
        node_keys = smeta.get("node_keys", [])
        node_u_arr = arrays.get(f"{prefix}__node_U")
        node_r_arr = arrays.get(f"{prefix}__node_R")
        static_out[cname] = {
            "displacements": arrays[f"{prefix}__U"],
            "reactions": arrays[f"{prefix}__R"],
            "applied_forces": arrays[f"{prefix}__F"],
            "node_displacements": (
                {k: node_u_arr[i] for i, k in enumerate(node_keys)}
                if node_u_arr is not None else {}
            ),
            "node_reactions": (
                {k: node_r_arr[i] for i, k in enumerate(node_keys)}
                if node_r_arr is not None else {}
            ),
        }

    forces_out: dict[str, dict[int, FrameForceResult]] = {}
    for cname, entries in manifest.get("frame_forces", {}).items():
        cmap: dict[int, FrameForceResult] = {}
        for item in entries:
            fid = int(item["frame_id"])
            key_base = f"ff__{cname}__{fid}"
            ends = arrays[f"{key_base}__ends"]
            st_arr = arrays[f"{key_base}__stations"]
            stations = [
                FrameStationForce(
                    ratio=float(row[0]),
                    x=float(row[1]),
                    N=float(row[2]),
                    V2=float(row[3]),
                    V3=float(row[4]),
                    T=float(row[5]),
                    M2=float(row[6]),
                    M3=float(row[7]),
                )
                for row in st_arr
            ]
            cmap[fid] = FrameForceResult(
                frame_id=fid,
                label=item["label"],
                case_name=cname,
                length=float(item["length"]),
                end_i=ends[0],
                end_j=ends[1],
                stations=stations,
            )
        forces_out[cname] = cmap

    modal_out = None
    if manifest.get("modal") is not None:
        modal_out = {
            "n_modes": manifest["modal"]["n_modes"],
            "frequencies": arrays["modal__frequencies"],
            "periods": arrays["modal__periods"],
            "mode_shapes": arrays["modal__mode_shapes"],
        }

    return {
        "manifest": manifest,
        "fixed_dofs": arrays["fixed_dofs"],
        "static_results": static_out,
        "modal": modal_out,
        "frame_forces": forces_out,
    }