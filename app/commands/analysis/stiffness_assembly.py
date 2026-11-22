# app/commands/analysis\stiffness_assembly.py
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy import sparse

from domain.definition import LinkPropLinear
from app.commands.analysis.frame_resolver import (
    compute_local_axes,
    resolve_frame_kinematics,
    resolve_section,
    rigid_offset_matrix,
)

@dataclass
class StiffnessAssembly:
    num_dofs: int
    K_global: sparse.csc_matrix
    frame_count: int = 0
    area_count: int = 0
    link_count: int = 0
    spring_node_count: int = 0
    skipped: list[tuple[str, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _apply_beam_releases(k: np.ndarray, ri: dict[str, bool], rj: dict[str, bool]) -> np.ndarray:
    rel_indices: list[int] = []
    if ri.get("R1", False) or ri.get("u1", False):
        rel_indices.append(0)
    if ri.get("U2", False) or ri.get("u2", False):
        rel_indices.append(1)
    if ri.get("U3", False) or ri.get("u3", False):
        rel_indices.append(2)
    if ri.get("R4", False) or ri.get("r1", False):
        rel_indices.append(3)
    if ri.get("R2", False) or ri.get("r2", False):
        rel_indices.append(4)
    if ri.get("R3", False) or ri.get("r3", False):
        rel_indices.append(5)

    if rj.get("R1", False) or rj.get("u1", False):
        rel_indices.append(6)
    if rj.get("U2", False) or rj.get("u2", False):
        rel_indices.append(7)
    if rj.get("U3", False) or rj.get("u3", False):
        rel_indices.append(8)
    if rj.get("R4", False) or rj.get("r1", False):
        rel_indices.append(9)
    if rj.get("R2", False) or rj.get("r2", False):
        rel_indices.append(10)
    if rj.get("R3", False) or rj.get("r3", False):
        rel_indices.append(11)

    if not rel_indices:
        return k

    k_mod = k.copy()
    for idx in rel_indices:
        k_ii = k_mod[idx, idx]
        if abs(k_ii) <= 1e-15:
            k_mod[idx, :] = 0.0
            k_mod[:, idx] = 0.0
            continue
        col = k_mod[:, idx].copy()
        row = k_mod[idx, :].copy()
        k_mod -= np.outer(col, row) / k_ii
        k_mod[idx, :] = 0.0
        k_mod[:, idx] = 0.0
    return k_mod


def _rigid_offset_matrix(off_i: float, off_j: float) -> np.ndarray:
    H = np.eye(12, dtype=float)
    if off_i > 0.0:
        H[1, 5] = off_i
        H[2, 4] = -off_i
    if off_j > 0.0:
        H[7, 11] = -off_j
        H[8, 10] = off_j
    return H


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
    release_i: dict[str, bool] | None = None,
    release_j: dict[str, bool] | None = None,
    use_shear_deform: bool = True,
    offset_i: float = 0.0,
    offset_j: float = 0.0,
    rigid_factor: float = 0.0,
) -> np.ndarray:
    if L <= 0.0:
        raise ValueError(f"Geçersiz eleman uzunluğu L={L}")

    eff_off_i = max(0.0, float(offset_i) * float(rigid_factor))
    eff_off_j = max(0.0, float(offset_j) * float(rigid_factor))
    L_clear = L - eff_off_i - eff_off_j
    if L_clear <= 1e-6:
        L_clear = L
        eff_off_i = 0.0
        eff_off_j = 0.0

    k = np.zeros((12, 12), dtype=float)
    ri = release_i or {}
    rj = release_j or {}

    EA_L = E * A / L_clear
    k[0, 0] += EA_L
    k[6, 6] += EA_L
    k[0, 6] -= EA_L
    k[6, 0] -= EA_L

    GJ_L = G * J / L_clear
    k[3, 3] += GJ_L
    k[9, 9] += GJ_L
    k[3, 9] -= GJ_L
    k[9, 3] -= GJ_L

    phi3 = 0.0
    if use_shear_deform and G > 0.0 and AS2 > 0.0 and I33 > 0.0:
        phi3 = (12.0 * E * I33) / (G * AS2 * L_clear**2)
    denom3 = 1.0 + phi3
    a3 = 12.0 * E * I33 / (denom3 * L_clear**3)
    b3 = 6.0 * E * I33 / (denom3 * L_clear**2)
    c3 = (4.0 + phi3) * E * I33 / (denom3 * L_clear)
    d3 = (2.0 - phi3) * E * I33 / (denom3 * L_clear)

    k[1, 1] += a3;  k[1, 5] += b3;  k[1, 7] -= a3;  k[1, 11] += b3
    k[5, 1] += b3;  k[5, 5] += c3;  k[5, 7] -= b3;  k[5, 11] += d3
    k[7, 1] -= a3;  k[7, 5] -= b3;  k[7, 7] += a3;  k[7, 11] -= b3
    k[11, 1] += b3; k[11, 5] += d3; k[11, 7] -= b3; k[11, 11] += c3

    phi2 = 0.0
    if use_shear_deform and G > 0.0 and AS3 > 0.0 and I22 > 0.0:
        phi2 = (12.0 * E * I22) / (G * AS3 * L_clear**2)
    denom2 = 1.0 + phi2
    a2 = 12.0 * E * I22 / (denom2 * L_clear**3)
    b2 = 6.0 * E * I22 / (denom2 * L_clear**2)
    c2 = (4.0 + phi2) * E * I22 / (denom2 * L_clear)
    d2 = (2.0 - phi2) * E * I22 / (denom2 * L_clear)

    k[2, 2] += a2;  k[2, 4] -= b2;  k[2, 8] -= a2;  k[2, 10] -= b2
    k[4, 2] -= b2;  k[4, 4] += c2;  k[4, 8] += b2;  k[4, 10] += d2
    k[8, 2] -= a2;  k[8, 4] += b2;  k[8, 8] += a2;  k[8, 10] += b2
    k[10, 2] -= b2; k[10, 4] += d2; k[10, 8] += b2; k[10, 10] += c2

    k = _apply_beam_releases(k, ri, rj)

    if eff_off_i > 0.0 or eff_off_j > 0.0:
        H = _rigid_offset_matrix(eff_off_i, eff_off_j)
        k = H.T @ k @ H

    return 0.5 * (k + k.T)


def transformation_matrix(p1, p2, beta_deg: float = 0.0, up_global=(0.0, 0.0, 1.0)):
    R, L = compute_local_axes(p1, p2, beta_deg=beta_deg, up_global=up_global)
    if L < 1e-9:
        raise ValueError(f"Sıfır uzunluklu eleman: L={L}")
    T = np.kron(np.eye(4), R)
    return T, L


def link_transformation_matrix(p1, p2) -> np.ndarray:
    p1 = np.asarray(p1, dtype=float)
    p2 = np.asarray(p2, dtype=float)
    v = p2 - p1
    L = float(np.linalg.norm(v))
    if L < 1e-9:
        return np.eye(12, dtype=float)
    T, _ = transformation_matrix(p1, p2, beta_deg=0.0)
    return T


def triangle_shell_stiffness_3d(
    nodes: list,
    thickness: float,
    material,
    area_section=None,
) -> np.ndarray:
    if len(nodes) < 3:
        return np.zeros((0, 0), dtype=float)

    E = float(getattr(material, "E1", 2.1e5))
    nu = float(getattr(material, "nu12", 0.3))
    t = float(thickness)
    if t <= 0.0 or E <= 0.0:
        return np.zeros((18, 18), dtype=float)

    t_bend = float(area_section.effective_bend_thick) if area_section is not None else t
    if t_bend <= 0.0:
        t_bend = t

    f11 = float(getattr(area_section, "membrane_f11", 1.0)) if area_section is not None else 1.0
    f22 = float(getattr(area_section, "membrane_f22", 1.0)) if area_section is not None else 1.0
    f12 = float(getattr(area_section, "membrane_f12", 1.0)) if area_section is not None else 1.0
    m11 = float(getattr(area_section, "bending_m11", 1.0)) if area_section is not None else 1.0
    m22 = float(getattr(area_section, "bending_m22", 1.0)) if area_section is not None else 1.0
    m12 = float(getattr(area_section, "bending_m12", 1.0)) if area_section is not None else 1.0

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
    e2_norm = float(np.linalg.norm(e2))
    e2 = (e2 / e2_norm) if e2_norm > 1e-9 else np.array([0.0, 1.0, 0.0])

    R = np.vstack([e1, e2, e3])
    T = np.kron(np.eye(6), R)

    pts_local = np.array([
        [0.0, 0.0],
        [np.dot(p1 - p0, e1), np.dot(p1 - p0, e2)],
        [np.dot(p2 - p0, e1), np.dot(p2 - p0, e2)],
    ], dtype=float)

    k_loc = np.zeros((18, 18), dtype=float)

    D_m = (E * t / (1.0 - nu**2)) * np.array([
        [1.0 * f11, nu * math.sqrt(max(f11 * f22, 0.0)), 0.0],
        [nu * math.sqrt(max(f11 * f22, 0.0)), 1.0 * f22, 0.0],
        [0.0, 0.0, ((1.0 - nu) / 2.0) * f12],
    ])

    x0, y0 = pts_local[0]
    x1, y1 = pts_local[1]
    x2, y2 = pts_local[2]

    b = [y1 - y2, y2 - y0, y0 - y1]
    c = [x2 - x1, x0 - x2, x1 - x0]
    two_A = 2.0 * area

    B_m = np.zeros((3, 6), dtype=float)
    for i in range(3):
        B_m[0, 2 * i] = b[i]
        B_m[1, 2 * i + 1] = c[i]
        B_m[2, 2 * i] = c[i]
        B_m[2, 2 * i + 1] = b[i]
    B_m /= two_A

    K_membrane_local = area * (B_m.T @ D_m @ B_m)

    for i in range(3):
        for j in range(3):
            k_loc[6 * i,     6 * j]     = K_membrane_local[2 * i,     2 * j]
            k_loc[6 * i,     6 * j + 1] = K_membrane_local[2 * i,     2 * j + 1]
            k_loc[6 * i + 1, 6 * j]     = K_membrane_local[2 * i + 1, 2 * j]
            k_loc[6 * i + 1, 6 * j + 1] = K_membrane_local[2 * i + 1, 2 * j + 1]

    bend_scale = (m11 + m22 + m12) / 3.0
    D_b = bend_scale * (E * t_bend**3 / (12.0 * (1.0 - nu**2)))
    L_char = math.sqrt(area)
    bend_val = D_b / (L_char**2) * 0.02

    for i in range(3):
        for dof_idx in (2, 3, 4, 5):
            idx = 6 * i + dof_idx
            k_loc[idx, idx] += bend_val

    k_loc = 0.5 * (k_loc + k_loc.T)
    k_glob = T.T @ k_loc @ T
    return 0.5 * (k_glob + k_glob.T)


def ensure_dof_indices(scene, dof_map: dict[str, int] | None = None) -> dict[str, int]:
    resolved_map: dict[str, int] = {}
    for i, (n_key, node) in enumerate(scene.nodes.items()):
        base = dof_map[n_key] if (dof_map is not None and n_key in dof_map) else (i * 6)
        node.dof_indices = [base + d for d in range(6)]
        resolved_map[n_key] = base
    return resolved_map


def _push_block(
    rows: list[np.ndarray],
    cols: list[np.ndarray],
    vals: list[np.ndarray],
    dofs: list[int],
    mat: np.ndarray,
) -> None:
    d_arr = np.asarray(dofs, dtype=np.int32)
    n = d_arr.size
    rows.append(np.repeat(d_arr, n))
    cols.append(np.tile(d_arr, n))
    vals.append(mat.ravel())


def _assemble_node_springs(
    node,
    rows: list[np.ndarray],
    cols: list[np.ndarray],
    vals: list[np.ndarray],
    num_dofs: int,
) -> bool:
    dofs = getattr(node, "dof_indices", None)
    if not dofs or len(dofs) != 6:
        return False
    springs = (
        float(getattr(node, "spring_u1", 0.0) or 0.0),
        float(getattr(node, "spring_u2", 0.0) or 0.0),
        float(getattr(node, "spring_u3", 0.0) or 0.0),
        float(getattr(node, "spring_r1", 0.0) or 0.0),
        float(getattr(node, "spring_r2", 0.0) or 0.0),
        float(getattr(node, "spring_r3", 0.0) or 0.0),
    )
    r_list: list[int] = []
    v_list: list[float] = []
    for idx, k_val in enumerate(springs):
        if k_val > 0.0:
            dof = dofs[idx]
            if dof is not None and 0 <= dof < num_dofs:
                r_list.append(int(dof))
                v_list.append(k_val)
    if not r_list:
        return False
    arr = np.asarray(r_list, dtype=np.int32)
    rows.append(arr)
    cols.append(arr)
    vals.append(np.asarray(v_list, dtype=float))
    return True


def _assemble_link(
    link,
    project,
    rows: list[np.ndarray],
    cols: list[np.ndarray],
    vals: list[np.ndarray],
    num_dofs: int,
    rigid_stiff: float = 1e12,
) -> str | None:
    ni = getattr(link, "node_i", None)
    nj = getattr(link, "node_j", None)
    if ni is None or nj is None:
        return "link uç düğümleri eksik"

    dofs_i = getattr(ni, "dof_indices", None)
    dofs_j = getattr(nj, "dof_indices", None)
    if not dofs_i or not dofs_j:
        return "link düğüm dof_indices tanımlı değil"

    propname = getattr(link, "propname", "")
    link_props = getattr(project, "link_props", None) or {}
    prop = link_props.get(propname)
    if prop is None:
        return f"LinkProp bulunamadı: {propname}"

    if not isinstance(prop, LinkPropLinear):
        return f"Desteklenmeyen LinkProp tipi: {type(prop).__name__}"

    dof_active = getattr(prop, "DOF", None) or {}
    fixed_map = getattr(prop, "Fixed", None) or {}
    ke_map = getattr(prop, "Ke", None) or {}

    k_diag = np.zeros(6, dtype=float)
    for idx, code in enumerate(("U1", "U2", "U3", "R1", "R2", "R3")):
        if not dof_active.get(code, True):
            continue
        if fixed_map.get(code, False):
            k_diag[idx] = rigid_stiff
        else:
            val = float(ke_map.get(code, 0.0) or 0.0)
            if val < 0.0:
                return f"Negatif link rijitliği {code}={val}"
            k_diag[idx] = val

    if not np.any(k_diag > 0.0):
        return None

    k_e = np.diag(k_diag)
    k_loc = np.block([
        [k_e, -k_e],
        [-k_e, k_e],
    ])

    p1 = (ni.x, ni.y, ni.z)
    p2 = (nj.x, nj.y, nj.z)
    T = link_transformation_matrix(p1, p2)
    k_glob = 0.5 * (T.T @ k_loc @ T + (T.T @ k_loc @ T).T)

    dofs = list(dofs_i) + list(dofs_j)
    if any(d is None or d < 0 or d >= num_dofs for d in dofs):
        return "link dof sınır dışı"

    _push_block(rows, cols, vals, dofs, k_glob)
    return None


def build_stiffness(
    scene,
    project,
    *,
    dof_map: dict[str, int] | None = None,
    validate: bool = True,
    use_shear_deform: bool = True,
) -> StiffnessAssembly:
    ensure_dof_indices(scene, dof_map=dof_map)
    num_dofs = len(scene.nodes) * 6

    rows: list[np.ndarray] = []
    cols: list[np.ndarray] = []
    vals: list[np.ndarray] = []
    skipped: list[tuple[str, str]] = []
    warnings: list[str] = []
    frame_count = 0
    area_count = 0
    link_count = 0
    spring_node_count = 0

    for node in scene.nodes.values():
        if _assemble_node_springs(node, rows, cols, vals, num_dofs):
            spring_node_count += 1

    for frame in scene.frames.values():
        err = _assemble_frame(frame, rows, cols, vals, num_dofs, use_shear_deform=use_shear_deform)
        if err is None:
            frame_count += 1
        else:
            skipped.append((str(getattr(frame, "label", "?")), err))

    for area_key, area in getattr(scene, "areas", {}).items():
        err = _assemble_area(area, rows, cols, vals, num_dofs)
        if err is None:
            area_count += 1
        else:
            skipped.append((str(getattr(area, "label", f"Area {area_key}")), err))

    for link_key, link in getattr(scene, "links", {}).items():
        err = _assemble_link(link, project, rows, cols, vals, num_dofs)
        if err is None:
            link_count += 1
        else:
            skipped.append((str(getattr(link, "label", f"Link {link_key}")), err))

    if rows:
        K = sparse.coo_matrix(
            (np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
            shape=(num_dofs, num_dofs),
        ).tocsc()
        K = 0.5 * (K + K.T)
    else:
        K = sparse.csc_matrix((num_dofs, num_dofs), dtype=float)

    asm = StiffnessAssembly(
        num_dofs=num_dofs,
        K_global=K,
        frame_count=frame_count,
        area_count=area_count,
        link_count=link_count,
        spring_node_count=spring_node_count,
        skipped=skipped,
        warnings=warnings,
    )

    if validate:
        from app.commands.analysis.validation import validate_stiffness
        errs = validate_stiffness(asm)
        asm.warnings.extend(errs)

    return asm


def _resolve_section_props(sec) -> dict[str, float]:
    props: dict[str, float] = {}
    cat = getattr(sec, "catalog_props", None) or {}
    prm = getattr(sec, "profile_params", None) or {}
    for src in (cat, prm):
        for k, v in src.items():
            if isinstance(v, (int, float)) and math.isfinite(float(v)):
                props[k] = float(v)

    h = props.get("h", 0.0)
    b = props.get("b", 0.0)
    if h > 0.0 and b > 0.0:
        if "Area" not in props or props["Area"] <= 0.0:
            props["Area"] = b * h
        if "I33" not in props or props["I33"] <= 0.0:
            props["I33"] = (b * h**3) / 12.0
        if "I22" not in props or props["I22"] <= 0.0:
            props["I22"] = (h * b**3) / 12.0
        if "J" not in props or props["J"] <= 0.0:
            a_max, b_min = max(h, b), min(h, b)
            ratio = b_min / a_max
            beta = (1.0 / 3.0) - 0.21 * ratio * (1.0 - (ratio**4) / 12.0)
            props["J"] = beta * a_max * (b_min**3)

    return props


def _assemble_frame(
    frame,
    rows: list[np.ndarray],
    cols: list[np.ndarray],
    vals: list[np.ndarray],
    num_dofs: int,
    use_shear_deform: bool = True,
) -> str | None:
    sec_res = resolve_section(getattr(frame, "section", None), getattr(frame, "modifiers", None))
    if sec_res is None:
        return "section veya kesit parametreleri eksik"
    if sec_res.E <= 0.0 or sec_res.G <= 0.0:
        return f"Geçersiz malzeme E1={sec_res.E}, G12={sec_res.G}"

    ni = getattr(frame, "node_i", None)
    nj = getattr(frame, "node_j", None)
    if ni is None or nj is None:
        return "frame uç düğümleri eksik"

    if math.dist((ni.x, ni.y, ni.z), (nj.x, nj.y, nj.z)) < 1e-9:
        return "Sıfır uzunluklu eleman"

    kin = resolve_frame_kinematics(frame, sec_res)
    k_loc = local_stiffness(
        E=sec_res.E,
        G=sec_res.G,
        A=sec_res.A,
        J=sec_res.J,
        I33=sec_res.I33,
        I22=sec_res.I22,
        AS2=sec_res.AS2,
        AS3=sec_res.AS3,
        L=kin.L_axis,
        release_i=getattr(frame, "release_i", None),
        release_j=getattr(frame, "release_j", None),
        use_shear_deform=use_shear_deform,
        offset_i=getattr(frame, "offset_length_i", 0.0) or 0.0,
        offset_j=getattr(frame, "offset_length_j", 0.0) or 0.0,
        rigid_factor=getattr(frame, "rigid_factor", 0.0) or 0.0,
    )

    k_node_loc = kin.T_ecc.T @ k_loc @ kin.T_ecc
    k_glob = kin.T_axis.T @ k_node_loc @ kin.T_axis

    dofs_i = getattr(ni, "dof_indices", None)
    dofs_j = getattr(nj, "dof_indices", None)
    if not dofs_i or not dofs_j:
        return "dof_indices tanımlı değil"

    dofs = list(dofs_i) + list(dofs_j)
    if any(d is None or d < 0 or d >= num_dofs for d in dofs):
        return "frame dof sınır dışı"

    _push_block(rows, cols, vals, dofs, k_glob)
    return None


def _assemble_area(
    area,
    rows: list[np.ndarray],
    cols: list[np.ndarray],
    vals: list[np.ndarray],
    num_dofs: int,
) -> str | None:
    nodes = getattr(area, "nodes", [])
    if len(nodes) < 3:
        return "area düğüm sayısı < 3"

    area_sec = getattr(area, "area_section", None)
    thickness = float(getattr(area, "thickness", 0.0) or 0.0)
    if thickness == 0.0 and area_sec is not None:
        thickness = float(getattr(area_sec, "thickness", 0.0) or 0.0)

    if thickness < 0.0:
        return "area kalınlık < 0"
    if thickness == 0.0:
        return None

    mat = getattr(area, "material", None) or (getattr(area_sec, "material", None) if area_sec else None)
    if not mat:
        return "area material yok"

    for i in range(1, len(nodes) - 1):
        tri_nodes = [nodes[0], nodes[i], nodes[i + 1]]
        k_tri_glob = triangle_shell_stiffness_3d(tri_nodes, thickness, mat, area_section=area_sec)
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

        _push_block(rows, cols, vals, tri_dofs, k_tri_glob)

    return None