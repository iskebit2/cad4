# core/analysis/analysis.py

from dataclasses import dataclass

import numpy as np

from .mass_source import (
    MassBreakdown,
    build_mass_data,
)

from .solver import (
    StructuralSolver,
    ModalResult,
)

from .modal_analysis import (
    SpectralResult,
    response_spectrum_solve,
)


# ============================================================
# ANALİZ SONUCU
# ============================================================

@dataclass
class StructuralAnalysisResult:

    mass: MassBreakdown

    node_masses: dict

    K: np.ndarray
    M: np.ndarray

    fixed_dofs: list

    modal: ModalResult

    spectral: SpectralResult | None = None

    def __inspector_tree__(self):

        data = {
            "Model": {
                "DOF": self.K.shape[0],
                "Fixed DOF": len(self.fixed_dofs),
            },

            "Mass": {
                "Seismic Mass":
                    f"{self.mass.total:.3f} ton",
                "G":
                    f"{self.mass.G:.3f} ton",
                "Q":
                    f"{self.mass.Q:.3f} ton",
            },

            "Modal": {
                "Modes":
                    self.modal.n_modes,
            },
        }

        if self.spectral is not None:

            data["Spectral"] = {
                "Modes":
                    len(self.spectral.modes),
                "Max UX":
                    f"{np.max(np.abs(self.spectral.ux_srss)):.3f} mm",
                "Max UY":
                    f"{np.max(np.abs(self.spectral.uy_srss)):.3f} mm",
                "Max UZ":
                    f"{np.max(np.abs(self.spectral.uz_srss)):.3f} mm",
            }

        return data


# ============================================================
# MODEL ANALİZİ
# ============================================================

def run_modal_analysis(
    scene,
    K,
    fixed_dofs,
    n=0.3,
    n_modes=10,
    spectrum=None,
):

    num_dofs = len(scene.nodes) * 6

    # --------------------------------------------------------
    # DOF'LAR
    # --------------------------------------------------------

    for i, node in enumerate(
        scene.nodes.values()
    ):

        node.dof_indices = list(
            range(
                i * 6,
                i * 6 + 6
            )
        )

    # --------------------------------------------------------
    # KÜTLE
    # --------------------------------------------------------

    M, mass, node_masses = (
        build_mass_data(
            scene,
            num_dofs,
            n
        )
    )

    # --------------------------------------------------------
    # SOLVER
    # --------------------------------------------------------

    solver = StructuralSolver(
        K_global=K,
        M_global=M,
        fixed_dofs=fixed_dofs,
        num_dofs=num_dofs,
    )

    # --------------------------------------------------------
    # MODAL
    # --------------------------------------------------------

    modal = solver.modal_solve(
        n_modes=n_modes
    )

    # --------------------------------------------------------
    # SPEKTRAL
    # --------------------------------------------------------

    spectral = None

    if spectrum is not None:

        spectral = response_spectrum_solve(
            modal=modal,
            M_global=M,
            num_dofs=num_dofs,
            spectrum=spectrum,
            n_modes=n_modes,
        )

    # --------------------------------------------------------
    # SONUÇ
    # --------------------------------------------------------

    return StructuralAnalysisResult(

        mass=mass,

        node_masses=node_masses,

        K=K,
        M=M,

        fixed_dofs=fixed_dofs,

        modal=modal,

        spectral=spectral,
    )