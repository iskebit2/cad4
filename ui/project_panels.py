# ui/project_panels.py
# ui/project_panels.py (AnalysisManagerPanel kısmı)

from __future__ import annotations

import threading
from queue import Queue, Empty
from typing import Optional

import imgui

from core.analysis.run import AnalysisService, AnalysisOptions, AnalysisBundle
from logging_config import CadLogger
from ui.base_panel import BasePanel

logger = CadLogger.get(__name__)


class AnalysisManagerPanel(BasePanel):
    """Analiz yöneticisi — thread'li çalıştırma + hata bandı + progress."""

    def __init__(self):
        self.visible = False
        self.app = None
        self.title = "Analiz Yöneticisi"

        # Seçenekler
        self._n_live = 0.3
        self._n_modes = 12
        self._run_modal = True
        self._run_spectral = False
        self._run_takeoff = True
        self._spectrum_name = ""
        self._spectrum_names: list[str] = []

        # Sonuç / durum
        self._bundle: Optional[AnalysisBundle] = None
        self._active_tab = 0
        self._status_msg = ""

        # Thread state
        self._worker: Optional[threading.Thread] = None
        self._result_queue: Queue = Queue()
        self._is_running = False
        self._t0 = 0.0

    # ------------------------------------------------------------------
    def open(self):
        self.visible = True
        self._refresh_spectrum_list()

    def close(self):
        self.visible = False

    def set_context(self, ctx: dict):
        for k, v in ctx.items():
            setattr(self, k, v)
        self._refresh_spectrum_list()

    # ------------------------------------------------------------------
    def _project(self):
        if self.app is not None:
            return getattr(self.app, "current_project", None)
        return None

    def _scene(self):
        if self.app is not None and getattr(self.app, "engine", None):
            return self.app.engine.scene
        return None

    def _refresh_spectrum_list(self):
        project = self._project()
        self._spectrum_names = (
            list(project.spectrum_functions.keys()) if project else []
        )

    # ------------------------------------------------------------------
    # ANALİZ — thread'li
    # ------------------------------------------------------------------
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

        import time
        self._t0 = time.time()

        def _worker():
            try:
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
        import time
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
            self._active_tab = 0
        else:
            self._status_msg = f"Hata: {payload}"

    # ------------------------------------------------------------------
    # DRAW
    # ------------------------------------------------------------------
    def draw(self):
        if not self.visible:
            return

        imgui.set_next_window_size(900, 700, imgui.FIRST_USE_EVER)
        expanded, opened = imgui.begin(self.title, True)
        if not opened:
            self.close()
            imgui.end()
            return

        self._poll_result()

        try:
            self._draw_options()
            imgui.separator()

            self._draw_error_banner()

            if self._bundle is not None:
                self._draw_results()
            else:
                imgui.text_colored(
                    "Henüz analiz çalıştırılmadı. 'Analizi Çalıştır'a bas.",
                    0.7, 0.8, 0.6, 1.0,
                )

            if self._status_msg:
                imgui.separator()
                color = (1.0, 0.5, 0.3, 1.0) if self._is_running else (
                    (0.4, 1.0, 0.4, 1.0) if self._status_msg.startswith("✓")
                    else (0.9, 0.7, 0.4, 1.0)
                )
                imgui.text_colored(self._status_msg, *color)

                if self._is_running:
                    imgui.same_line()
                    imgui.text("  ")
                    imgui.same_line()
                    # basit spinner
                    import time
                    dots = "." * (int(time.time() * 2) % 4)
                    imgui.text_colored(dots, 1.0, 0.9, 0.4, 1.0)
        finally:
            imgui.end()

    # ------------------------------------------------------------------
    def _draw_options(self):
        imgui.text_colored("Analiz Seçenekleri", 0.9, 0.85, 0.5, 1.0)
        imgui.spacing()

        imgui.push_item_width(120)
        _, self._n_live = imgui.input_float(
            "n (live çarpanı)", self._n_live, step=0.05, format="%.3f",
        )
        self._n_live = max(0.0, min(1.0, self._n_live))

        _, self._n_modes = imgui.input_int(
            "n_modes", self._n_modes, step=1,
        )
        self._n_modes = max(1, min(100, self._n_modes))
        imgui.pop_item_width()

        _, self._run_modal = imgui.checkbox("Modal", self._run_modal)
        imgui.same_line()
        _, self._run_spectral = imgui.checkbox("Spectral", self._run_spectral)
        imgui.same_line()
        _, self._run_takeoff = imgui.checkbox("Metraj", self._run_takeoff)

        if self._run_spectral:
            self._refresh_spectrum_list()
            if not self._spectrum_names:
                imgui.text_colored(
                    "  Uyarı: projede spektrum tanımı yok.",
                    0.9, 0.6, 0.3, 1.0,
                )
            else:
                imgui.push_item_width(240)
                try:
                    cur = self._spectrum_names.index(self._spectrum_name)
                except ValueError:
                    cur = 0
                    self._spectrum_name = self._spectrum_names[0]
                ch, idx = imgui.combo(
                    "Spektrum", cur, self._spectrum_names,
                )
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
            imgui.push_style_color(imgui.COLOR_BUTTON, 0.3, 0.3, 0.3, 1.0)

        label = "⏳ Çalışıyor..." if self._is_running else "▶ Analizi Çalıştır"
        if imgui.button(label, width=200, height=32) and not disabled:
            self._run_analysis()

        if disabled:
            imgui.pop_style_color(1)
            if not self._is_running:
                imgui.same_line()
                imgui.text_colored(
                    "(sahne veya proje yok)", 0.9, 0.6, 0.3, 1.0,
                )

    # ------------------------------------------------------------------
    def _draw_error_banner(self):
        if self._bundle is None or not self._bundle.errors:
            return

        imgui.push_style_color(imgui.COLOR_CHILD_BACKGROUND, 0.35, 0.12, 0.12, 1.0)
        imgui.begin_child("##err_banner", height=min(20 + 18 * len(self._bundle.errors), 120), border=True)
        imgui.text_colored("⚠ Analiz uyarıları:", 1.0, 0.7, 0.7, 1.0)
        for e in self._bundle.errors:
            imgui.bullet_text(e)
        imgui.end_child()
        imgui.pop_style_color(1)
        imgui.spacing()

    # ------------------------------------------------------------------
    # SONUÇLAR — sekmeler
    # ------------------------------------------------------------------
    def _draw_results(self):
        if self._bundle is None or self._bundle.result is None:
            imgui.text_colored("Sonuç yok", 1.0, 0.4, 0.4, 1.0)
            return

        try:
            if imgui.collapsing_header("Genel", flags=imgui.TREE_DEFAULT_OPEN)[0]:
                self._draw_tab_genel()
        except Exception:
            logger.exception("Genel hata")
            imgui.text_colored("⚠ Genel hata", 1.0, 0.4, 0.4, 1.0)

        try:
            if imgui.collapsing_header("Kütle")[0]:
                self._draw_tab_kütle()
        except Exception:
            logger.exception("Kütle hata")
            imgui.text_colored("⚠ Kütle hata", 1.0, 0.4, 0.4, 1.0)

        try:
            if imgui.collapsing_header("Modal")[0]:
                self._draw_tab_modal()
        except Exception:
            logger.exception("Modal hata")
            imgui.text_colored("⚠ Modal hata", 1.0, 0.4, 0.4, 1.0)

        if self._bundle.spectral is not None:
            try:
                if imgui.collapsing_header("Spectral")[0]:
                    self._draw_tab_spectral()
            except Exception:
                logger.exception("Spectral hata")

        if self._bundle.takeoff is not None:
            try:
                if imgui.collapsing_header("Metraj")[0]:
                    self._draw_tab_metraj()
            except Exception:
                logger.exception("Metraj hata")


    

    # ---------------- Genel ----------------
    def _draw_results(self):
        if self._bundle is None or self._bundle.result is None:
            imgui.text_colored("Sonuç yok", 1.0, 0.4, 0.4, 1.0)
            return

        if imgui.collapsing_header("Genel")[0]:
            try:
                self._draw_tab_genel()
            except Exception:
                logger.exception("[AnalysisPanel] Genel hata")
                imgui.text_colored("⚠ Genel sekmesinde hata", 1.0, 0.4, 0.4, 1.0)

        if imgui.collapsing_header("Kütle")[0]:
            try:
                self._draw_tab_kütle()
            except Exception:
                logger.exception("[AnalysisPanel] Kütle hata")
                imgui.text_colored("⚠ Kütle sekmesinde hata", 1.0, 0.4, 0.4, 1.0)

        if imgui.collapsing_header("Modal")[0]:
            try:
                self._draw_tab_modal()
            except Exception:
                logger.exception("[AnalysisPanel] Modal hata")
                imgui.text_colored("⚠ Modal sekmesinde hata", 1.0, 0.4, 0.4, 1.0)

        if self._bundle.spectral is not None:
            if imgui.collapsing_header("Spectral")[0]:
                try:
                    self._draw_tab_spectral()
                except Exception:
                    logger.exception("[AnalysisPanel] Spectral hata")
                    imgui.text_colored("⚠ Spectral sekmesinde hata", 1.0, 0.4, 0.4, 1.0)

        if self._bundle.takeoff is not None:
            if imgui.collapsing_header("Metraj")[0]:
                try:
                    self._draw_tab_metraj()
                except Exception:
                    logger.exception("[AnalysisPanel] Metraj hata")
                    imgui.text_colored("⚠ Metraj sekmesinde hata", 1.0, 0.4, 0.4, 1.0)

    def _draw_tab_genel(self):
        r = self._bundle.result
        if r is None:
            imgui.text("Sonuç yok")
            return

        imgui.text(f"DOF: {r.K.shape[0]}")
        imgui.text(f"Mesnetli DOF: {len(r.fixed_dofs)}")
        imgui.text(f"Frame (eklendi/atlandı): "
                f"{r.stiffness.frame_count} / {len(r.stiffness.skipped)}")

        if r.stiffness.skipped:
            imgui.separator()
            if imgui.tree_node(f"Atlanan frame'ler ({len(r.stiffness.skipped)})"):
                for label, reason in r.stiffness.skipped[:50]:
                    imgui.text_colored(f"  {label}: {reason}", 0.9, 0.7, 0.4, 1.0)
                if len(r.stiffness.skipped) > 50:
                    imgui.text(f"  ... ve {len(r.stiffness.skipped) - 50} tane daha")
                imgui.tree_pop()

        warns = list(r.mass.warnings) + list(r.stiffness.warnings)
        if warns:
            imgui.separator()
            imgui.text_colored("Uyarılar:", 0.9, 0.8, 0.4, 1.0)
            for w in warns[:20]:
                imgui.text_colored(f"  • {w}", 0.9, 0.75, 0.5, 1.0)
            if len(warns) > 20:
                imgui.text(f"  ... ve {len(warns) - 20} tane daha")
    # ---------------- Kütle ----------------
    def _draw_tab_kütle(self):
        r = self._bundle.result
        if r is None:
            return
        m = r.mass

        imgui.text_colored("Kütle Özeti", 0.9, 0.85, 0.5, 1.0)
        imgui.spacing()

        def _row(label, val, unit):
            imgui.text(label)
            imgui.same_line(240)
            imgui.text_colored(f"{val:>14.3f} {unit}", 0.7, 0.9, 0.7, 1.0)

        _row("Öz kütle", m.total_self_kg, "kg")
        _row("Dead (ham)", m.total_dead_kg, "kg")
        _row(f"Live (ham, ×{m.n_live:.2f} → kullanılan)",
             m.total_live_kg, "kg")
        _row("Toplam (n uygulanmış)", m.total_kg, "kg")
        _row("Toplam", m.total_ton, "ton")

        imgui.separator()
        imgui.text_colored("Kaynak Dökümü", 0.9, 0.85, 0.5, 1.0)
        imgui.spacing()

        from collections import defaultdict
        agg = defaultdict(float)
        for c in m.contributions:
            agg[c.source_type] += c.mass_kg
        for st, val in sorted(agg.items()):
            imgui.text(f"  {st:20s}")
            imgui.same_line(240)
            imgui.text_colored(f"{val:>14.3f} kg", 0.7, 0.9, 0.7, 1.0)

    # ---------------- Modal ----------------
    def _draw_tab_modal(self):
        r = self._bundle.result
        if r is None or r.modal is None:
            imgui.text("Modal sonuç yok")
            return
        modal = r.modal

        imgui.text_colored(
            f"{modal.n_modes} mod | "
            f"Mx={modal.total_mass_x:.2f}, "
            f"My={modal.total_mass_y:.2f}, "
            f"Mz={modal.total_mass_z:.2f} kg",
            0.85, 0.85, 0.55, 1.0,
        )
        imgui.spacing()

        cols = ["#", "T (s)", "f (Hz)", "Γx", "Γy", "Γz", "MeffX", "MeffY"]
        if imgui.begin_table("##modal_table", len(cols)):
            for h in cols:
                imgui.table_setup_column(h)
            imgui.table_headers_row()

            for i in range(modal.n_modes):
                imgui.table_next_row()
                imgui.table_set_column_index(0)
                imgui.text(str(i + 1))
                imgui.table_set_column_index(1)
                imgui.text(f"{modal.periods[i]:.4f}")
                imgui.table_set_column_index(2)
                imgui.text(f"{modal.frequencies[i]:.3f}")
                imgui.table_set_column_index(3)
                imgui.text(f"{modal.participation_factor_x[i]:+.4f}")
                imgui.table_set_column_index(4)
                imgui.text(f"{modal.participation_factor_y[i]:+.4f}")
                imgui.table_set_column_index(5)
                imgui.text(f"{modal.participation_factor_z[i]:+.4f}")
                imgui.table_set_column_index(6)
                imgui.text(f"{modal.effective_mass_x[i]:.2f}")
                imgui.table_set_column_index(7)
                imgui.text(f"{modal.effective_mass_y[i]:.2f}")

            imgui.end_table()

    # ---------------- Spectral ----------------
    def _draw_tab_spectral(self):
        s = self._bundle.spectral
        if s is None:
            return
        import numpy as np
        imgui.text_colored(
            f"{len(s.modes)} mod | SRSS max UX={np.max(np.abs(s.ux_srss)):.4f} mm",
            0.85, 0.85, 0.55, 1.0,
        )
        imgui.text(f"SRSS max UY={np.max(np.abs(s.uy_srss)):.4f} mm, "
                   f"UZ={np.max(np.abs(s.uz_srss)):.4f} mm")
        imgui.separator()

        cols = ["#", "T (s)", "Sa (g)", "Γx", "Γy", "Γz"]
        if imgui.begin_table("##spectral_modes", len(cols)):
            for h in cols:
                imgui.table_setup_column(h)
            imgui.table_headers_row()

            for m in s.modes:
                imgui.table_next_row()
                imgui.table_set_column_index(0)
                imgui.text(str(m.mode))
                imgui.table_set_column_index(1)
                imgui.text(f"{m.period:.4f}")
                imgui.table_set_column_index(2)
                imgui.text(f"{m.spectral_acceleration:.4f}")
                imgui.table_set_column_index(3)
                imgui.text(f"{m.participation_x:+.4f}")
                imgui.table_set_column_index(4)
                imgui.text(f"{m.participation_y:+.4f}")
                imgui.table_set_column_index(5)
                imgui.text(f"{m.participation_z:+.4f}")
            imgui.end_table()

    # ---------------- Metraj ----------------
    def _draw_tab_metraj(self):
        t = self._bundle.takeoff
        if t is None:
            return
        imgui.text_colored(
            f"{len(t.elements)} eleman | toplam {t.total_mass_kg:.2f} kg "
            f"({t.total_mass_ton:.4f} ton), ağırlık {t.total_weight_kN:.3f} kN",
            0.85, 0.85, 0.55, 1.0,
        )
        imgui.separator()

        cols = ["Malzeme", "Adet", "Kütle (kg)", "Kütle (ton)", "Ağırlık (kN)"]
        if imgui.begin_table("##takeoff_material", len(cols)):
            for h in cols:
                imgui.table_setup_column(h)
            imgui.table_headers_row()
            for name, s in sorted(t.by_material.items()):
                imgui.table_next_row()
                imgui.table_set_column_index(0)
                imgui.text(name)
                imgui.table_set_column_index(1)
                imgui.text(str(s.element_count))
                imgui.table_set_column_index(2)
                imgui.text(f"{s.total_mass_kg:.2f}")
                imgui.table_set_column_index(3)
                imgui.text(f"{s.total_mass_kg / 1000.0:.4f}")
                imgui.table_set_column_index(4)
                imgui.text(f"{s.total_weight_kN:.4f}")
            imgui.end_table()

class ReportPanel(BasePanel):
    def __init__(self):
        super().__init__(title="Rapor", width=460, height=520, pos_first_use=(500, 150))
        self.log = "Report"

    def open(self, rep=None):
        super().open()
        self.log = rep
    

class ProjectInfoPanel(BasePanel):
    def __init__(self):
        super().__init__(title="Proje Bilgileri", width=460, height=520, pos_first_use=(500, 150))
        self.info = None            # ProjectInfo (name, description, author)
        self.general_info = None    # GeneralProjectInfo
        self.site_info = None       # SiteInformation
        self.on_apply = None
        self._bufs = {}             # input buffer'ları

    def open(self, info=None, general_info=None, site_info=None, on_apply=None):
        super().open()
        self.info = info
        self.general_info = general_info
        self.site_info = site_info
        self.on_apply = on_apply
        self._bufs.clear()

    def draw_content(self):
        # --- Genel Proje Bilgileri ---
        imgui.text_colored("Genel", 0.5, 0.8, 1.0, 1.0)
        imgui.separator()
        if self.general_info:
            self._field("Firma", "company_name", self.general_info)
            self._field("Müşteri", "client_name", self.general_info)
            self._field("Proje Adı", "project_name", self.general_info)
            self._field("Proje No", "project_number", self.general_info)
            self._field("Model Adı", "model_name", self.general_info)
            self._field("Revizyon", "revision_number", self.general_info)
            self._field("Mühendis", "engineer", self.general_info)
            self._field("Kontrol", "checker", self.general_info)
            self._field("Şef", "supervisor", self.general_info)

        imgui.spacing()
        # --- Saha Bilgileri ---
        imgui.text_colored("Saha", 0.5, 0.8, 1.0, 1.0)
        imgui.separator()
        if self.site_info:
            self._field("Zemin Sınıfı", "soil_class", self.site_info)
            self._field_float("Yatak Katsayısı", "subgrade_modulus_kn_m3", self.site_info)
            self._field_float("Hareketli Yük Kat.", "live_load_factor", self.site_info)
            self._field("Kadastro", "cadastral_info", self.site_info)
            self._field("Tarih", "date", self.site_info)

        imgui.spacing()
        # --- Metadata ---
        imgui.text_colored("Metadata", 0.5, 0.8, 1.0, 1.0)
        imgui.separator()
        if self.info:
            self._field("Proje Adı (Kısa)", "name", self.info)
            self._field("Yazar", "author", self.info)
            self._field("Açıklama", "description", self.info)

        # --- Apply butonu ---
        imgui.spacing()
        if imgui.button("Uygula", width=-1):
            if callable(self.on_apply):
                self.on_apply(self.info, self.general_info, self.site_info)

    def _field(self, label, attr, obj):
        val = getattr(obj, attr, "") or ""
        imgui.text(label + ":")
        imgui.same_line(200)
        imgui.push_item_width(-1)
        new_val = imgui.input_text(f"##{attr}", str(val), 256)[1]
        imgui.pop_item_width()
        if new_val != val:
            setattr(obj, attr, new_val)

    def _field_float(self, label, attr, obj):
        val = float(getattr(obj, attr, 0.0) or 0.0)
        imgui.text(label + ":")
        imgui.same_line(200)
        imgui.push_item_width(-1)
        new_val = imgui.input_float(f"##{attr}", val)[1]
        imgui.pop_item_width()
        if new_val != val:
            setattr(obj, attr, new_val)

class ProjectConfigPanel(BasePanel):
    def __init__(self):
        super().__init__(title="Proje Yapılandırması", width=420, height=520, pos_first_use=(520, 180))
        self.config = None
        self.on_apply = None

    def open(self, config=None, on_apply=None):
        super().open()
        self.config = config
        self.on_apply = on_apply

    def draw_content(self):
        if not self.config:
            imgui.text_colored("Config yok", 0.5, 0.5, 0.5, 1.0)
            return

        # --- Rüzgar ---
        if imgui.collapsing_header("Rüzgar (TS EN 1991-1-4)", True)[0]:
            w = self.config.wind
            self._float("vb0 (m/s)", w, "vb0")
            self._combo("Arazi Kat.", w, "terrain_category", ["I","II","III","IV"])
            self._float("z0", w, "z0")
            self._float("z1", w, "z1")
            self._float("z2", w, "z2")
            self._float("cpi+", w, "cpi_positive")
            self._float("cpi-", w, "cpi_negative")

        # --- Kar ---
        if imgui.collapsing_header("Kar (TS EN 1991-1-3)", True)[0]:
            s = self.config.snow
            self._float("sk (kN/m²)", s, "sk")
            self._float("Ce", s, "exposure_coefficient")
            self._float("Ct", s, "thermal_coefficient")
            self._float("μ", s, "shape_coefficient")

        # --- Deprem ---
        if imgui.collapsing_header("Deprem (TBDY 2018)", True)[0]:
            e = self.config.seismic
            self._float("Ss", e, "ss")
            self._float("S1", e, "s1")
            self._combo("Zemin", e, "soil_class", ["ZA","ZB","ZC","ZD","ZE","ZF"])
            self._float("Önem (I)", e, "importance_factor")
            self._float("R", e, "behavior_factor")
            self._float("D", e, "overstrength_factor")

        imgui.spacing()
        if imgui.button("Uygula", width=-1):
            if callable(self.on_apply):
                self.on_apply(self.config)

    def _float(self, label, obj, attr, step=0.1):
        val = float(getattr(obj, attr, 0.0))
        imgui.text(label); imgui.same_line(180)
        imgui.push_item_width(-1)
        new_val = imgui.input_float(f"##{attr}", val, step=step)[1]
        imgui.pop_item_width()
        if new_val != val:
            setattr(obj, attr, new_val)

    def _combo(self, label, obj, attr, choices):
        cur = str(getattr(obj, attr, ""))
        idx = choices.index(cur) if cur in choices else 0
        imgui.text(label); imgui.same_line(180)
        imgui.push_item_width(-1)
        new_idx = imgui.combo(f"##{attr}", idx, choices)[1]
        imgui.pop_item_width()
        if choices[new_idx] != cur:
            setattr(obj, attr, choices[new_idx])

