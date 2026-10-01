# core/analysis/element.py
"""
3D çubuk eleman rijitlik ve dönüşüm matrisleri.

SAP2000 uyumlu: release'li uçlar için modifiye stiffness.
"""
import numpy as np
import logging

logger = logging.getLogger(__name__)


# ============================================================
# RİJİTLİK MATRİSİ
# ============================================================

def local_stiffness(E, G, A, J, I33, I22, L,
                    release_i=None, release_j=None):
    """
    3D çubuk eleman lokal rijitlik matrisi (12x12).
    
    Parameters
    ----------
    E, G : float — Elastisite ve kayma modülü (MPa)
    A : float — Kesit alanı (mm²)
    J : float — Burulma atalet momenti (mm⁴)
    I33 : float — Güçlü eksen atalet momenti (mm⁴)
    I22 : float — Zayıf eksen atalet momenti (mm⁴)
    L : float — Çubuk uzunluğu (mm)
    release_i, release_j : dict veya None
        {'R1': bool, ..., 'R6': bool} release seti
        R1: P  R2: V2  R3: V3  R4: T  R5: M2  R6: M3
    
    Returns
    -------
    k : np.ndarray (12, 12)
    """
    k = np.zeros((12, 12))
    EA_L = E * A / L
    GJ_L = G * J / L
    
    ri = release_i or {}
    rj = release_j or {}
    
    def rel(d, code):
        return d.get(code, False) if d else False
    
    # ---- Eksenel (local 0, 6) ----
    if not (rel(ri, 'R1') or rel(rj, 'R1')):
        k[0, 0] = k[6, 6] = EA_L
        k[0, 6] = k[6, 0] = -EA_L
    
    # ---- Burulma (local 3, 9) ----
    if not (rel(ri, 'R4') or rel(rj, 'R4')):
        k[3, 3] = k[9, 9] = GJ_L
        k[3, 9] = k[9, 3] = -GJ_L
    
    # ---- Z ekseni etrafında eğilme (I22 → UY, RZ) ----
    _add_bending_term(k, E, I22, L,
                      u_local=1, r_local=5,
                      release_i=rel(ri, 'R6'),
                      release_j=rel(rj, 'R6'))
    
    # ---- Y ekseni etrafında eğilme (I33 → UZ, RY) ----
    _add_bending_term(k, E, I33, L,
                      u_local=2, r_local=4,
                      release_i=rel(ri, 'R5'),
                      release_j=rel(rj, 'R5'),
                      sign=-1)
    
    return k


def _add_bending_term(k, E, I, L, u_local, r_local,
                      release_i, release_j, sign=1):
    """
    Eğilme terimlerini matrise ekle.
    
    u_local : yer değiştirme DOF (1 veya 2)
    r_local : rotasyon DOF (5 veya 4)
    sign    : +1 veya -1 (I22 ile I33 farklı işaret)
    """
    if release_i and release_j:
        return  # her iki uç pin → eğilme yok
    
    # Standart katsayılar
    k3 = 12 * E * I / (L ** 3)
    k2 = 6  * E * I / (L ** 2)
    k1 = 4  * E * I / L
    k_half = 2 * E * I / L
    
    # Tek uç pin → modifiye katsayılar
    if release_i or release_j:
        k3 = 3 * E * I / (L ** 3)
        k2 = 3 * E * I / (L ** 2)
        k1 = 3 * E * I / L
        k_half = 0
    
    u1, u2 = u_local, u_local + 6
    r1, r2 = r_local, r_local + 6
    
    s = sign
    k[u1, u1] = k[u2, u2] = k3
    k[u1, u2] = k[u2, u1] = -k3
    
    k[u1, r1] = k[r1, u1] = s * k2
    k[u1, r2] = k[r2, u1] = s * k2
    k[u2, r1] = k[r1, u2] = -s * k2
    k[u2, r2] = k[r2, u2] = -s * k2
    
    k[r1, r1] = k[r2, r2] = k1
    k[r1, r2] = k[r2, r1] = k_half


# ============================================================
# DÖNÜŞÜM MATRİSİ
# ============================================================

def transformation_matrix(p1, p2, beta_deg=0.0):
    """
    3D çubuk dönüşüm matrisi (12x12).
    
    Parameters
    ----------
    p1, p2 : array-like (3,) — uç noktaların koordinatları
    beta_deg : float — local eksen dönme açısı (derece)
    
    Returns
    -------
    T : np.ndarray (12, 12)
    L : float — çubuk uzunluğu
    """
    p1 = np.asarray(p1, dtype=float)
    p2 = np.asarray(p2, dtype=float)
    v = p2 - p1
    L = np.linalg.norm(v)
    
    if L < 1e-9:
        raise ValueError("Sıfır uzunluklu eleman")
    
    dx, dy, dz = v / L
    vx = np.array([dx, dy, dz])
    beta = np.radians(beta_deg)
    
    # Dikey eleman özel durumu (SAP2000 uyumlu)
    if np.isclose(abs(dz), 1.0, atol=1e-5):
        sign = 1.0 if dz > 0 else -1.0
        vy0 = np.array([0, sign, 0])
        vz0 = np.array([-sign, 0, 0])
    else:
        D = np.sqrt(dx*dx + dy*dy)
        vy0 = np.array([-dy/D, dx/D, 0])
        vz0 = np.array([-dx*dz/D, -dy*dz/D, D])
    
    R_0 = np.vstack([vx, vy0, vz0])
    
    # Beta rotasyonu
    R_beta = np.array([
        [1, 0, 0],
        [0, np.cos(beta), np.sin(beta)],
        [0, -np.sin(beta), np.cos(beta)],
    ])
    R = R_beta @ R_0
    
    T = np.zeros((12, 12))
    for i in range(4):
        T[i*3:(i+1)*3, i*3:(i+1)*3] = R
    
    return T, L