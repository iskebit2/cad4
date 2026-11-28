# ui/panels/polygon/polygon_panel.py
from __future__ import annotations

from imgui_bundle import imgui

from app.settings.categories import Category
from domain.element import Frame, Link
from domain.polygon import Polygon
from tools.area_to_frame import AreaToFrame
from ui.base.inspector_panel import InspectorPanel
from ui.panels.polygon.assign_load_tab import AssignLoadTab
from ui.panels.polygon.frame_assoc_tab import FrameAssocTab
from ui.panels.polygon.frame_transfer_tab import FrameTransferTab
from ui.panels.polygon.geometry_tab import GeometryTab
from ui.panels.polygon.load_manager_tab import LoadManagerTab
from ui.panels.polygon.topbar import TopBar
from ui.panels.polygon.wind_zones_tab import WindZonesTab


class PolygonPanel(InspectorPanel):
    panel_name = "polygon_properties"
    title = "Polygon"
    category = Category.DRAW
    context = ("project", "engine", "selection_polygons")
    width = 620
    height = 700
    pos_first_use = (900.0, 100.0)
    preview_flags = {"zones": False, "polygon": True}

    def __init__(self, app=None, **overrides) -> None:
        super().__init__(app=app, **overrides)
        self.project = None
        self.engine = None
        self.selection_polygons: list[Polygon] = []
        self.top_bar = TopBar(domain="polygon")
        self.geometry_tab = GeometryTab()
        self.assoc_tab = FrameAssocTab()
        self.assign_load_tab = AssignLoadTab()
        self.load_manager_tab = LoadManagerTab()
        self.wind_zones_tab = WindZonesTab()
        self.frame_transfer_tab = FrameTransferTab()
        self._active_tab = "geometry"

    def _on_context_ready(self) -> None:
        self._on_selection_changed(self.selection_polygons)

    def on_selection_changed(self, selected: list) -> None:
        if self.visible and self._active_tab == "assoc":
            return
        polys = [e for e in selected if isinstance(e, Polygon)]
        self._on_selection_changed(polys)
        self._sync_preview()

    def close(self) -> None:
        self._clear_preview()
        if self.engine and getattr(self.engine, "input", None):
            self.engine.input.set_context_pick_handler(None)
        super().close()

    def draw_content(self) -> None:
        self._update_pick_handler()
        if self.project is None:
            return
        self.top_bar.draw(self.ctx)
        imgui.separator()

        poly = self.ctx.primary if isinstance(self.ctx.primary, Polygon) else None
        if poly is None:
            self._clear_preview()
            imgui.text_disabled("Sahnede bir polygon seçin.")
            return

        service = AreaToFrame(self.project)
        if imgui.begin_tab_bar("##polygon_inspector_tabs"):
            if imgui.begin_tab_item("Geometri")[0]:
                self._active_tab = "geometry"
                self.geometry_tab.draw(self.ctx, poly)
                imgui.end_tab_item()
            if imgui.begin_tab_item("Frame Assoc")[0]:
                self._active_tab = "assoc"
                if self.assoc_tab.draw(self.ctx, poly, service):
                    self._sync_preview()
                imgui.end_tab_item()
            if imgui.begin_tab_item("Yük Ata")[0]:
                self._active_tab = "assign"
                self.assign_load_tab.draw(self.ctx, poly, service)
                imgui.end_tab_item()
            if imgui.begin_tab_item("Yük Yönetimi")[0]:
                self._active_tab = "loads"
                self.load_manager_tab.draw(self.ctx, poly, service)
                imgui.end_tab_item()
            if imgui.begin_tab_item("Rüzgar & Zone")[0]:
                self._active_tab = "zones"
                self.wind_zones_tab.draw(self.ctx, poly)
                imgui.end_tab_item()
            if imgui.begin_tab_item("Frame Aktarım")[0]:
                self._active_tab = "transfer"
                self.frame_transfer_tab.draw(self.ctx, poly, service)
                imgui.end_tab_item()
            imgui.end_tab_bar()

    def _update_pick_handler(self) -> None:
        if self.engine is None or getattr(self.engine, "input", None) is None:
            return
        if self.visible and self._active_tab == "assoc":
            self.engine.input.set_context_pick_handler(self._viewport_assoc_click)
        else:
            self.engine.input.set_context_pick_handler(None)

    def _viewport_assoc_click(self, x: float, y: float, button: int) -> bool:
        if button != 0 or self.assoc_tab.draft is None or self.project is None:
            return False
        vp = getattr(self.engine.viewport_manager, "active", None)
        pick_pass = getattr(self.engine.renderer, "pick_pass", None)
        if vp is None or pick_pass is None:
            return False
        el = vp.pick_at_neighborhood(pick_pass, int(x), int(y), radius=3)
        if not isinstance(el, (Frame, Link)):
            return False
        uid = int(el.unique_id)
        service = AreaToFrame(self.project)
        service.toggle(self.assoc_tab.draft, uid, uid not in self.assoc_tab.draft.associated)
        self._sync_preview()
        return True

    def _sync_preview(self) -> None:
        renderer = getattr(self.engine, "renderer", None) if self.engine else None
        if renderer is None:
            return
        preview = self.assoc_tab.build_preview() if self._active_tab == "assoc" else None
        renderer.set_assoc_preview(preview)

    def _clear_preview(self) -> None:
        renderer = getattr(self.engine, "renderer", None) if self.engine else None
        if renderer is not None:
            renderer.set_assoc_preview(None)