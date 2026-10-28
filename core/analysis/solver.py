# core/analysis/solver.py

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from scipy.linalg import eigh

logger = logging.getLogger(__name__)


import logging

logger = logging.getLogger(__name__)

@dataclass
class ModalResult:
    frequencies: np.ndarray            # (n_modes,) Hz
    periods: np.ndarray                # (n_modes,) s
    mode_shapes: np.ndarray            # (n_free_dofs, n_modes)
    modal_dofs: np.ndarray             # (n_free_dofs,) global DOF endeksleri

    modal_mass: np.ndarray             # (n_modes,) genelleştirilmiş kütle
    participation_factor_x: np.ndarray # (n_modes,)
    participation_factor_y: np.ndarray
    participation_factor_z: np.ndarray
    effective_mass_x: np.ndarray       # (n_modes,) kg
    effective_mass_y: np.ndarray
    effective_mass_z: np.ndarray

    total_mass_x: float = 0.0          # kg
    total_mass_y: float = 0.0
    total_mass_z: float = 0.0

    def __len__(self) -> int:
        return len(self.periods)

    @property
    def n_modes(self) -> int:
        return len(self.periods)

def perform_guyan_condensation(K, M, master_indices, slave_indices):
    # Matrisleri dense formata çevir
    K = K.toarray() if hasattr(K, 'toarray') else K
    M = M.toarray() if hasattr(M, 'toarray') else M

    # Bloklara ayır
    K_mm = K[np.ix_(master_indices, master_indices)]
    K_ms = K[np.ix_(master_indices, slave_indices)]
    K_sm = K[np.ix_(slave_indices, master_indices)]
    K_ss = K[np.ix_(slave_indices, slave_indices)]

    M_mm = M[np.ix_(master_indices, master_indices)]
    M_ms = M[np.ix_(master_indices, slave_indices)]
    M_sm = M[np.ix_(slave_indices, master_indices)]
    M_ss = M[np.ix_(slave_indices, slave_indices)]

    # T_s matrisini çöz: K_ss * T_s = -K_sm -> T_s = -inv(K_ss) * K_sm
    try:
        T_s = -np.linalg.solve(K_ss, K_sm)
    except np.linalg.LinAlgError:
        # Tekil matris riskine karşı küçük bir ridge (regularization) eklenebilir
        K_ss_reg = K_ss + 1e-10 * np.eye(K_ss.shape[0])
        T_s = -np.linalg.solve(K_ss_reg, K_sm)

    # İndirgenmiş (reduced) Stiffness Matrisi: K_red = K_mm + K_ms * T_s
    K_red = K_mm + K_ms @ T_s

    # İndirgenmiş (reduced) Mass Matrisi (Consistent mass dönüşümü):
    # M_red = M_mm + M_ms*T_s + T_s^T*M_sm + T_s^T*M_ss*T_s
    M_red = M_mm + (M_ms @ T_s) + (T_s.T @ M_sm) + (T_s.T @ M_ss @ T_s)

    # Simetriyi garantiye alalım
    K_red = 0.5 * (K_red + K_red.T)
    M_red = 0.5 * (M_red + M_red.T)

    return K_red, M_red

class StructuralSolver:
    ROT_MASS_SCALE: float = 1e-6
    MIN_MASS: float = 1e-9
    EIGEN_TOL: float = 1e-6

    def __init__(
        self,
        K_global: np.ndarray,
        M_global: np.ndarray,
        fixed_dofs,
        num_dofs: int,
    ):
        self.K = np.asarray(K_global, dtype=float)
        self.M = np.asarray(M_global, dtype=float)
        self.fixed_dofs = {int(d) for d in fixed_dofs if d is not None}
        self.num_dofs = int(num_dofs)

        all_dofs = set(range(self.num_dofs))
        self.free_dofs = np.array(sorted(all_dofs - self.fixed_dofs), dtype=int)

    def _guyan_reduced(self):
        K_red, M_red = self._reduced()
        m_diag = np.diag(M_red)
        master = np.where(m_diag > 1e-9)[0]
        slave = np.where(m_diag <= 1e-9)[0]

        if len(slave) == 0:
            return K_red[np.ix_(master, master)], M_red[np.ix_(master, master)]

        K_red_cond, M_red_cond = perform_guyan_condensation(K_red, M_red, master, slave)
        return K_red_cond, M_red_cond

    def _reduced(self) -> tuple[np.ndarray, np.ndarray]:
        idx = np.ix_(self.free_dofs, self.free_dofs)
        return self.K[idx], self.M[idx]

    def static_solve(self, F: np.ndarray) -> np.ndarray:
        K_red, _ = self._reduced()
        F_red = np.asarray(F, dtype=float)[self.free_dofs]
        U_red = np.linalg.solve(K_red, F_red)

        U = np.zeros(self.num_dofs)
        U[self.free_dofs] = U_red
        return U

    def modal_solve(
        self,
        n_modes: int = 10,
        debug: bool = True,
        use_condensation: bool = True,
    ) -> ModalResult:
        K_red, M_red = self._reduced()

        dof_types = self.free_dofs % 6
        trans_idx = np.where(dof_types < 3)[0]  # Öteleme (Master / a)
        rot_idx = np.where(dof_types >= 3)[0]    # Rotasyon (Slave / b)

        if debug:
            print("\n--- Guyan / Kütlesiz DOF Analizi ---")
            print(f"Toplam serbest DOF: {len(self.free_dofs)}")
            print(f"Öteleme (kütleli) DOF sayısı: {len(trans_idx)}")
            print(f"Rotasyon (kütlesiz) DOF sayısı: {len(rot_idx)}")
            print(f"Kondensasyon: {'AKTİF (Guyan)' if use_condensation else 'KAPALI (Full)'}")

        G: np.ndarray | None = None

        # ==============================================================
        # DAL 1: GUYAN STATİK KONDENSASYONU (Optimize Edilmiş Fonksiyon)
        # ==============================================================
        if use_condensation and len(rot_idx) > 0:
            # Güncel ve kararlı harici kondensasyon alt fonksiyonunu çağırıyoruz
            K_cond, M_cond = perform_guyan_condensation(K_red, M_red, trans_idx, rot_idx)

            # Kinematik ilişki matrisi T_s (G) geri kazanım adımları için hesaplanır
            K_bb = K_red[np.ix_(rot_idx, rot_idx)]
            K_ba = K_red[np.ix_(rot_idx, trans_idx)]
            try:
                from scipy.linalg import cho_factor, cho_solve
                c, low = cho_factor(K_bb, lower=True, check_finite=False)
                G = cho_solve((c, low), -K_ba, check_finite=False)
            except (np.linalg.LinAlgError, ValueError):
                # K_bb tekil veya kötü koşullu ise regularization ekleyerek kararlı çözüm sağlarız
                K_bb_reg = K_bb + 1e-10 * np.eye(K_bb.shape[0])
                try:
                    c, low = cho_factor(K_bb_reg, lower=True, check_finite=False)
                    G = cho_solve((c, low), -K_ba, check_finite=False)
                except Exception:
                    G, *_ = np.linalg.lstsq(K_bb_reg, -K_ba, rcond=None)

            eigenvalues, vectors_a = eigh(K_cond, M_cond)
            eigenvalues = np.maximum(eigenvalues, 0.0)
            order = np.argsort(eigenvalues)
            eigenvalues = eigenvalues[order]
            vectors_a = vectors_a[:, order]

            omega = np.sqrt(eigenvalues)
            frequencies = omega / (2.0 * np.pi)
            valid = frequencies > self.EIGEN_TOL

            eigenvalues = eigenvalues[valid]
            vectors_a = vectors_a[:, valid]
            frequencies = frequencies[valid]
            periods = np.where(frequencies > self.EIGEN_TOL, 1.0 / frequencies, np.inf)

            count = min(n_modes, len(frequencies))
            vectors_a = vectors_a[:, :count]
            frequencies = frequencies[:count]
            periods = periods[:count]

            # Tam DOF uzayına geri dönüştürme (Öteleme + Rotasyon = G @ vectors_a)
            full_vectors = np.zeros((len(self.free_dofs), count))
            full_vectors[trans_idx, :] = vectors_a
            if G is not None:
                full_vectors[rot_idx, :] = G @ vectors_a

            participation, eff_mass, modal_mass = self._participation_condensed(
                vectors_a, M_cond, trans_idx, rot_idx, G, self.free_dofs,
            )
            total_mass_x, total_mass_y, total_mass_z = self._total_masses_condensed(
                M_cond, trans_idx, rot_idx, G, self.free_dofs,
            )

        # ==============================================================
        # DAL 2: FULL DOF ÇÖZÜMÜ
        # ==============================================================
        else:
            M_eff = self._build_effective_mass(M_red)
            eigenvalues, full_vectors = eigh(K_red, M_eff)
            eigenvalues = np.maximum(eigenvalues, 0.0)
            order = np.argsort(eigenvalues)
            eigenvalues = eigenvalues[order]
            full_vectors = full_vectors[:, order]

            omega = np.sqrt(eigenvalues)
            frequencies = omega / (2.0 * np.pi)
            valid = frequencies > self.EIGEN_TOL

            eigenvalues = eigenvalues[valid]
            full_vectors = full_vectors[:, valid]
            frequencies = frequencies[valid]
            periods = np.where(frequencies > self.EIGEN_TOL, 1.0 / frequencies, np.inf)

            count = min(n_modes, len(frequencies))
            full_vectors = full_vectors[:, :count]
            frequencies = frequencies[:count]
            periods = periods[:count]

            participation, eff_mass, modal_mass = self._participation(
                full_vectors, M_red, self.free_dofs,
            )
            total_mass_x, total_mass_y, total_mass_z = self._total_masses(
                M_red, self.free_dofs,
            )

        return ModalResult(
            frequencies=frequencies,
            periods=periods,
            mode_shapes=full_vectors,
            modal_dofs=self.free_dofs,
            modal_mass=modal_mass,
            participation_factor_x=participation[:, 0],
            participation_factor_y=participation[:, 1],
            participation_factor_z=participation[:, 2],
            effective_mass_x=eff_mass[:, 0],
            effective_mass_y=eff_mass[:, 1],
            effective_mass_z=eff_mass[:, 2],
            total_mass_x=total_mass_x,
            total_mass_y=total_mass_y,
            total_mass_z=total_mass_z,
        )

    def _build_effective_mass(self, M: np.ndarray) -> np.ndarray:
        m_diag = np.diag(M).astype(float).copy()
        n = len(m_diag)
        if n == 0:
            return M.copy()

        M_eff = M.copy()
        m_max = float(m_diag.max()) if n else 1.0
        mass_tol = 1e-9 * max(1.0, m_max)

        trans_mass_map: dict[int, float] = {}
        for i, dof in enumerate(self.free_dofs):
            dof_int = int(dof)
            if dof_int % 6 == 0 and m_diag[i] > mass_tol:
                trans_mass_map[dof_int] = float(m_diag[i])

        for i in range(n):
            dof_int = int(self.free_dofs[i])
            dof_type = dof_int % 6
            if dof_type in (3, 4, 5):
                node_base = dof_int - dof_type
                m_trans = trans_mass_map.get(node_base, 1000.0)
                if M_eff[i, i] < self.MIN_MASS:
                    M_eff[i, i] = max(m_trans * self.ROT_MASS_SCALE, self.MIN_MASS)

        return M_eff

    def _participation_condensed(
        self,
        vectors_a: np.ndarray,
        M_cond: np.ndarray,
        trans_idx: np.ndarray,
        rot_idx: np.ndarray,
        G: np.ndarray | None,
        modal_dofs: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        n_modes = vectors_a.shape[1]
        if n_modes == 0:
            z = np.zeros((0, 3))
            return z, z, np.zeros(0)

        r_full = self._direction_vectors(modal_dofs)
        r_a = r_full[:, trans_idx]
        if G is not None:
            r_b = r_full[:, rot_idx]
            r_cond = r_a + r_b @ G
        else:
            r_cond = r_a

        M_phi = M_cond @ vectors_a
        modal_mass = np.einsum("ij,ij->j", vectors_a, M_phi)
        safe_mass = np.where(modal_mass > 0, modal_mass, 1.0)

        L = vectors_a.T @ M_cond @ r_cond.T
        participation = L / safe_mass[:, None]
        eff_mass = (L ** 2) / safe_mass[:, None]

        return participation, eff_mass, modal_mass

    def _total_masses_condensed(
        self,
        M_cond: np.ndarray,
        trans_idx: np.ndarray,
        rot_idx: np.ndarray,
        G: np.ndarray | None,
        modal_dofs: np.ndarray,
    ) -> tuple[float, float, float]:
        r_full = self._direction_vectors(modal_dofs)
        r_a = r_full[:, trans_idx]
        if G is not None:
            r_b = r_full[:, rot_idx]
            r_cond = r_a + r_b @ G
        else:
            r_cond = r_a

        totals = []
        for i in range(3):
            r_i = r_cond[i]
            totals.append(float(r_i @ M_cond @ r_i))
        return tuple(totals)  # type: ignore

    def _participation(
        self,
        mode_shapes: np.ndarray,
        M_red: np.ndarray,
        modal_dofs: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        n_modes = mode_shapes.shape[1]
        if n_modes == 0:
            z = np.zeros((0, 3))
            return z, z, np.zeros(0)

        r = self._direction_vectors(modal_dofs)
        M_phi = M_red @ mode_shapes
        modal_mass = np.einsum("ij,ij->j", mode_shapes, M_phi)
        safe_mass = np.where(modal_mass > 0, modal_mass, 1.0)

        L = mode_shapes.T @ M_red @ r.T
        participation = L / safe_mass[:, None]
        eff_mass = (L ** 2) / safe_mass[:, None]

        return participation, eff_mass, modal_mass

    @staticmethod
    def _total_masses(
        M_red: np.ndarray,
        modal_dofs: np.ndarray,
    ) -> tuple[float, float, float]:
        d = np.asarray(modal_dofs) % 6
        rx = (d == 0).astype(float)
        ry = (d == 1).astype(float)
        rz = (d == 2).astype(float)
        return (
            float(rx @ M_red @ rx),
            float(ry @ M_red @ ry),
            float(rz @ M_red @ rz),
        )

    def _direction_vectors(self, modal_dofs: np.ndarray) -> np.ndarray:
        d = np.asarray(modal_dofs) % 6
        return np.vstack([
            (d == 0).astype(float),
            (d == 1).astype(float),
            (d == 2).astype(float),
        ])