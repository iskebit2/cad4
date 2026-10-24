# core/analysis/validation.py
"""
Analiz ara doğrulama.
Her aşama sonunda çağrılır. Hata listesi döner; exception fırlatmaz.
"""
from __future__ import annotations

import math
from typing import List

import numpy as np


def validate_mass(asm) -> List[str]:
    """MassAssembly doğrula."""
    errs: List[str] = []

    N = asm.num_dofs
    M = asm.M_global

    if M.shape != (N, N):
        errs.append(f"M_global boyut {M.shape} != ({N},{N})")
        return errs

    if not np.allclose(M, M.T, atol=1e-9):
        errs.append("M_global simetrik değil")

    diag = np.diag(M)
    if np.any(diag < 0):
        errs.append(f"M_global negatif köşegen (min={diag.min():.3e})")

    if np.any(~np.isfinite(M)):
        errs.append("M_global NaN/Inf içeriyor")

    off = M - np.diag(diag)
    if np.any(np.abs(off) > 1e-9):
        errs.append("M_global off-diagonal içeriyor (lumped bekleniyor)")

    # Node kütleleri toplamı ile matris diyagonalinin toplamı
    # (her düğümde 3 öteleme DOF, aynı kütle)
    mass_from_nodes = sum(asm.node_masses.values())
    mass_from_M = float(np.sum(diag)) / 3.0
    if mass_from_nodes > 1e-9:
        rel = abs(mass_from_M - mass_from_nodes) / mass_from_nodes
        if rel > 1e-6:
            errs.append(
                f"Matris kütlesi ({mass_from_M:.6f} kg) != "
                f"node kütleleri ({mass_from_nodes:.6f} kg), rel={rel:.2e}"
            )

    # Raporla node_masses toplamı
    total_rep = asm.total_self_kg + asm.total_dead_kg + asm.n_live * asm.total_live_kg
    if mass_from_nodes > 1e-9:
        rel2 = abs(total_rep - mass_from_nodes) / mass_from_nodes
        if rel2 > 1e-6:
            errs.append(
                f"Rapor ({total_rep:.6f} kg) != node kütleleri ({mass_from_nodes:.6f} kg), "
                f"rel={rel2:.2e}"
            )

    # NaN/Inf
    for key, m in asm.node_masses.items():
        if not math.isfinite(m):
            errs.append(f"Node {key}: kütle NaN/Inf")

    return errs


def validate_stiffness(asm) -> List[str]:
    """StiffnessAssembly doğrula."""
    errs: List[str] = []
    K = asm.K_global
    N = asm.num_dofs

    if K.shape != (N, N):
        errs.append(f"K boyut {K.shape} != ({N},{N})")
        return errs

    if np.any(~np.isfinite(K)):
        errs.append("K NaN/Inf içeriyor")
        return errs

    # Simetri (sayısal tolerans)
    asym = np.max(np.abs(K - K.T))
    if asym > 1e-6 * max(1.0, np.max(np.abs(K))):
        errs.append(f"K simetrik değil (max asimetri={asym:.3e})")

    diag = np.diag(K)
    if np.any(diag < -1e-9):
        errs.append(f"K negatif köşegen (min={diag.min():.3e})")

    if np.allclose(K, 0.0):
        errs.append("K tamamen sıfır — hiç frame eklenmemiş olabilir")

    return errs