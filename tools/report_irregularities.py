# tools/report_irregularities.py
from __future__ import annotations

import math
from typing import Any

import numpy as np

from app.analysis.seismic_combos import ensure_seismic_cases_and_combos
from app.analysis.structuralanalysis import _evaluate_combinations
from core.report.report_dataframe import ReportDataFrame
from core.report.report_tree import ReportSection, SectionStatus


def _collect_stories(mesh: Any) -> list[tuple[float, list[str], float]]:
    groups: dict[float, list[str]] = {}
    internal_keys = getattr(mesh, "internal_node_keys", set()) or set()
    for n_key, node in getattr(mesh, "nodes", {}).items():
        if n_key in internal_keys:
            continue
        z = round(float(node.z), 0)
        groups.setdefault(z, []).append(n_key)
    levels = sorted(groups.keys())
    stories: list[tuple[float, list[str], float]] = []
    for i, z in enumerate(levels):
        h = z - levels[i - 1] if i > 0 else 0.0
        stories.append((z, groups[z], h))
    return stories[1:]


def _ensure_drift_results(project: Any) -> list[str]:
    res = project.analysis_results
    cfg = project.config.seismic
    if not all(c in res.static_results for c in cfg.drift_combo_names):
        ensure_seismic_cases_and_combos(project, include_design_combos=False)
        _evaluate_combinations(project, res.static_results)
    return [c for c in cfg.drift_combo_names if c in res.static_results]


def _frame_effective_shear_area(frame: Any) -> tuple[float, float, float]:
    ni = getattr(frame, "node_i", None)
    nj = getattr(frame, "node_j", None)
    if ni is None or nj is None:
        return 0.0, 0.0, 0.0
    dx = abs(float(nj.x) - float(ni.x))
    dy = abs(float(nj.y) - float(ni.y))
    dz = abs(float(nj.z) - float(ni.z))
    if dz <= 1e-6 or dz < max(dx, dy):
        return 0.0, 0.0, 0.0

    sec = getattr(frame, "section", None)
    if sec is None:
        return 0.0, 0.0, 0.0

    cat = getattr(sec, "catalog_props", None) or {}
    prm = getattr(sec, "profile_params", None) or {}
    params = {**cat, **prm}

    area = float(params.get("Area", 0.0) or 0.0)
    b = float(params.get("b", 0.0) or 0.0)
    h = float(params.get("h", 0.0) or 0.0)
    if area <= 0.0 and b > 0.0 and h > 0.0:
        area = b * h
    if area <= 0.0:
        return 0.0, 0.0, 0.0

    rot = math.radians(float(getattr(frame, "rotation_deg", 0.0) or 0.0))
    c = abs(math.cos(rot))
    s = abs(math.sin(rot))

    if b > 0.0 and h > 0.0 and max(b, h) / min(b, h) >= 6.0:
        major_x = h >= b
        if major_x:
            return 0.0, area * c, area * s
        return 0.0, area * s, area * c

    return area, 0.0, 0.0


def _area_wall_shear_area(area_elem: Any, story_height: float) -> tuple[float, float]:
    nodes = list(getattr(area_elem, "nodes", []) or [])
    if len(nodes) < 3:
        return 0.0, 0.0

    xs = [float(n.x) for n in nodes]
    ys = [float(n.y) for n in nodes]
    zs = [float(n.z) for n in nodes]
    dz = max(zs) - min(zs)
    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)
    plan_len = math.hypot(span_x, span_y)
    if dz <= 1e-6 or plan_len <= 1e-6 or dz < 0.25 * plan_len:
        return 0.0, 0.0

    th = float(getattr(area_elem, "thickness", 0.0) or 0.0)
    if th <= 1e-6:
        asec = getattr(area_elem, "area_section", None)
        th = float(getattr(asec, "thickness", 0.0) or 0.0) if asec is not None else 0.0
    if th <= 1e-6:
        return 0.0, 0.0

    aw = th * plan_len
    hn = max(story_height, 1.0)
    factor = 0.2 + (plan_len / hn) ** 2
    cos_a = span_x / plan_len
    sin_a = span_y / plan_len
    return aw * factor * cos_a, aw * factor * sin_a


def _collect_story_shear_areas(
    project: Any,
    stories: list[tuple[float, list[str], float]],
) -> list[dict[str, float]]:
    model = getattr(project, "math_model", None)
    if model is None:
        return []

    total_height = sum(h for _, _, h in stories)
    story_data: list[dict[str, float]] = []

    for idx, (z_top, _node_keys, h) in enumerate(stories):
        z_bot = z_top - h
        ac_sum = 0.0
        awx_sum = 0.0
        awy_sum = 0.0

        for frame in getattr(model, "frames", {}).values():
            ni = getattr(frame, "node_i", None)
            nj = getattr(frame, "node_j", None)
            if ni is None or nj is None:
                continue
            fz_min = min(float(ni.z), float(nj.z))
            fz_max = max(float(ni.z), float(nj.z))
            if fz_max < z_bot - 1.0 or fz_min > z_top + 1.0:
                continue
            if abs(fz_max - fz_min) <= 1.0:
                continue
            ac, wx, wy = _frame_effective_shear_area(frame)
            ac_sum += ac
            awx_sum += wx
            awy_sum += wy

        for area_elem in getattr(model, "areas", {}).values():
            nodes = list(getattr(area_elem, "nodes", []) or [])
            if len(nodes) < 3:
                continue
            zs = [float(n.z) for n in nodes]
            az_min = min(zs)
            az_max = max(zs)
            if az_max < z_bot - 1.0 or az_min > z_top + 1.0:
                continue
            if abs(az_max - az_min) <= 1.0:
                continue
            wx, wy = _area_wall_shear_area(area_elem, total_height)
            awx_sum += wx
            awy_sum += wy

        story_data.append({
            "story_idx": float(idx + 1),
            "z": z_top,
            "h": h,
            "Ac": ac_sum,
            "Awx": awx_sum,
            "Awy": awy_sum,
            "Aex": ac_sum + awx_sum,
            "Aey": ac_sum + awy_sum,
        })

    return story_data


def _collect_cumulative_story_weights_n(
    project: Any,
    mesh: Any,
    stories: list[tuple[float, list[str], float]],
) -> dict[float, float]:
    res = getattr(project, "analysis_results", None)
    mass_asm = getattr(res, "mass", None) if res is not None else None
    node_masses = getattr(mass_asm, "node_masses", None) or {}
    g_acc = 9.80665

    story_weights: dict[float, float] = {z: 0.0 for z, _, _ in stories}
    if not stories:
        return story_weights

    sorted_levels = [z for z, _, _ in stories]
    for n_key, m_kg in node_masses.items():
        node = mesh.nodes.get(n_key)
        if node is None:
            continue
        nz = round(float(node.z), 0)
        target_z = min(sorted_levels, key=lambda lv: abs(lv - nz))
        if abs(target_z - nz) <= 1.0:
            story_weights[target_z] += float(m_kg) * g_acc

    cum_weights: dict[float, float] = {}
    running = 0.0
    for z in reversed(sorted_levels):
        running += story_weights.get(z, 0.0)
        cum_weights[z] = running
    return cum_weights


def _story_shear_forces_n(
    project: Any,
    mesh: Any,
    sres: Any,
    stories: list[tuple[float, list[str], float]],
) -> dict[float, tuple[float, float]]:
    res = getattr(project, "analysis_results", None)
    stiff_asm = getattr(res, "stiffness", None) if res is not None else None
    K_global = getattr(stiff_asm, "K_global", None) if stiff_asm is not None else None
    U = np.asarray(getattr(sres, "displacements", []), dtype=float)
    F_app = np.asarray(getattr(sres, "applied_forces", []), dtype=float)
    R_sup = np.asarray(getattr(sres, "reactions", []), dtype=float)

    f_net = F_app + R_sup
    if f_net.size == 0 and K_global is not None and U.size > 0:
        f_net = np.asarray(K_global @ U, dtype=float)

    nodal_fx: dict[str, float] = {}
    nodal_fy: dict[str, float] = {}
    for n_key, node in getattr(mesh, "nodes", {}).items():
        dofs = getattr(node, "dof_indices", None)
        if not dofs or len(dofs) < 2:
            continue
        ix, iy = int(dofs[0]), int(dofs[1])
        if 0 <= ix < f_net.size and 0 <= iy < f_net.size:
            nodal_fx[n_key] = float(f_net[ix])
            nodal_fy[n_key] = float(f_net[iy])

    shears: dict[float, tuple[float, float]] = {}
    for z_cut, _nkeys, _h in stories:
        vx = 0.0
        vy = 0.0
        for n_key, node in getattr(mesh, "nodes", {}).items():
            if float(node.z) >= z_cut - 1.0:
                vx += nodal_fx.get(n_key, 0.0)
                vy += nodal_fy.get(n_key, 0.0)
        shears[z_cut] = (abs(vx), abs(vy))
    return shears


class TorsionIrregularityBuilder:
    section_id = "irregularity_a1"
    title = "A1 — Burulma Düzensizliği"

    def is_applicable(self, project: Any, context: Any) -> bool:
        res = getattr(project, "analysis_results", None)
        if res is None or not getattr(res, "static_results", None):
            return False
        return getattr(getattr(project, "config", None), "seismic", None) is not None

    def build(self, project: Any, context: Any) -> ReportSection:
        res = project.analysis_results
        cfg = project.config.seismic
        available_combos = _ensure_drift_results(project)
        if not available_combos:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=[
                    f"Burulma kontrolü için yük durumları bulunamadı ({', '.join(cfg.drift_combo_names)})."
                ],
            )

        mesh = res.mesh
        if mesh is None:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=["SolverMesh yok"],
            )

        stories = _collect_stories(mesh)
        if not stories:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=["Kat bulunamadı"],
            )

        rows: list[dict[str, Any]] = []
        for cname in available_combos:
            sres = res.static_results[cname]
            direction = "X" if "X" in cname.upper() else "Y"
            axis = 0 if direction == "X" else 1
            prev_disp: dict[str, float] = {}

            for z, node_keys, _h in stories:
                drifts: list[float] = []
                curr_disp: dict[str, float] = {}
                for k in node_keys:
                    if k not in sres.node_displacements:
                        continue
                    u_val = float(sres.node_displacements[k][axis])
                    curr_disp[k] = u_val
                    drifts.append(abs(u_val))
                prev_disp = curr_disp
                if len(drifts) < 2:
                    continue

                d_max = max(drifts)
                d_avg = sum(drifts) / len(drifts)
                eta = d_max / d_avg if d_avg > 0.0 else 1.0
                dbi = (eta / 1.2) ** 2 if eta > 1.2 else 1.0
                ecc_eff = 0.05 * dbi if 1.2 < eta <= 2.0 else 0.05
                rows.append({
                    "Yük Durumu": cname,
                    "Yön": direction,
                    "Kat": int(round(z)),
                    "Δmax (mm)": d_max,
                    "Δort (mm)": d_avg,
                    "ηbi": eta,
                    "A1": "Var" if eta > 1.2 else "Yok",
                    "Dbi": dbi,
                    "Ek Dışm.": ecc_eff,
                })

        df = ReportDataFrame(
            rows,
            columns=[
                "Yük Durumu", "Yön", "Kat", "Δmax (mm)", "Δort (mm)",
                "ηbi", "A1", "Dbi", "Ek Dışm.",
            ],
            custom_title="A1 — Burulma Düzensizliği Tahkiki",
            custom_desc=(
                "TBDY 2018 Tablo 3.1 & 3.6.2.1 — ηbi = (Δi)max / (Δi)ort > 1.2 ise A1 burulma düzensizliği vardır. "
                "1.2 < ηbi ≤ 2.0 aralığında ±%5 ek dışmerkezlik Dbi = (ηbi / 1.2)² katsayısı ile büyütülür."
            ),
            column_units={
                "Δmax (mm)": "mm",
                "Δort (mm)": "mm",
                "ηbi": "-",
                "Dbi": "-",
                "Ek Dışm.": "-",
            },
            column_formats={
                "Δmax (mm)": ".4f",
                "Δort (mm)": ".4f",
                "ηbi": ".3f",
                "Dbi": ".3f",
                "Ek Dışm.": ".4f",
            },
        )

        a1_count = sum(1 for r in rows if r["A1"] == "Var")
        notes = [f"{a1_count} katta A1 burulma düzensizliği tespit edildi"] if a1_count else []

        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=SectionStatus.READY,
            frames=[df],
            notes=notes,
        )


class WeakStoryIrregularityBuilder:
    section_id = "irregularity_b1"
    title = "B1 — Komşu Katlar Arası Dayanım Düzensizliği (Zayıf Kat)"

    def is_applicable(self, project: Any, context: Any) -> bool:
        return getattr(project, "math_model", None) is not None

    def build(self, project: Any, context: Any) -> ReportSection:
        res = getattr(project, "analysis_results", None)
        mesh = getattr(res, "mesh", None) if res is not None else None
        if mesh is None:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=["Analiz ağı (SolverMesh) bulunamadı"],
            )

        stories = _collect_stories(mesh)
        if len(stories) < 2:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=["Komşu kat kontrolü için en az 2 kat gereklidir"],
            )

        story_areas = _collect_story_shear_areas(project, stories)
        if not story_areas:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=["Kat kesit alanları hesaplanamadı"],
            )

        rows: list[dict[str, Any]] = []
        for i in range(len(story_areas) - 1):
            cur = story_areas[i]
            nxt = story_areas[i + 1]
            eta_x = cur["Aex"] / nxt["Aex"] if nxt["Aex"] > 0.0 else 1.0
            eta_y = cur["Aey"] / nxt["Aey"] if nxt["Aey"] > 0.0 else 1.0
            has_b1 = eta_x < 0.80 or eta_y < 0.80
            rows.append({
                "Kat": int(round(cur["z"])),
                "Üst Kat": int(round(nxt["z"])),
                "ΣAc (mm²)": cur["Ac"],
                "ΣAwx (mm²)": cur["Awx"],
                "Aex (mm²)": cur["Aex"],
                "ΣAwy (mm²)": cur["Awy"],
                "Aey (mm²)": cur["Aey"],
                "ηcix": eta_x,
                "ηciy": eta_y,
                "B1 (<0.80)": "Var" if has_b1 else "Yok",
            })

        df = ReportDataFrame(
            rows,
            columns=[
                "Kat", "Üst Kat", "ΣAc (mm²)", "ΣAwx (mm²)", "Aex (mm²)",
                "ΣAwy (mm²)", "Aey (mm²)", "ηcix", "ηciy", "B1 (<0.80)",
            ],
            custom_title="B1 — Komşu Katlar Arası Dayanım Düzensizliği (Zayıf Kat)",
            custom_desc=(
                "TBDY 2018 Tablo 3.1 & 3.6.2.3 — Herhangi bir deprem doğrultusunda ηci = (ΣAe)i / (ΣAe)i+1 < 0.80 "
                "ise B1 düzensizliği vardır (0.60 ≤ ηci < 0.80 aralığında R katsayısı 1.25·ηci ile çarpılır)."
            ),
            column_units={
                "ΣAc (mm²)": "mm²",
                "ΣAwx (mm²)": "mm²",
                "Aex (mm²)": "mm²",
                "ΣAwy (mm²)": "mm²",
                "Aey (mm²)": "mm²",
                "ηcix": "-",
                "ηciy": "-",
            },
            column_formats={
                "ΣAc (mm²)": ".0f",
                "ΣAwx (mm²)": ".0f",
                "Aex (mm²)": ".0f",
                "ΣAwy (mm²)": ".0f",
                "Aey (mm²)": ".0f",
                "ηcix": ".3f",
                "ηciy": ".3f",
            },
        )

        b1_count = sum(1 for r in rows if r["B1 (<0.80)"] == "Var")
        notes = [f"{b1_count} katta B1 zayıf kat düzensizliği tespit edildi"] if b1_count else []

        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=SectionStatus.READY,
            frames=[df],
            notes=notes,
        )


class SoftStoryIrregularityBuilder:
    section_id = "irregularity_b2"
    title = "B2 — Komşu Katlar Arası Rijitlik Düzensizliği (Yumuşak Kat)"

    def is_applicable(self, project: Any, context: Any) -> bool:
        res = getattr(project, "analysis_results", None)
        if res is None or not getattr(res, "static_results", None):
            return False
        return getattr(getattr(project, "config", None), "seismic", None) is not None

    def build(self, project: Any, context: Any) -> ReportSection:
        res = project.analysis_results
        cfg = project.config.seismic
        available_combos = _ensure_drift_results(project)
        if not available_combos:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=[
                    f"Yumuşak kat kontrolü için yük durumları bulunamadı ({', '.join(cfg.drift_combo_names)})."
                ],
            )

        mesh = res.mesh
        if mesh is None:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=["SolverMesh yok"],
            )

        stories = _collect_stories(mesh)
        if len(stories) < 2:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=["Komşu kat kontrolü için en az 2 kat gereklidir"],
            )

        rows: list[dict[str, Any]] = []
        for cname in available_combos:
            sres = res.static_results[cname]
            direction = "X" if "X" in cname.upper() else "Y"
            axis = 0 if direction == "X" else 1

            story_ratios: list[tuple[float, float, float, float]] = []
            prev_u: dict[str, float] = {}
            for z, node_keys, h in stories:
                curr_u: dict[str, float] = {}
                story_drifts: list[float] = []
                for k in node_keys:
                    if k not in sres.node_displacements:
                        continue
                    u_val = float(sres.node_displacements[k][axis])
                    curr_u[k] = u_val
                    story_drifts.append(abs(u_val))
                prev_u = curr_u
                if not story_drifts or h <= 0.0:
                    continue
                d_avg = sum(story_drifts) / len(story_drifts)
                story_ratios.append((z, h, d_avg, d_avg / h))

            for idx, (z, h, d_avg, ratio_cur) in enumerate(story_ratios):
                eta_up = (
                    ratio_cur / story_ratios[idx + 1][3]
                    if idx + 1 < len(story_ratios) and story_ratios[idx + 1][3] > 0.0
                    else 0.0
                )
                eta_down = (
                    ratio_cur / story_ratios[idx - 1][3]
                    if idx - 1 >= 0 and story_ratios[idx - 1][3] > 0.0
                    else 0.0
                )
                eta_max = max(eta_up, eta_down)
                rows.append({
                    "Yük Durumu": cname,
                    "Yön": direction,
                    "Kat": int(round(z)),
                    "h (mm)": h,
                    "(Δi)ort (mm)": d_avg,
                    "(Δi/hi)ort": ratio_cur,
                    "ηki (Üst)": eta_up,
                    "ηki (Alt)": eta_down,
                    "B2 (>2.0)": "Var" if eta_max > 2.0 else "Yok",
                })

        df = ReportDataFrame(
            rows,
            columns=[
                "Yük Durumu", "Yön", "Kat", "h (mm)", "(Δi)ort (mm)",
                "(Δi/hi)ort", "ηki (Üst)", "ηki (Alt)", "B2 (>2.0)",
            ],
            custom_title="B2 — Komşu Katlar Arası Rijitlik Düzensizliği (Yumuşak Kat)",
            custom_desc=(
                "TBDY 2018 Tablo 3.1 Denk.(3.3) — ηki = (Δi/hi)ort / (Δi+1/hi+1)ort > 2.0 "
                "veya ηki = (Δi/hi)ort / (Δi-1/hi-1)ort > 2.0 ise B2 yumuşak kat düzensizliği vardır."
            ),
            column_units={
                "h (mm)": "mm",
                "(Δi)ort (mm)": "mm",
                "(Δi/hi)ort": "-",
                "ηki (Üst)": "-",
                "ηki (Alt)": "-",
            },
            column_formats={
                "h (mm)": ".1f",
                "(Δi)ort (mm)": ".4f",
                "(Δi/hi)ort": ".6f",
                "ηki (Üst)": ".3f",
                "ηki (Alt)": ".3f",
            },
        )

        b2_count = sum(1 for r in rows if r["B2 (>2.0)"] == "Var")
        notes = [f"{b2_count} katta B2 yumuşak kat düzensizliği tespit edildi"] if b2_count else []

        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=SectionStatus.READY,
            frames=[df],
            notes=notes,
        )


class SecondOrderEffectsBuilder:
    section_id = "irregularity_second_order"
    title = "İkinci Mertebe Etkileri (θII)"

    def is_applicable(self, project: Any, context: Any) -> bool:
        res = getattr(project, "analysis_results", None)
        if res is None or not getattr(res, "static_results", None):
            return False
        return getattr(getattr(project, "config", None), "seismic", None) is not None

    def build(self, project: Any, context: Any) -> ReportSection:
        res = project.analysis_results
        cfg = project.config.seismic
        available_combos = _ensure_drift_results(project)
        if not available_combos:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=[
                    f"İkinci mertebe kontrolü için yük durumları bulunamadı ({', '.join(cfg.drift_combo_names)})."
                ],
            )

        mesh = res.mesh
        if mesh is None:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=["SolverMesh yok"],
            )

        stories = _collect_stories(mesh)
        if not stories:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=["Kat bulunamadı"],
            )

        cum_weights = _collect_cumulative_story_weights_n(project, mesh, stories)
        d_coeff = float(getattr(cfg, "D", 2.5))
        r_coeff = float(getattr(cfg, "R", 8.0))
        ch_coeff = float(getattr(cfg, "Ch", 0.5))
        theta_limit = 0.12 * d_coeff / (ch_coeff * r_coeff) if ch_coeff * r_coeff > 0.0 else 0.0

        rows: list[dict[str, Any]] = []
        for cname in available_combos:
            sres = res.static_results[cname]
            direction = "X" if "X" in cname.upper() else "Y"
            axis = 0 if direction == "X" else 1
            story_shears = _story_shear_forces_n(project, mesh, sres, stories)

            for z, node_keys, h in stories:
                drifts = [
                    abs(float(sres.node_displacements[k][axis]))
                    for k in node_keys
                    if k in sres.node_displacements
                ]
                if not drifts or h <= 0.0:
                    continue
                d_avg = sum(drifts) / len(drifts)
                w_cum = cum_weights.get(z, 0.0)
                vx, vy = story_shears.get(z, (0.0, 0.0))
                v_story = vx if axis == 0 else vy
                theta_ii = (d_avg * w_cum) / (v_story * h) if v_story > 0.0 else 0.0
                rows.append({
                    "Yük Durumu": cname,
                    "Yön": direction,
                    "Kat": int(round(z)),
                    "h (mm)": h,
                    "(Δi)ort (mm)": d_avg,
                    "ΣWk (kN)": w_cum / 1000.0,
                    "Vi (kN)": v_story / 1000.0,
                    "θII,i": theta_ii,
                    "Limit": theta_limit,
                    "Durum": "✓" if theta_ii <= theta_limit else "✗",
                })

        df = ReportDataFrame(
            rows,
            columns=[
                "Yük Durumu", "Yön", "Kat", "h (mm)", "(Δi)ort (mm)",
                "ΣWk (kN)", "Vi (kN)", "θII,i", "Limit", "Durum",
            ],
            custom_title="İkinci Mertebe Etkileri Tahkiki (θII)",
            custom_desc=(
                f"TBDY 2018 4.9.2 Denk.(4.35)-(4.36) — θII,i = (Δi)ort · ΣWk / (Vi · hi) ≤ 0.12·D/(Ch·R) = {theta_limit:.4f} "
                f"(D={d_coeff:g}, Ch={ch_coeff:g}, R={r_coeff:g})."
            ),
            column_units={
                "h (mm)": "mm",
                "(Δi)ort (mm)": "mm",
                "ΣWk (kN)": "kN",
                "Vi (kN)": "kN",
                "θII,i": "-",
                "Limit": "-",
            },
            column_formats={
                "h (mm)": ".1f",
                "(Δi)ort (mm)": ".4f",
                "ΣWk (kN)": ".2f",
                "Vi (kN)": ".2f",
                "θII,i": ".5f",
                "Limit": ".5f",
            },
        )

        exceed_count = sum(1 for r in rows if r["Durum"] == "✗")
        notes = [f"{exceed_count} katta ikinci mertebe sınırı (θII) aşıldı"] if exceed_count else []

        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=SectionStatus.READY,
            frames=[df],
            notes=notes,
        )


class IrregularitiesSectionBuilder:
    section_id = "irregularities"
    title = "Deprem Düzensizlik Kontrolleri"

    def __init__(self) -> None:
        self._child_builders = (
            TorsionIrregularityBuilder(),
            WeakStoryIrregularityBuilder(),
            SoftStoryIrregularityBuilder(),
            SecondOrderEffectsBuilder(),
        )

    def is_applicable(self, project: Any, context: Any) -> bool:
        return any(b.is_applicable(project, context) for b in self._child_builders)

    def build(self, project: Any, context: Any) -> ReportSection:
        children: list[ReportSection] = []
        notes: list[str] = []
        for builder in self._child_builders:
            if not builder.is_applicable(project, context):
                continue
            child = builder.build(project, context)
            children.append(child)
            notes.extend(child.notes)

        has_ready = any(c.status == SectionStatus.READY for c in children)
        status = SectionStatus.READY if has_ready else SectionStatus.MISSING_DATA
        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=status,
            notes=notes,
            children=children,
        )


__all__ = [
    "TorsionIrregularityBuilder",
    "WeakStoryIrregularityBuilder",
    "SoftStoryIrregularityBuilder",
    "SecondOrderEffectsBuilder",
    "IrregularitiesSectionBuilder",
]