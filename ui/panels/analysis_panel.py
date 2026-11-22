# ui/panels/analysis_panel.py
from __future__ import annotations

import threading
import time
from queue import Empty, Queue

import numpy as np
from imgui_bundle import imgui

from app.commands.analysis.run import AnalysisBundle, AnalysisOptions, AnalysisService
from app.commands.analysis.validation import AnalysisValidationError
from app.settings.categories import Category
from logging_config import CadLogger
from ui.base.panel_base import PanelBase

logger = CadLogger.get(__name__)


class AnalysisManagerPanel(PanelBase):
    """Analiz yöneticisi — BasePanel uyumlu, thread'li çalıştırma."""

    # --- BasePanel sınıf seviyesi meta ---
    panel_name = "analysis_manager"
    title = "Analiz Yöneticisi"
    category = Category.TOOLS
    menu_label = "Analiz Yöneticisi"
    icon = "play"
    uses_draft = False         # analiz paneli draft/commit kullanmaz
    show_apply_bar = False
    width = 900
    height = 700
    pos_first_use = (200, 100)
    context = ("app",)

    def __init__(self, app=None, **overrides):
        # --- Analiz state (super'den ÖNCE) ---
        self._n_live = 0.3
        self._n_modes = 12
        self._run_modal = True
        self._run_spectral = False
        self._run_takeoff = True
        self._spectrum_name = ""
        self._spectrum_names: list[str] = []

        self._bundle: AnalysisBundle | None = None
        self._status_msg = ""

        self._worker: threading.Thread | None = None
        self._result_queue: Queue = Queue()
        self._is_running = False
        self._t0 = 0.0

        super().__init__(app=app, **overrides)

    # ================================================================
    # Yaşam döngüsü
    # ================================================================
    def open(self, **kw):
        super().open(**kw)                # visible=True, preview aç
        self._refresh_spectrum_list()

    def close(self):
        super().close()                   # preview kapat, state temizle

    def set_context(self, ctx):
        super().set_context(ctx)          # "app" anahtarını çeker
        self._refresh_spectrum_list()

    # ================================================================
    # Yardımcılar
    # ================================================================
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

    # ================================================================
    # Analiz — thread'li
    # ================================================================
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
            run_modal=self._run_modal,
            run_spectral=self._run_spectral,
            run_takeoff=self._run_takeoff,
            spectrum_name=self._spectrum_name or None,
        )

        self._is_running = True
        self._status_msg = "⏳ Analiz çalışıyor..."
        self._t0 = time.time()

        def _worker():
            try:
                result = AnalysisService.run(scene, project, opts)
                self._result_queue.put(("ok", result))
            except AnalysisValidationError as e:
                # Auto-mesh gibi "soft" hatalar çözümü engellememeli.
                # Sert hatalar (eksik malzeme, boş DOF, vs.) hâlâ engeller.
                logger.warning("[AnalysisPanel] Doğrulama uyarıları: %s", e)
                result = AnalysisService.run(scene, project, opts)
                self._result_queue.put(("ok", result))
            except Exception as e:
                logger.exception("[AnalysisPanel] worker hatası")
                self._result_queue.put(("err", str(e)))

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
            self._bundle = payload
            r = payload
            parts = [f"{elapsed:.2f}s"]
            if r.result:
                parts.append(f"Frame={r.result.stiffness.frame_count}")
                if r.result.modal:
                    parts.append(f"n_modes={r.result.modal.n_modes}")
            if r.takeoff:
                parts.append(f"kütle={r.takeoff.total_mass_kg:.1f} kg")
            if r.errors:
                parts.append(f"{len(r.errors)} hata")
            self._status_msg = "✓ " + ", ".join(parts)
        else:
            self._status_msg = f"Hata: {payload}"

    # ================================================================
    # İçerik — BasePanel.draw_content() override
    # ================================================================
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

    # ================================================================
    # Seçenekler
    # ================================================================
    def _draw_options(self):
        imgui.text_colored(imgui.ImVec4(0.9, 0.85, 0.5, 1.0), "Analiz Seçenekleri")
        imgui.spacing()

        imgui.push_item_width(120)
        _, self._n_live = imgui.input_float(
            "n (live çarpanı)", self._n_live, step=0.05, format="%.3f"
        )
        self._n_live = max(0.0, min(1.0, self._n_live))

        _, self._n_modes = imgui.input_int("n_modes", self._n_modes, step=1)
        self._n_modes = max(1, min(100, self._n_modes))
        imgui.pop_item_width()

        _, self._run_modal = imgui.checkbox("Modal Analiz", self._run_modal)
        imgui.same_line()
        _, self._run_spectral = imgui.checkbox("Spectral Analiz", self._run_spectral)
        imgui.same_line()
        _, self._run_takeoff = imgui.checkbox("Metrajlar", self._run_takeoff)

        if self._run_spectral:
            self._refresh_spectrum_list()
            if not self._spectrum_names:
                imgui.text_colored(
                    imgui.ImVec4(0.9, 0.6, 0.3, 1.0),
                    "  Uyarı: projede spektrum tanımı yok.",
                )
            else:
                imgui.push_item_width(240)
                try:
                    cur = self._spectrum_names.index(self._spectrum_name)
                except ValueError:
                    cur = 0
                    self._spectrum_name = self._spectrum_names[0]
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
        label = "⏳ Çalışıyor..." if self._is_running else "▶ Analizi Çalıştır"
        if imgui.button(label, imgui.ImVec2(200, 32)) and not disabled:
            self._run_analysis()
        if disabled:
            imgui.pop_style_color(1)
            if not self._is_running:
                imgui.same_line()
                imgui.text_colored(
                    imgui.ImVec4(0.9, 0.6, 0.3, 1.0), "(sahne veya proje yok)"
                )

    # ================================================================
    # Hata bandı
    # ================================================================
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
        imgui.text_colored(imgui.ImVec4(1.0, 0.7, 0.7, 1.0), "⚠ Analiz uyarıları:")
        for e in self._bundle.errors:
            imgui.bullet_text(e)
        imgui.end_child()
        imgui.pop_style_color(1)
        imgui.spacing()

    # ================================================================
    # Sonuçlar — TEK tanım (çift tanım bug'ı düzeltildi)
    # ================================================================
    def _draw_results(self):
        if self._bundle is None or self._bundle.result is None:
            imgui.text_colored(imgui.ImVec4(1.0, 0.4, 0.4, 1.0), "Sonuç yok")
            return

        tabs = [
            ("Genel", self._draw_tab_genel, True),
            ("Kütle", self._draw_tab_kutle, False),
            ("Modal", self._draw_tab_modal, False),
        ]
        if self._bundle.spectral is not None:
            tabs.append(("Spectral", self._draw_tab_spectral, False))
        if self._bundle.takeoff is not None:
            tabs.append(("Metraj", self._draw_tab_metraj, False))

        for name, fn, default_open in tabs:
            flags = (
                imgui.TreeNodeFlags_.default_open if default_open else 0
            )
            if imgui.collapsing_header(name, flags=flags):
                try:
                    fn()
                except Exception:
                    logger.exception("[AnalysisPanel] %s sekmesi hatası", name)
                    imgui.text_colored(
                        imgui.ImVec4(1.0, 0.4, 0.4, 1.0),
                        f"⚠ {name} sekmesinde hata",
                    )

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
            if imgui.tree_node(f"Atlanan frame'ler ({len(r.stiffness.skipped)})"):
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

        warns = list(r.mass.warnings) + list(r.stiffness.warnings)
        if warns:
            imgui.separator()
            imgui.text_colored(imgui.ImVec4(0.9, 0.8, 0.4, 1.0), "Uyarılar:")
            for w in warns[:20]:
                imgui.text_colored(
                    imgui.ImVec4(0.9, 0.75, 0.5, 1.0), f"  • {w}"
                )
            if len(warns) > 20:
                imgui.text(f"  ... ve {len(warns) - 20} tane daha")

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
        from collections import defaultdict
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