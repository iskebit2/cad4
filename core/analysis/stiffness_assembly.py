# core/analysis/stiffness_assembly.py
"""
Rijitlik Matrisi Toplama — TEK Çıkış: StiffnessAssembly (Frame Timoshenko + Area 3D Shell Simetrik)

Birim Sözleşmesi (units.py):
    E   [MPa = N/mm²]
    G   [MPa = N/mm²]
    A   [mm²]
    AS2 [mm²] (Kesme alanı - y yönü)
    AS3 [mm²] (Kesme alanı - z yönü)
    I   [mm⁴]
    L   [mm]
    → K [N/mm] (öteleme), [N·mm/rad] (rotasyon)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np


@dataclass
class StiffnessAssembly:
    num_dofs: int
    K_global: np.ndarray
    frame_count: int = 0
    area_count: int = 0
    skipped: List[Tuple[str, str]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def local_stiffness(
    E: float,
    G: float,
    A: float,
    J: float,
    I33: float,
    I22: float,
    AS2: float,
    AS3: float,
    L: float,
    release_i: Optional[Dict[str, bool]] = None,
    release_j: Optional[Dict[str, bool]] = None,
    use_shear_deform: bool = True,
) -> np.ndarray:
    """
    3D Çubuk 12x12 Lokal Rijitlik Matrisi (Timoshenko Kesme Deformasyonu Destekli).
    """
    if L <= 0:
        raise ValueError(f"Geçersiz eleman uzunluğu L={L}")

    k = np.zeros((12, 12), dtype=float)
    ri = release_i or {}
    rj = release_j or {}

    def rel(d: Dict[str, bool], code: str) -> bool:
        return bool(d.get(code, False))

    # 1. Eksenel (UX: 0, 6)
    if not (rel(ri, "R1") or rel(rj, "R1")):
        EA_L = E * A / L
        k[0, 0] += EA_L
        k[6, 6] += EA_L
        k[0, 6] -= EA_L
        k[6, 0] -= EA_L

    # 2. Burulma (RX: 3, 9)
    if not (rel(ri, "R4") or rel(rj, "R4")):
        GJ_L = G * J / L
        k[3, 3] += GJ_L
        k[9, 9] += GJ_L
        k[3, 9] -= GJ_L
        k[9, 3] -= GJ_L

    # 3. Eğilme Yönü 1 (I33 - UY/RZ düzlemi: 1, 5, 7, 11)
    phi3 = 0.0
    if use_shear_deform and G > 0 and AS2 > 0 and I33 > 0:
        phi3 = (12.0 * E * I33) / (G * AS2 * L**2)
    denom3 = 1.0 + phi3
    a3 = 12.0 * E * I33 / (denom3 * L**3)
    b3 = 6.0 * E * I33 / (denom3 * L**2)
    c3 = (4.0 + phi3) * E * I33 / (denom3 * L)
    d3 = (2.0 - phi3) * E * I33 / (denom3 * L)

    k[1, 1] += a3;  k[1, 5] += b3;  k[1, 7] -= a3;  k[1, 11] += b3
    k[5, 1] += b3;  k[5, 5] += c3;  k[5, 7] -= b3;  k[5, 11] += d3
    k[7, 1] -= a3;  k[7, 5] -= b3;  k[7, 7] += a3;  k[7, 11] -= b3
    k[11, 1] += b3; k[11, 5] += d3; k[11, 7] -= b3; k[11, 11] += c3

    # 4. Eğilme Yönü 2 (I22 - UZ/RY düzlemi: 2, 4, 8, 10)
    phi2 = 0.0
    if use_shear_deform and G > 0 and AS3 > 0 and I22 > 0:
        phi2 = (12.0 * E * I22) / (G * AS3 * L**2)
    denom2 = 1.0 + phi2
    a2 = 12.0 * E * I22 / (denom2 * L**3)
    b2 = 6.0 * E * I22 / (denom2 * L**2)
    c2 = (4.0 + phi2) * E * I22 / (denom2 * L)
    d2 = (2.0 - phi2) * E * I22 / (denom2 * L)

    k[2, 2] += a2;  k[2, 4] -= b2;  k[2, 8] -= a2;  k[2, 10] -= b2
    k[4, 2] -= b2;  k[4, 4] += c2;  k[4, 8] += b2;  k[4, 10] += d2
    k[8, 2] -= a2;  k[8, 4] += b2;  k[8, 8] += a2;  k[8, 10] += b2
    k[10, 2] -= b2; k[10, 4] += d2; k[10, 8] += b2; k[10, 10] += c2

    return 0.5 * (k + k.T)


def transformation_matrix(
    p1: Tuple[float, float, float],
    p2: Tuple[float, float, float],
    beta_deg: float = 0.0,
) -> Tuple[np.ndarray, float]:
    p1 = np.asarray(p1, dtype=float)
    p2 = np.asarray(p2, dtype=float)
    v = p2 - p1
    L = float(np.linalg.norm(v))
    if L < 1e-9:
        raise ValueError(f"Sıfır uzunluklu eleman: L={L}")

    e1 = v / L
    dx, dy, dz = e1

    if abs(dz) > 0.9999:
        sign = 1.0 if dz > 0 else -1.0
        e2 = np.array([0.0, sign, 0.0])
        e3 = np.array([-sign, 0.0, 0.0])
    else:
        D = math.hypot(dx, dy)
        e2 = np.array([-dy / D, dx / D, 0.0])
        e3 = np.cross(e1, e2)

    if abs(beta_deg) > 1e-12:
        a = math.radians(beta_deg)
        ca, sa = math.cos(a), math.sin(a)
        e2, e3 = ca * e2 + sa * e3, -sa * e2 + ca * e3

    R = np.vstack([e1, e2, e3])
    T = np.zeros((12, 12), dtype=float)
    for i in range(4):
        T[i * 3 : (i + 1) * 3, i * 3 : (i + 1) * 3] = R

    return T, L


def triangle_shell_stiffness_3d(nodes: list, thickness: float, material) -> np.ndarray:
    n = len(nodes)
    if n < 3:
        return np.zeros((0, 0))

    E = float(getattr(material, "E1", 2.1e5))
    nu = float(getattr(material, "U12", 0.3))
    t = float(thickness)
    if t <= 0:
        return np.zeros((18, 18), dtype=float)

    p0 = np.array([nodes[0].x, nodes[0].y, nodes[0].z], dtype=float)
    p1 = np.array([nodes[1].x, nodes[1].y, nodes[1].z], dtype=float)
    p2 = np.array([nodes[2].x, nodes[2].y, nodes[2].z], dtype=float)

    v1 = p1 - p0
    v2 = p2 - p0
    normal = np.cross(v1, v2)
    area = 0.5 * float(np.linalg.norm(normal))
    if area < 1e-9:
        return np.zeros((18, 18), dtype=float)

    e3 = normal / np.linalg.norm(normal)
    e1 = v1 / np.linalg.norm(v1)
    e2 = np.cross(e3, e1)
    if np.linalg.norm(e2) > 1e-9:
        e2 = e2 / np.linalg.norm(e2)
    else:
        e2 = np.array([0, 1, 0])

    R = np.vstack([e1, e2, e3])
    T = np.zeros((18, 18), dtype=float)
    for i in range(6):
        T[i*3:(i+1)*3, i*3:(i+1)*3] = R

    pts_local = np.array([
        [0.0, 0.0],
        [np.dot(p1 - p0, e1), np.dot(p1 - p0, e2)],
        [np.dot(p2 - p0, e1), np.dot(p2 - p0, e2)]
    ], dtype=float)

    k_loc = np.zeros((18, 18), dtype=float)

    D_m = (E * t / (1.0 - nu**2)) * np.array([
        [1.0, nu, 0.0],
        [nu, 1.0, 0.0],
        [0.0, 0.0, (1.0 - nu) / 2.0]
    ])

    x0, y0 = pts_local[0]
    x1, y1 = pts_local[1]
    x2, y2 = pts_local[2]

    b = [y1 - y2, y2 - y0, y0 - y1]
    c = [x2 - x1, x0 - x2, x1 - x0]
    two_A = 2.0 * area

    B_m = np.zeros((3, 6))
    for i in range(3):
        B_m[0, 2*i]   = b[i]
        B_m[1, 2*i+1] = c[i]
        B_m[2, 2*i]   = c[i]
        B_m[2, 2*i+1] = b[i]
    B_m /= two_A

    K_membrane_local = area * (B_m.T @ D_m @ B_m)

    for i in range(3):
        for j in range(3):
            k_loc[6*i,   6*j]   = K_membrane_local[2*i,   2*j]
            k_loc[6*i,   6*j+1] = K_membrane_local[2*i,   2*j+1]
            k_loc[6*i+1, 6*j]   = K_membrane_local[2*i+1, 2*j]
            k_loc[6*i+1, 6*j+1] = K_membrane_local[2*i+1, 2*j+1]

    # D_b = (E * t**3 / (12.0 * (1.0 - nu**2)))
    # bend_val = max(D_b * area * 0.01, 1.0)

    # Plak eğilme rijitliği (N·mm)
    D_b = E * t**3 / (12.0 * (1.0 - nu**2))
    # Karakteristik uzunluk
    L_char = np.sqrt(area)
    # Rijitlik ölçeği (N/mm)
    bend_val = D_b / (L_char**2) * 0.02

    #######

    for i in range(3):
        for dof_idx in (2, 3, 4, 5):
            idx = 6*i + dof_idx
            k_loc[idx, idx] += bend_val

    k_loc = 0.5 * (k_loc + k_loc.T)
    k_glob = T.T @ k_loc @ T
    return 0.5 * (k_glob + k_glob.T)


def ensure_dof_indices(scene) -> None:
    for i, node in enumerate(scene.nodes.values()):
        node.dof_indices = list(range(i * 6, i * 6 + 6))


def build_stiffness(
    scene,
    project,
    *,
    validate: bool = True,
    use_shear_deform: bool = False,
) -> StiffnessAssembly:
    print(f"[STIFF] use_shear_deform = {use_shear_deform}")

    ensure_dof_indices(scene)
    num_dofs = len(scene.nodes) * 6

    K = np.zeros((num_dofs, num_dofs), dtype=float)
    skipped: List[Tuple[str, str]] = []
    warnings: List[str] = []
    frame_count = 0
    area_count = 0

    # 1. Frame Montajı
    for frame in scene.frames.values():
        err = _assemble_frame(frame, K, num_dofs, use_shear_deform=use_shear_deform)
        if err is None:
            frame_count += 1
        else:
            skipped.append((str(getattr(frame, "label", "?")), err))

    # 2. Area (Shell 3D) Montajı
    for area_key, area in getattr(scene, "areas", {}).items():
        err = _assemble_area(area, K, num_dofs)
        if err is None:
            area_count += 1
        else:
            skipped.append((str(getattr(area, "label", f"Area {area_key}")), err))

    K = 0.5 * (K + K.T)

    asm = StiffnessAssembly(
        num_dofs=num_dofs,
        K_global=K,
        frame_count=frame_count,
        area_count=area_count,
        skipped=skipped,
        warnings=warnings,
    )

    if validate:
        from core.analysis.validation import validate_stiffness
        errs = validate_stiffness(asm)
        asm.warnings.extend(errs)

    return asm


def _assemble_frame(
    frame, K: np.ndarray, num_dofs: int, use_shear_deform: bool = True
) -> Optional[str]:
    sec = getattr(frame, "section", None)
    if not sec:
        return "section yok"
    mat = getattr(sec, "material", None)
    if not mat:
        return "material yok"

    params = sec.profile_params or {}
    try:
        A = float(params["Area"]) * float(params.get("AMod", 1.0))
        J = float(params["J"]) * float(params.get("JMod", 1.0))
        I33 = float(params["I33"]) * float(params.get("I3Mod", 1.0))
        I22 = float(params["I22"]) * float(params.get("I2Mod", 1.0))
    except Exception as e:
        return f"Kesit parametre hatası: {e}"

    AS2 = float(params.get("AS2", A))
    AS3 = float(params.get("AS3", A))
    E = float(getattr(mat, "E1", 0.0))
    G = float(getattr(mat, "G12", 0.0))
    if E <= 0 or G <= 0:
        return f"Geçersiz malzeme E1={E}, G12={G}"

    p1 = (frame.node_i.x, frame.node_i.y, frame.node_i.z)
    p2 = (frame.node_j.x, frame.node_j.y, frame.node_j.z)
    try:
        T, L = transformation_matrix(p1, p2, getattr(frame, "rotation_deg", 0.0) or 0.0)
        k_loc = local_stiffness(
            E=E, G=G, A=A, J=J, I33=I33, I22=I22,
            AS2=AS2, AS3=AS3, L=L,
            release_i=getattr(frame, "release_i", None),
            release_j=getattr(frame, "release_j", None),
            use_shear_deform=use_shear_deform,
        )
    except Exception as e:
        return f"Matris hesap hatası: {e}"

    k_glob = T.T @ k_loc @ T
    dofs_i = getattr(frame.node_i, "dof_indices", None)
    dofs_j = getattr(frame.node_j, "dof_indices", None)
    if not dofs_i or not dofs_j:
        return "dof_indices tanımlı değil"

    dofs = list(dofs_i) + list(dofs_j)
    K[np.ix_(dofs, dofs)] += k_glob
    return None


def _assemble_area(area, K: np.ndarray, num_dofs: int) -> Optional[str]:
    nodes = getattr(area, "nodes", [])
    if len(nodes) < 3:
        return "area düğüm sayısı < 3"
    thickness = float(getattr(area, "thickness", 0.0))
    if thickness <= 0:
        return "area kalınlık <= 0"
    mat = getattr(area, "material", None)
    if not mat:
        return "area material yok"

    for i in range(1, len(nodes) - 1):
        tri_nodes = [nodes[0], nodes[i], nodes[i+1]]
        k_tri_glob = triangle_shell_stiffness_3d(tri_nodes, thickness, mat)
        if k_tri_glob.size == 0:
            continue

        tri_dofs = []
        for nd in tri_nodes:
            dofs = getattr(nd, "dof_indices", None)
            if not dofs:
                return "area düğüm dof_indices eksik"
            tri_dofs.extend(dofs)

        if any(d is None or d < 0 or d >= num_dofs for d in tri_dofs):
            return "area dof sınır dışı"

        K[np.ix_(tri_dofs, tri_dofs)] += k_tri_glob

    return None