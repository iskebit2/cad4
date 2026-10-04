# core/analysis/solver.py

from dataclasses import dataclass

import numpy as np
from scipy.linalg import eigh


# ============================================================
# MODAL SONUÇ
# ============================================================

@dataclass
class ModalResult:

    frequencies: np.ndarray
    periods: np.ndarray

    mode_shapes: np.ndarray
    modal_dofs: np.ndarray

    modal_mass: np.ndarray
    participation_factor_x: np.ndarray
    participation_factor_y: np.ndarray
    participation_factor_z: np.ndarray

    effective_mass_x: np.ndarray
    effective_mass_y: np.ndarray
    effective_mass_z: np.ndarray

    def __len__(self):
        return len(self.periods)

    @property
    def n_modes(self):
        return len(self.periods)

    def mode(self, index):
        return self.mode_shapes[:, index]

    def __inspector_tree__(self):

        modes = {}

        for i in range(self.n_modes):

            modes[f"Mode {i + 1}"] = {
                "Period": f"{self.periods[i]:.4f} s",
                "Frequency": f"{self.frequencies[i]:.4f} Hz",
                "Modal Mass": f"{self.modal_mass[i]:.4f}",
                "ΓX": f"{self.participation_factor_x[i]:.4f}",
                "ΓY": f"{self.participation_factor_y[i]:.4f}",
                "ΓZ": f"{self.participation_factor_z[i]:.4f}",
                "Mₑff X": f"{self.effective_mass_x[i]:.3f}",
                "Mₑff Y": f"{self.effective_mass_y[i]:.3f}",
                "Mₑff Z": f"{self.effective_mass_z[i]:.3f}",
            }

        return {
            "Modal Summary": {
                "Number of Modes": self.n_modes,
            },
            "Modes": modes,
        }


# ============================================================
# SOLVER
# ============================================================

class StructuralSolver:

    def __init__(
        self,
        K_global,
        M_global,
        fixed_dofs,
        num_dofs
    ):

        self.K = np.asarray(
            K_global,
            dtype=float
        )

        self.M = np.asarray(
            M_global,
            dtype=float
        )

        self.fixed_dofs = set(fixed_dofs)
        self.num_dofs = num_dofs

        self.free_dofs = np.array(
            sorted(
                set(range(num_dofs))
                - self.fixed_dofs
            ),
            dtype=int
        )

    # ========================================================
    # REDUCTION
    # ========================================================

    def _reduced_matrices(self):

        idx = np.ix_(
            self.free_dofs,
            self.free_dofs
        )

        return (
            self.K[idx],
            self.M[idx]
        )

    # ========================================================
    # STATİK
    # ========================================================

    def static_solve(
        self,
        F
    ):

        K, _ = self._reduced_matrices()

        F = np.asarray(
            F,
            dtype=float
        )

        F_red = F[
            self.free_dofs
        ]

        U_red = np.linalg.solve(
            K,
            F_red
        )

        U = np.zeros(
            self.num_dofs
        )

        U[
            self.free_dofs
        ] = U_red

        return U

    # ========================================================
    # MODAL
    # ========================================================

    def modal_solve(
        self,
        n_modes=10
    ):

        K, M = self._reduced_matrices()

        # ----------------------------------------------------
        # Sadece öteleme DOF'ları
        # ----------------------------------------------------

        modal_positions = [
            i
            for i, dof in enumerate(self.free_dofs)
            if dof % 6 in (0, 1, 2)
        ]

        modal_dofs = self.free_dofs[
            modal_positions
        ]

        K_m = K[
            np.ix_(
                modal_positions,
                modal_positions
            )
        ]

        M_m = M[
            np.ix_(
                modal_positions,
                modal_positions
            )
        ]

        # ----------------------------------------------------
        # Sıfır kütleli DOF'ları çıkar
        # ----------------------------------------------------

        mass_diag = np.diag(M_m)

        positive = mass_diag > 1e-12

        if not np.all(positive):

            K_m = K_m[
                np.ix_(
                    positive,
                    positive
                )
            ]

            M_m = M_m[
                np.ix_(
                    positive,
                    positive
                )
            ]

            modal_dofs = modal_dofs[
                positive
            ]

        # ----------------------------------------------------
        # Özdeğer çözümü
        # ----------------------------------------------------

        eigenvalues, vectors = eigh(
            K_m,
            M_m
        )

        eigenvalues = np.maximum(
            eigenvalues,
            0.0
        )

        omega = np.sqrt(
            eigenvalues
        )

        frequencies = (
            omega /
            (2.0 * np.pi)
        )

        periods = np.zeros_like(
            frequencies
        )

        positive_frequency = (
            frequencies > 1e-12
        )

        periods[
            positive_frequency
        ] = (
            1.0 /
            frequencies[
                positive_frequency
            ]
        )

        count = min(
            n_modes,
            len(periods)
        )

        frequencies = frequencies[:count]
        periods = periods[:count]
        vectors = vectors[:, :count]

        # ----------------------------------------------------
        # Modal kütle ve katılım
        # ----------------------------------------------------

        # ----------------------------------------------------
        # Modal kütle ve katılım
        # ----------------------------------------------------

        M_modal = M_m

        r_x = np.array([
            1.0 if dof % 6 == 0 else 0.0
            for dof in modal_dofs
        ])

        r_y = np.array([
            1.0 if dof % 6 == 1 else 0.0
            for dof in modal_dofs
        ])

        r_z = np.array([
            1.0 if dof % 6 == 2 else 0.0
            for dof in modal_dofs
        ])

        total_mass_x = (
            r_x @ M_modal @ r_x
        )

        total_mass_y = (
            r_y @ M_modal @ r_y
        )

        total_mass_z = (
            r_z @ M_modal @ r_z
        )

        modal_mass = np.zeros(count)

        gamma_x = np.zeros(count)
        gamma_y = np.zeros(count)
        gamma_z = np.zeros(count)

        effective_x = np.zeros(count)
        effective_y = np.zeros(count)
        effective_z = np.zeros(count)

        for i in range(count):

            phi = vectors[:, i]

            m_modal = (
                phi @ M_modal @ phi
            )

            modal_mass[i] = m_modal

            if m_modal <= 0.0:
                continue

            lx = (
                phi @ M_modal @ r_x
            )

            ly = (
                phi @ M_modal @ r_y
            )

            lz = (
                phi @ M_modal @ r_z
            )

            gamma_x[i] = lx / m_modal
            gamma_y[i] = ly / m_modal
            gamma_z[i] = lz / m_modal

            effective_x[i] = (
                lx * lx / m_modal
            )

            effective_y[i] = (
                ly * ly / m_modal
            )

            effective_z[i] = (
                lz * lz / m_modal
            )

        return ModalResult(
            frequencies=frequencies,
            periods=periods,
            mode_shapes=vectors,
            modal_dofs=modal_dofs,

            modal_mass=modal_mass,

            participation_factor_x=gamma_x,
            participation_factor_y=gamma_y,
            participation_factor_z=gamma_z,

            effective_mass_x=effective_x,
            effective_mass_y=effective_y,
            effective_mass_z=effective_z,
        )