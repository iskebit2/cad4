# core/analysis/solver.py
"""
Modal ve statik solver.

ModalResult içindeki değerler:
    periods[i]         — s cinsinden periyot
    frequencies[i]     — Hz
    mode_shapes[:, i]  — normalize mod şekli (modal_dofs üzerinde)
    modal_mass[i]      — phiᵀ M phi (normalize = 1.0, eigh kütle-normalize eder)
    participation_factor_x/y/z[i] — Γ = φᵀ M r / (φᵀ M φ)
    effective_mass_x/y/z[i]       — Γ² × m_modal; toplam efektif kütle
"""
from dataclasses import dataclass
from typing import List

import numpy as np
from scipy.linalg import eigh


@dataclass
class ModalResult:
    frequencies: np.ndarray
    periods: np.ndarray
    mode_shapes: np.ndarray            # (n_modal_dofs, n_modes)
    modal_dofs: np.ndarray             # orijinal DOF endeksleri

    modal_mass: np.ndarray
    participation_factor_x: np.ndarray
    participation_factor_y: np.ndarray
    participation_factor_z: np.ndarray
    effective_mass_x: np.ndarray
    effective_mass_y: np.ndarray
    effective_mass_z: np.ndarray

    total_mass_x: float = 0.0
    total_mass_y: float = 0.0
    total_mass_z: float = 0.0

    def __len__(self):
        return len(self.periods)

    @property
    def n_modes(self):
        return len(self.periods)

    def __inspector_tree__(self):
        modes = {}
        for i in range(self.n_modes):
            modes[f"Mode {i+1}"] = {
                "T (s)": f"{self.periods[i]:.4f}",
                "f (Hz)": f"{self.frequencies[i]:.3f}",
                "ΓX": f"{self.participation_factor_x[i]:.4f}",
                "ΓY": f"{self.participation_factor_y[i]:.4f}",
                "ΓZ": f"{self.participation_factor_z[i]:.4f}",
                "MeffX": f"{self.effective_mass_x[i]:.3f}",
            }
        return {
            "Summary": {
                "n_modes": self.n_modes,
                "total_mass_x": f"{self.total_mass_x:.3f} kg",
            },
            "Modes": modes,
        }


class StructuralSolver:
    def __init__(self, K_global, M_global, fixed_dofs, num_dofs):
        self.K = np.asarray(K_global, dtype=float)
        self.M = np.asarray(M_global, dtype=float)
        self.fixed_dofs = set(int(d) for d in fixed_dofs if d is not None)
        self.num_dofs = int(num_dofs)

        all_dofs = set(range(self.num_dofs))
        self.free_dofs = np.array(
            sorted(all_dofs - self.fixed_dofs),
            dtype=int,
        )

    # ==================================================================
    def _reduced(self):
        idx = np.ix_(self.free_dofs, self.free_dofs)
        return self.K[idx], self.M[idx]

    # ==================================================================
    def static_solve(self, F):
        K, _ = self._reduced()
        F = np.asarray(F, dtype=float)
        F_red = F[self.free_dofs]
        U_red = np.linalg.solve(K, F_red)
        U = np.zeros(self.num_dofs)
        U[self.free_dofs] = U_red
        return U

    # ==================================================================
    def modal_solve(self, n_modes=10):
        K, M = self._reduced()

        # Sadece öteleme DOF'ları (master)
        master = [i for i, d in enumerate(self.free_dofs) if int(d) % 6 in (0, 1, 2)]
        slave = [i for i, d in enumerate(self.free_dofs) if int(d) % 6 in (3, 4, 5)]

        K_mm = K[np.ix_(master, master)]
        M_mm = M[np.ix_(master, master)]

        if slave:
            K_ms = K[np.ix_(master, slave)]
            K_ss = K[np.ix_(slave, slave)]

            # K_ss'in rank-deficient olup olmadığını kontrol
            cond = np.linalg.cond(K_ss)
            import logging
            logging.getLogger(__name__).info(
                "[Modal] K_ss cond = %.2e, size = %d", cond, len(slave)
            )

            # pinv yerine lstsq ile daha stabil
            try:
                if cond < 1e12:
                    K_ss_inv = np.linalg.inv(K_ss)
                else:
                    # Near-singular: düzenleme ekle
                    n = K_ss.shape[0]
                    K_ss_reg = K_ss + 1e-6 * np.max(np.abs(np.diag(K_ss))) * np.eye(n)
                    K_ss_inv = np.linalg.inv(K_ss_reg)
                    logging.getLogger(__name__).warning(
                        "[Modal] K_ss near-singular (cond=%.2e), regularize", cond
                    )
            except np.linalg.LinAlgError:
                K_ss_inv = np.linalg.pinv(K_ss)

            K_eff = K_mm - K_ms @ K_ss_inv @ K_ms.T
        else:
            K_eff = K_mm

        M_eff = M_mm

        # Sıfır kütleli master'ları filtrele
        m_diag = np.diag(M_eff)
        positive = m_diag > 1e-12
        if not np.any(positive):
            raise RuntimeError("Pozitif kütleli DOF yok")

        if not np.all(positive):
            K_eff = K_eff[np.ix_(positive, positive)]
            M_eff = M_eff[np.ix_(positive, positive)]
            master = [m for m, p in zip(master, positive) if p]

        modal_dofs = self.free_dofs[np.array(master, dtype=int)]

        eigenvalues, vectors = eigh(K_eff, M_eff)
        eigenvalues = np.maximum(eigenvalues, 0.0)
        
        # Rijit cisim modlarını filtrele (eigenvalue ≈ 0)
        max_eig = eigenvalues.max()
        if max_eig <= 0:
            raise RuntimeError("Tüm eigenvalue'lar sıfır")
        
        eps = 1e-6 * max_eig
        positive = eigenvalues > eps
        
        n_rigid = int(np.sum(~positive))
        if n_rigid > 0:
            import logging
            logging.getLogger(__name__).warning(
                "[Modal] %d rijit cisim modu filtrelendi (mesnet yetersiz)",
                n_rigid,
            )
        
        if not np.any(positive):
            raise RuntimeError("Sadece rijit mod var — mesnetleri kontrol edin")
        
        eigenvalues = eigenvalues[positive]
        vectors = vectors[:, positive]
        
        # Şimdi n_modes'u al
        omega = np.sqrt(eigenvalues)
        frequencies = omega / (2.0 * np.pi)
        periods = np.where(frequencies > 1e-6, 1.0 / frequencies, 0.0)
        
        count = min(n_modes, len(frequencies))
        frequencies = frequencies[:count]
        periods = periods[:count]
        vectors = vectors[:, :count]

        # --- Participation ---
        r_x = np.array([1.0 if int(d) % 6 == 0 else 0.0 for d in modal_dofs])
        r_y = np.array([1.0 if int(d) % 6 == 1 else 0.0 for d in modal_dofs])
        r_z = np.array([1.0 if int(d) % 6 == 2 else 0.0 for d in modal_dofs])

        total_mass_x = float(r_x @ M_eff @ r_x)
        total_mass_y = float(r_y @ M_eff @ r_y)
        total_mass_z = float(r_z @ M_eff @ r_z)

        modal_mass = np.zeros(count)
        gamma_x = np.zeros(count)
        gamma_y = np.zeros(count)
        gamma_z = np.zeros(count)
        eff_x = np.zeros(count)
        eff_y = np.zeros(count)
        eff_z = np.zeros(count)

        for i in range(count):
            phi = vectors[:, i]
            m_modal = float(phi @ M_eff @ phi)
            modal_mass[i] = m_modal
            if m_modal <= 0:
                continue

            lx = float(phi @ M_eff @ r_x)
            ly = float(phi @ M_eff @ r_y)
            lz = float(phi @ M_eff @ r_z)

            gamma_x[i] = lx / m_modal
            gamma_y[i] = ly / m_modal
            gamma_z[i] = lz / m_modal

            eff_x[i] = lx * lx / m_modal
            eff_y[i] = ly * ly / m_modal
            eff_z[i] = lz * lz / m_modal

        return ModalResult(
            frequencies=frequencies,
            periods=periods,
            mode_shapes=vectors,
            modal_dofs=modal_dofs,
            modal_mass=modal_mass,
            participation_factor_x=gamma_x,
            participation_factor_y=gamma_y,
            participation_factor_z=gamma_z,
            effective_mass_x=eff_x,
            effective_mass_y=eff_y,
            effective_mass_z=eff_z,
            total_mass_x=total_mass_x,
            total_mass_y=total_mass_y,
            total_mass_z=total_mass_z,
        )

    