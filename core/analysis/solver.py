# core/analysis/solver.py
"""
Modal Çözücü — Genelleştirilmiş Özdeğer Problemi (K·φ = λ·M·φ)

Yöntem ve Kabuller:
------------------
- Statik kondensasyon (Guyan) kullanılmaz; tüm serbestlikler (Full DOF: 
  3 öteleme + 3 rotasyon) doğrudan çözüme dahil edilir.
- M (kütle matrisi) köşegendir (lumped). Öteleme DOF'larında gerçek kütle,
  rotasyonel DOF'larda ise tekilliği önlemek ve sayısal kararlılığı 
  sağlamak amacıyla düğüm öteleme kütlesine bağlı akıllı atalet (MMI) 
  regülasyonu uygulanır.
- Çözüm scipy.linalg.eigh ile gerçekleştirilir.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np
from scipy.linalg import eigh

logger = logging.getLogger(__name__)


@dataclass
class ModalResult:
    """Modal analiz sonuç veri yapısı."""

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


class StructuralSolver:
    """
    Genelleştirilmiş sistem çözücüsü (Statik ve Modal).
    """

    # Rotasyonel serbestlikler için kütle atalet ölçeği (MMI regülasyonu)
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

    def _reduced(self) -> Tuple[np.ndarray, np.ndarray]:
        """Mesnetli DOF'lar arındırılarak matrisler küçültülür."""
        idx = np.ix_(self.free_dofs, self.free_dofs)
        return self.K[idx], self.M[idx]

    def static_solve(self, F: np.ndarray) -> np.ndarray:
        """K·U = F bağıntısını çözer."""
        K_red, _ = self._reduced()
        F_red = np.asarray(F, dtype=float)[self.free_dofs]
        U_red = np.linalg.solve(K_red, F_red)

        U = np.zeros(self.num_dofs)
        U[self.free_dofs] = U_red
        return U

    def modal_solve(self, n_modes: int = 10, debug=False) -> ModalResult:
        """
        Full DOF modal analiz gerçekleştirir ve ilk `n_modes` modu döndürür.
        """
        K_red, M_red = self._reduced()
        M_eff = self._build_effective_mass(M_red)

        if debug:
            print("DEBUG")
            evals, evecs = eigh(K_red, M_eff)
            v = evecs[:, 0]
            lambda1 = evals[0]
            residual = K_red @ v - lambda1 * (M_eff @ v)
            print(f"||K_red·v - λ·M_eff·v|| = {np.linalg.norm(residual):.3e}")
            print(f"||K_red·v|| = {np.linalg.norm(K_red @ v):.3e}")
            print(f"||λ·M_eff·v|| = {np.linalg.norm(lambda1 * (M_eff @ v)):.3e}")
            print("-"*20)

        # Özdeğer problemi çözümü: K·φ = λ·M·φ
        eigenvalues, vectors = eigh(K_red, M_eff)
        eigenvalues = np.maximum(eigenvalues, 0.0)

        # Küçükten büyüğe sıralama
        order = np.argsort(eigenvalues)
        eigenvalues = eigenvalues[order]
        vectors = vectors[:, order]

        # Sıfır / rijit cisim modlarının filtrelenmesi
        omega = np.sqrt(eigenvalues)
        frequencies = omega / (2.0 * np.pi)
        valid = frequencies > self.EIGEN_TOL

        eigenvalues = eigenvalues[valid]
        vectors = vectors[:, valid]
        frequencies = frequencies[valid]

        periods = np.where(
            frequencies > self.EIGEN_TOL,
            1.0 / frequencies,
            np.inf,
        )

        count = min(n_modes, len(frequencies))
        modal_dofs = self.free_dofs

        # Katılım faktörleri ve efektif kütle hesapları
        participation, eff_mass, modal_mass = self._participation(
            vectors[:, :count], M_red, modal_dofs,
        )
        total_mass_x, total_mass_y, total_mass_z = self._total_masses(M_red, modal_dofs)

        return ModalResult(
            frequencies=frequencies[:count],
            periods=periods[:count],
            mode_shapes=vectors[:, :count],
            modal_dofs=modal_dofs,
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
        """
        Öteleme kütlelerini korur; kütlesiz rotasyonel DOF'lar için 
        düğüm bazlı öteleme kütlelerinden türetilen MMI regülasyonu uygular.
        """
        m_diag = np.diag(M).astype(float).copy()
        n = len(m_diag)
        if n == 0:
            return np.zeros((0, 0), dtype=float)

        m_max = float(m_diag.max()) if n else 1.0
        mass_tol = 1e-9 * max(1.0, m_max)

        # Düğüm bazlı öteleme kütlelerinin haritalanması (UX üzerinden)
        trans_mass_map: Dict[int, float] = {}
        for i, dof in enumerate(self.free_dofs):
            dof_int = int(dof)
            if dof_int % 6 == 0 and m_diag[i] > mass_tol:
                trans_mass_map[dof_int] = float(m_diag[i])

        # Efektif kütle matrisi köşegeninin inşası
        m_eff_diag = m_diag.copy()
        for i in range(n):
            dof_int = int(self.free_dofs[i])
            dof_type = dof_int % 6  # 0:UX, 1:UY, 2:UZ, 3:RX, 4:RY, 5:RZ

            if dof_type in (3, 4, 5):  # Rotasyonel DOF
                node_base = dof_int - dof_type
                m_trans = trans_mass_map.get(node_base, 1000.0)
                m_eff_diag[i] = max(m_trans * self.ROT_MASS_SCALE, self.MIN_MASS)
            else:  # Öteleme DOF
                if m_eff_diag[i] < self.MIN_MASS:
                    m_eff_diag[i] = self.MIN_MASS

        return np.diag(m_eff_diag)

    def _participation(
        self,
        mode_shapes: np.ndarray,
        M_red: np.ndarray,
        modal_dofs: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        n_modes = mode_shapes.shape[1]
        if n_modes == 0:
            z = np.zeros((0, 3))
            return z, z, np.zeros(0)

        r = self._direction_vectors(modal_dofs)
        M_phi = M_red @ mode_shapes
        modal_mass = np.einsum("ij,ij->j", mode_shapes, M_phi)
        safe_mass = np.where(modal_mass > 0, modal_mass, 1.0)

        L = np.einsum("ij,jk->ik", M_phi.T, r.T)
        participation = L / safe_mass[:, None]
        eff_mass = (L ** 2) / safe_mass[:, None]

        return participation, eff_mass, modal_mass

    def _direction_vectors(self, modal_dofs: np.ndarray) -> np.ndarray:
        d = np.asarray(modal_dofs) % 6
        return np.vstack([
            (d == 0).astype(float),
            (d == 1).astype(float),
            (d == 2).astype(float),
        ])

    @staticmethod
    def _total_masses(M_red: np.ndarray, modal_dofs: np.ndarray) -> Tuple[float, float, float]:
        d = np.asarray(modal_dofs) % 6
        rx = (d == 0).astype(float)
        ry = (d == 1).astype(float)
        rz = (d == 2).astype(float)
        return (
            float(rx @ M_red @ rx),
            float(ry @ M_red @ ry),
            float(rz @ M_red @ rz),
        )