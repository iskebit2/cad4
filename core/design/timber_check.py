# core/design/timber_check.py
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from core.report.report_dataframe import ReportDataFrame
from core.units import Dimension, UnitSystem, convert_value
from data.enums import MatType
from data.materials_catalog import get_catalog_params
from domain.definition import TimberConfig, TimberFloorSpec

G_ACCEL = 9.81


def _resolve_timber_strengths(material: Any, fallback_grade: str) -> dict[str, float]:
    grade = str(getattr(material, "grade", "") or "").strip()
    if not grade:
        mat_name = str(getattr(material, "name", "") or "").strip()
        grade = mat_name if mat_name else fallback_grade

    cat = get_catalog_params(grade, MatType.TIMBER)
    e005_mpa = float(cat["E_0_05"]) * 1000.0
    em_mpa = float(cat["Em_o_ort"]) * 1000.0
    if getattr(material, "E1", 0.0) > 0.0:
        em_mpa = float(material.E1)

    return {
        "grade": grade,
        "fm_k": float(cat["fm_k"]),
        "ft_0_k": float(cat["ft_0_k"]),
        "fc_0_k": float(cat["fc_0_k"]),
        "fv_k": float(cat["fv_k"]),
        "E_0_05": e005_mpa,
        "Em_o_ort": em_mpa,
        "density": float(getattr(material, "density", 0.0) or cat["density"]),
    }


def _extract_section_geometry(sec: Any, unit_system: UnitSystem) -> dict[str, float]:
    p = getattr(sec, "profile_params", None) or {}
    to_mm = lambda v: float(convert_value(Dimension.LENGTH, float(v), unit_system, UnitSystem.N_MM))
    to_mm2 = lambda v: float(convert_value(Dimension.AREA, float(v), unit_system, UnitSystem.N_MM))
    to_mm3 = lambda v: float(convert_value(Dimension.I3, float(v), unit_system, UnitSystem.N_MM))
    to_mm4 = lambda v: float(convert_value(Dimension.I4, float(v), unit_system, UnitSystem.N_MM))

    h = to_mm(p.get("h", 0.0))
    b = to_mm(p.get("b", 0.0))
    area = to_mm2(p.get("Area", b * h))
    as2 = to_mm2(p.get("AS2", (5.0 / 6.0) * area if area > 0.0 else 0.0))
    as3 = to_mm2(p.get("AS3", (5.0 / 6.0) * area if area > 0.0 else 0.0))
    i22 = to_mm4(p.get("I22", (h * b ** 3) / 12.0 if h > 0.0 and b > 0.0 else 0.0))
    i33 = to_mm4(p.get("I33", (b * h ** 3) / 12.0 if h > 0.0 and b > 0.0 else 0.0))

    raw_j = float(p.get("J", 0.0))
    if raw_j <= 0.0 and h > 0.0 and b > 0.0:
        a_dim = max(b, h)
        b_dim = min(b, h)
        ratio = b_dim / a_dim
        torsion = a_dim * (b_dim ** 3) * (1.0 / 3.0 - 0.21 * ratio * (1.0 - (ratio ** 4) / 12.0))
    else:
        torsion = to_mm4(raw_j)

    s22_raw = p.get("S22Left", p.get("S22", 0.0))
    s33_raw = p.get("S33Top", p.get("S33", 0.0))
    s22 = to_mm3(s22_raw) if float(s22_raw or 0.0) > 0.0 else ((2.0 * i22 / b) if b > 0.0 else 0.0)
    s33 = to_mm3(s33_raw) if float(s33_raw or 0.0) > 0.0 else ((2.0 * i33 / h) if h > 0.0 else 0.0)

    r22_raw = p.get("R22", 0.0)
    r33_raw = p.get("R33", 0.0)
    r22 = to_mm(r22_raw) if float(r22_raw or 0.0) > 0.0 else (math.sqrt(i22 / area) if area > 0.0 else 0.0)
    r33 = to_mm(r33_raw) if float(r33_raw or 0.0) > 0.0 else (math.sqrt(i33 / area) if area > 0.0 else 0.0)

    return {
        "h": h,
        "b": b,
        "Area": area,
        "As2": as2,
        "As3": as3,
        "Torsion": torsion,
        "I22": i22,
        "I33": i33,
        "S22": s22,
        "S33": s33,
        "R22": r22,
        "R33": r33,
    }


def check_timber_station(
    *,
    P_n: float,
    V2_n: float,
    V3_n: float,
    T_nmm: float,
    M2_nmm: float,
    M3_nmm: float,
    length_mm: float,
    geom: dict[str, float],
    strengths: dict[str, float],
    cfg: TimberConfig,
) -> dict[str, Any]:
    area = geom["Area"]
    as2 = geom["As2"]
    as3 = geom["As3"]
    s22 = geom["S22"]
    s33 = geom["S33"]
    torsion = geom["Torsion"]
    i_min = min(geom["R22"], geom["R33"])

    ft0k = strengths["ft_0_k"]
    fc0k = strengths["fc_0_k"]
    fm_k = strengths["fm_k"]
    fv_k = strengths["fv_k"]
    e005 = strengths["E_0_05"]

    sigma_axial = abs(P_n) / area if area > 0.0 else 0.0

    ft0d = ft0k * cfg.CN * cfg.CY * cfg.CB / cfg.OMEGA
    ok_tension = sigma_axial <= ft0d if P_n >= 0.0 else True

    lam = length_mm / i_min if i_min > 0.0 else 0.0
    f_e = (math.pi ** 2 * e005) / (lam ** 2) if lam > 0.0 else 1e12
    ratio_e = f_e / (2.0 * cfg.c_buckling * fc0k)
    cp = 1.0 + ratio_e - math.sqrt(max(0.0, (1.0 + ratio_e) ** 2 - f_e / (cfg.c_buckling * fc0k)))
    fc0d = fc0k * cfg.CN * cfg.CY * cfg.CB / cfg.OMEGA
    ok_compression = sigma_axial <= cp * fc0d if P_n < 0.0 else True

    tau2 = abs(V2_n) / as2 if as2 > 0.0 else 0.0
    tau3 = abs(V3_n) / as3 if as3 > 0.0 else 0.0
    fv_d = fv_k * cfg.CN * cfg.CY / cfg.OMEGA
    ok_shear2 = tau2 <= fv_d
    ok_shear3 = tau3 <= fv_d

    sigma_b2 = abs(M2_nmm) / s22 if s22 > 0.0 else 0.0
    sigma_b3 = abs(M3_nmm) / s33 if s33 > 0.0 else 0.0
    fm_d = fm_k * cfg.CN * cfg.CY * cfg.CB / cfg.OMEGA
    ok_bend2 = (sigma_axial + sigma_b2) <= fm_d
    ok_bend3 = (sigma_axial + sigma_b3) <= fm_d

    tau_torsion = abs(T_nmm) / torsion if torsion > 0.0 else 0.0
    ok_torsion = tau_torsion <= fv_d

    all_ok = all((
        ok_tension,
        ok_compression,
        ok_shear2,
        ok_shear3,
        ok_bend2,
        ok_bend3,
        ok_torsion,
    ))

    return {
        "sigma_axial": sigma_axial,
        "ft0d": ft0d,
        "fc0d": fc0d,
        "CP": cp,
        "ok_tension": ok_tension,
        "ok_compression": ok_compression,
        "tau2": tau2,
        "tau3": tau3,
        "fv_d": fv_d,
        "ok_shear2": ok_shear2,
        "ok_shear3": ok_shear3,
        "sigma_b2": sigma_b2,
        "sigma_b3": sigma_b3,
        "fm_d": fm_d,
        "ok_bend2": ok_bend2,
        "ok_bend3": ok_bend3,
        "tau_torsion": tau_torsion,
        "ok_torsion": ok_torsion,
        "OK": "✔️" if all_ok else "❌",
    }


def _select_design_case(project: Any, cfg: TimberConfig) -> str | None:
    frame_forces = getattr(project, "frame_forces", None) or {}
    if not frame_forces:
        return None
    if cfg.design_case_name in frame_forces:
        return cfg.design_case_name
    for cname in frame_forces:
        if "ULS" in cname.upper():
            return cname
    return next(iter(frame_forces.keys()))


def build_timber_frame_check_frames(project: Any) -> tuple[list[ReportDataFrame], list[str]]:
    notes: list[str] = []
    math_model = getattr(project, "math_model", None)
    if math_model is None:
        return [], ["MathModel bulunamadı."]

    cfg: TimberConfig = getattr(getattr(project, "config", None), "timber", None) or TimberConfig()
    unit_system: UnitSystem = getattr(project, "unit_system", UnitSystem.N_MM)

    timber_frames: list[tuple[int, Any, Any, Any]] = []
    for fid, frame in getattr(math_model, "frames", {}).items():
        sec = getattr(frame, "section", None)
        if isinstance(sec, str):
            sec = getattr(project, "sections", {}).get(sec)
        mat = getattr(sec, "material", None) if sec is not None else None
        if mat is not None and MatType.from_sap(getattr(mat, "mat_type", None)) == MatType.TIMBER:
            timber_frames.append((fid, frame, sec, mat))

    if not timber_frames:
        return [], ["Modelde ahşap çerçeve elemanı bulunmuyor."]

    param_rows: list[dict[str, Any]] = []
    frame_meta: dict[int, tuple[str, float, dict[str, float], dict[str, float]]] = {}

    for fid, frame, sec, mat in timber_frames:
        label = str(getattr(frame, "label", "") or f"F#{fid}")
        raw_len = float(frame.get_length())
        length_mm = float(convert_value(Dimension.LENGTH, raw_len, unit_system, UnitSystem.N_MM))
        geom = _extract_section_geometry(sec, unit_system)
        strengths = _resolve_timber_strengths(mat, cfg.default_grade)
        frame_meta[fid] = (label, length_mm, geom, strengths)

        param_rows.append({
            "Frame": label,
            "Length": length_mm,
            "PropName": getattr(sec, "name", ""),
            "Material": strengths["grade"],
            "Prop": getattr(getattr(sec, "profile_type", None), "value", ""),
            "Area": geom["Area"],
            "S22": geom["S22"],
            "S33": geom["S33"],
            "R22": geom["R22"],
            "R33": geom["R33"],
        })

    param_df = ReportDataFrame(
        param_rows,
        columns=["Frame", "Length", "PropName", "Material", "Prop", "Area", "S22", "S33", "R22", "R33"],
        custom_title="Ahşap Çubuk Özellikleri",
        custom_desc="Modeldeki aktif ahşap çerçeve elemanlarının kesit ve burkulma parametreleri.",
        column_units={
            "Length": "mm",
            "Area": "mm²",
            "S22": "mm³",
            "S33": "mm³",
            "R22": "mm",
            "R33": "mm",
        },
        column_formats={
            "Length": ".1f",
            "Area": ".1f",
            "S22": ".0f",
            "S33": ".0f",
            "R22": ".2f",
            "R33": ".2f",
        },
    )

    case_name = _select_design_case(project, cfg)
    if case_name is None:
        notes.append("Çerçeve iç kuvvetleri (frame_forces) henüz hesaplanmadığı için tahkik tablosu üretilmedi.")
        return [param_df], notes

    case_forces = project.frame_forces.get(case_name, {})
    result_rows: list[dict[str, Any]] = []

    for fid, (label, length_mm, geom, strengths) in frame_meta.items():
        ff = case_forces.get(fid)
        if ff is None or not getattr(ff, "stations", None):
            continue

        for st in ff.stations:
            p_n = float(convert_value(Dimension.FORCE, float(st.N), unit_system, UnitSystem.N_MM))
            v2_n = float(convert_value(Dimension.FORCE, float(st.V2), unit_system, UnitSystem.N_MM))
            v3_n = float(convert_value(Dimension.FORCE, float(st.V3), unit_system, UnitSystem.N_MM))
            t_nmm = float(convert_value(Dimension.MOMENT, float(st.T), unit_system, UnitSystem.N_MM))
            m2_nmm = float(convert_value(Dimension.MOMENT, float(st.M2), unit_system, UnitSystem.N_MM))
            m3_nmm = float(convert_value(Dimension.MOMENT, float(st.M3), unit_system, UnitSystem.N_MM))
            x_mm = float(convert_value(Dimension.LENGTH, float(st.x), unit_system, UnitSystem.N_MM))

            chk = check_timber_station(
                P_n=p_n,
                V2_n=v2_n,
                V3_n=v3_n,
                T_nmm=t_nmm,
                M2_nmm=m2_nmm,
                M3_nmm=m3_nmm,
                length_mm=length_mm,
                geom=geom,
                strengths=strengths,
                cfg=cfg,
            )

            result_rows.append({
                "Frame": label,
                "LoadCase": case_name,
                "ObjSta": x_mm,
                "P": p_n * 1e-3,
                "V2": v2_n * 1e-3,
                "V3": v3_n * 1e-3,
                "T": t_nmm * 1e-6,
                "M2": m2_nmm * 1e-6,
                "M3": m3_nmm * 1e-6,
                "sigma_axial": chk["sigma_axial"],
                "ft0d": chk["ft0d"],
                "fc0d": chk["fc0d"],
                "CP": chk["CP"],
                "tau2": chk["tau2"],
                "tau3": chk["tau3"],
                "fv_d": chk["fv_d"],
                "sigma_b2": chk["sigma_b2"],
                "sigma_b3": chk["sigma_b3"],
                "fm_d": chk["fm_d"],
                "OK": chk["OK"],
            })

    if not result_rows:
        notes.append(f"'{case_name}' yük durumu için ahşap eleman istasyon kuvveti bulunamadı.")
        return [param_df], notes

    result_df = ReportDataFrame(
        result_rows,
        columns=[
            "Frame", "LoadCase", "ObjSta", "P", "V2", "V3", "T", "M2", "M3",
            "sigma_axial", "ft0d", "fc0d", "CP", "tau2", "tau3", "fv_d",
            "sigma_b2", "sigma_b3", "fm_d", "OK",
        ],
        custom_title=f"Ahşap Çerçeve Mukavemet Tahkiki ({case_name})",
        custom_desc=(
            f"Türk Ahşap Bina Yönetmeliği — CN={cfg.CN:.2f}, CY={cfg.CY:.2f}, "
            f"CB={cfg.CB:.2f}, Ω={cfg.OMEGA:.2f}"
        ),
        column_units={
            "ObjSta": "mm",
            "P": "kN",
            "V2": "kN",
            "V3": "kN",
            "T": "kN·m",
            "M2": "kN·m",
            "M3": "kN·m",
            "sigma_axial": "N/mm²",
            "ft0d": "N/mm²",
            "fc0d": "N/mm²",
            "CP": "-",
            "tau2": "N/mm²",
            "tau3": "N/mm²",
            "fv_d": "N/mm²",
            "sigma_b2": "N/mm²",
            "sigma_b3": "N/mm²",
            "fm_d": "N/mm²",
            "OK": "",
        },
        column_formats={
            "ObjSta": ".0f",
            "P": ".1f",
            "V2": ".1f",
            "V3": ".1f",
            "T": ".2f",
            "M2": ".2f",
            "M3": ".2f",
            "sigma_axial": ".2f",
            "ft0d": ".2f",
            "fc0d": ".2f",
            "CP": ".3f",
            "tau2": ".2f",
            "tau3": ".2f",
            "fv_d": ".2f",
            "sigma_b2": ".2f",
            "sigma_b3": ".2f",
            "fm_d": ".2f",
        },
    )

    fail_count = sum(1 for r in result_rows if r["OK"] == "❌")
    if fail_count:
        notes.append(f"{fail_count} istasyonda ahşap mukavemet sınırı aşıldı.")

    return [param_df, result_df], notes


@dataclass
class TimberFloorEvaluator:
    spec: TimberFloorSpec
    unit_system: UnitSystem = UnitSystem.N_MM
    state: dict[str, Any] = field(default_factory=dict)

    def _to_mm(self, val: float) -> float:
        return float(convert_value(Dimension.LENGTH, float(val), self.unit_system, UnitSystem.N_MM))

    def _to_knm2(self, val: float) -> float:
        return float(convert_value(Dimension.AREA_LOAD, float(val), self.unit_system, UnitSystem.KN_M))

    def evaluate(self) -> tuple[ReportDataFrame, ReportDataFrame]:
        wood = get_catalog_params(self.spec.wood_grade, MatType.TIMBER)
        osb = get_catalog_params(self.spec.osb_grade, MatType.COLDFORMED, thickness_mm=self._to_mm(self.spec.t_osb))

        h_k = self._to_mm(self.spec.h_k)
        b_k = self._to_mm(self.spec.b_k)
        t_osb = self._to_mm(self.spec.t_osb)
        b_s = self._to_mm(self.spec.b_s)
        span_mm = self._to_mm(self.spec.span)
        g_kaplama_knm2 = self._to_knm2(self.spec.dead_load_knm2)
        q_hareketli_knm2 = self._to_knm2(self.spec.live_load_knm2)

        h_k_m = h_k / 1000.0
        b_k_m = b_k / 1000.0
        t_osb_m = t_osb / 1000.0
        b_s_m = b_s / 1000.0
        l_m = span_mm / 1000.0

        rho_wood = float(wood["density"])
        rho_osb = float(osb["density"])
        ro_kiris_knm3 = rho_wood * G_ACCEL / 1000.0
        ro_osb_knm3 = rho_osb * G_ACCEL / 1000.0

        g_kiris = ro_kiris_knm3 * h_k_m * b_k_m
        g_osb = ro_osb_knm3 * t_osb_m * b_s_m
        g_kaplama = g_kaplama_knm2 * b_s_m
        g_toplam = g_kiris + g_osb + g_kaplama

        q_d = g_toplam * self.spec.ULS_g + (q_hareketli_knm2 * b_s_m) * self.spec.ULS_q
        q_k = g_toplam * self.spec.SLS_g + (q_hareketli_knm2 * b_s_m) * self.spec.SLS_q

        m_d = q_d * (l_m ** 2) / 8.0
        m_k = q_k * (l_m ** 2) / 8.0

        wx = b_k * (h_k ** 2) / 6.0
        fm_k = float(wood["fm_k"])
        fm_d = (fm_k * self.spec.CN * self.spec.CY * self.spec.CB) / self.spec.OMEGA
        sigma_m_d = (m_d * 1e6) / wx
        chk = "✔️" if sigma_m_d <= fm_d else "❌"

        rows_stress: list[dict[str, Any]] = [
            {"Tanım": "Ahşap Sınıfı", "Formül": "-", "Sembol": "-", "Değer": self.spec.wood_grade, "Birim": "-"},
            {"Tanım": "OSB Sınıfı", "Formül": "-", "Sembol": "-", "Değer": self.spec.osb_grade, "Birim": "-"},
            {"Tanım": "Kesit Yüksekliği", "Formül": "-", "Sembol": "h_k", "Değer": f"{h_k:.1f}", "Birim": "mm"},
            {"Tanım": "Kesit Genişliği", "Formül": "-", "Sembol": "b_k", "Değer": f"{b_k:.1f}", "Birim": "mm"},
            {"Tanım": "OSB Kalınlığı", "Formül": "-", "Sembol": "t_osb", "Değer": f"{t_osb:.1f}", "Birim": "mm"},
            {"Tanım": "Açıklık", "Formül": "-", "Sembol": "L", "Değer": f"{span_mm:.1f}", "Birim": "mm"},
            {"Tanım": "Aks Aralığı", "Formül": "-", "Sembol": "b_s", "Değer": f"{b_s:.1f}", "Birim": "mm"},
            {"Tanım": "Dizayn Yükü (ULS)", "Formül": "q_d = γ_g·G + γ_q·Q", "Sembol": "q_d", "Değer": f"{q_d:.3f}", "Birim": "kN/m"},
            {"Tanım": "Karakteristik Yük (SLS)", "Formül": "q_k = G + Q", "Sembol": "q_k", "Değer": f"{q_k:.3f}", "Birim": "kN/m"},
            {"Tanım": "Dizayn Momenti (ULS)", "Formül": "M_d = q_d·L²/8", "Sembol": "M_d", "Değer": f"{m_d:.3f}", "Birim": "kN·m"},
            {"Tanım": "Karakteristik Moment (SLS)", "Formül": "M_k = q_k·L²/8", "Sembol": "M_k", "Değer": f"{m_k:.3f}", "Birim": "kN·m"},
            {"Tanım": "Kesit Modülü", "Formül": "Wx = b·h²/6", "Sembol": "Wx", "Değer": f"{wx:.0f}", "Birim": "mm³"},
            {"Tanım": "Tasarım Eğilme Dayanımı", "Formül": "fm,d = (fm,k·CN·CY·CB)/Ω", "Sembol": "fm,d", "Değer": f"{fm_d:.2f}", "Birim": "N/mm²"},
            {"Tanım": "Tasarım Eğilme Gerilmesi", "Formül": "σ_m,d = M_d/Wx", "Sembol": "σ_m,d", "Değer": f"{sigma_m_d:.2f}", "Birim": "N/mm²"},
            {"Tanım": "Eğilme Dayanım Kontrolü", "Formül": "σ_m,d ≤ fm,d", "Sembol": "chk", "Değer": chk, "Birim": "-"},
        ]

        if self.spec.fire_enabled:
            dk_n = self.spec.beta_n_mm_per_min * self.spec.t_fire_min
            d_eff = dk_n + self.spec.k0 * self.spec.d0_mm
            if self.spec.exposure == "4-sides":
                b_eff = b_k - 2.0 * d_eff
                h_eff = h_k - 2.0 * d_eff
                p_m = 2.0 * ((b_k - 2.0 * dk_n) / 1000.0 + (h_k - 2.0 * dk_n) / 1000.0)
                at_m2 = ((b_k - 2.0 * dk_n) / 1000.0) * ((h_k - 2.0 * dk_n) / 1000.0)
            else:
                b_eff = b_k - 2.0 * d_eff
                h_eff = h_k - 1.0 * d_eff
                p_m = (b_k - 2.0 * dk_n) / 1000.0 + 2.0 * (h_k - dk_n) / 1000.0
                at_m2 = ((b_k - 2.0 * dk_n) / 1000.0) * ((h_k - dk_n) / 1000.0)

            wx_fire = max(1e-6, b_eff) * (max(1e-6, h_eff) ** 2) / 6.0
            cyn = 1.0 - (1.0 / 200.0) * (p_m / at_m2) if at_m2 > 0.0 else 0.0
            gamma_fi = self.spec.OMEGA if self.spec.gamma_M_fi is None else self.spec.gamma_M_fi
            fm_d_fire = (fm_k * cyn * self.spec.CY20) / gamma_fi
            sigma_m_d_fire = (m_d * 1e6) / wx_fire
            chk_fire = "✔️" if (b_eff > 0.0 and h_eff > 0.0 and sigma_m_d_fire <= fm_d_fire) else "❌"

            rows_stress.extend([
                {"Tanım": "Yangın Süresi", "Formül": "t", "Sembol": "t_fi", "Değer": f"{self.spec.t_fire_min:.0f}", "Birim": "dk"},
                {"Tanım": "Etkili Kömürleşme Derinliği", "Formül": "d_eff = β_n·t + k0·d0", "Sembol": "d_eff", "Değer": f"{d_eff:.2f}", "Birim": "mm"},
                {"Tanım": "Yangın Düzeltme Katsayısı", "Formül": "CY_N = 1 - (1/200)·(p/A_T)", "Sembol": "CY_N", "Değer": f"{cyn:.3f}", "Birim": "-"},
                {"Tanım": "Yangın Tasarım Dayanımı", "Formül": "fm,fi,d = fm,k·CY_N·CY20/γ_M,fi", "Sembol": "fm,fi,d", "Değer": f"{fm_d_fire:.2f}", "Birim": "N/mm²"},
                {"Tanım": "Yangın Eğilme Gerilmesi", "Formül": "σ_m,fi,d = M_d / Wx_eff", "Sembol": "σ_m,fi,d", "Değer": f"{sigma_m_d_fire:.2f}", "Birim": "N/mm²"},
                {"Tanım": "Yangın Dayanım Kontrolü", "Formül": "σ_m,fi,d ≤ fm,fi,d", "Sembol": "chk_fi", "Değer": chk_fire, "Birim": "-"},
            ])

        stress_df = ReportDataFrame(
            rows_stress,
            columns=["Tanım", "Formül", "Sembol", "Değer", "Birim"],
            custom_title=f"{self.spec.name} — Eğilme ve Yangın Tahkiki",
            custom_desc="Türk Ahşap Bina Yönetmeliği ve EN 1995-1-2 esaslarına göre.",
        )

        e_wood_pa = float(wood["Em_o_ort"]) * 1e9
        e_osb_pa = float(osb["Em_o_ort"]) * 1e6

        g_dead_kgm2 = (g_kaplama_knm2 * 1000.0) / G_ACCEL
        q_live_kgm2 = (q_hareketli_knm2 * 1000.0) / G_ACCEL

        m_kiris_1m = (rho_wood * b_k_m * h_k_m) / b_s_m
        m_osb_1m = rho_osb * t_osb_m
        m_toplam_1m = m_kiris_1m + m_osb_1m + g_dead_kgm2 + q_live_kgm2

        i_l = (b_k_m * (h_k_m ** 3)) / 12.0
        ei_kiris_1m = (e_wood_pa * i_l) / b_s_m
        i_osb_l = (t_osb_m ** 3) / 12.0
        ei_osb_1m = e_osb_pa * i_osb_l
        ei_toplam_1m = ei_kiris_1m + ei_osb_1m

        f1 = (math.pi / (2.0 * (l_m ** 2))) * math.sqrt(ei_toplam_1m / m_toplam_1m)
        if f1 > 0.0 and f1 < 40.0 and ei_osb_1m > 0.0:
            n40 = ((((40.0 / f1) ** 2 - 1.0) ** ((b_s_m / l_m) ** 4)) * (ei_kiris_1m / ei_osb_1m)) ** 0.25
        else:
            n40 = 0.0
        v_resp = (4.0 * (0.4 + 0.6 * n40)) / (m_toplam_1m * b_s_m * l_m + 200.0)
        v_limit = b_k_m ** (f1 * self.spec.damping_ratio - 1.0)
        vib_check = "✔️" if (f1 >= 8.0 and v_resp <= v_limit) else "❌"

        w_q_nm = q_hareketli_knm2 * 1000.0 * b_s_m
        ei_single_beam = e_wood_pa * i_l
        sehim_q_m = (5.0 * w_q_nm * (l_m ** 4)) / (384.0 * ei_single_beam)
        sehim_limit_m = l_m / 300.0
        sehim_check = "✔️" if sehim_q_m <= sehim_limit_m else "❌"

        vib_rows = [
            {"Tanım": "Doğal Frekans", "Sembol": "f1", "Formül": "π/(2L²)·√(EI/m)", "Değer": f"{f1:.2f}", "Birim": "Hz"},
            {"Tanım": "40 Hz Altı Mod Sayısı", "Sembol": "n40", "Formül": "(((40/f1)²-1)^((a/L)⁴)·(EI_k/EI_osb))^0.25", "Değer": f"{n40:.2f}", "Birim": "-"},
            {"Tanım": "Birim Darbe Hız Tepkisi", "Sembol": "v", "Formül": "4·(0.4+0.6·n40)/(m·a·L+200)", "Değer": f"{v_resp:.5f}", "Birim": "m/s"},
            {"Tanım": "Hız Tepki Limiti", "Sembol": "v_lim", "Formül": "b^(f1·ξ - 1)", "Değer": f"{v_limit:.5f}", "Birim": "m/s"},
            {"Tanım": "Titreşim Kontrolü", "Sembol": "-", "Formül": "f1 ≥ 8 Hz ve v ≤ v_lim", "Değer": vib_check, "Birim": "-"},
            {"Tanım": "Hareketli Yük Sehimi", "Sembol": "δ_q", "Formül": "5·w_q·L⁴/(384·EI)", "Değer": f"{sehim_q_m * 1000.0:.2f}", "Birim": "mm"},
            {"Tanım": "Sehim Limiti", "Sembol": "δ_lim", "Formül": "L/300", "Değer": f"{sehim_limit_m * 1000.0:.2f}", "Birim": "mm"},
            {"Tanım": "Sehim Kontrolü (q)", "Sembol": "-", "Formül": "δ_q ≤ L/300", "Değer": sehim_check, "Birim": "-"},
        ]

        vib_df = ReportDataFrame(
            vib_rows,
            columns=["Tanım", "Sembol", "Formül", "Değer", "Birim"],
            custom_title=f"{self.spec.name} — Titreşim ve Sehim Analizi",
            custom_desc="Eurocode 5 (EN 1995-1-1) döşeme titreşim ve sehim sınır kontrolleri.",
        )

        return stress_df, vib_df


def build_timber_floor_frames(project: Any) -> list[ReportDataFrame]:
    specs: list[TimberFloorSpec] = getattr(project, "timber_floors", None) or []
    unit_system: UnitSystem = getattr(project, "unit_system", UnitSystem.N_MM)
    frames: list[ReportDataFrame] = []
    for spec in specs:
        evaluator = TimberFloorEvaluator(spec=spec, unit_system=unit_system)
        stress_df, vib_df = evaluator.evaluate()
        frames.extend([stress_df, vib_df])
    return frames