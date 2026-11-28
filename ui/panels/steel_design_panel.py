# ui/panels/steel_design_panel.py
from __future__ import annotations

from pathlib import Path

import numpy as np
from imgui_bundle import imgui

from app.analysis.force_recovery import FrameForceResult, load_analysis_results
from app.settings.categories import Category
from core.design.steel_check import (
    SteelMemberResult,
    build_combination_frame_forces,
    compute_model_geometry_hash,
    run_steel_design,
    save_steel_design_results,
)
from data.enums import MatType
from ui.base.panel_base import PanelBase


class SteelDesignPanel(PanelBase):
    panel_name = "steel_design"
    title = "Çelik Tahkik Yöneticisi"
    category = Category.TOOLS
    menu_label = "Çelik Tahkik (ÇYTHYEDY)"
    icon = "check"
    uses_draft = False
    show_apply_bar = False
    width = 1040
    height = 760
    pos_first_use = (180, 90)
    context = ("app",)

    def __init__(self, app=None, **overrides):
        self._selected_frame_id: int | None = None
        self._selected_combo_name: str = ""
        self._diagram_kind: int = 0
        self._status_msg: str = ""
        super().__init__(app=app, **overrides)

    def _project(self):
        return getattr(self.app, "current_project", None) if self.app else None

    def _steel_frames(self, project) -> list[tuple[int, object]]:
        math_model = getattr(project, "math_model", None)
        if math_model is None:
            return []
        out: list[tuple[int, object]] = []
        for fid, frame in sorted(math_model.frames.items()):
            sec = getattr(frame, "section", None)
            if isinstance(sec, str):
                sec = (getattr(project, "sections", None) or {}).get(sec)
            mat = getattr(sec, "material", None) if sec is not None else None
            if mat is not None and MatType.from_sap(getattr(mat, "mat_type", None)) == MatType.STEEL:
                out.append((fid, frame))
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

    def _sync_viewport_selection(self, steel_ids: list[int]) -> None:
        eng = getattr(self.app, "engine", None)
        sel_mgr = getattr(eng, "sel_mgr", None) if eng else None
        if sel_mgr is None:
            return
        selected = list(sel_mgr.get_selected())
        for el in selected:
            uid = getattr(el, "unique_id", None)
            if uid in steel_ids:
                self._selected_frame_id = int(uid)
                return

    def _run_checks(self, project, target_ids: list[int] | None = None) -> None:
        forces = self._resolve_frame_forces(project)
        if not forces:
            self._status_msg = "İç kuvvet sonucu (.cd4res) bulunamadı; önce statik analiz çalıştırın."
            return
        results = run_steel_design(project, forces, frame_ids=target_ids)
        if not results:
            self._status_msg = "Tahkik edilecek çelik eleman bulunamadı."
            return
        fails = sum(1 for r in results.values() if not r.ok)
        self._status_msg = f"✓ {len(results)} çelik eleman tahkik edildi ({fails} yetersiz)."

    def _save_design_to_disk(self, project) -> None:
        results: dict[int, SteelMemberResult] = getattr(project, "steel_design_results", None) or {}
        if not results:
            self._status_msg = "Kaydedilecek tahkik sonucu yok."
            return
        project_service = getattr(self.app, "project_service", None)
        proj_path = getattr(project_service, "file_path", None)
        target = Path(proj_path).with_suffix(".cd4des") if proj_path else Path("steel_design.cd4des")
        geo_hash = compute_model_geometry_hash(project)
        saved_path = save_steel_design_results(
            target,
            results,
            geometry_hash=geo_hash,
            design_method=project.config.steel.design_method,
        )
        project.steel_design_path = saved_path.name if proj_path else str(saved_path.resolve())
        project.steel_design_hash = geo_hash
        project.steel_design_warning = None
        if proj_path and project_service is not None:
            project_service.save_current()
        self._status_msg = f"✓ Tahkik kaydedildi: {saved_path}"

    def draw_content(self):
        project = self._project()
        if project is None:
            imgui.text("Aktif proje yok.")
            return

        steel_list = self._steel_frames(project)
        if not steel_list:
            imgui.text_colored(imgui.ImVec4(0.9, 0.7, 0.4, 1.0), "Modelde çelik çerçeve elemanı bulunmuyor.")
            return

        steel_ids = [fid for fid, _ in steel_list]
        self._sync_viewport_selection(steel_ids)
        if self._selected_frame_id not in steel_ids:
            self._selected_frame_id = steel_ids[0]

        current_hash = compute_model_geometry_hash(project)
        saved_hash = getattr(project, "steel_design_hash", None)
        if saved_hash and saved_hash != current_hash:
            imgui.text_colored(
                imgui.ImVec4(1.0, 0.45, 0.35, 1.0),
                "⚠ Model geometrisi veya yük kombinasyonları değişti; tahkiki yeniden çalıştırın.",
            )
            imgui.separator()
        elif getattr(project, "steel_design_warning", None):
            imgui.text_colored(imgui.ImVec4(1.0, 0.65, 0.3, 1.0), f"⚠ {project.steel_design_warning}")
            imgui.separator()

        self._draw_toolbar(project, steel_list)
        imgui.separator()

        avail = imgui.get_content_region_avail()
        left_w = 340.0
        imgui.begin_child("##steel_left", imgui.ImVec2(left_w, avail.y - 34.0), imgui.ChildFlags_.borders)
        self._draw_member_list_and_spec(project, steel_list)
        imgui.end_child()

        imgui.same_line()

        imgui.begin_child("##steel_right", imgui.ImVec2(0.0, avail.y - 34.0), imgui.ChildFlags_.borders)
        self._draw_member_details(project)
        imgui.end_child()

        if self._status_msg:
            imgui.text_colored(imgui.ImVec4(0.6, 0.95, 0.6, 1.0), self._status_msg)

    def _draw_toolbar(self, project, steel_list: list[tuple[int, object]]) -> None:
        cfg = project.config.steel
        methods = ["LRFD", "ASD"]
        cur_m = methods.index(cfg.design_method) if cfg.design_method in methods else 0
        imgui.push_item_width(110)
        ch, idx = imgui.combo("Yöntem", cur_m, methods)
        if ch:
            cfg.design_method = methods[idx]
        imgui.pop_item_width()

        imgui.same_line()
        imgui.push_item_width(100)
        ch_d, new_defl = imgui.input_float("Sehim L/", cfg.deflection_limit_ratio, step=50.0, format="%.0f")
        if ch_d and new_defl >= 50.0:
            cfg.deflection_limit_ratio = new_defl
        imgui.pop_item_width()

        imgui.same_line()
        if imgui.button("Tümünü Tahkik Et", imgui.ImVec2(150, 28)):
            self._run_checks(project)

        imgui.same_line()
        if imgui.button("Seçiliyi Tahkik Et", imgui.ImVec2(150, 28)) and self._selected_frame_id is not None:
            self._run_checks(project, target_ids=[self._selected_frame_id])

        imgui.same_line()
        if imgui.button("Kaydet (.cd4des)", imgui.ImVec2(150, 28)):
            self._save_design_to_disk(project)

    def _draw_member_list_and_spec(self, project, steel_list: list[tuple[int, object]]) -> None:
        results: dict[int, SteelMemberResult] = getattr(project, "steel_design_results", None) or {}
        imgui.text_colored(imgui.ImVec4(0.9, 0.85, 0.5, 1.0), f"Çelik Elemanlar ({len(steel_list)})")

        if imgui.begin_table(
            "##steel_members_tbl",
            4,
            imgui.TableFlags_.borders | imgui.TableFlags_.row_bg | imgui.TableFlags_.scroll_y,
            imgui.ImVec2(0.0, 240.0),
        ):
            for h in ("Eleman", "Kesit", "DCR", "Durum"):
                imgui.table_setup_column(h)
            imgui.table_headers_row()

            for fid, frame in steel_list:
                label = str(getattr(frame, "label", "") or f"F#{fid}")
                sec = getattr(frame, "section", None)
                sec_name = sec if isinstance(sec, str) else getattr(sec, "name", "")
                mres = results.get(fid)
                dcr_txt = f"{max(mres.max_dcr_interaction, mres.max_dcr_shear):.3f}" if mres else "-"
                ok_txt = ("OK" if mres.ok else "YETERSİZ") if mres else "-"

                imgui.table_next_row()
                imgui.table_set_column_index(0)
                is_sel = fid == self._selected_frame_id
                clicked, _ = imgui.selectable(f"{label}##f_{fid}", is_sel, imgui.SelectableFlags_.span_all_columns)
                if clicked:
                    self._selected_frame_id = fid
                imgui.table_set_column_index(1)
                imgui.text(str(sec_name))
                imgui.table_set_column_index(2)
                imgui.text(dcr_txt)
                imgui.table_set_column_index(3)
                if mres is not None:
                    col = imgui.ImVec4(0.35, 0.95, 0.45, 1.0) if mres.ok else imgui.ImVec4(1.0, 0.35, 0.35, 1.0)
                    imgui.text_colored(col, ok_txt)
                else:
                    imgui.text(ok_txt)
            imgui.end_table()

        imgui.separator()
        if self._selected_frame_id is None:
            return
        spec = project.get_or_create_steel_spec(self._selected_frame_id)
        imgui.text_colored(imgui.ImVec4(0.9, 0.85, 0.5, 1.0), "Burkulma ve Tahkik Parametreleri")

        m_types = ["Beam", "Column", "Brace"]
        cur_t = m_types.index(spec.member_type) if spec.member_type in m_types else 0
        imgui.push_item_width(140)
        ch_t, idx_t = imgui.combo("Eleman Tipi", cur_t, m_types)
        if ch_t:
            spec.member_type = m_types[idx_t]
        _, spec.kx = imgui.input_float("Kx (majör)", spec.kx, step=0.05, format="%.2f")
        _, spec.ky = imgui.input_float("Ky (minör)", spec.ky, step=0.05, format="%.2f")
        _, spec.kz = imgui.input_float("Kz (burulma)", spec.kz, step=0.05, format="%.2f")
        _, spec.lbx = imgui.input_float("Lb (YBB boyu)", spec.lbx, step=100.0, format="%.1f")
        _, spec.cb = imgui.input_float("Cb (moment düzeltme)", spec.cb, step=0.05, format="%.2f")
        _, spec.net_area_ratio = imgui.input_float("Ae/Ag oranı", spec.net_area_ratio, step=0.05, format="%.2f")
        _, spec.deflection_limit_ratio = imgui.input_float("Sehim sınırı L/", spec.deflection_limit_ratio, step=50.0, format="%.0f")
        imgui.pop_item_width()

    def _draw_member_details(self, project) -> None:
        fid = self._selected_frame_id
        if fid is None:
            return

        results: dict[int, SteelMemberResult] = getattr(project, "steel_design_results", None) or {}
        mres = results.get(fid)
        forces = self._resolve_frame_forces(project)
        combo_forces = build_combination_frame_forces(project, forces, project.config.steel) if forces else {}

        if mres is not None:
            status_col = imgui.ImVec4(0.35, 0.95, 0.45, 1.0) if mres.ok else imgui.ImVec4(1.0, 0.35, 0.35, 1.0)
            imgui.text_colored(
                status_col,
                f"{mres.label} | {mres.section_name} ({mres.material_name}) | "
                f"Başlık: {mres.flange_class}, Gövde: {mres.web_class}",
            )
            imgui.text(
                f"Kritik Kombinasyon: {mres.governing_combo} @ x={mres.governing_x:.0f} mm | "
                f"Etkileşim DCR={mres.max_dcr_interaction:.3f} | Kesme DCR={mres.max_dcr_shear:.3f} | "
                f"Sehim={mres.deflection_mm:.2f}/{mres.deflection_limit_mm:.2f} mm (DCR={mres.max_dcr_deflection:.3f})"
            )
            imgui.separator()

        avail_combos = sorted({c for c, cmap in combo_forces.items() if fid in cmap})
        if avail_combos:
            if self._selected_combo_name not in avail_combos:
                self._selected_combo_name = mres.governing_combo if (mres and mres.governing_combo in avail_combos) else avail_combos[0]
            imgui.push_item_width(220)
            ch_c, idx_c = imgui.combo("Kombinasyon", avail_combos.index(self._selected_combo_name), avail_combos)
            if ch_c:
                self._selected_combo_name = avail_combos[idx_c]
            imgui.pop_item_width()

            imgui.same_line()
            imgui.push_item_width(180)
            ch_d, idx_d = imgui.combo("Diyagram", self._diagram_kind, ["M3 (Majör Moment)", "V2 (Majör Kesme)", "N (Eksenel Kuvvet)", "DCR (Kapasite Oranı)"])
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
                st_checks = [s for s in (mres.stations if mres else []) if s.combo_name == self._selected_combo_name]
                vals = np.array([s.dcr_interaction for s in st_checks], dtype=float) if st_checks else np.zeros_like(xs)
                unit_lbl = "DCR"

            self._draw_diagram_canvas(xs, vals, ff.length, unit_lbl, limit_line=(1.0 if self._diagram_kind == 3 else None))

        if mres is not None and mres.stations:
            filtered = [s for s in mres.stations if s.combo_name == self._selected_combo_name] or mres.stations
            cols = ["Kombinasyon", "x (mm)", "N (kN)", "V2 (kN)", "M3 (kN·m)", "M2 (kN·m)", "N/Nc", "M3/Mcx", "DCR", "Denklem", "Durum"]
            if imgui.begin_table(
                "##steel_station_chk",
                len(cols),
                imgui.TableFlags_.borders | imgui.TableFlags_.row_bg | imgui.TableFlags_.scroll_y,
            ):
                for h in cols:
                    imgui.table_setup_column(h)
                imgui.table_headers_row()
                for st in filtered:
                    imgui.table_next_row()
                    row_vals = [
                        st.combo_name,
                        f"{st.x:.0f}",
                        f"{st.N * 1e-3:+.2f}",
                        f"{st.V2 * 1e-3:+.2f}",
                        f"{st.M3 * 1e-6:+.2f}",
                        f"{st.M2 * 1e-6:+.2f}",
                        f"{st.dcr_axial:.3f}",
                        f"{st.dcr_bend_x:.3f}",
                        f"{st.dcr_interaction:.3f}",
                        st.equation,
                        "OK" if st.ok else "X",
                    ]
                    for j, v in enumerate(row_vals):
                        imgui.table_set_column_index(j)
                        if j == 10:
                            c = imgui.ImVec4(0.35, 0.95, 0.45, 1.0) if st.ok else imgui.ImVec4(1.0, 0.35, 0.35, 1.0)
                            imgui.text_colored(c, v)
                        else:
                            imgui.text(v)
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
        canvas_h = 150.0
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

            line_col = imgui.get_color_u32(imgui.ImVec4(0.25, 0.75, 0.95, 1.0))
            fill_col = imgui.get_color_u32(imgui.ImVec4(0.25, 0.75, 0.95, 0.22))
            pts = [
                imgui.ImVec2(p0.x + pad_x + (float(x) / length) * plot_w, mid_y - float(v) * scale_y)
                for x, v in zip(xs, values)
            ]
            for i in range(len(pts) - 1):
                a, b = pts[i], pts[i + 1]
                dl.add_quad_filled(imgui.ImVec2(a.x, mid_y), a, b, imgui.ImVec2(b.x, mid_y), fill_col)
                dl.add_line(a, b, line_col, 2.0)

        min_v = float(np.min(values))
        max_v = float(np.max(values))
        dl.add_text(
            imgui.ImVec2(p0.x + 8.0, p0.y + 4.0),
            imgui.get_color_u32(imgui.ImVec4(0.85, 0.90, 0.95, 1.0)),
            f"min={min_v:.3g} {unit_lbl} | max={max_v:.3g} {unit_lbl}",
        )
        imgui.dummy(imgui.ImVec2(avail_w, canvas_h + 4.0))