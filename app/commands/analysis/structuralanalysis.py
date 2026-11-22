# app/commands/analysis\structuralanalysis.py
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from app.commands.analysis.mass_assembly import MassAssembly, build_mass
from app.commands.analysis.mesher import SolverMesh, build_solver_mesh
from app.commands.analysis.solve_static import StaticCaseResult, solve_static_case
from app.commands.analysis.solver import ModalResult, StructuralSolver
from app.commands.analysis.stiffness_assembly import StiffnessAssembly, build_stiffness, ensure_dof_indices
from app.commands.analysis.unit_guard import ensure_nmm
from app.commands.analysis.validation import validate_model, validate_stiffness


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
    if run_modal:
        modal = solver.modal_solve(n_modes=n_modes)
        if validate:
            warnings.extend(_validate_modal(modal))

    spec_obj = _resolve_spectrum(project, spectrum)
    spectral = None
    if modal is not None and spec_obj is not None:
        from app.commands.analysis.modal_analysis import response_spectrum_solve
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
        fixed_dofs=sorted(fixed_dofs),
        mesh=mesh,
        modal=modal,
        spectral=spectral,
        static_results=static_results,
        warnings=warnings,
    )