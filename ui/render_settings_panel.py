# ui/render_settings_panel.py
from __future__ import annotations

from imgui_bundle import imgui

from logging_config import CadLogger
from ui.base_panel import BasePanel

logger = CadLogger.get(__name__)


class RenderSettingsPanel(BasePanel):

    def __init__(self):
        self.visible = False
        self.renderer = None
        self.scene_renderer = None
        self.math_model_renderer = None
        self.scene = None
        self.engine = None

        self._node_point_size = 4.0
        self._node_symbol_size = 1.0
        self._axes_scale = 1.0
        self._polygon_alpha = 0.5

    def set_context(self, ctx: dict):
        self.renderer = ctx.get("renderer")
        self.scene_renderer = ctx.get("scene_renderer") or self.renderer
        self.math_model_renderer = ctx.get("math_model_renderer")
        self.scene = ctx.get("scene")
        self.engine = ctx.get("engine")
        self._sync()

    def _sync(self):
        mr = self.math_model_renderer
        if mr is None:
            return
        if mr.node_r:
            self._node_point_size = getattr(mr.node_r, "_point_size", self._node_point_size)
            self._node_symbol_size = getattr(mr.node_r, "_node_size", self._node_symbol_size)
        if self.scene:
            self._axes_scale = getattr(self.scene, "show_local_axes_scale", 1.0)

    def open(self):
        self.visible = True

    def close(self):
        self.visible = False

    def draw(self):
        if not self.visible:
            return
        imgui.set_next_window_size(imgui.ImVec2(460, 760), imgui.Cond_.once)
        _, opened = imgui.begin("Render Ayarları", True)
        try:
            if not opened:
                self.close()
                return
            self._draw()
        finally:
            imgui.end()

    def _draw(self):
        if self.renderer is None:
            imgui.text_colored(imgui.ImVec4(1.0, 0.6, 0.3, 1.0), "Aktif renderer yok.")
            return

        self._draw_render_mode()
        imgui.separator()
        self._draw_visibility()
        imgui.separator()
        self._draw_grid()
        imgui.separator()
        self._draw_polygon_style()
        imgui.separator()
        self._draw_nodes()
        imgui.separator()
        self._draw_global_axis()
        imgui.separator()
        self._draw_local_axes()
        imgui.separator()
        self._draw_lighting()
        imgui.separator()
        self._draw_plane_preview()
        imgui.separator()
        self._draw_debug()

    # ------------------------------------------------------------------
    def _draw_render_mode(self):
        mr = self.math_model_renderer
        if mr is None:
            return
        imgui.text("Math Model Render Modu")
        for i, mode in enumerate(mr.RENDER_MODES):
            if i:
                imgui.same_line()
            if imgui.radio_button(mode.capitalize(), mr.render_mode == mode):
                mr.set_render_mode(mode)

    def _draw_visibility(self):
        mr = self.math_model_renderer
        sr = self.scene_renderer
        if mr is None or sr is None:
            return
        imgui.text("Görünürlük")
        items = [
            (mr.show, "frame", "Frames"),
            (mr.show, "node", "Nodes"),
            (mr.show, "area", "Areas"),
            (mr.show, "link", "Links"),
            (mr.show, "restraint", "Restraints"),
            (sr.show, "polygon", "Polygons"),
            (sr.show, "lines", "Lines"),
            (sr.show, "zones", "Zones"),
            (sr.show, "grid_labels", "Grid Labels"),
            (sr.show, "selected_labels", "Selected Labels"),
        ]
        for i, (store, key, label) in enumerate(items):
            if i and i % 2:
                imgui.same_line()
            current = store.get(key, True)
            changed, v = imgui.checkbox(label, current)
            if changed:
                store[key] = v
                self._refresh()

    def _draw_grid(self):
        eng = self.engine
        if eng is None:
            return
        imgui.text("Grid")
        changed, v = imgui.checkbox("Grid Göster##grid_show", eng.show.get("grid", True))
        if changed:
            eng.show["grid"] = v
        gr = getattr(eng, "grid", None)
        grid = getattr(gr, "grid", None) if gr else None
        if grid is not None:
            changed, v = imgui.checkbox("Grid Etiketleri", getattr(grid, "show_labels", True))
            if changed:
                grid.show_labels = v
                if gr is not None:
                    gr.mark_dirty()

    def _draw_polygon_style(self):
        sr = self.scene_renderer
        if sr is None:
            return
        imgui.text("Polygon Stili")
        changed, v = imgui.slider_float("Şeffaflık##poly_alpha", self._polygon_alpha, 0.0, 1.0, "%.2f")
        if changed:
            self._polygon_alpha = v
        imgui.text_colored(
            imgui.ImVec4(0.6, 0.6, 0.6, 1.0),
            f"(alpha={self._polygon_alpha:.2f}) — SceneRenderer._draw_polygons sabit",
        )

    def _draw_nodes(self):
        mr = self.math_model_renderer
        if mr is None:
            return
        imgui.text("Node")
        changed, v = imgui.slider_float(
            "Point Size##node_ps", self._node_point_size, 1.0, 30.0, "%.1f px",
        )
        if changed:
            self._node_point_size = v
            mr.set_node_point_size(v)
        changed, v = imgui.slider_float(
            "Symbol Size##node_ss", self._node_symbol_size, 0.1, 2.0, "%.2f",
        )
        if changed:
            self._node_symbol_size = v
            if hasattr(mr, "set_restraint_size"):
                mr.set_restraint_size(v)
            else:
                mr.set_node_size(v, rebuild=False)
        imgui.same_line()
        if imgui.button("Yeniden İnşa##node_rebuild"):
            mr.set_node_size(self._node_symbol_size, rebuild=True)

    def _draw_global_axis(self):
        eng = self.engine
        if eng is None:
            return
        imgui.text("Global Eksen")
        changed, v = imgui.checkbox("Global Eksen Göster", eng.show.get("global_axis", True))
        if changed:
            eng.show["global_axis"] = v

    def _draw_local_axes(self):
        sc = self.scene
        if sc is None:
            imgui.text_colored(imgui.ImVec4(0.8, 0.8, 0.3, 1.0), "Sahne yok.")
            return
        imgui.text("Local Axes")
        changed, v = imgui.checkbox(
            "Eksenleri Göster",
            bool(getattr(sc, "show_local_axes", False)),
        )
        if changed:
            sc.show_local_axes = v
            sc.mark_dirty()
        changed, v = imgui.checkbox(
            "Sadece Seçililerde",
            bool(getattr(sc, "show_local_axes_for_selected", True)),
        )
        if changed:
            sc.show_local_axes_for_selected = v
            sc.mark_dirty()
        changed, v = imgui.slider_float("Ölçek##axes", self._axes_scale, 0.1, 5.0, "%.2f")
        if changed:
            self._axes_scale = v
            sc.show_local_axes_scale = v
            sc.mark_dirty()

    def _draw_lighting(self):
        mr = self.math_model_renderer
        if mr is None:
            return
        imgui.text("Işık")
        changed, v = imgui.checkbox("Işıkları Kullan", mr.use_lights)
        if changed:
            mr.set_use_lights(v)

        lights = getattr(mr.lighting, "lights", None)
        if not lights:
            return
        for i, light in enumerate(lights):
            changed, enabled = imgui.checkbox(f"Işık {i + 1} Aktif##light_{i}", light.enabled)
            if changed:
                light.enabled = enabled
            if not light.enabled:
                continue
            imgui.push_item_width(120)
            changed, intensity = imgui.slider_float(
                f"Şiddet##light_{i}_int", float(light.intensity), 0.0, 3.0, "%.2f",
            )
            if changed:
                light.intensity = intensity
            imgui.pop_item_width()
            imgui.push_item_width(90)
            changed, direction = imgui.drag_float3(
                f"Yön##light_{i}_dir", list(light.direction), 0.01, 0.0, 0.0, "%.2f",
            )
            if changed:
                light.direction = [float(x) for x in direction]
            imgui.pop_item_width()
        changed, ambient = imgui.slider_float(
            "Ambient", float(getattr(mr.lighting, "ambient", 0.2)), 0.0, 1.0, "%.2f",
        )
        if changed:
            mr.lighting.ambient = ambient

    def _draw_plane_preview(self):
        eng = self.engine
        if eng is None:
            return
        imgui.text("Plane Önizleme")
        changed, v = imgui.checkbox(
            "Önizleme Göster",
            eng.interaction_renderer.preview_plane is not None,
        )
        if changed and not v:
            eng.interaction_renderer.preview_plane = None

    def _draw_debug(self):
        eng = self.engine
        if eng is None:
            return
        mr = self.math_model_renderer
        imgui.text("Debug")
        if mr is None:
            return
        if imgui.tree_node("Sayaçlar"):
            for label, r in (
                ("frame", mr.frame_r),
                ("node", mr.node_r),
                ("area", mr.area_r),
                ("link", mr.link_r),
            ):
                if r is not None:
                    imgui.text(f"{label}: elements={len(r.elements)} vcount={r.vcount} icount={r.icount}")
            imgui.tree_pop()
        if imgui.tree_node("State"):
            imgui.text(f"render_mode: {mr.render_mode}")
            imgui.text(f"use_lights: {mr.use_lights}")
            imgui.text(f"hover_id: {eng.hover_id}")
            imgui.text(f"hover_enabled: {eng.hover_enabled}")
            imgui.tree_pop()

    

    def _refresh(self):
        if self.engine and getattr(self.engine, "project", None):
            self.engine.update_geo(self.engine.project)