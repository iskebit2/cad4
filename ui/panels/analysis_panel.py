# ui/panels/analysis_panel.py
from __future__ import annotations

import threading
import time
from collections import defaultdict
from queue import Empty, Queue

import numpy as np
from imgui_bundle import imgui

from app.commands.analysis.force_recovery import (
    FrameForceResult,
    recover_frame_forces,
    save_analysis_results,
)
from app.commands.analysis.run import AnalysisBundle, AnalysisOptions, AnalysisService
from app.settings.categories import Category
from logging_config import CadLogger
from ui.base.panel_base import PanelBase

logger = CadLogger.get(__name__)


class AnalysisManagerPanel(PanelBase):
    panel_name = "analysis_manager"
    title = "Analiz Yöneticisi"
    category = Category.TOOLS
    menu_label = "Analiz Yöneticisi"
    icon = "play"
    uses_draft = False
    show_apply_bar = False
    width = 920
    height = 720
    pos_first_use = (200, 100)
    context = ("app",)

    def __init__(self, app=None, **overrides):
        self._n_live = 0.3
        self._n_modes = 12
        self._run_static = True
        self._run_modal = True
        self._run_spectral = False
        self._run_takeoff = True
        self._use_shear_deform = True
        self._recover_forces = True
        self._spectrum_name = ""
        self._spectrum_names: list[str] = []

        self._bundle: AnalysisBundle | None = None
        self._frame_forces: dict[str, dict[int, FrameForceResult]] = {}
        self._selected_static_case: str = ""
        self._selected_frame_idx: int = 0
        self._status_msg = ""

        self._worker: threading.Thread | None = None
        self._result_queue: Queue = Queue()
        self._is_running = False
        self._t0 = 0.0

        super().__init__(app=app, **overrides)

    def open(self, **kw):
        super().open(**kw)
        self._refresh_spectrum_list()

    def close(self):
        super().close()

    def set_context(self, ctx):
        super().set_context(ctx)
        self._refresh_spectrum_list()

    def _project(self):
        return getattr(self.app, "current_project", None) if self.app else None

    def _scene(self):
        eng = getattr(self.app, "engine", None) if self.app else None
        return getattr(eng, "math_model", None) if eng else None

    def _refresh_spectrum_list(self):
        project = self._project()
        self._spectrum_names = (
            list(project.spectrum_functions.keys()) if project else []
        )

    def _run_analysis(self):
        if self._is_running:
            return
        scene = self._scene()
        project = self._project()
        if scene is None or project is None:
            self._status_msg = "Sahne/proje yok"
            return

        opts = AnalysisOptions(
            n_live=self._n_live,
            n_modes=self._n_modes,
            run_static=self._run_static,
            run_modal=self._run_modal,
            run_spectral=self._run_spectral,
            run_takeoff=self._run_takeoff,
            spectrum_name=self._spectrum_name or None,
            use_shear_deform=self._use_shear_deform,
        )
        do_forces = self._recover_forces

        self._is_running = True
        self._status_msg = "Analiz çalışıyor..."
        self._t0 = time.time()

        def _worker():
            bundle = AnalysisService.run(scene, project, opts)
            forces: dict[str, dict[int, FrameForceResult]] = {}
            if (
                do_forces
                and bundle.result is not None
                and bundle.result.mesh is not None
                and bundle.result.static_results
            ):
                forces = recover_frame_forces(
                    project,
                    bundle.result.mesh,
                    bundle.result.static_results,
                    use_shear_deform=opts.use_shear_deform,
                )
            self._result_queue.put(("ok", (bundle, forces)))

        self._worker = threading.Thread(target=_worker, daemon=True)
        self._worker.start()

    def _poll_result(self):
        try:
            kind, payload = self._result_queue.get_nowait()
        except Empty:
            return
        self._is_running = False
        elapsed = time.time() - self._t0

        if kind == "ok":
            bundle, forces = payload
            self._bundle = bundle
            self._frame_forces = forces
            self._selected_frame_idx = 0

            if bundle.result and bundle.result.static_results:
                case_names = list(bundle.result.static_results.keys())
                if self._selected_static_case not in case_names:
                    self._selected_static_case = case_names[0]
            else:
                self._selected_static_case = ""

            parts = [f"{elapsed:.2f}s"]
            if bundle.result:
                parts.append(f"Frame={bundle.result.stiffness.frame_count}")
                if bundle.result.static_results:
                    parts.append(f"Static={len(bundle.result.static_results)}")
                if bundle.result.modal:
                    parts.append(f"n_modes={bundle.result.modal.n_modes}")
            if bundle.takeoff:
                parts.append(f"kütle={bundle.takeoff.total_mass_kg:.1f} kg")
            if bundle.errors:
                parts.append(f"{len(bundle.errors)} hata")
            self._status_msg = "✓ " + ", ".join(parts)
        else:
            self._status_msg = f"Hata: {payload}"

    def _save_results_to_disk(self):
        if self._bundle is None or self._bundle.result is None:
            return
        project = self._project()
        proj_path = getattr(project, "filepath", None) or getattr(project, "path", None)
        target = f"{proj_path}.cd4res" if proj_path else "analysis_results.cd4res"
        saved_path = save_analysis_results(
            target,
            self._bundle.result,
            frame_forces=self._frame_forces or None,
        )
        self._status_msg = f"✓ Kaydedildi: {saved_path}"

    def draw_content(self):
        self._poll_result()

        self._draw_options()
        imgui.separator()
        self._draw_error_banner()

        if self._bundle is not None:
            self._draw_results()
        else:
            imgui.text_colored(
                imgui.ImVec4(0.7, 0.8, 0.6, 1.0),
                "Henüz analiz çalıştırılmadı. 'Analizi Çalıştır'a bas.",
            )

        if self._status_msg:
            imgui.separator()
            color = self._status_color()
            imgui.text_colored(imgui.ImVec4(*color), self._status_msg)
            if self._is_running:
                imgui.same_line()
                dots = "." * (int(time.time() * 2) % 4)
                imgui.text_colored(imgui.ImVec4(1.0, 0.9, 0.4, 1.0), dots)

    def _status_color(self):
        if self._is_running:
            return (1.0, 0.5, 0.3, 1.0)
        if self._status_msg.startswith("✓"):
            return (0.4, 1.0, 0.4, 1.0)
        return (0.9, 0.7, 0.4, 1.0)

    def _draw_options(self):
        imgui.text_colored(imgui.ImVec4(0.9, 0.85, 0.5, 1.0), "Analiz Seçenekleri")
        imgui.spacing()

        imgui.push_item_width(120)
        _, self._n_live = imgui.input_float(
            "n (live çarpanı)", self._n_live, step=0.05, format="%.3f"
        )
        self._n_live = max(0.0, min(1.0, self._n_live))

        imgui.same_line(280)
        _, self._n_modes = imgui.input_int("n_modes", self._n_modes, step=1)
        self._n_modes = max(1, min(100, self._n_modes))
        imgui.pop_item_width()

        _, self._run_static = imgui.checkbox("Statik Analiz", self._run_static)
        imgui.same_line()
        _, self._run_modal = imgui.checkbox("Modal Analiz", self._run_modal)
        imgui.same_line()
        _, self._run_spectral = imgui.checkbox("Spectral Analiz", self._run_spectral)
        imgui.same_line()
        _, self._run_takeoff = imgui.checkbox("Metrajlar", self._run_takeoff)

        _, self._use_shear_deform = imgui.checkbox("Kayma Deformasyonu", self._use_shear_deform)
        imgui.same_line()
        _, self._recover_forces = imgui.checkbox("İç Kuvvet Hesabı", self._recover_forces)

        if self._run_spectral:
            self._refresh_spectrum_list()
            if not self._spectrum_names:
                imgui.text_colored(
                    imgui.ImVec4(0.9, 0.6, 0.3, 1.0),
                    "  Uyarı: projede spektrum tanımı yok.",
                )
            else:
                imgui.push_item_width(240)
                if self._spectrum_name not in self._spectrum_names:
                    self._spectrum_name = self._spectrum_names[0]
                cur = self._spectrum_names.index(self._spectrum_name)
                ch, idx = imgui.combo("Spektrum", cur, self._spectrum_names)
                if ch:
                    self._spectrum_name = self._spectrum_names[idx]
                imgui.pop_item_width()

        imgui.spacing()

        disabled = (
            self._is_running
            or self._scene() is None
            or self._project() is None
        )
        if disabled:
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.3, 0.3, 0.3, 1.0)
            )
        label = "Çalışıyor..." if self._is_running else "Analizi Çalıştır"
        if imgui.button(label, imgui.ImVec2(180, 32)) and not disabled:
            self._run_analysis()
        if disabled:
            imgui.pop_style_color(1)
            if not self._is_running:
                imgui.same_line()
                imgui.text_colored(
                    imgui.ImVec4(0.9, 0.6, 0.3, 1.0), "(sahne veya proje yok)"
                )

        if self._bundle is not None and self._bundle.result is not None and not self._is_running:
            imgui.same_line()
            if imgui.button("Sonuçları Kaydet (.cd4res)", imgui.ImVec2(210, 32)):
                self._save_results_to_disk()

    def _draw_error_banner(self):
        if self._bundle is None or not self._bundle.errors:
            return
        imgui.push_style_color(
            imgui.Col_.child_bg, imgui.ImVec4(0.35, 0.12, 0.12, 1.0)
        )
        imgui.begin_child(
            "##err_banner",
            imgui.ImVec2(0, min(20 + 18 * len(self._bundle.errors), 120)),
            imgui.ChildFlags_.borders,
        )
        imgui.text_colored(imgui.ImVec4(1.0, 0.7, 0.7, 1.0), "Analiz uyarıları:")
        for e in self._bundle.errors:
            imgui.bullet_text(e)
        imgui.end_child()
        imgui.pop_style_color(1)
        imgui.spacing()

    def _draw_results(self):
        if self._bundle is None or self._bundle.result is None:
            imgui.text_colored(imgui.ImVec4(1.0, 0.4, 0.4, 1.0), "Sonuç yok")
            return

        tabs = [
            ("Genel", self._draw_tab_genel, True),
            ("Kütle", self._draw_tab_kutle, False),
        ]
        if self._bundle.result.static_results:
            tabs.append(("Statik", self._draw_tab_statik, True))
        if self._frame_forces:
            tabs.append(("İç Kuvvetler", self._draw_tab_ic_kuvvetler, False))
        if self._bundle.result.modal is not None:
            tabs.append(("Modal", self._draw_tab_modal, False))
        if self._bundle.spectral is not None:
            tabs.append(("Spectral", self._draw_tab_spectral, False))
        if self._bundle.takeoff is not None:
            tabs.append(("Metraj", self._draw_tab_metraj, False))

        for name, fn, default_open in tabs:
            flags = (
                imgui.TreeNodeFlags_.default_open if default_open else 0
            )
            if imgui.collapsing_header(name, flags=flags):
                fn()

    def _draw_tab_genel(self):
        r = self._bundle.result
        imgui.text(f"DOF: {r.K.shape[0]}")
        imgui.text(f"Mesnetli DOF: {len(r.fixed_dofs)}")
        imgui.text(
            f"Frame (eklendi/atlandı): "
            f"{r.stiffness.frame_count} / {len(r.stiffness.skipped)}"
        )

        if r.stiffness.skipped:
            imgui.separator()
            if imgui.tree_node(f"Atlanan elemanlar ({len(r.stiffness.skipped)})"):
                for label, reason in r.stiffness.skipped[:50]:
                    imgui.text_colored(
                        imgui.ImVec4(0.9, 0.7, 0.4, 1.0),
                        f"  {label}: {reason}",
                    )
                if len(r.stiffness.skipped) > 50:
                    imgui.text(
                        f"  ... ve {len(r.stiffness.skipped) - 50} tane daha"
                    )
                imgui.tree_pop()

        warns = list(r.warnings)
        if warns:
            imgui.separator()
            imgui.text_colored(imgui.ImVec4(0.9, 0.8, 0.4, 1.0), "Uyarılar:")
            for w in warns[:20]:
                imgui.text_colored(
                    imgui.ImVec4(0.9, 0.75, 0.5, 1.0), f"  • {w}"
                )
            if len(warns) > 20:
                imgui.text(f"  ... ve {len(warns) - 20} tane daha")

    def _draw_tab_statik(self):
        static_res = self._bundle.result.static_results
        if not static_res:
            imgui.text("Statik sonuç yok")
            return

        case_names = list(static_res.keys())
        if self._selected_static_case not in case_names:
            self._selected_static_case = case_names[0]

        imgui.push_item_width(220)
        cur_idx = case_names.index(self._selected_static_case)
        ch, idx = imgui.combo("Yük Durumu (LoadCase)", cur_idx, case_names)
        if ch:
            self._selected_static_case = case_names[idx]
        imgui.pop_item_width()

        res = static_res[self._selected_static_case]
        U = res.displacements
        F = res.applied_forces
        R = res.reactions

        max_ux = float(np.max(np.abs(U[0::6]))) if U.size >= 6 else 0.0
        max_uy = float(np.max(np.abs(U[1::6]))) if U.size >= 6 else 0.0
        max_uz = float(np.max(np.abs(U[2::6]))) if U.size >= 6 else 0.0
        sum_fx = float(np.sum(F[0::6])) if F.size >= 6 else 0.0
        sum_fy = float(np.sum(F[1::6])) if F.size >= 6 else 0.0
        sum_fz = float(np.sum(F[2::6])) if F.size >= 6 else 0.0

        imgui.spacing()
        imgui.text_colored(
            imgui.ImVec4(0.7, 0.9, 0.7, 1.0),
            f"Max |U|: UX={max_ux:.4f} mm, UY={max_uy:.4f} mm, UZ={max_uz:.4f} mm",
        )
        imgui.text(
            f"Toplam Yük (F): FX={sum_fx:.2f} N, FY={sum_fy:.2f} N, FZ={sum_fz:.2f} N"
        )

        fixed_set = set(self._bundle.result.fixed_dofs)
        reac_rows: list[tuple[str, np.ndarray]] = []
        for n_key, r_vec in res.node_reactions.items():
            if np.linalg.norm(r_vec) > 1e-6:
                reac_rows.append((n_key, r_vec))

        if reac_rows:
            imgui.separator()
            imgui.text_colored(
                imgui.ImVec4(0.9, 0.85, 0.5, 1.0),
                f"Mesnet Reaksiyonları ({len(reac_rows)} düğüm)",
            )
            cols = ["Düğüm", "RX (N)", "RY (N)", "RZ (N)", "MX (N·mm)", "MY (N·mm)", "MZ (N·mm)"]
            if imgui.begin_table("##static_reactions", len(cols), imgui.TableFlags_.borders | imgui.TableFlags_.row_bg):
                for h in cols:
                    imgui.table_setup_column(h)
                imgui.table_headers_row()
                for n_key, rv in reac_rows[:100]:
                    imgui.table_next_row()
                    vals = [
                        n_key,
                        f"{rv[0]:+.2f}",
                        f"{rv[1]:+.2f}",
                        f"{rv[2]:+.2f}",
                        f"{rv[3]:+.1f}",
                        f"{rv[4]:+.1f}",
                        f"{rv[5]:+.1f}",
                    ]
                    for j, v in enumerate(vals):
                        imgui.table_set_column_index(j)
                        imgui.text(v)
                imgui.end_table()

    def _draw_tab_ic_kuvvetler(self):
        if not self._frame_forces:
            imgui.text("İç kuvvet verisi yok")
            return

        case_names = list(self._frame_forces.keys())
        if self._selected_static_case not in case_names:
            self._selected_static_case = case_names[0]

        case_map = self._frame_forces[self._selected_static_case]
        if not case_map:
            imgui.text("Bu yük durumu için eleman kuvveti bulunamadı")
            return

        frame_items = list(case_map.values())
        frame_labels = [f"{ff.label} (id={ff.frame_id}, L={ff.length:.0f} mm)" for ff in frame_items]
        if self._selected_frame_idx >= len(frame_items):
            self._selected_frame_idx = 0

        imgui.push_item_width(340)
        ch, idx = imgui.combo("Çubuk Eleman", self._selected_frame_idx, frame_labels)
        if ch:
            self._selected_frame_idx = idx
        imgui.pop_item_width()

        ff = frame_items[self._selected_frame_idx]
        if not ff.stations:
            imgui.text("İstasyon verisi yok")
            return

        xs = np.array([s.x for s in ff.stations], dtype=float)
        m3s = np.array([s.M3 for s in ff.stations], dtype=float)
        v2s = np.array([s.V2 for s in ff.stations], dtype=float)

        imgui.spacing()
        imgui.text_colored(
            imgui.ImVec4(0.85, 0.85, 0.55, 1.0),
            f"M3 min/max: {float(np.min(m3s)):.1f} / {float(np.max(m3s)):.1f} N·mm | "
            f"V2 min/max: {float(np.min(v2s)):.2f} / {float(np.max(v2s)):.2f} N",
        )

        self._draw_moment_diagram(xs, m3s, ff.length)

        cols = ["x/L", "x (mm)", "N (N)", "V2 (N)", "V3 (N)", "T (N·mm)", "M2 (N·mm)", "M3 (N·mm)"]
        if imgui.begin_table("##station_forces", len(cols), imgui.TableFlags_.borders | imgui.TableFlags_.row_bg):
            for h in cols:
                imgui.table_setup_column(h)
            imgui.table_headers_row()
            for st in ff.stations:
                imgui.table_next_row()
                vals = [
                    f"{st.ratio:.3f}",
                    f"{st.x:.1f}",
                    f"{st.N:+.2f}",
                    f"{st.V2:+.2f}",
                    f"{st.V3:+.2f}",
                    f"{st.T:+.1f}",
                    f"{st.M2:+.1f}",
                    f"{st.M3:+.1f}",
                ]
                for j, v in enumerate(vals):
                    imgui.table_set_column_index(j)
                    imgui.text(v)
            imgui.end_table()

    def _draw_moment_diagram(self, xs: np.ndarray, values: np.ndarray, length: float):
        if xs.size < 2 or length <= 0.0:
            return
        avail_w = max(240.0, imgui.get_content_region_avail().x)
        canvas_h = 130.0
        p0 = imgui.get_cursor_screen_pos()
        p1 = imgui.ImVec2(p0.x + avail_w, p0.y + canvas_h)

        draw_list = imgui.get_window_draw_list()
        draw_list.add_rect_filled(p0, p1, imgui.get_color_u32(imgui.ImVec4(0.10, 0.12, 0.16, 1.0)))
        draw_list.add_rect(p0, p1, imgui.get_color_u32(imgui.ImVec4(0.30, 0.35, 0.42, 1.0)))

        pad_x = 18.0
        pad_y = 18.0
        mid_y = p0.y + canvas_h * 0.5
        plot_w = avail_w - 2.0 * pad_x
        max_abs = float(np.max(np.abs(values)))

        axis_col = imgui.get_color_u32(imgui.ImVec4(0.65, 0.65, 0.70, 0.9))
        line_col = imgui.get_color_u32(imgui.ImVec4(0.25, 0.85, 0.55, 1.0))
        fill_col = imgui.get_color_u32(imgui.ImVec4(0.25, 0.85, 0.55, 0.22))

        draw_list.add_line(
            imgui.ImVec2(p0.x + pad_x, mid_y),
            imgui.ImVec2(p0.x + pad_x + plot_w, mid_y),
            axis_col,
            1.5,
        )

        if max_abs > 1e-12:
            scale_y = (canvas_h * 0.5 - pad_y) / max_abs
            pts: list[imgui.ImVec2] = []
            for x_val, m_val in zip(xs, values):
                sx = p0.x + pad_x + (float(x_val) / length) * plot_w
                sy = mid_y + float(m_val) * scale_y
                pts.append(imgui.ImVec2(sx, sy))

            for i in range(len(pts) - 1):
                a = pts[i]
                b = pts[i + 1]
                a0 = imgui.ImVec2(a.x, mid_y)
                b0 = imgui.ImVec2(b.x, mid_y)
                draw_list.add_quad_filled(a0, a, b, b0, fill_col)
                draw_list.add_line(a, b, line_col, 2.0)

        imgui.dummy(imgui.ImVec2(avail_w, canvas_h + 4.0))

    def _draw_tab_kutle(self):
        m = self._bundle.result.mass
        imgui.text_colored(imgui.ImVec4(0.9, 0.85, 0.5, 1.0), "Kütle Özeti")
        imgui.spacing()

        def _row(label, val, unit):
            imgui.text(label)
            imgui.same_line(240)
            imgui.text_colored(
                imgui.ImVec4(0.7, 0.9, 0.7, 1.0), f"{val:>14.3f} {unit}"
            )

        _row("Öz kütle", m.total_self_kg, "kg")
        _row("Dead (ham)", m.total_dead_kg, "kg")
        _row(f"Live (ham, ×{m.n_live:.2f} → kullanılan)", m.total_live_kg, "kg")
        _row("Toplam (n uygulanmış)", m.total_kg, "kg")
        _row("Toplam", m.total_ton, "ton")

        imgui.separator()
        imgui.text_colored(imgui.ImVec4(0.9, 0.85, 0.5, 1.0), "Kaynak Dökümü")
        agg = defaultdict(float)
        for c in m.contributions:
            agg[c.source_type] += c.mass_kg
        for st, val in sorted(agg.items()):
            imgui.text(f"  {st:20s}")
            imgui.same_line(240)
            imgui.text_colored(
                imgui.ImVec4(0.7, 0.9, 0.7, 1.0), f"{val:>14.3f} kg"
            )

    def _draw_tab_modal(self):
        r = self._bundle.result
        if r.modal is None:
            imgui.text("Modal sonuç yok")
            return
        modal = r.modal
        imgui.text_colored(
            imgui.ImVec4(0.85, 0.85, 0.55, 1.0),
            f"{modal.n_modes} mod | Mx={modal.total_mass_x:.2f}, "
            f"My={modal.total_mass_y:.2f}, Mz={modal.total_mass_z:.2f} kg",
        )
        imgui.spacing()
        cols = ["#", "T (s)", "f (Hz)", "Γx", "Γy", "Γz", "MeffX", "MeffY"]
        if imgui.begin_table("##modal_table", len(cols)):
            for h in cols:
                imgui.table_setup_column(h)
            imgui.table_headers_row()
            for i in range(modal.n_modes):
                imgui.table_next_row()
                vals = [
                    str(i + 1),
                    f"{modal.periods[i]:.4f}",
                    f"{modal.frequencies[i]:.3f}",
                    f"{modal.participation_factor_x[i]:+.4f}",
                    f"{modal.participation_factor_y[i]:+.4f}",
                    f"{modal.participation_factor_z[i]:+.4f}",
                    f"{modal.effective_mass_x[i]:.2f}",
                    f"{modal.effective_mass_y[i]:.2f}",
                ]
                for j, v in enumerate(vals):
                    imgui.table_set_column_index(j)
                    imgui.text(v)
            imgui.end_table()

    def _draw_tab_spectral(self):
        s = self._bundle.spectral
        if s is None:
            return
        imgui.text_colored(
            imgui.ImVec4(0.85, 0.85, 0.55, 1.0),
            f"{len(s.modes)} mod | SRSS max UX={np.max(np.abs(s.ux_srss)):.4f} mm",
        )
        imgui.text(
            f"SRSS max UY={np.max(np.abs(s.uy_srss)):.4f} mm, "
            f"UZ={np.max(np.abs(s.uz_srss)):.4f} mm"
        )
        imgui.separator()
        cols = ["#", "T (s)", "Sa (g)", "Γx", "Γy", "Γz"]
        if imgui.begin_table("##spectral_modes", len(cols)):
            for h in cols:
                imgui.table_setup_column(h)
            imgui.table_headers_row()
            for m in s.modes:
                imgui.table_next_row()
                vals = [
                    str(m.mode),
                    f"{m.period:.4f}",
                    f"{m.spectral_acceleration:.4f}",
                    f"{m.participation_x:+.4f}",
                    f"{m.participation_y:+.4f}",
                    f"{m.participation_z:+.4f}",
                ]
                for j, v in enumerate(vals):
                    imgui.table_set_column_index(j)
                    imgui.text(v)
            imgui.end_table()

    def _draw_tab_metraj(self):
        t = self._bundle.takeoff
        if t is None:
            return
        imgui.text_colored(
            imgui.ImVec4(0.85, 0.85, 0.55, 1.0),
            f"{len(t.elements)} eleman | toplam {t.total_mass_kg:.2f} kg "
            f"({t.total_mass_ton:.4f} ton), ağırlık {t.total_weight_kN:.3f} kN",
        )
        imgui.separator()
        cols = ["Malzeme", "Adet", "Kütle (kg)", "Kütle (ton)", "Ağırlık (kN)"]
        if imgui.begin_table("##takeoff_material", len(cols)):
            for h in cols:
                imgui.table_setup_column(h)
            imgui.table_headers_row()
            for name, s in sorted(t.by_material.items()):
                imgui.table_next_row()
                vals = [
                    name,
                    str(s.element_count),
                    f"{s.total_mass_kg:.2f}",
                    f"{s.total_mass_kg / 1000.0:.4f}",
                    f"{s.total_weight_kN:.4f}",
                ]
                for j, v in enumerate(vals):
                    imgui.table_set_column_index(j)
                    imgui.text(v)
            imgui.end_table()