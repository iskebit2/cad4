# core/analysis/structuralanalysis.py
"""
Orchestration — mass + stiffness + modal (+ spectrum).

Birim sözleşmesi: units.py.
"""
from dataclasses import dataclass, field

import numpy as np

from .mass_assembly import MassAssembly, build_mass
from .solver import ModalResult, StructuralSolver
from .stiffness_assembly import StiffnessAssembly, build_stiffness
from core.analysis.unit_guard import ensure_nmm


@dataclass
class StructuralAnalysisResult:
    mass: MassAssembly
    stiffness: StiffnessAssembly
    fixed_dofs: list[int]
    modal: ModalResult | None = None
    spectral: object | None = None    # sonra doldurulacak
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
                "Skipped": len(self.stiffness.skipped),
            },
            "Mass (kg)": {
                "Self": f"{self.mass.total_self_kg:.3f}",
                "Dead": f"{self.mass.total_dead_kg:.3f}",
                "Live (ham)": f"{self.mass.total_live_kg:.3f}",
                f"Total (n={self.mass.n_live:.2f})":
                    f"{self.mass.total_kg:.3f}",
                "Total (ton)": f"{self.mass.total_ton:.4f}",
            },
        }
        if self.modal is not None:
            data["Modal"] = {
                "n_modes": self.modal.n_modes,
                "T1 (s)": f"{self.modal.periods[0]:.4f}",
                "f1 (Hz)": f"{self.modal.frequencies[0]:.3f}",
            }
        if self.warnings:
            data["Warnings"] = {f"Uyarı {i+1}": w for i, w in enumerate(self.warnings)}
        return data


# ============================================================================
# YARDIMCILAR
# ============================================================================
def _collect_fixed_dofs(scene) -> list[int]:
    """Mesnetli node'ların DOF endekslerini topla."""
    fixed: list[int] = []
    for node in scene.nodes.values():
        dofs = getattr(node, "dof_indices", None)
        if not dofs:
            continue
        r = getattr(node, "restraint", None)
        if r is None:
            continue
        # Node.DOF_ORDER = ('ux','uy','uz','rx','ry','rz')
        for i, dof_name in enumerate(("ux", "uy", "uz", "rx", "ry", "rz")):
            if getattr(r, dof_name, False):
                if i < len(dofs) and dofs[i] is not None:
                    fixed.append(int(dofs[i]))
    return fixed


def _validate_modal(modal: ModalResult, tol: float = 1e-6) -> list[str]:
    """Modal sonuç doğrulaması."""
    errs = []

    if not np.all(np.diff(modal.frequencies) >= -tol):
        errs.append("Frekanslar artan değil")

    if np.any(modal.frequencies < -tol):
        errs.append("Negatif frekans var")

    # Toplam efektif kütle, toplam modal kütleye yakın olmalı (yeterli mod varsa)
    # (uyarı olarak raporlanır — eksik mod normaldir)

    return errs


# ============================================================================
# ANA FONKSİYON
# ============================================================================
def run_analysis(
    scene,
    project,
    n_live: float = 0.3,
    n_modes: int = 10,
    spectrum=None,
    *,
    validate: bool = True,
    use_shear_deform: bool = True, # Varsayılan olarak aktif
) -> StructuralAnalysisResult:
    """
    Tam analiz zinciri: mass → stiffness → modal (+ spectrum).

    Parameters
    ----------
    scene    : Scene
    project  : Project (load_patterns için)
    n_live   : live yük çarpanı
    n_modes  : kaç mod isteniyor
    spectrum : opsiyonel spektrum (get_sa(T) → Sa[g])
    """
    # --- 0. Birim guard: solver N_MM varsayar ---
    ensure_nmm(project)
    
    # --- 1. Mass ---
    mass_asm = build_mass(scene, project, n_live=n_live, validate=validate)

    # --- 2. Stiffness ---
    stiff_asm = build_stiffness(scene, project, validate=validate, use_shear_deform=use_shear_deform)

    # --- 3. Mesnetli DOF'lar ---
    fixed_dofs = _collect_fixed_dofs(scene)

    if not fixed_dofs:
        # Uyarı — mesnetsiz model
        stiff_asm.warnings.append("Mesnetli DOF yok — modal analiz çökebilir")

    # --- 4. Modal ---
    modal = None
    warnings = list(mass_asm.warnings) + list(stiff_asm.warnings)

    try:
        solver = StructuralSolver(
            K_global=stiff_asm.K_global,
            M_global=mass_asm.M_global,
            fixed_dofs=fixed_dofs,
            num_dofs=mass_asm.num_dofs,
        )
        modal = solver.modal_solve(n_modes=n_modes)
        if validate:
            warnings.extend(_validate_modal(modal))
    except Exception as e:
        warnings.append(f"Modal çözüm hatası: {e}")
        import logging
        logging.getLogger(__name__).exception("[Analysis] modal_solve")

    spec_obj = _resolve_spectrum(project, spectrum)

    # --- 5. Spektral (opsiyonel) ---
    spectral = None
    if modal is not None and spectrum is not None:
        try:
            from .modal_analysis import response_spectrum_solve
            spectral = response_spectrum_solve(
                    modal=modal,
                    M_global=mass_asm.M_global,
                    num_dofs=mass_asm.num_dofs,
                    spectrum=spec_obj,
                    n_modes=n_modes,
                )
        except Exception as e:
            warnings.append(f"Spektral çözüm hatası: {e}")
            import logging
            logging.getLogger(__name__).exception("[Analysis] spectrum_solve")

    result = StructuralAnalysisResult(
        mass=mass_asm,
        stiffness=stiff_asm,
        fixed_dofs=fixed_dofs,
        modal=modal,
        spectral=spectral,
        warnings=warnings,
    )
    return result

def _resolve_spectrum(project, spectrum):
    if spectrum is None:
        return None
    if isinstance(spectrum, str):
        return project.spectrum_functions.get(spectrum)
    return spectrum