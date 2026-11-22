# app/commands/analysis\solver.py
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import eigsh, splu


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

    total_mass_x: float = 0.0
    total_mass_y: float = 0.0
    total_mass_z: float = 0.0

    def __len__(self) -> int:
        return len(self.periods)

    @property
    def n_modes(self) -> int:
        return len(self.periods)


class StructuralSolver:
    ROT_MASS_SCALE: float = 1e-6
    MIN_MASS: float = 1e-9
    EIGEN_TOL: float = 1e-6

    def __init__(
        self,
        K_global,
        M_global,
        fixed_dofs=None,
        num_dofs: int | None = None,
        dof_map: dict[str, int] | None = None,
        nodes: dict | None = None,
    ):
        self.K = K_global.tocsc() if sparse.issparse(K_global) else sparse.csc_matrix(np.asarray(K_global, dtype=float))
        self.M = M_global.tocsc() if sparse.issparse(M_global) else sparse.csc_matrix(np.asarray(M_global, dtype=float))
        self.num_dofs = int(num_dofs) if num_dofs is not None else int(self.K.shape[0])
        self.dof_map = dict(dof_map) if dof_map is not None else {}
        if not self.dof_map and nodes is not None:
            self.dof_map = {
                n_key: int(node.dof_indices[0])
                for n_key, node in nodes.items()
                if getattr(node, "dof_indices", None)
            }
        if len(self.dof_map) == 0 and self.num_dofs > 0:
            raise RuntimeError(
                f"dof_map boş! num_dofs={self.num_dofs}. "
                f"Node'larda dof_indices atanmamış."
            )

        resolved_fixed: set[int] = set()
        if fixed_dofs is not None:
            resolved_fixed.update(int(d) for d in fixed_dofs if d is not None)
        elif nodes is not None:
            for n_key, node in nodes.items():
                dofs = getattr(node, "dof_indices", None)
                if not dofs and n_key in self.dof_map:
                    base = self.dof_map[n_key]
                    dofs = [base + i for i in range(6)]
                r = getattr(node, "restraint", None)
                if dofs and r is not None:
                    for i, name in enumerate(("ux", "uy", "uz", "rx", "ry", "rz")):
                        if getattr(r, name, False) and i < len(dofs) and dofs[i] is not None:
                            resolved_fixed.add(int(dofs[i]))

        self.fixed_dofs = resolved_fixed
        all_dofs = set(range(self.num_dofs))
        self.free_dofs = np.array(sorted(all_dofs - self.fixed_dofs), dtype=np.intp)
        self._lu_cache = None

    def _reduced(self) -> tuple[sparse.csc_matrix, sparse.csc_matrix]:
        idx = self.free_dofs
        return self.K[idx, :][:, idx].tocsc(), self.M[idx, :][:, idx].tocsc()

    def _get_lu(self):
        if self._lu_cache is None and self.free_dofs.size > 0:
            K_red, _ = self._reduced()
            self._lu_cache = splu(K_red)
        return self._lu_cache

    def static_solve(self, F: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        F_vec = np.asarray(F, dtype=float)
        U = np.zeros(self.num_dofs, dtype=float)

        if self.free_dofs.size > 0:
            lu = self._get_lu()
            U[self.free_dofs] = lu.solve(F_vec[self.free_dofs])

        R = self.K @ U - F_vec
        if self.free_dofs.size > 0:
            R[self.free_dofs] = 0.0

        return U, R

    def modal_solve(
        self,
        n_modes: int = 10,
        use_condensation: bool = True,
    ) -> ModalResult:
        K_red, M_red = self._reduced()
        n_free = K_red.shape[0]
        if n_free == 0:
            empty = np.zeros(0, dtype=float)
            return ModalResult(
                frequencies=empty,
                periods=empty,
                mode_shapes=np.zeros((0, 0), dtype=float),
                modal_dofs=self.free_dofs,
                modal_mass=empty,
                participation_factor_x=empty,
                participation_factor_y=empty,
                participation_factor_z=empty,
                effective_mass_x=empty,
                effective_mass_y=empty,
                effective_mass_z=empty,
            )

        M_eff = self._build_effective_mass(M_red)
        k_req = min(max(n_modes + 4, n_modes), n_free - 1) if n_free > 1 else 1

        if n_free <= 60 or k_req >= n_free - 1:
            from scipy.linalg import eigh
            eigenvalues, full_vectors = eigh(K_red.toarray(), M_eff.toarray())
        else:
            eigenvalues, full_vectors = eigsh(
                K_red,
                k=k_req,
                M=M_eff,
                sigma=0.0,
                which="LM",
                tol=1e-7,
            )

        eigenvalues = np.maximum(np.real(eigenvalues), 0.0)
        full_vectors = np.real(full_vectors)
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

    def _build_effective_mass(self, M: sparse.csc_matrix) -> sparse.csc_matrix:
        m_diag = M.diagonal().astype(float)
        n = len(m_diag)
        if n == 0:
            return M.copy()

        m_max = float(m_diag.max()) if n else 1.0
        mass_tol = 1e-9 * max(1.0, m_max)

        trans_mass_map: dict[int, float] = {}
        for i, dof in enumerate(self.free_dofs):
            dof_int = int(dof)
            if dof_int % 6 == 0 and m_diag[i] > mass_tol:
                trans_mass_map[dof_int] = float(m_diag[i])

        add_diag = np.zeros(n, dtype=float)
        for i in range(n):
            dof_int = int(self.free_dofs[i])
            dof_type = dof_int % 6
            if dof_type in (3, 4, 5):
                node_base = dof_int - dof_type
                m_trans = trans_mass_map.get(node_base, 1000.0)
                if m_diag[i] < self.MIN_MASS:
                    add_diag[i] = max(m_trans * self.ROT_MASS_SCALE, self.MIN_MASS) - m_diag[i]

        if np.any(add_diag > 0.0):
            return (M + sparse.diags(add_diag, format="csc")).tocsc()
        return M

    def _participation(
        self,
        mode_shapes: np.ndarray,
        M_red: sparse.csc_matrix,
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

        L = mode_shapes.T @ (M_red @ r.T)
        participation = L / safe_mass[:, None]
        eff_mass = (L ** 2) / safe_mass[:, None]

        return participation, eff_mass, modal_mass

    @staticmethod
    def _total_masses(
        M_red: sparse.csc_matrix,
        modal_dofs: np.ndarray,
    ) -> tuple[float, float, float]:
        d = np.asarray(modal_dofs) % 6
        rx = (d == 0).astype(float)
        ry = (d == 1).astype(float)
        rz = (d == 2).astype(float)
        return (
            float(rx @ (M_red @ rx)),
            float(ry @ (M_red @ ry)),
            float(rz @ (M_red @ rz)),
        )

    def _direction_vectors(self, modal_dofs: np.ndarray) -> np.ndarray:
        d = np.asarray(modal_dofs) % 6
        return np.vstack([
            (d == 0).astype(float),
            (d == 1).astype(float),
            (d == 2).astype(float),
        ])