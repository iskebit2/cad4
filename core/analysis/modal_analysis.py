# core/analysis/modal_analysis.py

from dataclasses import dataclass

import numpy as np

from .mass_source import G_MM_S2
from .solver import ModalResult


# ============================================================
# SPEKTRAL MOD SONUCU
# ============================================================

@dataclass
class SpectralModeResult:

    mode: int

    period: float
    frequency: float

    participation_x: float
    participation_y: float
    participation_z: float

    spectral_acceleration: float

    displacement_x: np.ndarray
    displacement_y: np.ndarray
    displacement_z: np.ndarray

    def __inspector_tree__(self):

        return {
            f"Mode {self.mode}": {
                "Period": f"{self.period:.4f} s",
                "Frequency": f"{self.frequency:.4f} Hz",
                "ΓX": f"{self.participation_x:.4f}",
                "ΓY": f"{self.participation_y:.4f}",
                "ΓZ": f"{self.participation_z:.4f}",
                "Sa": f"{self.spectral_acceleration:.4f} g",
            }
        }


# ============================================================
# SPEKTRAL SONUÇ
# ============================================================

@dataclass
class SpectralResult:

    modes: list

    ux_srss: np.ndarray
    uy_srss: np.ndarray
    uz_srss: np.ndarray

    def __inspector_tree__(self):

        return {
            "Spectral Analysis": {
                "Modes Used": len(self.modes),
            },
            "SRSS": {
                "UX Max": f"{np.max(np.abs(self.ux_srss)):.3f} mm",
                "UY Max": f"{np.max(np.abs(self.uy_srss)):.3f} mm",
                "UZ Max": f"{np.max(np.abs(self.uz_srss)):.3f} mm",
            },
        }


# ============================================================
# RESPONSE SPECTRUM
# ============================================================

def _direction_vector(
    modal_dofs,
    direction
):

    if direction == "X":
        component = 0

    elif direction == "Y":
        component = 1

    elif direction == "Z":
        component = 2

    else:
        raise ValueError(
            f"Geçersiz yön: {direction}"
        )

    return np.array([
        1.0 if dof % 6 == component
        else 0.0
        for dof in modal_dofs
    ])


def response_spectrum_solve(
    modal: ModalResult,
    M_global,
    num_dofs,
    spectrum,
    n_modes=None
):

    if n_modes is None:
        n_modes = modal.n_modes

    n_modes = min(
        n_modes,
        modal.n_modes
    )

    modal_dofs = modal.modal_dofs

    M_modal = M_global[
        np.ix_(
            modal_dofs,
            modal_dofs
        )
    ]

    r_x = _direction_vector(
        modal_dofs,
        "X"
    )

    r_y = _direction_vector(
        modal_dofs,
        "Y"
    )

    r_z = _direction_vector(
        modal_dofs,
        "Z"
    )

    ux_modes = []
    uy_modes = []
    uz_modes = []

    mode_results = []

    for i in range(n_modes):

        phi = modal.mode_shapes[:, i]

        T = modal.periods[i]

        if T <= 0.0:
            continue

        # --------------------------------------------
        # Modal participation
        # --------------------------------------------

        m_modal = (
            phi @ M_modal @ phi
        )

        if m_modal <= 0.0:
            continue

        lx = phi @ M_modal @ r_x
        ly = phi @ M_modal @ r_y
        lz = phi @ M_modal @ r_z

        gamma_x = lx / m_modal
        gamma_y = ly / m_modal
        gamma_z = lz / m_modal

        # --------------------------------------------
        # Spektral ivme
        # --------------------------------------------

        Sa_g = spectrum.get_sa(T)

        Sa = Sa_g * G_MM_S2

        omega2 = (
            2.0 *
            np.pi /
            T
        ) ** 2

        displacement_factor = (
            Sa /
            omega2
        )

        # --------------------------------------------
        # Mod şekli × modal katsayı
        # --------------------------------------------

        ux_modal = (
            gamma_x *
            displacement_factor *
            phi
        )

        uy_modal = (
            gamma_y *
            displacement_factor *
            phi
        )

        uz_modal = (
            gamma_z *
            displacement_factor *
            phi
        )

        # --------------------------------------------
        # Full DOF
        # --------------------------------------------

        ux_full = np.zeros(num_dofs)
        uy_full = np.zeros(num_dofs)
        uz_full = np.zeros(num_dofs)

        ux_full[
            modal_dofs
        ] = ux_modal

        uy_full[
            modal_dofs
        ] = uy_modal

        uz_full[
            modal_dofs
        ] = uz_modal

        ux_modes.append(ux_full)
        uy_modes.append(uy_full)
        uz_modes.append(uz_full)

        mode_results.append(
            SpectralModeResult(
                mode=i + 1,

                period=T,
                frequency=modal.frequencies[i],

                participation_x=gamma_x,
                participation_y=gamma_y,
                participation_z=gamma_z,

                spectral_acceleration=Sa_g,

                displacement_x=ux_full,
                displacement_y=uy_full,
                displacement_z=uz_full,
            )
        )

    # ========================================================
    # SRSS
    # ========================================================

    if ux_modes:

        ux_srss = np.sqrt(
            np.sum(
                np.square(ux_modes),
                axis=0
            )
        )

        uy_srss = np.sqrt(
            np.sum(
                np.square(uy_modes),
                axis=0
            )
        )

        uz_srss = np.sqrt(
            np.sum(
                np.square(uz_modes),
                axis=0
            )
        )

    else:

        ux_srss = np.zeros(num_dofs)
        uy_srss = np.zeros(num_dofs)
        uz_srss = np.zeros(num_dofs)

    return SpectralResult(
        modes=mode_results,

        ux_srss=ux_srss,
        uy_srss=uy_srss,
        uz_srss=uz_srss,
    )