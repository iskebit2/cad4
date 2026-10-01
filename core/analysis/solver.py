# core/analysis/solver.py
"""Statik, modal ve spektral çözümler."""
import numpy as np
from scipy.linalg import eigh
import logging

logger = logging.getLogger(__name__)


class StructuralSolver:
    """
    Yapısal analiz çözücü.
    
    Kullanım:
        solver = StructuralSolver(K_global, M_global, fixed_dofs)
        U = solver.static_solve(F)
        freqs, periods, modes = solver.modal_solve(n_modes=10)
    """
    
    def __init__(self, K_global, M_global, fixed_dofs, num_dofs):
        self.K = K_global
        self.M = M_global
        self.fixed_dofs = set(fixed_dofs)
        self.num_dofs = num_dofs
        
        all_dofs = set(range(num_dofs))
        self.free_dofs = sorted(all_dofs - self.fixed_dofs)
        self.free_dofs_arr = np.array(self.free_dofs, dtype=int)
        
        # Reduced matrisler
        self.K_red = None
        self.M_red = None
    
    def _build_reduced(self):
        if self.K_red is not None:
            return
        idx = np.ix_(self.free_dofs, self.free_dofs)
        self.K_red = self.K[idx]
        self.M_red = self.M[idx]
    
    # ---------------------------------------------------------
    # STATİK
    # ---------------------------------------------------------
    
    def static_solve(self, F, stabilization=None):
        """
        K·U = F çözümü.
        
        Parameters
        ----------
        F : np.ndarray (num_dofs,)
        stabilization : float veya None
            Sıfır diyagonallere eklenecek değer. None ise otomatik.
        
        Returns
        -------
        U : np.ndarray (num_dofs,)
        """
        self._build_reduced()
        
        # Stabilizasyon (sıfır diyagonal için)
        K = self.K_red.copy()
        diag = np.abs(np.diag(K))
        zero_diag = diag < 1e-9
        
        if np.any(zero_diag):
            if stabilization is None:
                max_diag = np.max(diag)
                stabilization = max_diag * 1e-8
            
            logger.warning(
                f"[Solver] {np.sum(zero_diag)} sıfır diyagonal, "
                f"stabilization={stabilization:.2e} eklendi"
            )
            for i in np.where(zero_diag)[0]:
                K[i, i] += stabilization
        
        F_red = F[self.free_dofs_arr]
        
        try:
            U_red = np.linalg.solve(K, F_red)
        except np.linalg.LinAlgError as e:
            logger.error(f"[Solver] Static solve hatası: {e}")
            return np.zeros(self.num_dofs)
        
        U = np.zeros(self.num_dofs)
        U[self.free_dofs_arr] = U_red
        return U
    
    # ---------------------------------------------------------
    # MODAL
    # ---------------------------------------------------------
    
    def modal_solve(self, n_modes=10, only_translations=True,
                    stabilization=None):
        """
        Modal analiz — K·Φ = ω²·M·Φ özdeğer problemi.
        
        Parameters
        ----------
        n_modes : int
        only_translations : bool
            True ise sadece UX, UY, UZ DOF'ları kullanılır.
        stabilization : float veya None
        
        Returns
        -------
        freqs : np.ndarray (n_modes,)
        periods : np.ndarray (n_modes,)
        eigenvectors : np.ndarray (n_modal_dofs, n_modes)
        modal_dofs : np.ndarray — hangi DOF'lar kullanıldı
        """
        self._build_reduced()
        
        # Modal DOF'ları seç
        if only_translations:
            modal_dofs = np.array(
                [d for d in self.free_dofs if d % 6 in (0, 1, 2)],
                dtype=int
            )
        else:
            modal_dofs = self.free_dofs_arr
        
        idx = np.ix_(modal_dofs, modal_dofs)
        K_m = self.K[idx].copy()
        M_m = self.M[idx].copy()
        
        # Stabilizasyon
        diag = np.abs(np.diag(K_m))
        zero_diag = diag < 1e-9
        if np.any(zero_diag):
            if stabilization is None:
                stabilization = np.max(diag) * 1e-8
            for i in np.where(zero_diag)[0]:
                K_m[i, i] += stabilization
        
        # Zero-mass kontrolü
        zero_mass = np.diag(M_m) < 1e-15
        if np.any(zero_mass):
            logger.warning(f"[Solver] {np.sum(zero_mass)} sıfır kütleli DOF var")
            # Küçük kütle ekle
            for i in np.where(zero_mass)[0]:
                M_m[i, i] = 1e-9
        
        logger.info(f"[Solver] Modal analiz: {len(modal_dofs)} DOF")
        
        eigenvalues, eigenvectors = eigh(K_m, M_m)
        
        omega = np.sqrt(np.maximum(eigenvalues, 0.0))
        freqs = omega / (2 * np.pi)
        periods = np.where(freqs > 1e-6, 1.0 / freqs, 0.0)
        
        # İlk n_modes
        freqs = freqs[:n_modes]
        periods = periods[:n_modes]
        eigenvectors = eigenvectors[:, :n_modes]
        
        return freqs, periods, eigenvectors, modal_dofs
    
    # ---------------------------------------------------------
    # YARDIMCI
    # ---------------------------------------------------------
    
    def expand_to_full(self, U_reduced, reduced_dofs):
        """Reduced vektörü full DOF'a genişlet."""
        U = np.zeros(self.num_dofs)
        U[reduced_dofs] = U_reduced
        return U