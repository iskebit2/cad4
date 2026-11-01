# ui/polygon_properties_panel.py
from __future__ import annotations

from imgui_bundle import imgui

from data.enums import PolygonType
from domain.element import Polygon
from domain.plane import Plane
from logging_config import CadLogger
from ui.base_panel import BasePanel
from ui.widgets.color_picker import color_edit3
from ui.zone_viewer_panel import ZoneViewerPanel

logger = CadLogger.get(__name__)


class PolygonPropertiesPanel(BasePanel):

    PANEL_W = 360
    PANEL_H = 300

    DRAW_MODE_ICONS = [
        ("single_point", "●", "Tek nokta (boundary analiz)"),
        ("rectangle", "▭", "Dikdörtgen (2 nokta)"),
        ("sequential", "✎", "Sıralı nokta"),
    ]

    POLYGON_TYPES = [
        "GENERIC", "SURFACE_ONEWAY", "SURFACE_TWOWAY",
        "ZONE", "SECTION_CUT", "LOAD_AREA",
    ]

    _zone_viewer: ZoneViewerPanel | None = None

    def __init__(self):
        super().__init__(
            title="Polygon",
            width=self.PANEL_W,
            height=self.PANEL_H,
            pos_first_use=(900, 100),
        )
        self.app = None
        self.scene = None
        self._selected_id: int | None = None
        self._drawing: bool = False
        self.context = None

    @classmethod
    def get_zone_viewer(cls) -> ZoneViewerPanel:
        if cls._zone_viewer is None:
            cls._zone_viewer = ZoneViewerPanel()
        return cls._zone_viewer

    def draw(self):
        super().draw()
        # ★ Zone viewer'ı buradan besle — sadece açıksa
        viewer = type(self)._zone_viewer
        if viewer is not None and viewer.visible:
            viewer.set_context(self.context)   # scene her frame taze
            viewer.draw()
    
    def _project(self):
        return getattr(self.app, "current_project", None) if self.app else None

    def set_context(self, ctx: dict):
        super().set_context(ctx)
        self.context = ctx
        self.scene = ctx.get("scene")

    def open(self, polygon: Polygon | None = None):
        super().open()
        if polygon is not None:
            self._selected_id = int(polygon.unique_id)

    def _polygon(self) -> Polygon | None:
        if self._selected_id is None or self.scene is None:
            return None
        return self.scene.polygons.get(self._selected_id)

    def draw_content(self):
        self._draw_toolbar()
        imgui.separator()

        p = self._polygon()
        if p is None:
            imgui.text_colored(
                imgui.ImVec4(0.6, 0.6, 0.6, 1.0),
                "Hazır. Çizim için bir mod seç veya mevcut polygon seç.",
            )
            return

        self._draw_properties(p)
        self._draw_wind_zones_button(p)
        

    # ------------------------------------------------------------------
    def _draw_toolbar(self):
        # Sol: çizim modları
        for mode, icon, tip in self.DRAW_MODE_ICONS:
            active = (
                self._drawing
                and self.app is not None
                and self.app.engine
                and self.app.engine.draw_mgr.is_active
                and self.app.engine.draw_mgr.mode == mode
            )
            if active:
                imgui.push_style_color(
                    imgui.Col_.button, imgui.ImVec4(0.20, 0.55, 0.3, 1.0)
                )
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

        # Assoc / Sil / Plane
        p = self._polygon()
        enabled = p is not None

        if not enabled:
            imgui.push_style_color(
                imgui.Col_.button, imgui.ImVec4(0.3, 0.3, 0.3, 1.0)
            )
        if imgui.button("⇄", imgui.ImVec2(26, 24)):
            if enabled:
                self._auto_assoc_frames(p)
        if imgui.is_item_hovered():
            imgui.set_tooltip("Otomatik frame assoc")
        imgui.same_line(0, 2)

        if imgui.button("⊞", imgui.ImVec2(26, 24)):
            if enabled:
                self._switch_to_plane(p)
        if imgui.is_item_hovered():
            imgui.set_tooltip("Plane düzlemine geç")
        imgui.same_line(0, 2)

        if imgui.button("🗑", imgui.ImVec2(26, 24)):
            if enabled:
                self._delete_polygon(p)
        if imgui.is_item_hovered():
            imgui.set_tooltip("Sil")
        if not enabled:
            imgui.pop_style_color(1)

    # ------------------------------------------------------------------
    def _draw_properties(self, p: Polygon):
        imgui.text_colored(
            imgui.ImVec4(0.5, 0.85, 1.0, 1.0),
            f"{p.label or 'Polygon'} (id={p.unique_id})",
        )

        # Tip
        imgui.text("Tip")
        imgui.same_line(80)
        try:
            cur_idx = self.POLYGON_TYPES.index(p.poly_type.name)
        except (ValueError, AttributeError):
            cur_idx = 0
        imgui.push_item_width(-1)
        changed, new_idx = imgui.combo("##ptype", cur_idx, self.POLYGON_TYPES)
        imgui.pop_item_width()
        if changed:
            p.poly_type = getattr(PolygonType, self.POLYGON_TYPES[new_idx])
            p.mark_dirty()
            if self.scene:
                self.scene.mark_dirty()

        # Renk — basit color_edit3
        imgui.text("Renk")
        imgui.same_line(80)
        color_rgb = list(p.color[:3]) if p.color else [0.8, 0.3, 0.8]
        changed, new_rgb = color_edit3("", color_rgb)
        if changed:
            alpha = p.color[3] if p.color and len(p.color) > 3 else 1.0
            p.color = [*new_rgb, alpha]
            p.mark_dirty()
            if self.scene:
                self.scene.mark_dirty()

        # Info
        imgui.text(f"Köşe: {len(p.nodes)}   Assoc: {len(p.associated_frame_ids)}")

        # Transfer
        imgui.text("Dağıtım")
        imgui.same_line(80)
        dist_types = ["one_way_u1", "one_way_u2", "two_way"]
        dist_labels = ["U1", "U2", "TWO"]
        cur = (
            dist_types.index(p.transfer_dist_type)
            if p.transfer_dist_type in dist_types else 0
        )
        imgui.push_item_width(-1)
        changed, new_idx = imgui.combo("##dist", cur, dist_labels)
        imgui.pop_item_width()
        if changed:
            p.transfer_dist_type = dist_types[new_idx]
            p.mark_dirty()

        # Yükler
        if p.assigned_loads:
            imgui.separator()
            imgui.text_colored(
                imgui.ImVec4(0.85, 0.9, 0.95, 1.0), "Yükler"
            )
            for load in p.assigned_loads:
                imgui.bullet_text(
                    f"{load.pattern_name}: {load.value:.2f}"
                )

    # ------------------------------------------------------------------
    def _start_drawing(self, mode: str):
        if self.app is None or not self.app.engine:
            return
        mgr = self.app.engine.draw_mgr
        if mgr is None:
            return
        # Aynı moddaysa iptal
        if mgr.is_active and mgr.mode == mode:
            mgr.cancel()
            self._drawing = False
            return
        mgr.cancel()
        mgr.start(mode=mode)
        self._drawing = True
        logger.info("[PolygonPanel] Çizim başladı: %s", mode)

    def _auto_assoc_frames(self, p: Polygon):
        if self.scene is None:
            return
        try:
            plane = Plane.from_polygon(p)
            ids = []
            for frame in self.scene.frames.values():
                status = plane.classify_element(frame, "frame")
                if status != "OUTSIDE":
                    ids.append(int(frame.unique_id))
            p.associated_frame_ids = ids
            p.mark_dirty()
            self.scene.mark_dirty()
            logger.info(
                "[PolygonPanel] %s: %d frame assoc", p.label, len(ids),
            )
        except Exception:
            logger.exception("[PolygonPanel] auto assoc hatası")

    def _switch_to_plane(self, p: Polygon):
        if self.app is None or self.scene is None:
            return
        try:
            plane = Plane.from_polygon(p)
            proj = self._project()
            if proj is not None:
                proj.add_plane(plane)
                proj.plane_mgr.activate(plane)
            if self.app.engine:
                self.app.engine.apply_plane_filter()
                if self.app.engine.renderer:
                    self.app.engine.renderer.update_geo(self.scene)
                if hasattr(self.app, "_toggle_2d"):
                    r = self.app.engine.renderer
                    if r and r.projection != "plane_2d":
                        self.app._toggle_2d()
            logger.info("[PolygonPanel] Plane aktif: %s", plane.name)
        except Exception:
            logger.exception("[PolygonPanel] plane geçişi hatası")

    def _delete_polygon(self, p: Polygon):
        if self.scene is None:
            return
        try:
            self.scene.remove_element(p)
            self._selected_id = None
            if self.app and self.app.engine:
                self.app.engine.renderer.update_geo(self.scene)
                self.app.engine.sel_mgr.clear()
            logger.info("[PolygonPanel] Silindi: %s", p.label)
        except Exception:
            logger.exception("[PolygonPanel] silme hatası")

    def _draw_wind_zones_button(self, p: Polygon):
        if not p.zone_children_by_direction:
            return
        imgui.separator()
        total = sum(len(v) for v in p.zone_children_by_direction.values())
        imgui.text_colored(
            imgui.ImVec4(0.85, 0.9, 0.95, 1.0),
            f"Rüzgar Zone'ları: {total}",
        )
        if imgui.button("Zone'ları Görüntüle (2D)", imgui.ImVec2(-1, 28)):
            viewer = self.get_zone_viewer()
            if self.context:
                viewer.set_context(self.context)   # scene vs. taşınır
                viewer.show_polygon(p)