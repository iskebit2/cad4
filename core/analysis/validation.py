# core/analysis/validation.py
"""
Analiz ara doğrulama.

Her aşama sonunda çağrılır. Hata listesi döndürür; exception fırlatmaz.
Tüm toleranslar ölçek-bağımsız (göreli) veya mutlak olarak açıkça belirtilmiştir.
"""
from __future__ import annotations

from typing import List

import numpy as np

from core.units import MEGAGRAM


# ============================================================================
# Sabitler — toleranslar
# ============================================================================
# Simetri: M ve K için göreli tolerans
SYMMETRY_RTOL = 1e-8

# Lumped: off-diagonal "sıfır" eşiği (mutlak, ton cinsinden)
LUMPED_OFFDIAG_ATOL = 1e-10

# Consistent mass: kütle korunumu için göreli tolerans
CONSISTENT_MASS_RTOL = 1e-3   # %0.1

# Lumped mass: köşegen toplamı vs node_masses için göreli tolerans
LUMPED_MASS_RTOL = 1e-2       # %1

# K: simetri için göreli tolerans
K_SYMMETRY_RTOL = 1e-6

# K: negatif köşegen eşiği (mutlak, N/mm)
K_NEG_DIAG_ATOL = 1e-9


# ============================================================================
# Yardımcılar
# ============================================================================
def _is_symmetric(A: np.ndarray, rtol: float) -> tuple[bool, float]:
    """Simetri kontrolü. (bool, max_rel_asym) döndürür."""
    scale = max(float(np.max(np.abs(A))), 1.0)
    asym = float(np.max(np.abs(A - A.T)))
    return asym <= rtol * scale, asym / scale


def _offdiag_max(A: np.ndarray) -> float:
    """Köşegen dışı mutlak maksimum."""
    if A.size == 0:
        return 0.0
    mask = ~np.eye(A.shape[0], dtype=bool)
    if not mask.any():
        return 0.0
    return float(np.max(np.abs(A[mask])))


def _translation_dof_indices(num_nodes: int, num_dofs: int) -> np.ndarray:
    """
    Her düğümün UX (offset 0) global DOF endekslerini döndürür.
    Düğüm sırası: 0..num_nodes-1, her biri 6 DOF.
    """
    idx = np.arange(num_nodes) * 6
    return idx[idx < num_dofs]


def _total_mass_consistent(M: np.ndarray) -> float:
    """
    Consistent mass korunum toplamı: Σ_ij M_ij.
    (Tüm yönler için değil, sadece UX blokları için.)
    """
    n = M.shape[0]
    total = 0.0
    # UX blokları: satır/sütun 0, 6, 12, ... (her düğümün UX'i)
    ux_idx = np.arange(0, n, 6)
    if len(ux_idx) == 0:
        return 0.0
    # UX satır/sütun bloğunun toplamı
    total = float(np.sum(M[np.ix_(ux_idx, ux_idx)]))
    return total


# ============================================================================
# Kütle doğrulama
# ============================================================================
def validate_mass(asm, is_consistent: bool = False) -> List[str]:
    """
    MassAssembly nesnesi üzerinde kütle ve matris doğrulama kontrolleri.

    Parametreler
    ------------
    asm : MassAssembly
    is_consistent : bool
        True  → Consistent mass (off-diagonal terimler beklenir).
        False → Lumped mass (sadece köşegen).

    Döndürür
    --------
    List[str] : hata mesajları (boşsa sorun yok)
    """
    errors: List[str] = []
    M = np.asarray(asm.M_global, dtype=float)

    if M.size == 0:
        errors.append("M_global boş")
        return errors

    # ------------------------------------------------------------------
    # 1) Sonlu değerler
    # ------------------------------------------------------------------
    if np.any(~np.isfinite(M)):
        errors.append("M_global NaN/Inf içeriyor")
        return errors

    # ------------------------------------------------------------------
    # 2) Simetri
    # ------------------------------------------------------------------
    sym_ok, rel_asym = _is_symmetric(M, SYMMETRY_RTOL)
    if not sym_ok:
        errors.append(
            f"M_global simetrik değil (göreli asimetri={rel_asym:.3e})"
        )

    # ------------------------------------------------------------------
    # 3) Lumped / Consistent yapı kontrolü
    # ------------------------------------------------------------------
    offdiag_max = _offdiag_max(M)
    if not is_consistent:
        if offdiag_max > LUMPED_OFFDIAG_ATOL:
            errors.append(
                f"M_global off-diagonal içeriyor "
                f"(max={offdiag_max:.3e}, lumped bekleniyor)"
            )
    else:
        # Consistent mass'ta off-diagonal beklenir; sıfırsa uyarı
        if offdiag_max <= LUMPED_OFFDIAG_ATOL:
            # Bu bir hata değil, sadece bilgi amaçlı
            pass  # sessiz geç

    # ------------------------------------------------------------------
    # 4) Kütle kontrolü
    # ------------------------------------------------------------------
    node_total_ton = sum(asm.node_masses.values()) / MEGAGRAM
    if node_total_ton <= 0:
        return errors  # karşılaştırma anlamsız

    if is_consistent:
        # Consistent: Σ_ij M_ij ≈ Σ node_masses
        M_total_ton = _total_mass_consistent(M)
        if M_total_ton <= 0:
            errors.append(
                f"Consistent M toplamı sıfır "
                f"(Σ M_ij=0, node_masses={node_total_ton:.3f} ton)"
            )
        else:
            rel = abs(M_total_ton - node_total_ton) / node_total_ton
            if rel > CONSISTENT_MASS_RTOL:
                errors.append(
                    f"Consistent kütle korunumu: "
                    f"Σ M_ij={M_total_ton:.4f} ton, "
                    f"node_masses={node_total_ton:.4f} ton, "
                    f"göreli fark={rel:.3e}"
                )
    else:
        # Lumped: Σ M_diag (UX) ≈ Σ node_masses
        ux_idx = _translation_dof_indices(len(asm.node_masses), M.shape[0])
        if len(ux_idx) == 0:
            errors.append("M boyutu düğüm sayısıyla uyumsuz")
            return errors

        M_diag_ton = float(np.sum(M[ux_idx, ux_idx]))
        rel = abs(M_diag_ton - node_total_ton) / node_total_ton
        if rel > LUMPED_MASS_RTOL:
            errors.append(
                f"Lumped kütle: Σ M_UX={M_diag_ton:.4f} ton, "
                f"node_masses={node_total_ton:.4f} ton, "
                f"göreli fark={rel:.3e}"
            )

    return errors


# ============================================================================
# Rijitlik doğrulama
# ============================================================================
def validate_stiffness(asm) -> List[str]:
    """StiffnessAssembly doğrula."""
    errs: List[str] = []
    K = np.asarray(asm.K_global, dtype=float)
    N = int(asm.num_dofs)

    # ------------------------------------------------------------------
    # 1) Boyut
    # ------------------------------------------------------------------
    if K.shape != (N, N):
        errs.append(f"K boyut {K.shape} != ({N},{N})")
        return errs

    # ------------------------------------------------------------------
    # 2) Sonlu değerler
    # ------------------------------------------------------------------
    if np.any(~np.isfinite(K)):
        errs.append("K NaN/Inf içeriyor")
        return errs

    # ------------------------------------------------------------------
    # 3) Tamamen sıfır
    # ------------------------------------------------------------------
    if np.allclose(K, 0.0):
        errs.append("K tamamen sıfır — hiç eleman eklenmemiş olabilir")
        return errs

    # ------------------------------------------------------------------
    # 4) Simetri (ölçek-bağımsız göreli)
    # ------------------------------------------------------------------
    sym_ok, rel_asym = _is_symmetric(K, K_SYMMETRY_RTOL)
    if not sym_ok:
        errs.append(f"K simetrik değil (göreli asimetri={rel_asym:.3e})")

    # ------------------------------------------------------------------
    # 5) Negatif köşegen
    # ------------------------------------------------------------------
    diag = np.diag(K)
    if np.any(diag < -K_NEG_DIAG_ATOL):
        errs.append(
            f"K negatif köşegen (min={diag.min():.3e})"
        )

    return errs