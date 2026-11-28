# ui/panels/timber_design_panel.py
from __future__ import annotations

from pathlib import Path

import numpy as np
from imgui_bundle import imgui

from app.analysis.force_recovery import FrameForceResult, load_analysis_results
from app.settings.categories import Category
from core.design.steel_check import build_combination_frame_forces
from core.design.timber_check import (
    _extract_section_geometry,
    _resolve_timber_strengths,
    check_timber_station,
)
from core.units import Dimension, UnitSystem, convert_value
from data.enums import MatType
from domain.definition import SteelConfig, TimberConfig
from ui.base.panel_base import PanelBase


class TimberDesignPanel(PanelBase):
    panel_name = "timber_design"
    title = "Ahşap Tahkik Yöneticisi"
    category = Category.TOOLS
    menu_label = "Ahşap Tahkik"
    icon = "check"
    uses_draft = False
    show_apply_bar = False
    width = 1040
    height = 760
    pos_first_use = (190, 95)
    context = ("app",)

    def __init__(self, app=None, **overrides):
        self._selected_frame_id: int | None = None
        self._selected_combo_name: str = ""
        self._diagram_kind: int = 0
        self._status_msg: str = ""
        self._results: dict[int, dict] = {}
        super().__init__(app=app, **overrides)

    def _project(self):
        return getattr(self.app, "current_project", None) if self.app else None

    def _timber_frames(self, project) -> list[tuple[int, object, object, object]]:
        math_model = getattr(project, "math_model", None)
        if math_model is None:
            return []
        out: list[tuple[int, object, object, object]] = []
        for fid, frame in sorted(math_model.frames.items()):
            sec = getattr(frame, "section", None)
            if isinstance(sec, str):
                sec = (getattr(project, "sections", None) or {}).get(sec)
            mat = getattr(sec, "material", None) if sec is not None else None
            if mat is not None and MatType.from_sap(getattr(mat, "mat_type", None)) == MatType.TIMBER:
                out.append((fid, frame, sec, mat))
        return out

    def _resolve_frame_forces(self, project) -> dict[str, dict[int, FrameForceResult]]:
        ff = getattr(project, "frame_forces", None)
        if ff:
            return ff
        project_service = getattr(self.app, "project_service", None)
        proj_path = getattr(project_service, "file_path", None)
        res_ref = getattr(project, "analysis_results_path", None)
        candidate: Path | None = None
        if res_ref and proj_path:
            p = Path(res_ref)
            candidate = p if p.is_absolute() else (Path(proj_path).parent / p)
        elif proj_path:
            candidate = Path(proj_path).with_suffix(".cd4res")
        if candidate is not None and candidate.is_file():
            loaded = load_analysis_results(candidate)
            ff_loaded = loaded.get("frame_forces") or {}
            if ff_loaded:
                project.frame_forces = ff_loaded
                return ff_loaded
        return {}

    def _sync_viewport_selection(self, timber_ids: list[int]) -> None:
        eng = getattr(self.app, "engine", None)
        sel_mgr = getattr(eng, "sel_mgr", None) if eng else None
        if sel_mgr is None:
            return
        for el in sel_mgr.get_selected():
            uid = getattr(el, "unique_id", None)
            if uid in timber_ids:
                self._selected_frame_id = int(uid)
                return

    def _run_checks(self, project, timber_list: list[tuple[int, object, object, object]], target_ids: list[int] | None = None) -> None:
        raw_forces = self._resolve_frame_forces(project)
        if not raw_forces:
            self._status_msg = "İç kuvvet sonucu (.cd4res) bulunamadı; önce statik analiz çalıştırın."
            return

        combo_forces = build_combination_frame_forces(project, raw_forces, SteelConfig(include_non_auto_combos=True))
        cfg: TimberConfig = project.config.timber
        unit_system: UnitSystem = getattr(project, "unit_system", UnitSystem.N_MM)
        targets = set(target_ids) if target_ids is not None else {fid for fid, _, _, _ in timber_list}

        if target_ids is None:
            self._results.clear()

        checked_count = 0
        for fid, frame, sec, mat in timber_list:
            if fid not in targets:
                continue
            label = str(getattr(frame, "label", "") or f"F#{fid}")
            length_mm = float(convert_value(Dimension.LENGTH, float(frame.get_length()), unit_system, UnitSystem.N_MM))
            geom = _extract_section_geometry(sec, unit_system)
            strengths = _resolve_timber_strengths(mat, cfg.default_grade)

            station_rows: list[dict] = []
            gov_combo = "-"
            gov_x = 0.0
            max_ratio = 0.0
            all_ok = True

            for cname, cmap in combo_forces.items():
                ff = cmap.get(fid)
                if ff is None or not ff.stations:
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

                    r_axial = (chk["sigma_axial"] / chk["ft0d"]) if p_n >= 0.0 and chk["ft0d"] > 0.0 else (
                        (chk["sigma_axial"] / (chk["CP"] * chk["fc0d"])) if (chk["CP"] * chk["fc0d"]) > 0.0 else 0.0
                    )
                    r_shear = max(
                        (chk["tau2"] / chk["fv_d"]) if chk["fv_d"] > 0.0 else 0.0,
                        (chk["tau3"] / chk["fv_d"]) if chk["fv_d"] > 0.0 else 0.0,
                        (chk["tau_torsion"] / chk["fv_d"]) if chk["fv_d"] > 0.0 else 0.0,
                    )
                    r_bend = max(
                        ((chk["sigma_axial"] + chk["sigma_b2"]) / chk["fm_d"]) if chk["fm_d"] > 0.0 else 0.0,
                        ((chk["sigma_axial"] + chk["sigma_b3"]) / chk["fm_d"]) if chk["fm_d"] > 0.0 else 0.0,
                    )
                    st_dcr = max(r_axial, r_shear, r_bend)
                    st_ok = chk["OK"] == "✔️"
                    if not st_ok:
                        all_ok = False
                    if st_dcr >= max_ratio:
                        max_ratio = st_dcr
                        gov_combo = cname
                        gov_x = x_mm

                    station_rows.append({
                        "combo": cname,
                        "x": x_mm,
                        "P": p_n,
                        "V2": v2_n,
                        "V3": v3_n,
                        "T": t_nmm,
                        "M2": m2_nmm,
                        "M3": m3_nmm,
                        "dcr": st_dcr,
                        "ok": st_ok,
                        **chk,
                    })

            if station_rows:
                self._results[fid] = {
                    "frame_id": fid,
                    "label": label,
                    "section": getattr(sec, "name", ""),
                    "grade": strengths["grade"],
                    "length": length_mm,
                    "gov_combo": gov_combo,
                    "gov_x": gov_x,
                    "max_dcr": max_ratio,
                    "ok": all_ok,
                    "stations": station_rows,
                }
                checked_count += 1

        fails = sum(1 for r in self._results.values() if not r["ok"])
        self._status_msg = f"✓ {checked_count} ahşap eleman tahkik edildi ({fails} yetersiz)."

    def draw_content(self):
        project = self._project()
        if project is None:
            imgui.text("Aktif proje yok.")
            return

        timber_list = self._timber_frames(project)
        if not timber_list:
            imgui.text_colored(imgui.ImVec4(0.9, 0.7, 0.4, 1.0), "Modelde ahşap çerçeve elemanı bulunmuyor.")
            return

        timber_ids = [fid for fid, _, _, _ in timber_list]
        self._sync_viewport_selection(timber_ids)
        if self._selected_frame_id not in timber_ids:
            self._selected_frame_id = timber_ids[0]

        self._draw_toolbar(project, timber_list)
        imgui.separator()

        avail = imgui.get_content_region_avail()
        imgui.begin_child("##timber_left", imgui.ImVec2(330.0, avail.y - 32.0), imgui.ChildFlags_.borders)
        self._draw_left_pane(project, timber_list)
        imgui.end_child()

        imgui.same_line()

        imgui.begin_child("##timber_right", imgui.ImVec2(0.0, avail.y - 32.0), imgui.ChildFlags_.borders)
        self._draw_right_pane(project)
        imgui.end_child()

        if self._status_msg:
            imgui.text_colored(imgui.ImVec4(0.6, 0.95, 0.6, 1.0), self._status_msg)

    def _draw_toolbar(self, project, timber_list: list[tuple[int, object, object, object]]) -> None:
        cfg: TimberConfig = project.config.timber
        imgui.push_item_width(75)
        _, cfg.CN = imgui.input_float("CN", cfg.CN, step=0.05, format="%.2f")
        imgui.same_line()
        _, cfg.CY = imgui.input_float("CY", cfg.CY, step=0.05, format="%.2f")
        imgui.same_line()
        _, cfg.CB = imgui.input_float("CB", cfg.CB, step=0.05, format="%.2f")
        imgui.same_line()
        _, cfg.OMEGA = imgui.input_float("Ω", cfg.OMEGA, step=0.05, format="%.2f")
        imgui.pop_item_width()

        imgui.same_line()
        if imgui.button("Tümünü Tahkik Et", imgui.ImVec2(145, 28)):
            self._run_checks(project, timber_list)

        imgui.same_line()
        if imgui.button("Seçiliyi Tahkik Et", imgui.ImVec2(145, 28)) and self._selected_frame_id is not None:
            self._run_checks(project, timber_list, target_ids=[self._selected_frame_id])

    def _draw_left_pane(self, project, timber_list: list[tuple[int, object, object, object]]) -> None:
        imgui.text_colored(imgui.ImVec4(0.9, 0.85, 0.5, 1.0), f"Ahşap Elemanlar ({len(timber_list)})")
        if imgui.begin_table(
            "##timber_members_tbl",
            4,
            imgui.TableFlags_.borders | imgui.TableFlags_.row_bg | imgui.TableFlags_.scroll_y,
            imgui.ImVec2(0.0, 270.0),
        ):
            for h in ("Eleman", "Kesit", "DCR", "Durum"):
                imgui.table_setup_column(h)
            imgui.table_headers_row()

            for fid, frame, sec, _ in timber_list:
                label = str(getattr(frame, "label", "") or f"F#{fid}")
                sec_name = getattr(sec, "name", "")
                mres = self._results.get(fid)
                dcr_txt = f"{mres['max_dcr']:.3f}" if mres else "-"
                ok_txt = ("OK" if mres["ok"] else "YETERSİZ") if mres else "-"

                imgui.table_next_row()
                imgui.table_set_column_index(0)
                clicked, _ = imgui.selectable(
                    f"{label}##tf_{fid}",
                    fid == self._selected_frame_id,
                    imgui.SelectableFlags_.span_all_columns,
                )
                if clicked:
                    self._selected_frame_id = fid
                imgui.table_set_column_index(1)
                imgui.text(str(sec_name))
                imgui.table_set_column_index(2)
                imgui.text(dcr_txt)
                imgui.table_set_column_index(3)
                if mres is not None:
                    col = imgui.ImVec4(0.35, 0.95, 0.45, 1.0) if mres["ok"] else imgui.ImVec4(1.0, 0.35, 0.35, 1.0)
                    imgui.text_colored(col, ok_txt)
                else:
                    imgui.text(ok_txt)
            imgui.end_table()

        imgui.separator()
        cfg: TimberConfig = project.config.timber
        imgui.text_colored(imgui.ImVec4(0.9, 0.85, 0.5, 1.0), "Yönetmelik Katsayıları")
        imgui.push_item_width(130)
        _, cfg.c_buckling = imgui.input_float("Burkulma c", cfg.c_buckling, step=0.05, format="%.2f")
        _, cfg.default_grade = imgui.input_text("Varsayılan Sınıf", cfg.default_grade)
        _, cfg.design_case_name = imgui.input_text("Rapor Durumu", cfg.design_case_name)
        imgui.pop_item_width()

    def _draw_right_pane(self, project) -> None:
        fid = self._selected_frame_id
        if fid is None:
            return

        mres = self._results.get(fid)
        raw_forces = self._resolve_frame_forces(project)
        combo_forces = build_combination_frame_forces(project, raw_forces, SteelConfig(include_non_auto_combos=True)) if raw_forces else {}

        if mres is not None:
            col = imgui.ImVec4(0.35, 0.95, 0.45, 1.0) if mres["ok"] else imgui.ImVec4(1.0, 0.35, 0.35, 1.0)
            imgui.text_colored(col, f"{mres['label']} | {mres['section']} ({mres['grade']}) | L={mres['length']:.0f} mm")
            imgui.text(
                f"Kritik Kombinasyon: {mres['gov_combo']} @ x={mres['gov_x']:.0f} mm | "
                f"Maks. DCR={mres['max_dcr']:.3f}"
            )
            imgui.separator()

        avail_combos = sorted({c for c, cmap in combo_forces.items() if fid in cmap})
        if avail_combos:
            if self._selected_combo_name not in avail_combos:
                self._selected_combo_name = mres["gov_combo"] if (mres and mres["gov_combo"] in avail_combos) else avail_combos[0]
            imgui.push_item_width(220)
            ch_c, idx_c = imgui.combo("Kombinasyon", avail_combos.index(self._selected_combo_name), avail_combos)
            if ch_c:
                self._selected_combo_name = avail_combos[idx_c]
            imgui.pop_item_width()

            imgui.same_line()
            imgui.push_item_width(190)
            ch_d, idx_d = imgui.combo(
                "Diyagram",
                self._diagram_kind,
                ["M3 (Majör Moment)", "V2 (Majör Kesme)", "N (Eksenel Kuvvet)", "DCR (Kapasite Oranı)"],
            )
            if ch_d:
                self._diagram_kind = idx_d
            imgui.pop_item_width()

            ff = combo_forces[self._selected_combo_name][fid]
            xs = np.array([s.x for s in ff.stations], dtype=float)
            if self._diagram_kind == 0:
                vals = np.array([s.M3 for s in ff.stations], dtype=float)
                unit_lbl = "N·mm"
            elif self._diagram_kind == 1:
                vals = np.array([s.V2 for s in ff.stations], dtype=float)
                unit_lbl = "N"
            elif self._diagram_kind == 2:
                vals = np.array([s.N for s in ff.stations], dtype=float)
                unit_lbl = "N"
            else:
                st_rows = [s for s in (mres["stations"] if mres else []) if s["combo"] == self._selected_combo_name]
                vals = np.array([s["dcr"] for s in st_rows], dtype=float) if st_rows else np.zeros_like(xs)
                unit_lbl = "DCR"

            self._draw_diagram_canvas(xs, vals, ff.length, unit_lbl, limit_line=(1.0 if self._diagram_kind == 3 else None))

        if mres is not None and mres["stations"]:
            filtered = [s for s in mres["stations"] if s["combo"] == self._selected_combo_name] or mres["stations"]
            cols = [
                "Kombinasyon", "x (mm)", "P (kN)", "M3 (kN·m)",
                "σ_ax", "fc0d", "CP", "τ2", "fv,d", "σ_b3", "fm,d", "DCR", "Durum",
            ]
            if imgui.begin_table(
                "##timber_station_chk",
                len(cols),
                imgui.TableFlags_.borders | imgui.TableFlags_.row_bg | imgui.TableFlags_.scroll_y,
            ):
                for h in cols:
                    imgui.table_setup_column(h)
                imgui.table_headers_row()
                for st in filtered:
                    imgui.table_next_row()
                    vals_row = [
                        st["combo"],
                        f"{st['x']:.0f}",
                        f"{st['P'] * 1e-3:+.2f}",
                        f"{st['M3'] * 1e-6:+.2f}",
                        f"{st['sigma_axial']:.2f}",
                        f"{st['fc0d']:.2f}",
                        f"{st['CP']:.3f}",
                        f"{st['tau2']:.2f}",
                        f"{st['fv_d']:.2f}",
                        f"{st['sigma_b3']:.2f}",
                        f"{st['fm_d']:.2f}",
                        f"{st['dcr']:.3f}",
                        "OK" if st["ok"] else "X",
                    ]
                    for j, val in enumerate(vals_row):
                        imgui.table_set_column_index(j)
                        if j == 12:
                            c = imgui.ImVec4(0.35, 0.95, 0.45, 1.0) if st["ok"] else imgui.ImVec4(1.0, 0.35, 0.35, 1.0)
                            imgui.text_colored(c, val)
                        else:
                            imgui.text(val)
                imgui.end_table()

    def _draw_diagram_canvas(
        self,
        xs: np.ndarray,
        values: np.ndarray,
        length: float,
        unit_lbl: str,
        limit_line: float | None = None,
    ) -> None:
        if xs.size < 2 or length <= 0.0:
            return
        avail_w = max(260.0, imgui.get_content_region_avail().x)
        canvas_h = 145.0
        p0 = imgui.get_cursor_screen_pos()
        p1 = imgui.ImVec2(p0.x + avail_w, p0.y + canvas_h)

        dl = imgui.get_window_draw_list()
        dl.add_rect_filled(p0, p1, imgui.get_color_u32(imgui.ImVec4(0.09, 0.11, 0.15, 1.0)))
        dl.add_rect(p0, p1, imgui.get_color_u32(imgui.ImVec4(0.30, 0.35, 0.42, 1.0)))

        pad_x = 20.0
        pad_y = 22.0
        mid_y = p0.y + canvas_h * 0.5
        plot_w = avail_w - 2.0 * pad_x
        max_abs = max(float(np.max(np.abs(values))), float(limit_line or 0.0))

        dl.add_line(
            imgui.ImVec2(p0.x + pad_x, mid_y),
            imgui.ImVec2(p0.x + pad_x + plot_w, mid_y),
            imgui.get_color_u32(imgui.ImVec4(0.65, 0.65, 0.70, 0.9)),
            1.5,
        )

        if max_abs > 1e-12:
            scale_y = (canvas_h * 0.5 - pad_y) / max_abs
            if limit_line is not None:
                ly = mid_y - limit_line * scale_y
                dl.add_line(
                    imgui.ImVec2(p0.x + pad_x, ly),
                    imgui.ImVec2(p0.x + pad_x + plot_w, ly),
                    imgui.get_color_u32(imgui.ImVec4(1.0, 0.35, 0.35, 0.85)),
                    1.2,
                )

            line_col = imgui.get_color_u32(imgui.ImVec4(0.95, 0.68, 0.25, 1.0))
            fill_col = imgui.get_color_u32(imgui.ImVec4(0.95, 0.68, 0.25, 0.22))
            pts = [
                imgui.ImVec2(p0.x + pad_x + (float(x) / length) * plot_w, mid_y - float(v) * scale_y)
                for x, v in zip(xs, values)
            ]
            for i in range(len(pts) - 1):
                a, b = pts[i], pts[i + 1]
                dl.add_quad_filled(imgui.ImVec2(a.x, mid_y), a, b, imgui.ImVec2(b.x, mid_y), fill_col)
                dl.add_line(a, b, line_col, 2.0)

        dl.add_text(
            imgui.ImVec2(p0.x + 8.0, p0.y + 4.0),
            imgui.get_color_u32(imgui.ImVec4(0.85, 0.90, 0.95, 1.0)),
            f"min={float(np.min(values)):.3g} {unit_lbl} | max={float(np.max(values)):.3g} {unit_lbl}",
        )
        imgui.dummy(imgui.ImVec2(avail_w, canvas_h + 4.0))