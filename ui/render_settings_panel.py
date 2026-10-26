# ui/render_settings_panel.py
from __future__ import annotations
from typing import Optional
import imgui
from ui.base_panel import BasePanel
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class RenderSettingsPanel(BasePanel):
    def __init__(self):
        self.visible = False
        self.renderer = None
        self.scene = None

        # UI cache
        self._node_point_size = 4.0
        self._node_symbol_size = 1.0
        self._axes_scale = 1.0
        self._load_scale = 1.0
        self._anim_dur = 2.0

    def set_context(self, ctx: dict):
        logger.info("[RenderSettings] set_context keys=%s renderer=%r",
                list(ctx.keys()), ctx.get("renderer"))
        self.renderer = ctx.get("renderer")
        self.scene = ctx.get("scene")
        self._sync_from_renderer()

    def _sync_from_renderer(self):
        """Renderer'daki mevcut değerleri UI cache'ine çek."""
        r = self.renderer
        if r is None:
            return
        try:
            if r.node_r:
                self._node_point_size = getattr(r.node_r, "_point_size", self._node_point_size)
                self._node_symbol_size = getattr(r.node_r, "_node_size", self._node_symbol_size)
            if self.scene:
                self._axes_scale = getattr(self.scene, "show_local_axes_scale", 1.0)
            self._load_scale = getattr(r, "_load_scale_override", 1.0)
        except Exception:
            logger.exception("[RenderSettings] sync hatası")

    def open(self):  self.visible = True
    def close(self): self.visible = False

    def draw(self):
        if not self.visible:
            return
        imgui.set_next_window_size(420, 640, imgui.ONCE)
        expanded, opened = imgui.begin("Render Ayarları", True)
        if not opened:
            self.close(); imgui.end(); return

        if self.renderer is None:
            imgui.text_colored("Aktif renderer yok.", 1.0, 0.6, 0.3)
            imgui.end(); return

        self._draw_render_mode()
        imgui.separator()
        self._draw_visibility()
        imgui.separator()
        self._draw_nodes()
        imgui.separator()
        self._draw_lights()
        imgui.separator()
        self._draw_local_axes()
        imgui.separator()
        self._draw_loads()
        imgui.separator()
        self._draw_animation()

        imgui.end()

    # ---------------- bölümler ----------------
    def _draw_render_mode(self):
        r = self.renderer
        imgui.text("Render Modu")
        for i, mode in enumerate(r.RENDER_MODES):
            if i: imgui.same_line()
            if imgui.radio_button(mode.capitalize(), r.render_mode == mode):
                r.set_render_mode(mode)

    def _draw_visibility(self):
        r = self.renderer
        imgui.text("Görünürlük")
        items = [
            ("grid", "Grid"), ("axes", "Axes"),
            ("frame", "Frames"), ("area", "Areas"),
            ("link", "Links"), ("node", "Nodes"),
            ("polygon", "Polygons"), ("restraint", "Restraints"),
        ]
        for i, (k, label) in enumerate(items):
            if i and i % 2: imgui.same_line()
            changed, v = imgui.checkbox(label, r.show.get(k, True))
            if changed:
                r.set_show(k, v)

        # --- Loads (özel: iki katman senkron) ---
        changed, v = imgui.checkbox("Loads", r.show.get("loads", False))
        if changed:
            if hasattr(r, "set_loads_enabled"):
                r.set_loads_enabled(v)
            else:
                r.set_show("loads", v)

    def _draw_nodes(self):
        r = self.renderer
        imgui.text("Node")
        changed, v = imgui.slider_float(
            "Point Size##node_ps", self._node_point_size, 1.0, 20.0, "%.1f px"
        )
        if changed:
            self._node_point_size = v
            r.set_node_point_size(v)

        changed, v = imgui.slider_float(
            "Symbol Size##node_ss", self._node_symbol_size, 0.1, 5.0, "%.2f"
        )
        if changed:
            self._node_symbol_size = v
            r.set_node_size(v, rebuild=False)
        imgui.same_line()
        if imgui.button("Yeniden İnşa##node_rebuild"):
            r.set_node_size(self._node_symbol_size, rebuild=True)

    def _draw_lights(self):
        r = self.renderer
        imgui.text("Işık")
        changed, v = imgui.checkbox("Işıkları Kullan", r.use_lights)
        if changed:
            r.set_use_lights(v)
        # TODO: LightingSystem parametreleri

    def _draw_local_axes(self):
        r, sc = self.renderer, self.scene
        imgui.text("Local Axes")
        if sc is None:
            imgui.text_colored("Sahne yok.", 0.8, 0.8, 0.3)
            return
        changed, _ = imgui.checkbox("Eksenleri Göster",
                                    bool(getattr(sc, "show_local_axes", False)))
        if changed:
            r.toggle_local_axes()
        changed, _ = imgui.checkbox("Sadece Seçililerde",
                                    bool(getattr(sc, "show_local_axes_for_selected", True)))
        if changed:
            r.toggle_local_axes_selected_only()

        changed, v = imgui.slider_float("Ölçek##axes", self._axes_scale, 0.1, 5.0, "%.2f")
        if changed:
            self._axes_scale = v
            r.set_local_axes_scale(v)

    def _draw_loads(self):
        r = self.renderer
        imgui.text("Yükler")
        enabled = bool(r.show.get("loads", False))
        changed, v = imgui.checkbox("Yükleri Göster", enabled)
        if changed:
            r.set_loads_enabled(v)
        changed, v = imgui.slider_float("Yük Ölçeği", self._load_scale, 0.1, 5.0, "%.2f")
        if changed:
            self._load_scale = v
            r.set_load_scale(v)

    def _draw_animation(self):
        r = self.renderer
        imgui.text("Animasyon")
        changed, v = imgui.slider_float("Süre", self._anim_dur, 0.5, 10.0, "%.1f s")
        if changed:
            self._anim_dur = v
        imgui.same_line()
        if imgui.button("Başlat"):
            r.start_anim(self._anim_dur)