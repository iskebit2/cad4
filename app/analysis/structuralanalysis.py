from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from app.analysis.mass_assembly import MassAssembly, build_mass
from app.analysis.mesher import SolverMesh, build_solver_mesh
from app.analysis.modal_analysis import response_spectrum_solve
from app.analysis.solve_static import StaticCaseResult, solve_static_case
from app.analysis.solver import ModalResult, StructuralSolver
from app.analysis.stiffness_assembly import StiffnessAssembly, build_stiffness, ensure_dof_indices
from app.analysis.unit_guard import ensure_nmm
from app.analysis.validation import validate_model, validate_stiffness
from core.units import G_MM_S2


@dataclass
class StructuralAnalysisResult:
    mass: MassAssembly
    stiffness: StiffnessAssembly
    fixed_dofs: list[int]
    mesh: SolverMesh | None = None
    modal: ModalResult | None = None
    spectral: object | None = None
    static_results: dict[str, StaticCaseResult] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def K(self) -> np.ndarray:
        return self.stiffness.K_global

    @property
    def M(self) -> np.ndarray:
        return self.mass.M_global

    def __inspector_tree__(self):
        data = {
            "Model": {
                "DOF": self.K.shape[0],
                "Fixed DOF": len(self.fixed_dofs),
                "Frame": self.stiffness.frame_count,
                "Area": self.stiffness.area_count,
                "Link": self.stiffness.link_count,
                "Skipped": len(self.stiffness.skipped),
            },
            "Mass (kg)": {
                "Self": f"{self.mass.total_self_kg:.3f}",
                "Dead": f"{self.mass.total_dead_kg:.3f}",
                "Live (ham)": f"{self.mass.total_live_kg:.3f}",
                f"Total (n={self.mass.n_live:.2f})": f"{self.mass.total_kg:.3f}",
                "Total (ton)": f"{self.mass.total_ton:.4f}",
            },
        }
        if self.static_results:
            data["Static Cases"] = {
                cname: f"max|U|={float(np.max(np.abs(res.displacements))):.4f}"
                for cname, res in self.static_results.items()
            }
        if self.modal is not None and len(self.modal.periods) > 0:
            data["Modal"] = {
                "n_modes": self.modal.n_modes,
                "T1 (s)": f"{self.modal.periods[0]:.4f}",
                "f1 (Hz)": f"{self.modal.frequencies[0]:.3f}",
            }
        if self.warnings:
            data["Warnings"] = {f"Uyarı {i + 1}": w for i, w in enumerate(self.warnings)}
        return data


def _collect_fixed_dofs(scene) -> list[int]:
    fixed: list[int] = []
    for node in scene.nodes.values():
        dofs = getattr(node, "dof_indices", None)
        if not dofs:
            continue
        r = getattr(node, "restraint", None)
        if r is None:
            continue
        for i, dof_name in enumerate(("ux", "uy", "uz", "rx", "ry", "rz")):
            if getattr(r, dof_name, False):
                if i < len(dofs) and dofs[i] is not None:
                    fixed.append(int(dofs[i]))
    return fixed


def _validate_modal(modal: ModalResult, tol: float = 1e-6) -> list[str]:
    errs: list[str] = []
    if not np.all(np.diff(modal.frequencies) >= -tol):
        errs.append("Frekanslar artan değil")
    if np.any(modal.frequencies < -tol):
        errs.append("Negatif frekans var")
    return errs


def _resolve_spectrum(project, spectrum):
    if spectrum is None:
        return None
    if isinstance(spectrum, str):
        return project.spectrum_functions.get(spectrum)
    return spectrum


def _build_static_result_from_u(
    case_name: str,
    U: np.ndarray,
    stiff_asm: StiffnessAssembly,
    dof_map: dict[str, int],
    mesh: SolverMesh,
    fixed_dofs: list[int],
) -> StaticCaseResult:
    K_U = np.asarray(stiff_asm.K_global @ U, dtype=float)
    F = K_U.copy()
    R = np.zeros_like(K_U)
    if fixed_dofs:
        F[fixed_dofs] = 0.0
        R[fixed_dofs] = K_U[fixed_dofs]

    node_disp: dict[str, np.ndarray] = {}
    node_reac: dict[str, np.ndarray] = {}
    for n_key, base in dof_map.items():
        node_disp[n_key] = U[base : base + 6].copy()
        node_reac[n_key] = R[base : base + 6].copy()

    sum_F = np.array([np.sum(F[i::6]) for i in range(6)], dtype=float)
    sum_R = np.array([np.sum(R[i::6]) for i in range(6)], dtype=float)

    return StaticCaseResult(
        case_name=case_name,
        displacements=U,
        reactions=R,
        applied_forces=F,
        node_displacements=node_disp,
        node_reactions=node_reac,
        sum_F=sum_F,
        sum_R=sum_R,
    )


def _solve_response_spectrum_case(
    project,
    rs_case,
    modal: ModalResult,
    mass_asm: MassAssembly,
    stiff_asm: StiffnessAssembly,
    dof_map: dict[str, int],
    mesh: SolverMesh,
    fixed_dofs: list[int],
    n_modes: int,
) -> StaticCaseResult | None:
    assignments = getattr(rs_case, "assignments", None) or []
    if not assignments:
        return None

    num_dofs = mass_asm.num_dofs
    u_dir_sq = np.zeros(num_dofs, dtype=float)
    u_abs_sum = np.zeros(num_dofs, dtype=float)

    for assign in assignments:
        spec_fn = project.spectrum_functions.get(assign.function_name)
        if spec_fn is None:
            continue
        sp = response_spectrum_solve(
            modal=modal,
            M_global=mass_asm.M_global,
            num_dofs=num_dofs,
            spectrum=spec_fn,
            n_modes=n_modes,
        )
        sf_ratio = float(assign.sf) / G_MM_S2 if G_MM_S2 > 0.0 else 1.0
        lname = str(assign.load_name or "").strip().upper()
        angle_rad = math.radians(float(assign.angle))

        if lname in ("U3", "UZ", "Z"):
            u_comp = sf_ratio * sp.uz_srss
        else:
            u_comp = sf_ratio * (
                math.cos(angle_rad) * sp.ux_srss + math.sin(angle_rad) * sp.uy_srss
            )

        u_dir_sq += np.square(u_comp)
        u_abs_sum += np.abs(u_comp)

    dir_combo = str(getattr(rs_case, "dir_combo", "SRSS")).strip().upper()
    U = u_abs_sum if dir_combo == "ABS" else np.sqrt(u_dir_sq)

    dominant_idx = 0 if np.max(np.abs(U[0::6])) >= np.max(np.abs(U[1::6])) else 1
    sign_ref = 1.0
    for idx in range(dominant_idx, num_dofs, 6):
        if abs(U[idx]) > 1e-12:
            sign_ref = 1.0 if U[idx] >= 0.0 else -1.0
            break
    U = U * sign_ref

    return _build_static_result_from_u(
        rs_case.name, U, stiff_asm, dof_map, mesh, fixed_dofs
    )


def _evaluate_combinations(
    project,
    static_results: dict[str, StaticCaseResult],
) -> None:
    combos = getattr(project, "combinations", None) or {}
    if not combos:
        return

    pending = dict(combos)
    for _pass in range(len(pending) + 1):
        progressed = False
        for cname, combo in list(pending.items()):
            if cname in static_results:
                del pending[cname]
                continue
            items = getattr(combo, "items", None) or []
            if not items:
                del pending[cname]
                continue
            if not all(it.case_or_pattern_name in static_results for it in items):
                continue

            first = static_results[items[0].case_or_pattern_name]
            U = np.zeros_like(first.displacements)
            R = np.zeros_like(first.reactions)
            F = np.zeros_like(first.applied_forces)
            sum_F = np.zeros(6, dtype=float)
            sum_R = np.zeros(6, dtype=float)
            node_disp = {k: np.zeros(6, dtype=float) for k in first.node_displacements}
            node_reac = {k: np.zeros(6, dtype=float) for k in first.node_reactions}

            ctype = str(getattr(combo, "combo_type", "Linear Add")).strip().lower()
            for idx, it in enumerate(items):
                src = static_results[it.case_or_pattern_name]
                sf = float(it.scale_factor)
                if ctype == "envelope" and idx > 0:
                    U = np.maximum(U, sf * src.displacements)
                    R = np.maximum(R, sf * src.reactions)
                    F = np.maximum(F, sf * src.applied_forces)
                    sum_F = np.maximum(sum_F, sf * src.sum_F)
                    sum_R = np.maximum(sum_R, sf * src.sum_R)
                    for k in node_disp:
                        node_disp[k] = np.maximum(node_disp[k], sf * src.node_displacements[k])
                        node_reac[k] = np.maximum(node_reac[k], sf * src.node_reactions[k])
                else:
                    U += sf * src.displacements
                    R += sf * src.reactions
                    F += sf * src.applied_forces
                    sum_F += sf * src.sum_F
                    sum_R += sf * src.sum_R
                    for k in node_disp:
                        node_disp[k] += sf * src.node_displacements[k]
                        node_reac[k] += sf * src.node_reactions[k]

            static_results[cname] = StaticCaseResult(
                case_name=cname,
                displacements=U,
                reactions=R,
                applied_forces=F,
                node_displacements=node_disp,
                node_reactions=node_reac,
                sum_F=sum_F,
                sum_R=sum_R,
            )
            del pending[cname]
            progressed = True

        if not pending or not progressed:
            break


def run_analysis(
    project,
    *,
    scene=None,
    n_live: float = 0.3,
    n_modes: int = 10,
    run_static: bool = True,
    run_modal: bool = True,
    static_case_names: list[str] | None = None,
    spectrum=None,
    validate: bool = True,
    use_shear_deform: bool = True,
) -> StructuralAnalysisResult:
    ensure_nmm(project)

    model = getattr(project, "math_model", None) or scene
    pre_report = validate_model(model, project, strict=validate)
    mesh = build_solver_mesh(model)

    mass_asm = build_mass(mesh, project, n_live=n_live, validate=validate)
    stiff_asm = build_stiffness(mesh, project, validate=validate, use_shear_deform=use_shear_deform)

    dof_map = ensure_dof_indices(mesh)
    fixed_dofs: set[int] = set()
    for n_key, node in mesh.nodes.items():
        base = dof_map.get(n_key)
        if base is None:
            continue
        restraint = getattr(node, "restraint", None)
        if restraint is None:
            continue
        for i, name in enumerate(("ux", "uy", "uz", "rx", "ry", "rz")):
            if getattr(restraint, name, False):
                fixed_dofs.add(base + i)

    sorted_fixed = sorted(fixed_dofs)

    warnings = (
        list(pre_report.warnings)
        + list(mass_asm.warnings)
        + list(stiff_asm.warnings)
    )

    stiff_warns = validate_stiffness(stiff_asm, fixed_dofs=fixed_dofs, check_rank=True)
    warnings.extend(stiff_warns)

    solver = StructuralSolver(
        K_global=stiff_asm.K_global,
        M_global=mass_asm.M_global,
        num_dofs=mass_asm.num_dofs,
        dof_map=dof_map,
        fixed_dofs=fixed_dofs,
        nodes=mesh.nodes,
    )

    static_results: dict[str, StaticCaseResult] = {}
    if run_static:
        all_cases = getattr(project, "load_cases", None) or {}
        targets = static_case_names if static_case_names is not None else [
            cname for cname, lc in all_cases.items()
            if getattr(lc, "run_case", True) and str(getattr(lc, "case_type", "LinStatic")).lower() in ("linstatic", "linearstatic")
        ]
        for cname in targets:
            static_results[cname] = solve_static_case(project, solver, mesh, cname)

    modal: ModalResult | None = None
    if run_modal or getattr(project, "response_spectrum_cases", None):
        modal = solver.modal_solve(n_modes=n_modes)
        if validate:
            warnings.extend(_validate_modal(modal))

    if modal is not None:
        for rs_name, rs_case in (getattr(project, "response_spectrum_cases", None) or {}).items():
            rs_res = _solve_response_spectrum_case(
                project, rs_case, modal, mass_asm, stiff_asm, dof_map, mesh, sorted_fixed, n_modes
            )
            if rs_res is not None:
                static_results[rs_name] = rs_res

    if static_results:
        _evaluate_combinations(project, static_results)

    spec_obj = _resolve_spectrum(project, spectrum)
    spectral = None
    if modal is not None and spec_obj is not None:
        spectral = response_spectrum_solve(
            modal=modal,
            M_global=mass_asm.M_global,
            num_dofs=mass_asm.num_dofs,
            spectrum=spec_obj,
            n_modes=n_modes,
        )

    return StructuralAnalysisResult(
        mass=mass_asm,
        stiffness=stiff_asm,
        fixed_dofs=sorted_fixed,
        mesh=mesh,
        modal=modal,
        spectral=spectral,
        static_results=static_results,
        warnings=warnings,
    )