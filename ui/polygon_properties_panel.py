# ui/polygon_properties_panel.py
from __future__ import annotations

from imgui_bundle import imgui

from data.enums import PolygonType
from domain.polygon import Polygon
from domain.plane import Plane
from ui.base_panel import BasePanel
from ui.widgets.color_picker import color_edit3


class PolygonPropertiesPanel(BasePanel):

    W = 360
    H = 340

    MODES = (
        ("single_point", "●", "Tek nokta"),
        ("rectangle", "▭", "Dikdörtgen"),
        ("sequential", "✎", "Sıralı"),
    )
    TYPES = ("GENERIC", "SURFACE_ONEWAY", "SURFACE_TWOWAY",
             "ZONE", "SECTION_CUT", "LOAD_AREA")
    DIST_TYPES = ("one_way_u1", "one_way_u2", "two_way")
    DIST_LABELS = ("U1", "U2", "TWO")

    def __init__(self):
        super().__init__(title="Polygon", width=self.W, height=self.H,
                         pos_first_use=(900, 100))
        self.app = None
        self.project = None
        self.context = None
        self._selected_ids: set[int] = set()
        self._drawing = False
        self._batch_type = 0
        self._batch_dist = 0
        self._batch_color = [0.8, 0.3, 0.8]

    # ------------------------------------------------------------------
    def set_context(self, ctx: dict):
        super().set_context(ctx)
        self.context = ctx
        self.project = ctx.get("project")

    def open(self, polygon: Polygon | None = None):
        super().open()
        if polygon is not None:
            self._selected_ids = {int(polygon.unique_id)}
        self._sync_from_selection()

    def on_selection_changed(self, selected: list):
        self._selected_ids = {
            int(e.unique_id) for e in selected
            if hasattr(e, "poly_type")
        }

    # ------------------------------------------------------------------
    def _polygons(self) -> list[Polygon]:
        if not self.project or not self._selected_ids:
            return []
        return [self.project.polygons[i] for i in self._selected_ids
                if i in self.project.polygons]

    def _one(self) -> Polygon | None:
        items = self._polygons()
        return items[0] if len(items) == 1 else None

    def _sync_from_selection(self):
        eng = getattr(self.app, "engine", None) if self.app else None
        sel = getattr(eng, "sel_mgr", None) if eng else None
        if sel:
            self._selected_ids = {
                int(e.unique_id) for e in sel.get_selected()
                if hasattr(e, "poly_type")
            }

    def _refresh_polygons(self):
        eng = getattr(self.app, "engine", None) if self.app else None
        pr = getattr(eng, "presentation_renderer", None) if eng else None
        if pr and self.project:
            pr.update_polygons(list(self.project.polygons.values()))

    # ------------------------------------------------------------------
    def draw_content(self):
        self._toolbar()
        imgui.separator()

        items = self._polygons()
        if not items:
            imgui.text_colored(imgui.ImVec4(0.6, 0.6, 0.6, 1.0),
                               "Hazır. Çizim modu seç veya polygon seç.")
            return

        if len(items) == 1:
            self._properties_single(items[0])
        else:
            self._properties_multi(items)

        if len(items) == 1:
            self._wind_zones_button(items[0])

    # ------------------------------------------------------------------
    def _toolbar(self):
        for mode, icon, tip in self.MODES:
            active = self._drawing and self._manager() and self._manager().is_active and self._manager().mode == mode
            if active:
                imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.2, 0.55, 0.3, 1.0))
            if imgui.button(icon, imgui.ImVec2(26, 24)):
                self._start_drawing(mode)
            if active:
                imgui.pop_style_color(1)
            if imgui.is_item_hovered():
                imgui.set_tooltip(tip)
            imgui.same_line(0, 2)

        imgui.same_line(0, 6)
        imgui.text("|")
        imgui.same_line(0, 6)

        items = self._polygons()
        enabled = bool(items)
        if not enabled:
            imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.3, 0.3, 0.3, 1.0))

        if imgui.button("⇄", imgui.ImVec2(26, 24)) and enabled:
            for p in items:
                self._auto_assoc(p)
        if imgui.is_item_hovered():
            imgui.set_tooltip("Frame assoc")
        imgui.same_line(0, 2)

        if imgui.button("⊞", imgui.ImVec2(26, 24)) and enabled:
            for p in items:
                self._to_plane(p)
        if imgui.is_item_hovered():
            imgui.set_tooltip("Plane düzlemine geç")
        imgui.same_line(0, 2)

        if imgui.button("🗑", imgui.ImVec2(26, 24)) and enabled:
            for p in list(items):
                self._delete(p)
        if imgui.is_item_hovered():
            imgui.set_tooltip("Sil")
        if not enabled:
            imgui.pop_style_color(1)

    # ------------------------------------------------------------------
    def _properties_single(self, p: Polygon):
        imgui.text_colored(imgui.ImVec4(0.5, 0.85, 1.0, 1.0),
                           f"{p.label or 'Polygon'} (id={p.unique_id})")
        self._combo("Tip", "##ptype", self.TYPES,
                    self._type_name(p), lambda i: self._set_type(p, i))
        self._color(p, on_change=lambda c: self._set_color(p, c))
        imgui.text(f"Köşe: {len(p.nodes)}   Assoc: {len(p.associated_frame_ids)}")
        self._combo("Dağıtım", "##dist", self.DIST_LABELS,
                    self._dist_index(p), lambda i: self._set_dist(p, i))
        if p.assigned_loads:
            imgui.separator()
            imgui.text_colored(imgui.ImVec4(0.85, 0.9, 0.95, 1.0), "Yükler")
            for load in p.assigned_loads:
                imgui.bullet_text(f"{load.pattern_name}: {load.value:.2f}")

    def _properties_multi(self, items: list[Polygon]):
        imgui.text_colored(imgui.ImVec4(0.5, 0.85, 1.0, 1.0),
                           f"{len(items)} polygon seçili")
        imgui.separator()

        imgui.text("Tip")
        imgui.same_line(80)
        imgui.push_item_width(-1)
        _, self._batch_type = imgui.combo("##btype", self._batch_type, self.TYPES)
        imgui.pop_item_width()

        imgui.text("Renk")
        imgui.same_line(80)
        _, new_rgb = color_edit3("##bcolor", list(self._batch_color))
        self._batch_color = list(new_rgb)

        imgui.text("Dağıtım")
        imgui.same_line(80)
        imgui.push_item_width(-1)
        _, self._batch_dist = imgui.combo("##bdist", self._batch_dist, self.DIST_LABELS)
        imgui.pop_item_width()

        imgui.spacing()
        if imgui.button("Tümüne Uygula", imgui.ImVec2(-1, 30)):
            self._apply_batch(items)

        imgui.spacing()
        total_nodes = sum(len(p.nodes) for p in items)
        total_assoc = sum(len(p.associated_frame_ids) for p in items)
        imgui.text(f"Köşe: {total_nodes}   Assoc: {total_assoc}")

    def _apply_batch(self, items: list[Polygon]):
        poly_type = getattr(PolygonType, self.TYPES[self._batch_type])
        dist = self.DIST_TYPES[self._batch_dist]
        color = [*self._batch_color, 1.0]
        for p in items:
            p.poly_type = poly_type
            p.transfer_dist_type = dist
            p.color = color
            p.mark_dirty()
        self._refresh_polygons()

    # ------------------------------------------------------------------
    def _combo(self, label, tag, items, current, on_change):
        imgui.text(label)
        imgui.same_line(80)
        imgui.push_item_width(-1)
        changed, idx = imgui.combo(tag, current, items)
        imgui.pop_item_width()
        if changed:
            on_change(idx)

    def _color(self, p: Polygon, on_change):
        imgui.text("Renk")
        imgui.same_line(80)
        rgb = list(p.color[:3]) if p.color else [0.8, 0.3, 0.8]
        changed, new_rgb = color_edit3("", rgb)
        if changed:
            on_change(list(new_rgb))

    @staticmethod
    def _type_name(p) -> int:
        try:
            return PolygonPropertiesPanel.TYPES.index(p.poly_type.name)
        except (ValueError, AttributeError):
            return 0

    def _set_type(self, p, idx):
        p.poly_type = getattr(PolygonType, self.TYPES[idx])
        p.mark_dirty()
        self._refresh_polygons()

    def _set_color(self, p, rgb):
        alpha = p.color[3] if p.color and len(p.color) > 3 else 1.0
        p.color = [*rgb, alpha]
        p.mark_dirty()
        self._refresh_polygons()

    def _dist_index(self, p) -> int:
        return self.DIST_TYPES.index(p.transfer_dist_type) \
            if p.transfer_dist_type in self.DIST_TYPES else 0

    def _set_dist(self, p, idx):
        p.transfer_dist_type = self.DIST_TYPES[idx]
        p.mark_dirty()

    # ------------------------------------------------------------------
    def _manager(self):
        eng = getattr(self.app, "engine", None) if self.app else None
        return getattr(eng, "draw_mgr", None) if eng else None

    def _start_drawing(self, mode: str):
        mgr = self._manager()
        if mgr is None:
            return
        if mgr.is_active and mgr.mode == mode:
            mgr.cancel()
            self._drawing = False
            return
        mgr.cancel()
        mgr.start(mode=mode)
        self._drawing = True

    def _auto_assoc(self, p: Polygon):
        if self.project is None:
            return
        plane = Plane.from_polygon(p)
        p.associated_frame_ids = [
            int(f.unique_id) for f in self.project.scene.frames.values()
            if plane.classify_element(f, "frame") != "OUTSIDE"
        ]
        p.mark_dirty()

    def _to_plane(self, p: Polygon):
        plane = Plane.from_polygon(p)
        self.project.add_plane(plane)
        self.project.activate_plane(plane)
        eng = getattr(self.app, "engine", None)
        if eng and eng.renderer:
            eng.renderer.update_geo(self.project)

    def _delete(self, p: Polygon):
        if self.project is None:
            return
        self.project.remove_polygon(p.unique_id)
        self._selected_ids.discard(p.unique_id)
        eng = getattr(self.app, "engine", None)
        if eng:
            if eng.presentation_renderer:
                eng.presentation_renderer.update_polygons(
                    list(self.project.polygons.values())
                )
            if eng.sel_mgr:
                eng.sel_mgr.clear()

    # ------------------------------------------------------------------
    def _wind_zones_button(self, p: Polygon):
        if not p.zone_children_by_direction:
            return
        imgui.separator()
        total = sum(len(v) for v in p.zone_children_by_direction.values())
        imgui.text_colored(imgui.ImVec4(0.85, 0.9, 0.95, 1.0),
                           f"Rüzgar Zone'ları: {total}")
        dirs = list(p.zone_children_by_direction.keys())
        cur = dirs.index(p.show_zones_direction) + 1 \
              if p.show_zones_direction in dirs else 0
        labels = ["Kapalı"] + dirs
        imgui.push_item_width(-1)
        changed, idx = imgui.combo("##zone_dir", cur, labels)
        imgui.pop_item_width()
        if changed:
            p.show_zones_direction = None if idx == 0 else dirs[idx - 1]
            p.mark_dirty()
            self._refresh_polygons()