# app/analysis/force_recovery.py
from __future__ import annotations

import json
import math
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from app.analysis.mesher import SolverMesh
from app.analysis.solve_static import (
    _GRAVITY_MM_S2,
    _add_uniform_local_vector_fef,
    _apply_release_mask,
    _assemble_frame_distributed_load,
    _trapezoidal_fef_axial,
    _trapezoidal_fef_transverse,
)
from app.analysis.stiffness_assembly import (
    _rigid_offset_matrix,
    ensure_dof_indices,
    local_stiffness,
    transformation_matrix,
)
from app.analysis.frame_resolver import resolve_frame_kinematics, resolve_section, frame_load_direction_vector
from domain.definition import LoadPattern
from domain.element import Frame

if TYPE_CHECKING:
    from app.analysis.solve_static import StaticCaseResult
    from app.analysis.structuralanalysis import StructuralAnalysisResult


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


@dataclass
class PersistedReportStaticResult:
    sum_F: np.ndarray
    sum_R: np.ndarray
    node_displacements: dict[str, np.ndarray]


@dataclass
class PersistedReportModalResult:
    frequencies: np.ndarray
    periods: np.ndarray
    modal_mass: np.ndarray
    effective_mass_x: np.ndarray
    effective_mass_y: np.ndarray
    effective_mass_z: np.ndarray
    total_mass_x: float
    total_mass_y: float
    total_mass_z: float

    @property
    def n_modes(self) -> int:
        return len(self.periods)


@dataclass
class PersistedReportMeshNode:
    z: float


@dataclass
class PersistedReportMesh:
    nodes: dict[str, PersistedReportMeshNode]
    internal_node_keys: set[str]


@dataclass
class PersistedReportAnalysisResults:
    static_results: dict[str, PersistedReportStaticResult]
    modal: PersistedReportModalResult | None
    mesh: PersistedReportMesh | None
    warnings: list[str] = field(default_factory=list)


def _frame_local_equivalent_nodal_loads(
    project,
    frame: Frame,
    sec_res,
    kin,
    case_name: str,
) -> tuple[np.ndarray, list[tuple[float, float, np.ndarray, np.ndarray, bool]]]:
    f_eq_clear = np.zeros(12, dtype=float)
    span_loads: list[tuple[float, float, np.ndarray, np.ndarray, bool]] = []

    load_case = (getattr(project, "load_cases", None) or {}).get(case_name)
    if load_case is None:
        return f_eq_clear, span_loads

    R = kin.R_axis.T
    L_axis = kin.L_axis
    L_clear = kin.L_clear
    x0_clear = kin.eff_off_i
    x1_clear = kin.eff_off_i + L_clear

    patterns: dict[str, LoadPattern] = getattr(project, "load_patterns", None) or {}
    w_line = sec_res.weight_per_len

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
            dir_vec, proj_factor = frame_load_direction_vector(
    kin.R_axis, kin.L_axis, dload.coord_sys, dload.load_dir, dload.direction
)
            if proj_factor == 0.0:
                continue
            local_dir = R.T @ (dir_vec * proj_factor)
            is_moment = str(dload.force_or_moment or "Force").strip().lower().startswith("m")

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
                q1_raw = float(seg.q1) * sf
                q2_raw = float(seg.q2) * sf
                q1 = q1_raw + (q2_raw - q1_raw) * t_a
                q2 = q1_raw + (q2_raw - q1_raw) * t_b

                q1_vec = q1 * local_dir
                q2_vec = q2 * local_dir
                span_loads.append((a, b, q1_vec, q2_vec, is_moment))

                if is_moment:
                    for comp in range(3):
                        if abs(q1_vec[comp]) <= 1e-15 and abs(q2_vec[comp]) <= 1e-15:
                            continue
                        mi, mj = _trapezoidal_fef_axial(a, b, float(q1_vec[comp]), float(q2_vec[comp]), L_clear)
                        f_eq_clear[3 + comp] += mi
                        f_eq_clear[9 + comp] += mj
                else:
                    if abs(q1_vec[0]) > 1e-15 or abs(q2_vec[0]) > 1e-15:
                        fi1, fj1 = _trapezoidal_fef_axial(a, b, float(q1_vec[0]), float(q2_vec[0]), L_clear)
                        f_eq_clear[0] += fi1
                        f_eq_clear[6] += fj1
                    if abs(q1_vec[1]) > 1e-15 or abs(q2_vec[1]) > 1e-15:
                        ri2, mi3, rj2, mj3 = _trapezoidal_fef_transverse(a, b, float(q1_vec[1]), float(q2_vec[1]), L_clear)
                        f_eq_clear[1] += ri2
                        f_eq_clear[5] += mi3
                        f_eq_clear[7] += rj2
                        f_eq_clear[11] += mj3
                    if abs(q1_vec[2]) > 1e-15 or abs(q2_vec[2]) > 1e-15:
                        ri3, mi2, rj3, mj2 = _trapezoidal_fef_transverse(a, b, float(q1_vec[2]), float(q2_vec[2]), L_clear)
                        f_eq_clear[2] += ri3
                        f_eq_clear[4] -= mi2
                        f_eq_clear[8] += rj3
                        f_eq_clear[10] -= mj2

        for gload in getattr(frame, "gravity_loads", None) or []:
            if gload.pattern_name == pat_name and w_line > 0.0:
                g_glob = np.array(
                    [float(gload.multiplier_x), float(gload.multiplier_y), float(gload.multiplier_z)],
                    dtype=float,
                )
                q_loc = (sf * w_line) * (R.T @ g_glob)
                span_loads.append((0.0, L_clear, q_loc, q_loc, False))
                _accumulate_uniform_fef(f_eq_clear, q_loc, L_clear)

        if sw_mult != 0.0 and w_line > 0.0:
            q_loc = (sf * sw_mult * w_line) * (R.T @ np.array([0.0, 0.0, -1.0]))
            span_loads.append((0.0, L_clear, q_loc, q_loc, False))
            _accumulate_uniform_fef(f_eq_clear, q_loc, L_clear)

    rel_i = frame.release_i or {}
    for idx, keys in enumerate((("R1", "u1"), ("U2", "u2"), ("U3", "u3"), ("R4", "r1"), ("R2", "r2"), ("R3", "r3"))):
        if any(rel_i.get(k, False) for k in keys):
            f_eq_clear[idx] = 0.0

    rel_j = frame.release_j or {}
    for idx, keys in enumerate((("R1", "u1"), ("U2", "u2"), ("U3", "u3"), ("R4", "r1"), ("R2", "r2"), ("R3", "r3"))):
        if any(rel_j.get(k, False) for k in keys):
            f_eq_clear[6 + idx] = 0.0

    f_eq_node_loc = kin.T_ecc.T @ (kin.H.T @ f_eq_clear)
    return f_eq_node_loc, span_loads


def _accumulate_uniform_fef(f_eq: np.ndarray, q_loc: np.ndarray, L: float) -> None:
    f_eq[0] += 0.5 * q_loc[0] * L
    f_eq[6] += 0.5 * q_loc[0] * L
    f_eq[1] += 0.5 * q_loc[1] * L
    f_eq[7] += 0.5 * q_loc[1] * L
    f_eq[5] += q_loc[1] * (L * L) / 12.0
    f_eq[11] -= q_loc[1] * (L * L) / 12.0
    f_eq[2] += 0.5 * q_loc[2] * L
    f_eq[8] += 0.5 * q_loc[2] * L
    f_eq[4] -= q_loc[2] * (L * L) / 12.0
    f_eq[10] += q_loc[2] * (L * L) / 12.0


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
    use_shear_deform: bool = True,
) -> tuple[np.ndarray, np.ndarray, float, list[tuple[float, float, np.ndarray, np.ndarray, bool]]]:
    ni, nj = frame.node_i, frame.node_j
    sec_res = resolve_section(frame.section, getattr(frame, "modifiers", None))
    kin = resolve_frame_kinematics(frame, sec_res)

    k_loc = local_stiffness(
        E=sec_res.E,
        G=sec_res.G,
        A=sec_res.A,
        J=sec_res.J,
        I33=sec_res.I33,
        I22=sec_res.I22,
        AS2=sec_res.AS2,
        AS3=sec_res.AS3,
        L=kin.L_axis,
        release_i=getattr(frame, "release_i", None),
        release_j=getattr(frame, "release_j", None),
        use_shear_deform=use_shear_deform,
        offset_i=getattr(frame, "offset_length_i", 0.0) or 0.0,
        offset_j=getattr(frame, "offset_length_j", 0.0) or 0.0,
        rigid_factor=getattr(frame, "rigid_factor", 0.0) or 0.0,
    )

    k_node_loc = kin.T_ecc.T @ k_loc @ kin.T_ecc
    dofs = list(ni.dof_indices) + list(nj.dof_indices)
    u_glob = U[dofs]
    u_loc = kin.T_axis @ u_glob

    f_eq_node_loc, span_loads = _frame_local_equivalent_nodal_loads(project, frame, sec_res, kin, case_name)
    f_nodal_loc = k_node_loc @ u_loc - f_eq_node_loc

    if kin.transform_stiffness:
        f_axis_loc = np.linalg.solve(kin.T_ecc.T, f_nodal_loc)
    else:
        f_axis_loc = f_nodal_loc

    if kin.eff_off_i > 0.0 or kin.eff_off_j > 0.0:
        f_clear_loc = np.linalg.solve(kin.H.T, f_axis_loc)
    else:
        f_clear_loc = f_axis_loc

    return f_clear_loc[:6], f_clear_loc[6:12], kin.L_clear, span_loads


def _evaluate_station(end_i, x, span_loads):
    N = -float(end_i[0])
    V2 = float(end_i[1])
    V3 = float(end_i[2])
    T = -float(end_i[3])
    M2 = -float(end_i[4]) - float(end_i[2]) * x
    M3 = -float(end_i[5]) + float(end_i[1]) * x

    for a, b, q1_vec, q2_vec, is_moment in span_loads:
        if x <= a:
            continue
        if is_moment:
            m1_int, _ = _integrate_trapezoid(a, b, q1_vec[0], q2_vec[0], x)
            m2_int, _ = _integrate_trapezoid(a, b, q1_vec[1], q2_vec[1], x)
            m3_int, _ = _integrate_trapezoid(a, b, q1_vec[2], q2_vec[2], x)
            T -= m1_int
            M2 -= m2_int
            M3 -= m3_int
        else:
            f1_int, _ = _integrate_trapezoid(a, b, q1_vec[0], q2_vec[0], x)
            f2_int, m3_int = _integrate_trapezoid(a, b, q1_vec[1], q2_vec[1], x)
            f3_int, m2_int = _integrate_trapezoid(a, b, q1_vec[2], q2_vec[2], x)
            N -= f1_int
            V2 += f2_int
            V3 += f3_int
            M2 -= m2_int
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
    samples_per_segment: int = 5,
) -> dict[str, dict[int, FrameForceResult]]:
    from app.analysis.stiffness_assembly import ensure_dof_indices

    ensure_dof_indices(mesh)
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
                    project, sub_frame, U, case_name, use_shear_deform=use_shear_deform
                )
                if seg_idx == 0:
                    first_end_i = end_i.copy()
                if seg_idx == len(child_keys) - 1:
                    last_end_j = end_j.copy()

                n_pts = max(2, int(samples_per_segment))
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
        arrays[f"{prefix}__sum_F"] = np.asarray(sres.sum_F, dtype=np.float64)
        arrays[f"{prefix}__sum_R"] = np.asarray(sres.sum_R, dtype=np.float64)
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
        arrays["modal__modal_mass"] = np.asarray(result.modal.modal_mass, dtype=np.float64)
        arrays["modal__effective_mass_x"] = np.asarray(result.modal.effective_mass_x, dtype=np.float64)
        arrays["modal__effective_mass_y"] = np.asarray(result.modal.effective_mass_y, dtype=np.float64)
        arrays["modal__effective_mass_z"] = np.asarray(result.modal.effective_mass_z, dtype=np.float64)
        modal_meta = {
            "n_modes": int(result.modal.n_modes),
            "total_mass_x": float(result.modal.total_mass_x),
            "total_mass_y": float(result.modal.total_mass_y),
            "total_mass_z": float(result.modal.total_mass_z),
        }

    mesh_meta = None
    if result.mesh is not None:
        mesh_node_keys = list(result.mesh.nodes)
        arrays["mesh__node_z"] = np.asarray(
            [result.mesh.nodes[key].z for key in mesh_node_keys],
            dtype=np.float64,
        )
        mesh_meta = {
            "node_keys": mesh_node_keys,
            "internal_node_keys": sorted(result.mesh.internal_node_keys),
        }

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
        "mesh": mesh_meta,
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
        applied_forces = arrays[f"{prefix}__F"]
        reactions = arrays[f"{prefix}__R"]
        static_out[cname] = {
            "displacements": arrays[f"{prefix}__U"],
            "reactions": reactions,
            "applied_forces": applied_forces,
            "sum_F": arrays.get(
                f"{prefix}__sum_F",
                np.asarray(
                    [np.sum(applied_forces[i::6]) for i in range(6)],
                    dtype=np.float64,
                ),
            ),
            "sum_R": arrays.get(
                f"{prefix}__sum_R",
                np.asarray(
                    [np.sum(reactions[i::6]) for i in range(6)],
                    dtype=np.float64,
                ),
            ),
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
        modal_meta = manifest["modal"]
        n_modes = int(modal_meta["n_modes"])
        missing_modal_values = np.full(n_modes, np.nan, dtype=np.float64)
        modal_out = {
            "n_modes": n_modes,
            "frequencies": arrays["modal__frequencies"],
            "periods": arrays["modal__periods"],
            "mode_shapes": arrays["modal__mode_shapes"],
            "modal_mass": arrays.get("modal__modal_mass", missing_modal_values),
            "effective_mass_x": arrays.get("modal__effective_mass_x", missing_modal_values),
            "effective_mass_y": arrays.get("modal__effective_mass_y", missing_modal_values),
            "effective_mass_z": arrays.get("modal__effective_mass_z", missing_modal_values),
            "total_mass_x": float(modal_meta.get("total_mass_x", np.nan)),
            "total_mass_y": float(modal_meta.get("total_mass_y", np.nan)),
            "total_mass_z": float(modal_meta.get("total_mass_z", np.nan)),
        }

    mesh_out = None
    mesh_meta = manifest.get("mesh")
    if mesh_meta is not None:
        node_z = arrays["mesh__node_z"]
        node_keys = mesh_meta.get("node_keys", [])
        mesh_out = {
            "nodes": {
                key: {"z": float(node_z[i])}
                for i, key in enumerate(node_keys)
            },
            "internal_node_keys": mesh_meta.get("internal_node_keys", []),
        }

    return {
        "manifest": manifest,
        "fixed_dofs": arrays["fixed_dofs"],
        "static_results": static_out,
        "modal": modal_out,
        "mesh": mesh_out,
        "frame_forces": forces_out,
    }


def load_report_analysis_results(filepath: str | Path) -> PersistedReportAnalysisResults:
    saved = load_analysis_results(filepath)
    static_results = {
        case_name: PersistedReportStaticResult(
            sum_F=case["sum_F"],
            sum_R=case["sum_R"],
            node_displacements=case["node_displacements"],
        )
        for case_name, case in saved["static_results"].items()
    }

    modal_data = saved["modal"]
    modal = (
        PersistedReportModalResult(
            frequencies=modal_data["frequencies"],
            periods=modal_data["periods"],
            modal_mass=modal_data["modal_mass"],
            effective_mass_x=modal_data["effective_mass_x"],
            effective_mass_y=modal_data["effective_mass_y"],
            effective_mass_z=modal_data["effective_mass_z"],
            total_mass_x=modal_data["total_mass_x"],
            total_mass_y=modal_data["total_mass_y"],
            total_mass_z=modal_data["total_mass_z"],
        )
        if modal_data is not None else None
    )

    mesh_data = saved["mesh"]
    mesh = (
        PersistedReportMesh(
            nodes={
                key: PersistedReportMeshNode(z=node["z"])
                for key, node in mesh_data["nodes"].items()
            },
            internal_node_keys=set(mesh_data["internal_node_keys"]),
        )
        if mesh_data is not None else None
    )
    return PersistedReportAnalysisResults(
        static_results=static_results,
        modal=modal,
        mesh=mesh,
        warnings=list(saved["manifest"].get("warnings", [])),
    )