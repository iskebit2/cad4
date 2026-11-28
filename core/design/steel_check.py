# core/design/steel_check.py
from __future__ import annotations

import hashlib
import json
import math
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.analysis.force_recovery import FrameForceResult, FrameStationForce
from core.report.report_dataframe import ReportDataFrame
from core.units import Dimension, UnitSystem, convert_value
from data.enums import MatType, SectionType
from data.materials_catalog import get_catalog_params
from domain.definition import LoadCombination, SteelConfig, SteelMemberSpec


@dataclass
class SteelStationCheck:
    combo_name: str
    ratio: float
    x: float
    N: float
    V2: float
    V3: float
    T: float
    M2: float
    M3: float
    Pc: float
    Mcx: float
    Mcy: float
    Vcx: float
    Vcy: float
    dcr_axial: float
    dcr_bend_x: float
    dcr_bend_y: float
    dcr_shear_x: float
    dcr_shear_y: float
    dcr_interaction: float
    equation: str
    ok: bool


@dataclass
class SteelMemberResult:
    frame_id: int
    label: str
    section_name: str
    material_name: str
    length: float
    design_method: str
    flange_class: str
    web_class: str
    governing_combo: str
    governing_ratio: float
    governing_x: float
    max_dcr_interaction: float
    max_dcr_shear: float
    max_dcr_deflection: float
    deflection_mm: float
    deflection_limit_mm: float
    ok: bool
    stations: list[SteelStationCheck] = field(default_factory=list)


def compute_model_geometry_hash(project: Any) -> str:
    h = hashlib.sha256()
    math_model = getattr(project, "math_model", None)
    if math_model is None:
        return h.hexdigest()

    for nid in sorted(math_model.nodes.keys()):
        n = math_model.nodes[nid]
        h.update(f"N:{nid}:{round(float(n.x), 6)}:{round(float(n.y), 6)}:{round(float(n.z), 6)}".encode())

    for fid in sorted(math_model.frames.keys()):
        f = math_model.frames[fid]
        ni = getattr(getattr(f, "node_i", None), "unique_id", -1)
        nj = getattr(getattr(f, "node_j", None), "unique_id", -1)
        sec = getattr(f, "section", None)
        sec_name = sec if isinstance(sec, str) else getattr(sec, "name", "")
        rot = round(float(getattr(f, "rotation_deg", 0.0) or 0.0), 4)
        h.update(f"F:{fid}:{ni}:{nj}:{sec_name}:{rot}".encode())

    for sname in sorted((getattr(project, "sections", None) or {}).keys()):
        sec = project.sections[sname]
        mat = getattr(sec, "material", None)
        mat_sig = f"{getattr(mat, 'name', '')}:{getattr(mat, 'fy', 0.0)}:{getattr(mat, 'fu', 0.0)}:{getattr(mat, 'E1', 0.0)}"
        prm = json.dumps(getattr(sec, "profile_params", {}) or {}, sort_keys=True)
        h.update(f"S:{sname}:{mat_sig}:{prm}".encode())

    for cname in sorted((getattr(project, "combinations", None) or {}).keys()):
        cmb = project.combinations[cname]
        items_sig = [(it.case_or_pattern_name, round(float(it.scale_factor), 6)) for it in getattr(cmb, "items", [])]
        h.update(f"C:{cname}:{cmb.combo_type}:{cmb.auto_design}:{items_sig}".encode())

    return h.hexdigest()


def _resolve_steel_material(mat: Any, cfg: SteelConfig, thickness_mm: float) -> dict[str, float]:
    fy = float(getattr(mat, "fy", 0.0) or 0.0)
    fu = float(getattr(mat, "fu", 0.0) or 0.0)
    e_mod = float(getattr(mat, "E1", 0.0) or 0.0)
    g_mod = float(getattr(mat, "G12", 0.0) or 0.0)

    grade = str(getattr(mat, "grade", "") or getattr(mat, "name", "") or cfg.default_grade).strip()
    if fy <= 0.0 or fu <= 0.0 or e_mod <= 0.0:
        cat = get_catalog_params(grade, MatType.STEEL, thickness_mm=max(1.0, thickness_mm))
        if fy <= 0.0:
            fy = float(cat["fy"])
        if fu <= 0.0:
            fu = float(cat["fu"])
        if e_mod <= 0.0:
            e_mod = float(cat["E"])
        if g_mod <= 0.0:
            g_mod = float(cat["G"])

    if g_mod <= 0.0:
        g_mod = e_mod / 2.6

    return {
        "name": str(getattr(mat, "name", grade)),
        "fy": fy,
        "fu": fu,
        "E": e_mod,
        "G": g_mod,
    }


def _resolve_steel_section(sec: Any, unit_system: UnitSystem) -> dict[str, float | str]:
    raw: dict[str, float] = {}
    for src in (getattr(sec, "catalog_props", None) or {}, getattr(sec, "profile_params", None) or {}):
        for k, v in src.items():
            if v is not None:
                raw[k] = float(v)

    to_mm = lambda v: float(convert_value(Dimension.LENGTH, float(v), unit_system, UnitSystem.N_MM))
    to_mm2 = lambda v: float(convert_value(Dimension.AREA, float(v), unit_system, UnitSystem.N_MM))
    to_mm3 = lambda v: float(convert_value(Dimension.I3, float(v), unit_system, UnitSystem.N_MM))
    to_mm4 = lambda v: float(convert_value(Dimension.I4, float(v), unit_system, UnitSystem.N_MM))
    to_mm6 = lambda v: float(convert_value(Dimension.I6, float(v), unit_system, UnitSystem.N_MM))

    sec_type: SectionType = getattr(sec, "profile_type", SectionType.I)
    h = to_mm(raw.get("h", raw.get("d", 0.0)))
    b = to_mm(raw.get("b", raw.get("bf", 0.0)))
    tw = to_mm(raw.get("tw", raw.get("t", 0.0)))
    tf = to_mm(raw.get("tf", raw.get("t", 0.0)))
    t = to_mm(raw.get("t", 0.0))
    r = to_mm(raw.get("r", 0.0))

    area = to_mm2(raw["Area"]) if raw.get("Area", 0.0) > 0.0 else (b * h)
    i33 = to_mm4(raw["I33"]) if raw.get("I33", 0.0) > 0.0 else (b * (h ** 3) / 12.0)
    i22 = to_mm4(raw["I22"]) if raw.get("I22", 0.0) > 0.0 else (h * (b ** 3) / 12.0)
    j = to_mm4(raw["J"]) if raw.get("J", 0.0) > 0.0 else (1e-4 * min(i22, i33))

    s33_raw = raw.get("S33Top", raw.get("S33", 0.0))
    s22_raw = raw.get("S22Left", raw.get("S22", 0.0))
    s33 = to_mm3(s33_raw) if s33_raw > 0.0 else ((2.0 * i33 / h) if h > 0.0 else 0.0)
    s22 = to_mm3(s22_raw) if s22_raw > 0.0 else ((2.0 * i22 / b) if b > 0.0 else 0.0)

    z33 = to_mm3(raw["Z33"]) if raw.get("Z33", 0.0) > 0.0 else (1.12 * s33)
    z22 = to_mm3(raw["Z22"]) if raw.get("Z22", 0.0) > 0.0 else (1.50 * s22)

    r33 = to_mm(raw["R33"]) if raw.get("R33", 0.0) > 0.0 else (math.sqrt(i33 / area) if area > 0.0 else 0.0)
    r22 = to_mm(raw["R22"]) if raw.get("R22", 0.0) > 0.0 else (math.sqrt(i22 / area) if area > 0.0 else 0.0)

    hw = max(0.0, h - 2.0 * tf - 2.0 * r) if sec_type == SectionType.I else max(0.0, h - 2.0 * t)
    cw_default = (i22 * ((h - tf) ** 2) / 4.0) if sec_type == SectionType.I and h > tf else 0.0
    cw = to_mm6(raw["Cw"]) if raw.get("Cw", 0.0) > 0.0 else cw_default

    as2 = to_mm2(raw["AS2"]) if raw.get("AS2", 0.0) > 0.0 else (h * tw if tw > 0.0 else 0.5 * area)
    as3 = to_mm2(raw["AS3"]) if raw.get("AS3", 0.0) > 0.0 else (2.0 * b * tf if tf > 0.0 else 0.5 * area)

    return {
        "sec_type": sec_type.value,
        "h": h,
        "b": b,
        "tw": tw,
        "tf": tf,
        "t": t,
        "r": r,
        "hw": hw,
        "Area": area,
        "I33": i33,
        "I22": i22,
        "J": j,
        "Cw": cw,
        "S33": s33,
        "S22": s22,
        "Z33": z33,
        "Z22": z22,
        "R33": r33,
        "R22": r22,
        "AS2": as2,
        "AS3": as3,
    }


def classify_section_cythyedy(geom: dict[str, float | str], fy: float, e_mod: float) -> tuple[str, str, float, float]:
    sec_type = str(geom["sec_type"])
    h = float(geom["h"])
    b = float(geom["b"])
    tw = float(geom["tw"])
    tf = float(geom["tf"])
    t = float(geom["t"])
    hw = float(geom["hw"])

    sqrt_efy = math.sqrt(e_mod / fy) if fy > 0.0 else 28.0

    if sec_type == SectionType.PIPE.value:
        dt = (h / t) if t > 0.0 else 0.0
        if dt <= 0.07 * (e_mod / fy):
            return "Kompakt", "Kompakt", 1.0, 1.0
        if dt <= 0.31 * (e_mod / fy):
            return "Kompakt Olmayan", "Kompakt Olmayan", 1.0, 1.0
        qa = min(1.0, (0.038 * e_mod) / (fy * dt) + 2.0 / 3.0) if dt > 0.0 else 1.0
        return "Narin", "Narin", 1.0, qa

    if sec_type == SectionType.BOX.value:
        bt = ((b - 3.0 * t) / t) if t > 0.0 else 0.0
        ht = ((h - 3.0 * t) / t) if t > 0.0 else 0.0
        lam_pf = 1.12 * sqrt_efy
        lam_rf = 1.40 * sqrt_efy
        lam_pw = 2.42 * sqrt_efy
        lam_rw = 5.70 * sqrt_efy
        f_cls = "Kompakt" if bt <= lam_pf else ("Kompakt Olmayan" if bt <= lam_rf else "Narin")
        w_cls = "Kompakt" if ht <= lam_pw else ("Kompakt Olmayan" if ht <= lam_rw else "Narin")
        qa = 1.0
        if f_cls == "Narin" and bt > 0.0:
            be = 1.92 * t * sqrt_efy * (1.0 - 0.38 / bt * sqrt_efy)
            qa *= min(1.0, max(0.4, be / max(1.0, b - 3.0 * t)))
        if w_cls == "Narin" and ht > 0.0:
            he = 1.92 * t * sqrt_efy * (1.0 - 0.38 / ht * sqrt_efy)
            qa *= min(1.0, max(0.4, he / max(1.0, h - 3.0 * t)))
        return f_cls, w_cls, 1.0, qa

    lam_f = (0.5 * b / tf) if tf > 0.0 else 0.0
    lam_w = (hw / tw) if tw > 0.0 else 0.0

    lam_pf = 0.38 * sqrt_efy
    lam_rf = 1.00 * sqrt_efy
    lam_pw = 3.76 * sqrt_efy
    lam_rw = 5.70 * sqrt_efy

    if lam_f <= lam_pf:
        f_cls = "Kompakt"
    elif lam_f <= lam_rf:
        f_cls = "Kompakt Olmayan"
    else:
        f_cls = "Narin"

    if lam_w <= lam_pw:
        w_cls = "Kompakt"
    elif lam_w <= lam_rw:
        w_cls = "Kompakt Olmayan"
    else:
        w_cls = "Narin"

    qs = 1.0
    lam_r_comp_f = 0.56 * sqrt_efy
    if lam_f > lam_r_comp_f:
        if lam_f <= 1.03 * sqrt_efy:
            qs = 1.415 - 0.74 * lam_f / sqrt_efy
        else:
            qs = (0.69 * e_mod) / (fy * (lam_f ** 2))
        qs = max(0.3, min(1.0, qs))

    qa = 1.0
    lam_r_comp_w = 1.49 * sqrt_efy
    if lam_w > lam_r_comp_w and tw > 0.0:
        be = 1.92 * tw * sqrt_efy * (1.0 - 0.34 / lam_w * sqrt_efy)
        be = min(hw, max(0.0, be))
        area = float(geom["Area"])
        a_eff = area - (hw - be) * tw
        qa = max(0.3, min(1.0, a_eff / area)) if area > 0.0 else 1.0

    return f_cls, w_cls, qs, qa


def _resistance_factors(method: str) -> dict[str, float]:
    if str(method).upper() == "ASD":
        return {
            "t_y": 1.0 / 1.67,
            "t_u": 1.0 / 2.00,
            "c": 1.0 / 1.67,
            "b": 1.0 / 1.67,
            "v": 1.0 / 1.50,
        }
    return {
        "t_y": 0.90,
        "t_u": 0.75,
        "c": 0.90,
        "b": 0.90,
        "v": 1.00,
    }


def compute_axial_capacity_cythyedy(
    geom: dict[str, float | str],
    mat: dict[str, float],
    spec: SteelMemberSpec,
    length_mm: float,
    qs: float,
    qa: float,
    method: str,
) -> tuple[float, float]:
    area = float(geom["Area"])
    r33 = float(geom["R33"])
    r22 = float(geom["R22"])
    i33 = float(geom["I33"])
    i22 = float(geom["I22"])
    j = float(geom["J"])
    cw = float(geom["Cw"])
    fy = mat["fy"]
    fu = mat["fu"]
    e_mod = mat["E"]
    g_mod = mat["G"]
    fac = _resistance_factors(method)

    pn_y = fy * area
    ae = area * spec.net_area_ratio * spec.shear_lag_u
    pn_u = fu * ae
    pt_cap = min(fac["t_y"] * pn_y, fac["t_u"] * pn_u)

    kl_rx = (spec.kx * length_mm / r33) if r33 > 0.0 else 0.0
    kl_ry = (spec.ky * length_mm / r22) if r22 > 0.0 else 0.0
    kl_r = max(kl_rx, kl_ry)
    fe_flex = (math.pi ** 2 * e_mod) / (kl_r ** 2) if kl_r > 0.0 else 1e12

    kz_l = spec.kz * length_mm
    ix_iy = i33 + i22
    if ix_iy > 0.0 and kz_l > 0.0:
        fe_tor = ((math.pi ** 2 * e_mod * cw) / (kz_l ** 2) + g_mod * j) / ix_iy
    else:
        fe_tor = 1e12

    fe = min(fe_flex, fe_tor)
    q = qs * qa
    q_fy = q * fy
    ratio = q_fy / fe if fe > 0.0 else 0.0
    if ratio <= 2.25:
        fcr = q * (0.658 ** ratio) * fy
    else:
        fcr = 0.877 * fe

    pc_cap = fac["c"] * fcr * area
    return pt_cap, pc_cap


def compute_flexural_capacity_cythyedy(
    geom: dict[str, float | str],
    mat: dict[str, float],
    spec: SteelMemberSpec,
    length_mm: float,
    flange_class: str,
    method: str,
) -> tuple[float, float]:
    fy = mat["fy"]
    e_mod = mat["E"]
    g_mod = mat["G"]
    z33 = float(geom["Z33"])
    z22 = float(geom["Z22"])
    s33 = float(geom["S33"])
    s22 = float(geom["S22"])
    i22 = float(geom["I22"])
    j = float(geom["J"])
    cw = float(geom["Cw"])
    r22 = float(geom["R22"])
    h = float(geom["h"])
    b = float(geom["b"])
    tf = float(geom["tf"])
    sec_type = str(geom["sec_type"])
    fac = _resistance_factors(method)

    mp_x = fy * z33
    mp_y = fy * z22

    mn_x = mp_x
    if flange_class == "Kompakt Olmayan" and tf > 0.0:
        lam = 0.5 * b / tf
        lam_pf = 0.38 * math.sqrt(e_mod / fy)
        lam_rf = 1.00 * math.sqrt(e_mod / fy)
        if lam_rf > lam_pf:
            mn_x = min(mn_x, mp_x - (mp_x - 0.7 * fy * s33) * ((lam - lam_pf) / (lam_rf - lam_pf)))

    lb = spec.lbx if spec.lbx > 0.0 else length_mm
    if sec_type == SectionType.I.value and r22 > 0.0 and s33 > 0.0 and h > tf:
        ho = h - tf
        rts = math.sqrt(math.sqrt(i22 * cw) / s33) if cw > 0.0 else r22
        lp = 1.76 * r22 * math.sqrt(e_mod / fy)
        c_ltb = 1.0
        term = (j * c_ltb) / (s33 * ho)
        lr = 1.95 * rts * (e_mod / (0.7 * fy)) * math.sqrt(
            term + math.sqrt(term ** 2 + 6.76 * ((0.7 * fy / e_mod) ** 2))
        )
        if lb > lp:
            if lb <= lr and lr > lp:
                mn_ltb = spec.cb * (mp_x - (mp_x - 0.7 * fy * s33) * ((lb - lp) / (lr - lp)))
            else:
                fcr_ltb = ((spec.cb * (math.pi ** 2) * e_mod) / ((lb / rts) ** 2)) * math.sqrt(
                    1.0 + 0.078 * term * ((lb / rts) ** 2)
                )
                mn_ltb = fcr_ltb * s33
            mn_x = min(mn_x, mn_ltb)

    mn_y = min(mp_y, 1.6 * fy * s22)
    if flange_class == "Kompakt Olmayan" and tf > 0.0:
        lam = 0.5 * b / tf
        lam_pf = 0.38 * math.sqrt(e_mod / fy)
        lam_rf = 1.00 * math.sqrt(e_mod / fy)
        if lam_rf > lam_pf:
            mn_y = min(mn_y, mp_y - (mp_y - 0.7 * fy * s22) * ((lam - lam_pf) / (lam_rf - lam_pf)))

    return fac["b"] * mn_x, fac["b"] * mn_y


def compute_shear_capacity_cythyedy(
    geom: dict[str, float | str],
    mat: dict[str, float],
    method: str,
) -> tuple[float, float]:
    fy = mat["fy"]
    e_mod = mat["E"]
    h = float(geom["h"])
    tw = float(geom["tw"])
    as2 = float(geom["AS2"])
    as3 = float(geom["AS3"])
    sec_type = str(geom["sec_type"])
    fac = _resistance_factors(method)

    cv1 = 1.0
    phi_v = fac["v"]
    if sec_type == SectionType.I.value and tw > 0.0:
        h_tw = h / tw
        if h_tw <= 2.24 * math.sqrt(e_mod / fy):
            cv1 = 1.0
            phi_v = 1.0 if str(method).upper() != "ASD" else (1.0 / 1.50)
        else:
            kv = 5.34
            lim = 1.10 * math.sqrt(kv * e_mod / fy)
            if h_tw > lim:
                cv1 = lim / h_tw

    vcx = phi_v * 0.6 * fy * as2 * cv1
    vcy = fac["v"] * 0.6 * fy * as3
    return vcx, vcy


def build_combination_frame_forces(
    project: Any,
    frame_forces: dict[str, dict[int, FrameForceResult]],
    cfg: SteelConfig,
) -> dict[str, dict[int, FrameForceResult]]:
    combos: dict[str, LoadCombination] = getattr(project, "combinations", None) or {}
    if not combos:
        return frame_forces

    selected_combos = {
        cname: cmb
        for cname, cmb in combos.items()
        if cfg.include_non_auto_combos or getattr(cmb, "auto_design", False) or not any(
            getattr(c, "auto_design", False) for c in combos.values()
        )
    }
    if not selected_combos:
        return frame_forces

    out: dict[str, dict[int, FrameForceResult]] = {}
    for cname, cmb in selected_combos.items():
        ctype = str(getattr(cmb, "combo_type", "Linear Add") or "Linear Add").strip().lower()
        items = getattr(cmb, "items", []) or []
        if not items:
            continue

        all_fids: set[int] = set()
        for it in items:
            cmap = frame_forces.get(it.case_or_pattern_name)
            if cmap:
                all_fids.update(cmap.keys())

        combo_map: dict[int, FrameForceResult] = {}
        for fid in all_fids:
            template: FrameForceResult | None = None
            for it in items:
                ff = (frame_forces.get(it.case_or_pattern_name) or {}).get(fid)
                if ff is not None and ff.stations:
                    template = ff
                    break
            if template is None:
                continue

            n_sta = len(template.stations)
            arr_end_i = np.zeros(6, dtype=float)
            arr_end_j = np.zeros(6, dtype=float)
            arr_sta = np.zeros((n_sta, 6), dtype=float)
            has_init = False

            for it in items:
                ff = (frame_forces.get(it.case_or_pattern_name) or {}).get(fid)
                if ff is None or len(ff.stations) != n_sta:
                    continue
                sf = float(it.scale_factor)
                ei = np.asarray(ff.end_i, dtype=float) * sf
                ej = np.asarray(ff.end_j, dtype=float) * sf
                st_mat = np.array([[s.N, s.V2, s.V3, s.T, s.M2, s.M3] for s in ff.stations], dtype=float) * sf

                if ctype == "envelope":
                    if not has_init:
                        arr_end_i = ei.copy()
                        arr_end_j = ej.copy()
                        arr_sta = st_mat.copy()
                        has_init = True
                    else:
                        mask_i = np.abs(ei) > np.abs(arr_end_i)
                        arr_end_i[mask_i] = ei[mask_i]
                        mask_j = np.abs(ej) > np.abs(arr_end_j)
                        arr_end_j[mask_j] = ej[mask_j]
                        mask_s = np.abs(st_mat) > np.abs(arr_sta)
                        arr_sta[mask_s] = st_mat[mask_s]
                elif ctype == "absolute add":
                    arr_end_i += np.abs(ei)
                    arr_end_j += np.abs(ej)
                    arr_sta += np.abs(st_mat)
                elif ctype == "srss":
                    arr_end_i += ei ** 2
                    arr_end_j += ej ** 2
                    arr_sta += st_mat ** 2
                else:
                    arr_end_i += ei
                    arr_end_j += ej
                    arr_sta += st_mat

            if ctype == "srss":
                arr_end_i = np.sqrt(arr_end_i)
                arr_end_j = np.sqrt(arr_end_j)
                arr_sta = np.sqrt(arr_sta)

            stations = [
                FrameStationForce(
                    ratio=template.stations[i].ratio,
                    x=template.stations[i].x,
                    N=float(arr_sta[i, 0]),
                    V2=float(arr_sta[i, 1]),
                    V3=float(arr_sta[i, 2]),
                    T=float(arr_sta[i, 3]),
                    M2=float(arr_sta[i, 4]),
                    M3=float(arr_sta[i, 5]),
                )
                for i in range(n_sta)
            ]
            combo_map[fid] = FrameForceResult(
                frame_id=fid,
                label=template.label,
                case_name=cname,
                length=template.length,
                end_i=arr_end_i,
                end_j=arr_end_j,
                stations=stations,
            )

        if combo_map:
            out[cname] = combo_map

    return out if out else frame_forces


def _compute_max_deflection_mm(
    project: Any,
    frame: Any,
    length_mm: float,
    unit_system: UnitSystem,
) -> float:
    analysis_res = getattr(project, "analysis_results", None)
    static_results = getattr(analysis_res, "static_results", None) or {}
    if not static_results or length_mm <= 1e-6:
        return 0.0

    ni = getattr(frame, "node_i", None)
    nj = getattr(frame, "node_j", None)
    if ni is None or nj is None:
        return 0.0

    ki = str(getattr(ni, "unique_id", ""))
    kj = str(getattr(nj, "unique_id", ""))
    p1 = np.array([float(ni.x), float(ni.y), float(ni.z)], dtype=float)
    p2 = np.array([float(nj.x), float(nj.y), float(nj.z)], dtype=float)
    axis_vec = p2 - p1
    norm = float(np.linalg.norm(axis_vec))
    if norm <= 1e-9:
        return 0.0
    e1 = axis_vec / norm

    max_perp = 0.0
    for sres in static_results.values():
        nd = getattr(sres, "node_displacements", None) or {}
        ui = nd.get(ki)
        uj = nd.get(kj)
        if ui is None or uj is None:
            continue
        du = np.asarray(uj[:3], dtype=float) - np.asarray(ui[:3], dtype=float)
        du_perp = du - np.dot(du, e1) * e1
        disp_val = float(np.linalg.norm(du_perp))
        disp_mm = float(convert_value(Dimension.LENGTH, disp_val, unit_system, UnitSystem.N_MM))
        if disp_mm > max_perp:
            max_perp = disp_mm

    return max_perp


def evaluate_steel_member(
    project: Any,
    frame: Any,
    combo_forces: dict[str, dict[int, FrameForceResult]],
    spec: SteelMemberSpec,
    cfg: SteelConfig,
) -> SteelMemberResult | None:
    sec = getattr(frame, "section", None)
    if isinstance(sec, str):
        sec = (getattr(project, "sections", None) or {}).get(sec)
    if sec is None:
        return None
    mat = getattr(sec, "material", None)
    if mat is None or MatType.from_sap(getattr(mat, "mat_type", None)) != MatType.STEEL:
        return None

    unit_system: UnitSystem = getattr(project, "unit_system", UnitSystem.N_MM)
    fid = int(frame.unique_id)
    label = str(getattr(frame, "label", "") or f"F#{fid}")
    length_mm = float(convert_value(Dimension.LENGTH, float(frame.get_length()), unit_system, UnitSystem.N_MM))
    geom = _resolve_steel_section(sec, unit_system)
    thick = max(float(geom["tf"]), float(geom["tw"]), float(geom["t"]), 10.0)
    mat_props = _resolve_steel_material(mat, cfg, thick)

    f_cls, w_cls, qs, qa = classify_section_cythyedy(geom, mat_props["fy"], mat_props["E"])
    pt_cap, pc_cap = compute_axial_capacity_cythyedy(
        geom, mat_props, spec, length_mm, qs, qa, cfg.design_method
    )
    mcx, mcy = compute_flexural_capacity_cythyedy(
        geom, mat_props, spec, length_mm, f_cls, cfg.design_method
    )
    vcx, vcy = compute_shear_capacity_cythyedy(geom, mat_props, cfg.design_method)

    station_checks: list[SteelStationCheck] = []
    gov_combo = "-"
    gov_ratio = 0.0
    gov_x = 0.0
    max_inter = 0.0
    max_shear = 0.0

    for cname, cmap in combo_forces.items():
        ff = cmap.get(fid)
        if ff is None or not ff.stations:
            continue
        for st in ff.stations:
            n_val = float(convert_value(Dimension.FORCE, float(st.N), unit_system, UnitSystem.N_MM))
            v2_val = float(convert_value(Dimension.FORCE, float(st.V2), unit_system, UnitSystem.N_MM))
            v3_val = float(convert_value(Dimension.FORCE, float(st.V3), unit_system, UnitSystem.N_MM))
            t_val = float(convert_value(Dimension.MOMENT, float(st.T), unit_system, UnitSystem.N_MM))
            m2_val = float(convert_value(Dimension.MOMENT, float(st.M2), unit_system, UnitSystem.N_MM))
            m3_val = float(convert_value(Dimension.MOMENT, float(st.M3), unit_system, UnitSystem.N_MM))
            x_mm = float(convert_value(Dimension.LENGTH, float(st.x), unit_system, UnitSystem.N_MM))

            p_cap = pt_cap if n_val >= 0.0 else pc_cap
            pr_pc = (abs(n_val) / p_cap) if p_cap > 0.0 else 0.0
            mrx_mcx = (abs(m3_val) / mcx) if mcx > 0.0 else 0.0
            mry_mcy = (abs(m2_val) / mcy) if mcy > 0.0 else 0.0

            if pr_pc >= 0.2:
                inter = pr_pc + (8.0 / 9.0) * (mrx_mcx + mry_mcy)
                eq_name = "ÇYTHYEDY 11.1a"
            else:
                inter = 0.5 * pr_pc + (mrx_mcx + mry_mcy)
                eq_name = "ÇYTHYEDY 11.1b"

            dcr_vx = (abs(v2_val) / vcx) if vcx > 0.0 else 0.0
            dcr_vy = (abs(v3_val) / vcy) if vcy > 0.0 else 0.0
            st_max_shear = max(dcr_vx, dcr_vy)
            st_ok = inter <= 1.0 and st_max_shear <= 1.0

            if inter >= max_inter:
                max_inter = inter
                gov_combo = cname
                gov_ratio = float(st.ratio)
                gov_x = x_mm
            if st_max_shear > max_shear:
                max_shear = st_max_shear

            station_checks.append(
                SteelStationCheck(
                    combo_name=cname,
                    ratio=float(st.ratio),
                    x=x_mm,
                    N=n_val,
                    V2=v2_val,
                    V3=v3_val,
                    T=t_val,
                    M2=m2_val,
                    M3=m3_val,
                    Pc=p_cap,
                    Mcx=mcx,
                    Mcy=mcy,
                    Vcx=vcx,
                    Vcy=vcy,
                    dcr_axial=pr_pc,
                    dcr_bend_x=mrx_mcx,
                    dcr_bend_y=mry_mcy,
                    dcr_shear_x=dcr_vx,
                    dcr_shear_y=dcr_vy,
                    dcr_interaction=inter,
                    equation=eq_name,
                    ok=st_ok,
                )
            )

    defl_ratio = spec.deflection_limit_ratio if spec.deflection_limit_ratio > 0.0 else cfg.deflection_limit_ratio
    defl_lim_mm = (length_mm / defl_ratio) if defl_ratio > 0.0 else 0.0
    defl_mm = _compute_max_deflection_mm(project, frame, length_mm, unit_system)
    dcr_defl = (defl_mm / defl_lim_mm) if defl_lim_mm > 0.0 else 0.0

    is_ok = max_inter <= 1.0 and max_shear <= 1.0 and dcr_defl <= 1.0

    return SteelMemberResult(
        frame_id=fid,
        label=label,
        section_name=str(getattr(sec, "name", "")),
        material_name=mat_props["name"],
        length=length_mm,
        design_method=cfg.design_method,
        flange_class=f_cls,
        web_class=w_cls,
        governing_combo=gov_combo,
        governing_ratio=gov_ratio,
        governing_x=gov_x,
        max_dcr_interaction=max_inter,
        max_dcr_shear=max_shear,
        max_dcr_deflection=dcr_defl,
        deflection_mm=defl_mm,
        deflection_limit_mm=defl_lim_mm,
        ok=is_ok,
        stations=station_checks,
    )


def run_steel_design(
    project: Any,
    frame_forces: dict[str, dict[int, FrameForceResult]],
    frame_ids: list[int] | None = None,
) -> dict[int, SteelMemberResult]:
    math_model = getattr(project, "math_model", None)
    if math_model is None or not frame_forces:
        return {}

    cfg: SteelConfig = getattr(getattr(project, "config", None), "steel", None) or SteelConfig()
    combo_forces = build_combination_frame_forces(project, frame_forces, cfg)
    target_ids = set(frame_ids) if frame_ids is not None else set(math_model.frames.keys())

    results: dict[int, SteelMemberResult] = {}
    for fid in sorted(target_ids):
        frame = math_model.frames.get(fid)
        if frame is None:
            continue
        spec = project.get_or_create_steel_spec(fid)
        res = evaluate_steel_member(project, frame, combo_forces, spec, cfg)
        if res is not None:
            results[fid] = res

    project.steel_design_results = results
    project.steel_design_hash = compute_model_geometry_hash(project)
    project.steel_design_warning = None
    return results


def save_steel_design_results(
    filepath: str | Path,
    results: dict[int, SteelMemberResult],
    geometry_hash: str,
    design_method: str = "LRFD",
) -> Path:
    path = Path(filepath)
    if path.suffix != ".cd4des":
        path = path.with_suffix(".cd4des")

    payload_members: dict[str, Any] = {}
    for fid, mres in results.items():
        d = asdict(mres)
        payload_members[str(fid)] = d

    manifest = {
        "schema_version": 1,
        "design_code": "ÇYTHYEDY-2018",
        "design_method": design_method,
        "geometry_hash": geometry_hash,
        "member_count": len(results),
    }

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("steel_results.json", json.dumps(payload_members))

    return path


def load_steel_design_results(filepath: str | Path) -> tuple[dict[int, SteelMemberResult], dict[str, Any]]:
    path = Path(filepath)
    with zipfile.ZipFile(path, "r") as zf:
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        raw_members = json.loads(zf.read("steel_results.json").decode("utf-8"))

    results: dict[int, SteelMemberResult] = {}
    for fid_str, mdict in raw_members.items():
        stations = [SteelStationCheck(**st) for st in mdict.pop("stations", [])]
        mres = SteelMemberResult(**mdict, stations=stations)
        results[int(fid_str)] = mres

    return results, manifest


def build_steel_frame_check_frames(project: Any) -> tuple[list[ReportDataFrame], list[str]]:
    notes: list[str] = []
    math_model = getattr(project, "math_model", None)
    if math_model is None:
        return [], ["MathModel bulunamadı."]

    cfg: SteelConfig = getattr(getattr(project, "config", None), "steel", None) or SteelConfig()
    unit_system: UnitSystem = getattr(project, "unit_system", UnitSystem.N_MM)

    steel_frames: list[tuple[int, Any, Any, Any]] = []
    for fid, frame in math_model.frames.items():
        sec = getattr(frame, "section", None)
        if isinstance(sec, str):
            sec = (getattr(project, "sections", None) or {}).get(sec)
        mat = getattr(sec, "material", None) if sec is not None else None
        if mat is not None and MatType.from_sap(getattr(mat, "mat_type", None)) == MatType.STEEL:
            steel_frames.append((fid, frame, sec, mat))

    if not steel_frames:
        return [], ["Modelde çelik çerçeve elemanı bulunmuyor."]

    param_rows: list[dict[str, Any]] = []
    for fid, frame, sec, mat in steel_frames:
        label = str(getattr(frame, "label", "") or f"F#{fid}")
        length_mm = float(convert_value(Dimension.LENGTH, float(frame.get_length()), unit_system, UnitSystem.N_MM))
        geom = _resolve_steel_section(sec, unit_system)
        thick = max(float(geom["tf"]), float(geom["tw"]), float(geom["t"]), 10.0)
        mat_props = _resolve_steel_material(mat, cfg, thick)
        f_cls, w_cls, _, _ = classify_section_cythyedy(geom, mat_props["fy"], mat_props["E"])
        spec = project.get_or_create_steel_spec(fid)

        param_rows.append({
            "Frame": label,
            "Length": length_mm,
            "Section": getattr(sec, "name", ""),
            "Material": mat_props["name"],
            "fy": mat_props["fy"],
            "Area": geom["Area"],
            "Z33": geom["Z33"],
            "Z22": geom["Z22"],
            "Kx": spec.kx,
            "Ky": spec.ky,
            "Lb": spec.lbx,
            "FlangeClass": f_cls,
            "WebClass": w_cls,
        })

    param_df = ReportDataFrame(
        param_rows,
        columns=[
            "Frame", "Length", "Section", "Material", "fy", "Area",
            "Z33", "Z22", "Kx", "Ky", "Lb", "FlangeClass", "WebClass",
        ],
        custom_title="Çelik Çubuk Özellikleri ve Enkesit Sınıfları",
        custom_desc="ÇYTHYEDY Bölüm 5 — Başlık ve gövde yerel burkulma sınıflandırması.",
        column_units={
            "Length": "mm",
            "fy": "MPa",
            "Area": "mm²",
            "Z33": "mm³",
            "Z22": "mm³",
            "Kx": "-",
            "Ky": "-",
            "Lb": "mm",
        },
        column_formats={
            "Length": ".1f",
            "fy": ".1f",
            "Area": ".1f",
            "Z33": ".0f",
            "Z22": ".0f",
            "Kx": ".2f",
            "Ky": ".2f",
            "Lb": ".0f",
        },
    )

    stored_results: dict[int, SteelMemberResult] = getattr(project, "steel_design_results", None) or {}
    if not stored_results:
        frame_forces = getattr(project, "frame_forces", None) or {}
        if frame_forces:
            stored_results = run_steel_design(project, frame_forces)
        else:
            warn = getattr(project, "steel_design_warning", None)
            notes.append(warn or "Çelik tahkik sonuçları henüz hesaplanmadı.")
            return [param_df], notes

    current_hash = compute_model_geometry_hash(project)
    saved_hash = getattr(project, "steel_design_hash", None)
    if saved_hash and saved_hash != current_hash:
        notes.append("Model geometrisi veya yük kombinasyonları tahkik sonrası değişmiş; tahkiki yeniden çalıştırın.")

    summary_rows: list[dict[str, Any]] = []
    for fid, frame, _, _ in steel_frames:
        mres = stored_results.get(fid)
        if mres is None:
            continue
        summary_rows.append({
            "Frame": mres.label,
            "Section": mres.section_name,
            "Method": mres.design_method,
            "GovCombo": mres.governing_combo,
            "GovSta": mres.governing_x,
            "DCR_PM": mres.max_dcr_interaction,
            "DCR_V": mres.max_dcr_shear,
            "Defl": mres.deflection_mm,
            "DeflLim": mres.deflection_limit_mm,
            "DCR_Defl": mres.max_dcr_deflection,
            "OK": "✔️" if mres.ok else "❌",
        })

    if not summary_rows:
        notes.append("Çelik elemanlar için tahkik kaydı bulunamadı.")
        return [param_df], notes

    summary_df = ReportDataFrame(
        summary_rows,
        columns=[
            "Frame", "Section", "Method", "GovCombo", "GovSta",
            "DCR_PM", "DCR_V", "Defl", "DeflLim", "DCR_Defl", "OK",
        ],
        custom_title=f"Çelik Çerçeve Tasarım ve Tahkik Özeti ({cfg.design_method})",
        custom_desc="ÇYTHYEDY Bölüm 7, 8, 9, 10, 11 ve 13 kritik zarf oranları.",
        column_units={
            "GovSta": "mm",
            "DCR_PM": "-",
            "DCR_V": "-",
            "Defl": "mm",
            "DeflLim": "mm",
            "DCR_Defl": "-",
        },
        column_formats={
            "GovSta": ".0f",
            "DCR_PM": ".3f",
            "DCR_V": ".3f",
            "Defl": ".2f",
            "DeflLim": ".2f",
            "DCR_Defl": ".3f",
        },
    )

    fail_count = sum(1 for r in summary_rows if r["OK"] == "❌")
    if fail_count:
        notes.append(f"{fail_count} çelik elemanda yönetmelik sınır değeri aşıldı.")

    return [param_df, summary_df], notes