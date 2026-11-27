# app/analysis/frame_resolver.py
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from data.enums import LoadDirection, SectionType

_GRAVITY_MM_S2 = 9806.65


@dataclass(frozen=True)
class ResolvedSection:
    A: float
    J: float
    I33: float
    I22: float
    AS2: float
    AS3: float
    E: float
    G: float
    density: float
    mass_per_len: float
    weight_per_len: float
    h: float
    b: float
    cg_offset2: float
    cg_offset3: float
    ecc_v2: float
    ecc_v3: float


@dataclass(frozen=True)
class ResolvedFrameKinematics:
    L_node: float
    L_axis: float
    L_clear: float
    R_node: np.ndarray
    R_axis: np.ndarray
    T_node: np.ndarray
    T_axis: np.ndarray
    ecc_i_local: np.ndarray
    ecc_j_local: np.ndarray
    eff_off_i: float
    eff_off_j: float
    H: np.ndarray
    T_ecc: np.ndarray
    transform_stiffness: bool


def _raw_section_dict(sec) -> dict[str, float]:
    merged: dict[str, float] = {}
    cat = getattr(sec, "catalog_props", None)
    if cat:
        for k, v in cat.items():
            if v is not None:
                merged[k] = float(v)
    params = getattr(sec, "profile_params", None)
    if params:
        for k, v in params.items():
            if v is not None:
                merged[k] = float(v)
    return merged


def _derive_missing_geometry(sec_type: SectionType, p: dict[str, float]) -> None:
    h = float(p.get("h", p.get("d", 0.0)) or 0.0)
    b = float(p.get("b", p.get("bf", 0.0)) or 0.0)
    tw = float(p.get("tw", 0.0) or 0.0)
    tf = float(p.get("tf", 0.0) or 0.0)
    t = float(p.get("t", 0.0) or 0.0)

    if sec_type == SectionType.CIRCLE and h > 0.0:
        r = 0.5 * h
        p.setdefault("Area", math.pi * r * r)
        inertia = 0.25 * math.pi * (r ** 4)
        p.setdefault("I33", inertia)
        p.setdefault("I22", inertia)
        p.setdefault("J", 2.0 * inertia)
        p.setdefault("AS2", 0.9 * p["Area"])
        p.setdefault("AS3", 0.9 * p["Area"])
        return

    if sec_type == SectionType.PIPE and h > 0.0 and t > 0.0:
        ro = 0.5 * h
        ri = max(0.0, ro - t)
        p.setdefault("Area", math.pi * (ro * ro - ri * ri))
        inertia = 0.25 * math.pi * (ro ** 4 - ri ** 4)
        p.setdefault("I33", inertia)
        p.setdefault("I22", inertia)
        p.setdefault("J", 2.0 * inertia)
        p.setdefault("AS2", 0.5 * p["Area"])
        p.setdefault("AS3", 0.5 * p["Area"])
        return

    if sec_type == SectionType.BOX and h > 0.0 and b > 0.0 and t > 0.0:
        hi = max(0.0, h - 2.0 * t)
        bi = max(0.0, b - 2.0 * t)
        p.setdefault("Area", b * h - bi * hi)
        p.setdefault("I33", (b * (h ** 3) - bi * (hi ** 3)) / 12.0)
        p.setdefault("I22", (h * (b ** 3) - hi * (bi ** 3)) / 12.0)
        bm = max(1e-6, b - t)
        hm = max(1e-6, h - t)
        p.setdefault("J", (2.0 * t * (bm * hm) ** 2) / (bm + hm))
        p.setdefault("AS2", 2.0 * h * t)
        p.setdefault("AS3", 2.0 * b * t)
        return

    if sec_type == SectionType.I and h > 0.0 and b > 0.0 and tw > 0.0 and tf > 0.0:
        hw = max(0.0, h - 2.0 * tf)
        p.setdefault("Area", 2.0 * b * tf + hw * tw)
        p.setdefault("I33", (b * (h ** 3) - (b - tw) * (hw ** 3)) / 12.0)
        p.setdefault("I22", (2.0 * tf * (b ** 3) + hw * (tw ** 3)) / 12.0)
        p.setdefault("J", (2.0 * b * (tf ** 3) + hw * (tw ** 3)) / 3.0)
        p.setdefault("AS2", h * tw)
        p.setdefault("AS3", (5.0 / 3.0) * b * tf)
        return

    if h > 0.0 and b > 0.0:
        p.setdefault("Area", b * h)
        p.setdefault("I33", b * (h ** 3) / 12.0)
        p.setdefault("I22", h * (b ** 3) / 12.0)
        a_dim = max(b, h)
        b_dim = min(b, h)
        ratio = b_dim / a_dim
        j_rect = a_dim * (b_dim ** 3) * (1.0 / 3.0 - 0.21 * ratio * (1.0 - (ratio ** 4) / 12.0))
        p.setdefault("J", j_rect)
        p.setdefault("AS2", (5.0 / 6.0) * b * h)
        p.setdefault("AS3", (5.0 / 6.0) * b * h)


def resolve_section(sec, frame_modifiers: dict[str, float] | None = None) -> ResolvedSection | None:
    if sec is None:
        return None
    mat = getattr(sec, "material", None)
    if mat is None:
        return None

    p = _raw_section_dict(sec)
    sec_type = getattr(sec, "profile_type", SectionType.RECT)
    _derive_missing_geometry(sec_type, p)

    if "Area" not in p or "I33" not in p or "I22" not in p:
        return None

    f_mods = frame_modifiers or {}
    a_mod = float(p.get("AMod", 1.0)) * float(f_mods.get("Area", f_mods.get("AMod", 1.0)))
    j_mod = float(p.get("JMod", 1.0)) * float(f_mods.get("J", f_mods.get("JMod", 1.0)))
    i3_mod = float(p.get("I3Mod", 1.0)) * float(f_mods.get("I33", f_mods.get("I3Mod", 1.0)))
    i2_mod = float(p.get("I2Mod", 1.0)) * float(f_mods.get("I22", f_mods.get("I2Mod", 1.0)))
    as2_mod = float(p.get("AS2Mod", 1.0)) * float(f_mods.get("AS2", f_mods.get("AS2Mod", 1.0)))
    as3_mod = float(p.get("AS3Mod", 1.0)) * float(f_mods.get("AS3", f_mods.get("AS3Mod", 1.0)))
    m_mod = float(p.get("MMod", 1.0)) * float(f_mods.get("Mass", f_mods.get("MMod", 1.0)))
    w_mod = float(p.get("WMod", 1.0)) * float(f_mods.get("Weight", f_mods.get("WMod", 1.0)))

    raw_area = float(p["Area"])
    A = raw_area * a_mod
    I33 = float(p["I33"]) * i3_mod
    I22 = float(p["I22"]) * i2_mod
    raw_j = float(p.get("J", 0.0))
    J = (raw_j * j_mod) if raw_j > 0.0 else (1e-6 * min(I22, I33))
    AS2 = float(p.get("AS2", raw_area)) * as2_mod
    AS3 = float(p.get("AS3", raw_area)) * as3_mod

    E = float(getattr(mat, "E1", 0.0))
    G = float(getattr(mat, "G12", 0.0))
    density = float(getattr(mat, "density", 0.0))

    mass_per_len = density * raw_area * m_mod
    weight_per_len = density * raw_area * w_mod * _GRAVITY_MM_S2

    h = float(p.get("h", p.get("d", 0.0)) or 0.0)
    b = float(p.get("b", p.get("bf", 0.0)) or 0.0)

    return ResolvedSection(
        A=A,
        J=J,
        I33=I33,
        I22=I22,
        AS2=AS2,
        AS3=AS3,
        E=E,
        G=G,
        density=density,
        mass_per_len=mass_per_len,
        weight_per_len=weight_per_len,
        h=h,
        b=b,
        cg_offset2=float(getattr(sec, "cg_offset2", 0.0) or 0.0),
        cg_offset3=float(getattr(sec, "cg_offset3", 0.0) or 0.0),
        ecc_v2=float(getattr(sec, "ecc_v2", 0.0) or 0.0),
        ecc_v3=float(getattr(sec, "ecc_v3", 0.0) or 0.0),
    )


def compute_local_axes(p1, p2, beta_deg: float = 0.0, up_global=(0.0, 0.0, 1.0)) -> tuple[np.ndarray, float]:
    v = np.asarray(p2, dtype=float) - np.asarray(p1, dtype=float)
    L = float(np.linalg.norm(v))
    if L < 1e-9:
        return np.eye(3, dtype=float), 0.0
    e1 = v / L
    up = np.asarray(up_global, dtype=float)
    if abs(np.dot(e1, up)) > 0.9999:
        up = np.array([0.0, 1.0, 0.0]) if abs(e1[2]) > 0.9999 else np.array([0.0, 0.0, 1.0])
    e3 = np.cross(e1, up)
    e3 /= np.linalg.norm(e3)
    e2 = np.cross(e3, e1)
    if abs(beta_deg) > 1e-12:
        a = math.radians(beta_deg)
        ca, sa = math.cos(a), math.sin(a)
        e2, e3 = ca * e2 + sa * e3, -sa * e2 + ca * e3
    R = np.vstack([e1, e2, e3])
    return R, L


def _cardinal_point_code(cardinal_pt: str | int | None) -> int:
    if cardinal_pt is None:
        return 10
    if isinstance(cardinal_pt, int):
        return cardinal_pt
    token = str(cardinal_pt).strip().split()[0]
    if token.isdigit():
        return int(token)
    return 10


def cardinal_centroid_offset(sec_res: ResolvedSection | None, cardinal_pt: str | int | None) -> tuple[float, float]:
    if sec_res is None:
        return 0.0, 0.0
    code = _cardinal_point_code(cardinal_pt)
    half_h = 0.5 * sec_res.h
    half_b = 0.5 * sec_res.b
    c2 = sec_res.cg_offset2
    c3 = sec_res.cg_offset3

    if code == 1:
        return c2 + half_b, c3 + half_h
    if code == 2:
        return c2, c3 + half_h
    if code == 3:
        return c2 - half_b, c3 + half_h
    if code == 4:
        return c2 + half_b, c3
    if code == 5:
        return c2, c3
    if code == 6:
        return c2 - half_b, c3
    if code == 7:
        return c2 + half_b, c3 - half_h
    if code == 8:
        return c2, c3 - half_h
    if code == 9:
        return c2 - half_b, c3 - half_h
    if code == 11:
        return c2 - sec_res.ecc_v2, c3 - sec_res.ecc_v3
    return c2, c3


def rigid_offset_matrix(off_i: float, off_j: float) -> np.ndarray:
    H = np.eye(12, dtype=float)
    if off_i > 0.0:
        H[1, 5] = off_i
        H[2, 4] = -off_i
    if off_j > 0.0:
        H[7, 11] = -off_j
        H[8, 10] = off_j
    return H


def eccentricity_transform_matrix(ecc_i_loc: np.ndarray, ecc_j_loc: np.ndarray) -> np.ndarray:
    T_ecc = np.eye(12, dtype=float)
    e1i, e2i, e3i = float(ecc_i_loc[0]), float(ecc_i_loc[1]), float(ecc_i_loc[2])
    T_ecc[0, 4] = e3i
    T_ecc[0, 5] = -e2i
    T_ecc[1, 3] = -e3i
    T_ecc[1, 5] = e1i
    T_ecc[2, 3] = e2i
    T_ecc[2, 4] = -e1i

    e1j, e2j, e3j = float(ecc_j_loc[0]), float(ecc_j_loc[1]), float(ecc_j_loc[2])
    T_ecc[6, 10] = e3j
    T_ecc[6, 11] = -e2j
    T_ecc[7, 9] = -e3j
    T_ecc[7, 11] = e1j
    T_ecc[8, 9] = e2j
    T_ecc[8, 10] = -e1j
    return T_ecc


def resolve_frame_kinematics(frame, sec_res: ResolvedSection | None = None) -> ResolvedFrameKinematics:
    ni = getattr(frame, "node_i", None)
    nj = getattr(frame, "node_j", None)
    p1 = np.array([ni.x, ni.y, ni.z], dtype=float)
    p2 = np.array([nj.x, nj.y, nj.z], dtype=float)
    beta = float(getattr(frame, "rotation_deg", 0.0) or 0.0)

    R_node, L_node = compute_local_axes(p1, p2, beta_deg=beta)
    T_node = np.kron(np.eye(4), R_node)

    if sec_res is None:
        sec_res = resolve_section(getattr(frame, "section", None), getattr(frame, "modifiers", None))

    cp_e2, cp_e3 = cardinal_centroid_offset(sec_res, getattr(frame, "cardinal_pt", "10 (centroid)"))
    if getattr(frame, "mirror2", False) or getattr(frame, "mirror_abt2", False):
        cp_e2 = -cp_e2
    if getattr(frame, "mirror3", False) or getattr(frame, "mirror_abt3", False):
        cp_e3 = -cp_e3

    jt_i = np.asarray(getattr(frame, "jt_offset_i", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0), dtype=float)
    jt_j = np.asarray(getattr(frame, "jt_offset_j", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0), dtype=float)
    ins_cs = str(getattr(frame, "insertion_coord_sys", "Local") or "Local").strip().upper()

    if ins_cs == "GLOBAL":
        jt_i_glob = jt_i
        jt_j_glob = jt_j
        cp_glob = R_node.T @ np.array([0.0, cp_e2, cp_e3], dtype=float)
        p1_axis = p1 + jt_i_glob + cp_glob
        p2_axis = p2 + jt_j_glob + cp_glob
    else:
        ecc_i_init = np.array([jt_i[0], jt_i[1] + cp_e2, jt_i[2] + cp_e3], dtype=float)
        ecc_j_init = np.array([jt_j[0], jt_j[1] + cp_e2, jt_j[2] + cp_e3], dtype=float)
        p1_axis = p1 + R_node.T @ ecc_i_init
        p2_axis = p2 + R_node.T @ ecc_j_init

    R_axis, L_axis = compute_local_axes(p1_axis, p2_axis, beta_deg=beta)
    if L_axis <= 1e-9:
        R_axis = R_node
        L_axis = L_node
        p1_axis = p1
        p2_axis = p2

    T_axis = np.kron(np.eye(4), R_axis)
    ecc_i_local = R_axis @ (p1_axis - p1)
    ecc_j_local = R_axis @ (p2_axis - p2)

    off_i = float(getattr(frame, "offset_length_i", 0.0) or 0.0)
    off_j = float(getattr(frame, "offset_length_j", 0.0) or 0.0)
    rf = float(getattr(frame, "rigid_factor", 0.0) or 0.0)
    eff_off_i = max(0.0, off_i * rf)
    eff_off_j = max(0.0, off_j * rf)
    L_clear = L_axis - eff_off_i - eff_off_j
    if L_clear <= 1e-6:
        L_clear = L_axis
        eff_off_i = 0.0
        eff_off_j = 0.0

    H = rigid_offset_matrix(eff_off_i, eff_off_j)
    transform_stiffness = bool(getattr(frame, "transform", True))
    T_ecc = eccentricity_transform_matrix(ecc_i_local, ecc_j_local) if transform_stiffness else np.eye(12, dtype=float)

    return ResolvedFrameKinematics(
        L_node=L_node,
        L_axis=L_axis,
        L_clear=L_clear,
        R_node=R_node,
        R_axis=R_axis,
        T_node=T_node,
        T_axis=T_axis,
        ecc_i_local=ecc_i_local,
        ecc_j_local=ecc_j_local,
        eff_off_i=eff_off_i,
        eff_off_j=eff_off_j,
        H=H,
        T_ecc=T_ecc,
        transform_stiffness=transform_stiffness,
    )

def frame_load_direction_vector(
    R_axis: np.ndarray,
    L_axis: float,
    coord_sys: str,
    load_dir: str,
    direction: LoadDirection | None,
) -> tuple[np.ndarray, float]:
    if L_axis <= 1e-12:
        return np.zeros(3, dtype=float), 0.0

    e1 = R_axis[0]
    e2 = R_axis[1]
    e3 = R_axis[2]
    proj_xy = math.hypot(float(e1[0]), float(e1[1]))
    proj_xz = math.hypot(float(e1[0]), float(e1[2]))
    proj_yz = math.hypot(float(e1[1]), float(e1[2]))

    if direction is not None:
        if direction == LoadDirection.LOCAL_1:
            return e1, 1.0
        if direction == LoadDirection.LOCAL_2:
            return e2, 1.0
        if direction == LoadDirection.LOCAL_3:
            return e3, 1.0
        if direction == LoadDirection.GLOBAL_X:
            return np.array([1.0, 0.0, 0.0]), 1.0
        if direction == LoadDirection.GLOBAL_Y:
            return np.array([0.0, 1.0, 0.0]), 1.0
        if direction == LoadDirection.GLOBAL_Z:
            return np.array([0.0, 0.0, 1.0]), 1.0
        if direction == LoadDirection.PROJECTED_X:
            return np.array([1.0, 0.0, 0.0]), proj_yz
        if direction == LoadDirection.PROJECTED_Y:
            return np.array([0.0, 1.0, 0.0]), proj_xz
        if direction == LoadDirection.PROJECTED_Z:
            return np.array([0.0, 0.0, 1.0]), proj_xy
        if direction == LoadDirection.GRAVITY:
            return np.array([0.0, 0.0, -1.0]), 1.0

    cs = str(coord_sys or "GLOBAL").strip().upper()
    ld = str(load_dir or "").strip().upper()

    if cs == "LOCAL":
        if ld in ("1", "X"):
            return e1, 1.0
        if ld in ("2", "Y"):
            return e2, 1.0
        if ld in ("3", "Z"):
            return e3, 1.0
        return e2, 1.0

    if ld in ("1", "4", "X", "UX", "FX"):
        return np.array([1.0, 0.0, 0.0]), 1.0
    if ld in ("2", "5", "Y", "UY", "FY"):
        return np.array([0.0, 1.0, 0.0]), 1.0
    if ld in ("3", "6", "Z", "UZ", "FZ"):
        return np.array([0.0, 0.0, 1.0]), 1.0
    if ld in ("7", "PX"):
        return np.array([1.0, 0.0, 0.0]), proj_yz
    if ld in ("8", "PY"):
        return np.array([0.0, 1.0, 0.0]), proj_xz
    if ld in ("9", "PZ"):
        return np.array([0.0, 0.0, 1.0]), proj_xy
    if ld in ("10", "GRAV", "GRAVITY"):
        return np.array([0.0, 0.0, -1.0]), 1.0

    return np.array([0.0, 0.0, -1.0]), 1.0