# ui/ui_host.py
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Callable

from imgui_bundle import imgui

from assets.themes import _apply_dark_theme, _load_fonts
from inspector import InspectorWindow
from inspector.schemas import CatalogAdapter
from logging_config import CadLogger
from plane.plane import Plane
from plane.plane_source_dialog import PlaneSourceDialog
from ui.base.panel_base import CATEGORY_ORDER
from ui.context_menu import ContextMenuManager
from ui.context_resolvers import resolve_context
from ui.widgets.file_dialog import ImGuiFileDialog
from ui.widgets.status_bar import StatusBar
from ui.widgets.toolbar import Toolbar
from app.services.toolbar_specs import default_commands
from app.commands import project_commands as PC
from viewport.viewport_panel import ViewportPanel


if TYPE_CHECKING:
    from app.cad_app import CadApp

logger = CadLogger.get(__name__)


class UIHost:
    """Saf ImGui orkestratörü. GLFW, OpenGL ve domain iş mantığı bilmez."""

    def __init__(self, app: "CadApp"):
        self.app = app
        self.toolbar: Toolbar | None = None
        self.status_bar = StatusBar()
        self.file_dialog: ImGuiFileDialog | None = None
        self.plane_source_dialog: PlaneSourceDialog | None = None
        self.inspector: InspectorWindow | None = None
        self.context_menu = ContextMenuManager(self.app)

        self._is_resetting = False
        self._viewport_panels: list[ViewportPanel] = []
        self._last_active_viewport_name: str | None = None
        self._initialized = False

    def init_context(self) -> None:
        imgui.create_context()
        io = imgui.get_io()
        io.config_flags |= imgui.ConfigFlags_.docking_enable
        io.config_windows_move_from_title_bar_only = True
        _load_fonts(font_size=16)
        _apply_dark_theme()

    def on_engine_ready(self) -> None:
        reg = self.app.panel_registry

        self.file_dialog = ImGuiFileDialog()
        self.plane_source_dialog = PlaneSourceDialog(self)

        # Inspector — panel registry'den instance al, yoksa app ile kur
        self.inspector = reg.instance("inspector_panel")
        if not isinstance(self.inspector, InspectorWindow):
            self.inspector = InspectorWindow(app=self.app)
            from app.services.panel_registry import PanelEntry
            reg.register(PanelEntry(
                instance=self.inspector,
                name="inspector_panel",
                title="Inspector",
                category="Management",
                quick=True,
                shortcut="F10",
                menu_label="Inspector",
                icon="log-in",
                context=["app"],
            ))
        else:
            # registry'den geldiyse app'i bağla
            self.inspector.app = self.app
            self.inspector._bind_app()

        # catalog adapter (dict → protokol)
        from inspector.schemas import CatalogAdapter
        self.inspector.set_catalog(CatalogAdapter(self.app))

        # İlk açılışta seçim boş, proje bağlı
        self.inspector.set_selection([])

        # Toolbar
        self.toolbar = Toolbar(
            put_command=self.app.put_command,
            panel_registry=reg,
            extra_commands=default_commands(),
            app_getter=lambda: self.app,
        )

        self._ensure_default_viewport()
        self._initialized = True
        logger.info("[UIHost] Hazır (%d panel)", len(reg.all()))

    def shutdown(self) -> None:
        self._viewport_panels.clear()
        self._last_active_viewport_name = None
        self._initialized = False

    # ------------------------------------------------------------------
    # MODAL DİYALOGLAR (ImGui pencere kararları)
    # ------------------------------------------------------------------
    def open_open_dialog(self, on_select: Callable[[str], None]) -> None:
        if self.file_dialog is not None:
            self.file_dialog.open(
                mode="open",
                filters=[".cd4"],
                title="Proje Aç",
                initial_dir=os.getcwd(),
                on_select=on_select,
            )

    def open_save_dialog(self, on_select: Callable[[str], None]) -> None:
        if self.file_dialog is not None:
            self.file_dialog.open(
                mode="save",
                filters=[".cd4"],
                title="Projeyi Kaydet",
                initial_dir=os.getcwd(),
                default_name="model.cd4",
                on_select=on_select,
            )

    def open_plane_source_dialog(self) -> None:
        if self.plane_source_dialog is not None:
            self.plane_source_dialog.open()

    def prepare_panel(self, name: str, panel: Any) -> None:
        """Paneli açılmadan önce güncel uygulama bağlamıyla hazırlar."""
        entry = self.app.panel_registry.get(name)
        if entry is None:
            return
        context = resolve_context(self, self.app, entry.context)
        setter = getattr(panel, "set_context", None)
        if callable(setter):
            setter(context)

    # ------------------------------------------------------------------
    # ÇİZİM DÖNGÜSÜ
    # ------------------------------------------------------------------
    def notify_key(self, key: int, action: int, mods: int) -> None:
        self.status_bar.notify_key(key, action, mods)

    def log_command_result(self, text: str, level: str = "info") -> None:
        panel = self.app.panel_registry.instance("command_panel")
        if panel is not None and hasattr(panel, "append_result"):
            panel.append_result(text, level=level)
        self.status_bar.notify_command(text)

    def draw_frame(self, dt: float) -> None:
        if not self._initialized:
            return

        self._draw_dock_space()

        ps = self.app.project_service
        if self.toolbar is not None:
            self.toolbar.draw(
                model_text=ps.model_text,
                current_unit=ps.project.unit_system,
                project=ps.project,
            )

        self._draw_marquee_overlays()
        if self.file_dialog is not None:
            self.file_dialog.draw()

        for vp_panel in list(self._viewport_panels):
            vp_panel.draw()

        for entry in self.app.panel_registry.visible():
            if entry.instance is self.inspector:
                continue
            entry.instance.draw()

        if self.plane_source_dialog is not None:
            self.plane_source_dialog.draw()
        if self.inspector is not None:
            self.inspector.draw()

        self._forward_viewport_mouse_events()

        eng = self.app.engine
        inp = eng.input.state if eng else None
        is_drawing = bool(eng and eng.draw_mgr and eng.draw_mgr.is_active)
        app_status = "Çizim Aktif" if is_drawing else self.status_bar.last_event_text

        vm = self.app.viewport_manager
        active_vp = vm.active if vm is not None else None
        active_plane = getattr(active_vp, "plane", None) if active_vp is not None else None
        ucs_name = active_plane.name if active_plane is not None else "Global"
        ucs_pos = getattr(eng.input, "mouse_ucs_pos", None) if (eng and eng.input) else None

        self.status_bar.draw(
            engine_connected=(eng is not None),
            app_status=app_status,
            mouse_pos=(inp.mouse_pos.x, inp.mouse_pos.y) if inp else (0.0, 0.0),
            mouse_buttons=inp.buttons if inp else {},
            modifiers=inp.modifiers if inp else 0,
            fps=(1.0 / dt) if dt > 0 else 0.0,
            ucs_name=ucs_name,
            ucs_pos=ucs_pos,
        )

    def _draw_dock_space(self) -> None:
        viewport = imgui.get_main_viewport()
        work_pos = imgui.ImVec2(viewport.work_pos.x, viewport.work_pos.y)
        work_size = imgui.ImVec2(
            viewport.work_size.x,
            max(1.0, viewport.work_size.y - self.status_bar.height),
        )
        imgui.set_next_window_pos(work_pos)
        imgui.set_next_window_size(work_size)
        imgui.push_style_var(imgui.StyleVar_.window_rounding, 0.0)
        imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
        imgui.push_style_var(imgui.StyleVar_.window_padding, imgui.ImVec2(0.0, 0.0))
        flags = (
            imgui.WindowFlags_.no_title_bar
            | imgui.WindowFlags_.no_collapse
            | imgui.WindowFlags_.no_resize
            | imgui.WindowFlags_.no_move
            | imgui.WindowFlags_.no_bring_to_front_on_focus
            | imgui.WindowFlags_.no_nav_focus
            | imgui.WindowFlags_.no_docking
            | imgui.WindowFlags_.no_background
        )
        imgui.begin("##DockSpace", None, flags)
        imgui.pop_style_var(3)
        imgui.dock_space(imgui.get_id("DockSpace"))
        self.context_menu.render()
        imgui.end()

    # ------------------------------------------------------------------
    # VIEWPORT PENCERELERİ & FARE YÖNLENDİRME
    # ------------------------------------------------------------------
    def toggle_view_2d(self) -> None:
        self.command_queue.put(PC.Toggle2D())

    def _ensure_default_viewport(self) -> None:
        vm = self.app.viewport_manager
        if vm is None:
            return
        vp = vm.get("iso")
        if vp is None:
            vp = vm.create_viewport(name="iso", width=1200, height=800, preset="iso")
        vm.ensure_viewport_plane(vp, self.app.current_project)
        if not any(p.viewport_name == "iso" for p in self._viewport_panels):
            self._viewport_panels.append(ViewportPanel(self, "iso", vm))

    def open_viewport(self, preset: str):
        vm = self.app.viewport_manager
        if vm is None:
            return None
        name = vm.next_name(preset)
        vp = vm.create_viewport(name=name, width=800, height=600, preset=preset)
        vm.ensure_viewport_plane(vp, self.app.current_project)
        self._viewport_panels.append(ViewportPanel(self, name, vm))
        return vp

    def open_plane_viewport(self, plane, is_2d: bool = True):
        vm = self.app.viewport_manager
        if vm is None or plane is None:
            return None
        name = vm.next_name(f"Plane: {plane.name}")
        vp = vm.create_viewport(
            name=name, width=800, height=600,
            plane=plane, is_2d=is_2d,
        )
        self._viewport_panels.append(ViewportPanel(self, name, vm))
        return vp


    def close_all_viewports(self) -> None:
        vm = self.app.viewport_manager
        if vm is not None:
            for name in list(vm.viewports.keys()):
                vm.remove_viewport(name)
        self._viewport_panels.clear()
        self._last_active_viewport_name = None

    def on_viewport_panel_closed(self, panel: ViewportPanel) -> None:
        if panel in self._viewport_panels:
            self._viewport_panels.remove(panel)
        if self._last_active_viewport_name == panel.viewport_name:
            self._last_active_viewport_name = None

    def _forward_viewport_mouse_events(self) -> None:
        eng = self.app.engine
        vm = self.app.viewport_manager
        if eng is None or vm is None or not self._viewport_panels:
            return

        io = imgui.get_io()
        state = eng.input.state
        state.modifiers = (
            (1 if io.key_shift else 0)
            | (2 if io.key_ctrl else 0)
            | (4 if io.key_alt else 0)
            | (8 if io.key_super else 0)
        )

        target = next((p for p in self._viewport_panels if p._is_hovered), None)
        if target is None and (io.mouse_down[0] or io.mouse_down[1] or io.mouse_down[2]):
            if self._last_active_viewport_name:
                target = next(
                    (
                        p
                        for p in self._viewport_panels
                        if p.viewport_name == self._last_active_viewport_name
                    ),
                    None,
                )
        if target is None:
            return

        if self._last_active_viewport_name != target.viewport_name:
            vm.set_active(target.viewport_name)
            self._last_active_viewport_name = target.viewport_name

        vp = vm.get(target.viewport_name)
        if vp is None:
            return

        mouse = imgui.get_mouse_pos()
        x_px = int(mouse.x - target._item_min.x)
        y_px = int(mouse.y - target._item_min.y)

        state.mouse_pos.x = float(x_px)
        state.mouse_pos.y = float(y_px)
        state.buttons[0] = bool(imgui.is_mouse_down(imgui.MouseButton_.left))
        state.buttons[1] = bool(imgui.is_mouse_down(imgui.MouseButton_.right))
        state.buttons[2] = bool(imgui.is_mouse_down(imgui.MouseButton_.middle))

        if target._is_hovered:
            eng.set_viewport_pointer(vp, x_px, y_px)
            eng.input.dispatch_move(
                x_px, y_px, float(io.mouse_delta.x), float(io.mouse_delta.y)
            )

        for btn_id, imgui_btn in (
            (0, imgui.MouseButton_.left),
            (2, imgui.MouseButton_.middle),
            (1, imgui.MouseButton_.right),
        ):
            if target._is_hovered and imgui.is_mouse_clicked(imgui_btn):
                eng.input.dispatch_click(x_px, y_px, btn_id)
            if imgui.is_mouse_released(imgui_btn):
                eng.input.dispatch_release(x_px, y_px, btn_id)

        if target._is_hovered:
            wheel = float(io.mouse_wheel)
            if wheel != 0.0:
                eng.input.dispatch_scroll(wheel)
                io.mouse_wheel = 0.0

    def _draw_marquee_overlays(self) -> None:
        eng = self.app.engine
        marquee = getattr(eng, "marquee", None) if eng else None
        if not marquee or not marquee.is_active:
            return
        coords = marquee.get_box_coords()
        if not coords:
            return
        panel = next(
            (p for p in self._viewport_panels if p.viewport_name == marquee.viewport_name),
            None,
        )
        if not panel:
            return

        x1, y1, x2, y2 = coords
        min_x, max_x = min(x1, x2), max(x1, x2)
        min_y, max_y = min(y1, y2), max(y1, y2)
        item_min = panel._item_min
        p0 = imgui.ImVec2(item_min.x + min_x, item_min.y + min_y)
        p1 = imgui.ImVec2(item_min.x + max_x, item_min.y + max_y)

        is_crossing = x2 < x1
        fill_color = (
            imgui.ImVec4(0.20, 0.85, 0.20, 0.22)
            if is_crossing
            else imgui.ImVec4(0.20, 0.50, 0.95, 0.22)
        )
        border_color = (
            imgui.ImVec4(0.30, 1.00, 0.30, 0.95)
            if is_crossing
            else imgui.ImVec4(0.40, 0.75, 1.00, 0.95)
        )
        draw_list = imgui.get_foreground_draw_list()
        draw_list.add_rect_filled(p0, p1, imgui.get_color_u32(fill_color))
        draw_list.add_rect(p0, p1, imgui.get_color_u32(border_color))

    # ------------------------------------------------------------------
    # PROJE / SEÇİM BİLDİRİMLERİ (Sadece kendi ImGui bileşenleri için)
    # ------------------------------------------------------------------
    def on_project_changed(self) -> None:
        if self.inspector is not None:
            self.inspector.set_catalog(CatalogAdapter(self.app))
        if self._initialized:
            self._ensure_default_viewport()

    def on_selection_changed(self, selected: list) -> None:
        self.status_bar.notify_selection(selected)
        if self.inspector is not None:
            self.inspector.set_selection(selected)
        for entry in self.app.panel_registry.all():
            callback = getattr(entry.instance, "on_selection_changed", None)
            if callable(callback):
                callback(selected)

    def reset_all(self) -> None:
        if self._is_resetting:
            return
        self._is_resetting = True
        try:
            for entry in self.app.panel_registry.all():
                panel = entry.instance
                panel.visible = False
                panel._preview_snapshot = None
                panel._original = None
                panel.draft = None
                panel._dirty = False

            self.close_all_viewports()
            self._ensure_default_viewport()
            self.app.command_queue.put(PC.ClearSelection())
        finally:
            self._is_resetting = False