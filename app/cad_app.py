# app/cad_app.py

from __future__ import annotations
import time

from pathlib import Path

import glfw
from imgui_bundle import imgui
from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_BLEND, GL_COLOR_BUFFER_BIT, GL_CULL_FACE,
    GL_DEPTH_BUFFER_BIT, GL_DEPTH_TEST, GL_ELEMENT_ARRAY_BUFFER, GL_FRAMEBUFFER,
    GL_ONE_MINUS_SRC_ALPHA, GL_SRC_ALPHA,
    glBindBuffer, glBindFramebuffer, glBindVertexArray, glBlendFunc, glClear, glClearColor,
    glDisable, glEnable, glUseProgram, glViewport,
)

from app.app_actions import AppActions
from app.cad_window import CadWindow
from app.input_bindings import build_bindings
from app.panel_registry import PANEL_SPECS, PanelSpec
from app.toolbar import Toolbar
from core.gl_engine import Engine
from domain.project import Project
from inspector import InspectorWindow
from inspector.catalog_project import ProjectCatalog
from app.debug_panel import DebugPanel
from core.viewport_manager import ViewportManager
from plane.plane_source_dialog import PlaneSourceDialog
from ui.viewport_panel import ViewportPanel

from logging_config import CadLogger
logger = CadLogger.get(__name__)


class CadApp:

    def __init__(self, window: CadWindow):
        self.window = window
        self.engine: Engine | None = None
        self.initialized = False

        self.debug_panel = DebugPanel(self)

        self.current_project = Project()
        self.current_file_path: str | None = None
        self._model_text = "MODEL: NEW SCENE"
        self._catalog = ProjectCatalog(self.current_project)
        self.hover_visual_enabled = True
        
        self._show_only_ids: set[int] | None = None
        self.inspector: InspectorWindow | None = None
        self._io = None

        self.panels: dict[str, dict] = {}
        self._panels_by_category: dict[str, list[str]] = {}

        # Viewport sistemi (engine oluşturulunca doldurulur)
        self.viewport_manager = None
        self._viewport_panels: list = []
        self._last_active_viewport_name: str | None = None
        self.plane_source_dialog = PlaneSourceDialog(self)
        
        self.actions = AppActions(self)
        self._init_registry()

        self.toolbar = Toolbar(
            commands=self._build_toolbar_commands(),
            panel_states=self._build_panel_states(),
        )

        self._wire_panel_hooks()
        self._wire_window()

    # ------------------------------------------------------------------
    def _init_registry(self) -> None:
        for spec in PANEL_SPECS:
            if spec.kind != "panel" or spec.cls is None:
                continue
            inst = spec.cls()
            inst.app = self
            self.panels[spec.name] = {
                "instance": inst,
                "title": spec.title,
                "category": spec.category,
                "quick": spec.quick,
                "shortcut": spec.shortcut,
                "menu_label": spec.menu_label,
                "icon": spec.icon,
                "context": spec.context,
            }
            self._panels_by_category.setdefault(spec.category, []).append(spec.name)
            setattr(self, spec.name, inst)

    def _wire_panel_hooks(self) -> None:
        fl = self.panels.get("assign_frame_distributed_load", {}).get("instance")
        if fl:
            fl.on_apply = self.actions.apply_frame_load

        at = self.panels.get("area_to_frame", {}).get("instance")
        if at:
            at.on_transfer_complete = self.actions.on_area_transfer_complete

        rs = self.panels.get("render_settings", {}).get("instance")
        if rs:
            rs.get_loads_visible = self.actions.get_loads_visible
            rs.set_loads_visible = self.actions.set_loads_visible

        s2k = self.panels.get("s2k_panel", {}).get("instance")
        if s2k:
            s2k.on_import_complete = self.actions.on_s2k_import_complete
            s2k.get_project = lambda: self.current_project
            s2k.get_selected_elements = self._selected

        ins = self.panels.get("inspector", {}).get("instance")
        if ins:
            ins.app = self
            ins.set_catalog(self._catalog)

        wind = self.panels.get("wind_analysis", {}).get("instance")
        if wind:
            wind.on_run_analysis = self.actions.run_wind
            wind.on_select_direction = self.actions.select_wind_direction

    def _wire_window(self) -> None:
        self.window.on_resize = self._on_resize
        self.window.on_key = self._on_key
        self.window.on_mouse_button = self._on_mouse_button
        self.window.on_mouse_move = self._on_mouse_move
        self.window.on_scroll = self._on_scroll

    # ------------------------------------------------------------------
    def _on_resize(self, w, h) -> None:
        if self.engine:
            self.engine.resize(max(1, w), max(1, h))

    def _on_key(self, key, scancode, action, mods) -> None:
        
        if self.engine:
            self.engine.input.on_key(key, action, mods)

    def _on_mouse_button(self, button, action, mods) -> None:
        if self.engine:
            self.engine.input.on_mouse_button(button, action, mods)

    def _on_mouse_move(self, x, y) -> None:
        if self.engine:
            self.engine.input.on_mouse_move(x, y)

    def _on_scroll(self, xoff, yoff):
        if imgui.get_io().want_capture_mouse:
            return
        if imgui.is_window_hovered(imgui.HoveredFlags_.any_window):
            return
        if self.engine:
            self.engine.input.on_scroll(yoff)

    # ------------------------------------------------------------------
    def frame(self, dt: float) -> None:
        # t_start = time.perf_counter()
        self._ensure_engine()
        if not self.initialized:
            return
        if self._io is None:
            self._io = imgui.get_io()

        # ★ DockSpace (her frame, diğer pencerelerden önce)
        self._draw_dock_space()

        self.toolbar.draw(
            model_text=self._model_text,
            current_unit=self.current_project.unit_system if self.current_project else None,
            project=self.current_project,
        )
        self.actions.draw_dialog()
        self.actions.process_wind_queue()
        self._update_scene_if_dirty()
        self._render_scene(dt)               # viewport'ları render et (FBO)
        # t_render = time.perf_counter()
        self._draw_panels()                  # ImGui panelleri (viewport pencereleri dahil)
        self._forward_active_viewport_events()
        self.debug_panel.draw()

        self._consume_plane_completion()

        if self.engine and self.engine.pending_pick_check:
            self.engine.check_pick_result()

        # if time.perf_counter() - t_start > 0.033:
        #     logger.debug("[CadApp.frame] SLOW: %.1f ms (render: %.1f)", (time.perf_counter() - t_start) * 1000, (t_render - t_start) * 1000)

    def _ensure_engine(self) -> None:
        if self.initialized:
            return
        w, h = self.window.fb_width, self.window.fb_height
        if w <= 1 or h <= 1:
            return

        self.engine = Engine(w, h)
        self.engine.init_gl()
        self.engine.set_working_plane_provider(self._active_working_plane)
        self.engine.on_hover_changed_callback = self.actions.on_hover_changed
        self.engine.sel_mgr.on_selection_changed = self.actions.on_selection_changed
        
        self.engine.set_app(self)

        # Tek ve doğru binding yüklemesi
        from app.input_bindings import build_bindings
        bindings = build_bindings(self)
        
        for key, action in bindings.items():
            if isinstance(key, tuple):
                k, m = key
                self.engine.input.bind(k, m, action)
            else:
                self.engine.input.bind(key, 0, action)

        # --- DİNAMİK KISAYOL KÖPRÜSÜ (OTOMATİK) ---
        # input_bindings.py'ye eklenen her şey otomatik olarak buradan doğrulanır.
        self.window.is_shortcut_registered = lambda k, m: self.engine and any(
            b_key == k and (b_mods & (glfw.MOD_SHIFT | glfw.MOD_CONTROL | glfw.MOD_ALT | glfw.MOD_SUPER)) == m
            for (b_key, b_mods) in self.engine.input._bindings.keys()
        )

        self.initialized = True

        # ★ Viewport sistemi
        self.viewport_manager = ViewportManager(self.engine)
        self.engine.viewport_manager = self.viewport_manager
        vp = self.viewport_manager.create_viewport(
            name="iso", width=1200, height=800, preset="iso",
        )
        viewport_panel = ViewportPanel(self,
            "iso", self.viewport_manager, preset="iso",
        )
        
        self._viewport_panels.append(viewport_panel)
        if self.current_project:
            self.set_project(self.current_project)

    def _update_scene_if_dirty(self) -> None:
        model = self.engine.math_model if self.engine else None
        if model and model.is_dirty():
            self.engine.renderer.update_geo(model)
            model.clear_dirty()

    def _forward_active_viewport_events(self) -> None:
        """Hovered (veya drag devam eden) viewport panelinin ImGui event'lerini
        CameraController'a iletir. Paneller saf çizim; event routing burada."""
        eng = self.engine
        vm = self.viewport_manager
        if eng is None or vm is None or not self._viewport_panels:
            return

        io = imgui.get_io()
        any_drag = bool(io.mouse_down[0] or io.mouse_down[1] or io.mouse_down[2])

        hovered = next(
            (p for p in self._viewport_panels if p._is_hovered),
            None,
        )
        target = hovered
        if target is None and any_drag and self._last_active_viewport_name:
            target = next(
                (p for p in self._viewport_panels
                if p.viewport_name == self._last_active_viewport_name),
                None,
            )
        if target is None:
            return

        vm.set_active(target.viewport_name)
        self._last_active_viewport_name = target.viewport_name
        self._forward_imgui_events(target)


    def _forward_imgui_events(self, panel) -> None:
        eng = self.engine
        if eng is None:
            return
        vp = self.viewport_manager.get(panel.viewport_name)
        if vp is None:
            return

        io = imgui.get_io()
        item_min = panel._item_min
        mouse = imgui.get_mouse_pos()
        x_px = int(mouse.x - item_min.x)
        y_px = int(mouse.y - item_min.y)

        self._sync_input_state(eng, io, panel._is_hovered)
        if panel._is_hovered:
            eng.set_viewport_pointer(vp, x_px, y_px)

        # ---- Mouse move (HER frame, hover'da) ----
        dx = float(io.mouse_delta.x)
        dy = float(io.mouse_delta.y)
        if panel._is_hovered:
            eng.input.dispatch_move(x_px, y_px, dx, dy)

        # ---- Mouse click ----
        if panel._is_hovered:
            for button, imgui_btn in (
                (0, imgui.MouseButton_.left),
                (2, imgui.MouseButton_.middle),
                (1, imgui.MouseButton_.right),
            ):
                if imgui.is_mouse_clicked(imgui_btn):
                    eng.input.dispatch_click(x_px, y_px, button)
                    break   # bir tık = bir event

        # ---- Mouse release ----
        for button, imgui_btn in (
            (0, imgui.MouseButton_.left),
            (2, imgui.MouseButton_.middle),
            (1, imgui.MouseButton_.right),
        ):
            if imgui.is_mouse_released(imgui_btn):
                eng.input.dispatch_release(x_px, y_px, button)

        # ---- Scroll ----
        wheel = float(io.mouse_wheel)
        if wheel != 0.0 and panel._is_hovered:
            eng.input.dispatch_scroll(wheel)
            io.mouse_wheel = 0.0

        # ---- Keyboard ----
        if panel._is_hovered or self._any_viewport_active():
            self._forward_keys(eng)
            
    def _any_viewport_active(self) -> bool:
        """Herhangi bir viewport hovered veya drag aktif mi?"""
        for panel in self._viewport_panels:
            if getattr(panel, "_is_hovered", False):
                return True
        # Drag devam ediyorsa da aktif say
        io = imgui.get_io()
        if io.mouse_down[0] or io.mouse_down[1] or io.mouse_down[2]:
            return self._last_active_viewport_name is not None
        return False

    def _forward_keys(self, eng):
        """ImGui key state → engine input dispatch."""
        import glfw
        # Key → glfw mapping
        key_map = {
            imgui.Key.escape: glfw.KEY_ESCAPE,
            imgui.Key.space: glfw.KEY_SPACE,
            imgui.Key.enter: glfw.KEY_ENTER,
            imgui.Key.tab: glfw.KEY_TAB,
            imgui.Key.delete: glfw.KEY_DELETE,
            imgui.Key.backspace: glfw.KEY_BACKSPACE,
            imgui.Key.left_arrow: glfw.KEY_LEFT,
            imgui.Key.right_arrow: glfw.KEY_RIGHT,
            imgui.Key.up_arrow: glfw.KEY_UP,
            imgui.Key.down_arrow: glfw.KEY_DOWN,
        }
        mods = 0
        io = imgui.get_io()
        if io.key_ctrl: mods |= glfw.MOD_CONTROL
        if io.key_shift: mods |= glfw.MOD_SHIFT
        if io.key_alt: mods |= glfw.MOD_ALT
        if io.key_super: mods |= glfw.MOD_SUPER

        for imgui_key, glfw_key in key_map.items():
            if imgui.is_key_pressed(imgui_key):
                eng.input.dispatch_key(glfw_key, mods)
        
    @staticmethod
    def _sync_input_state(eng, io, item_hovered: bool) -> None:
        """ImGui state → InputManager.state. GLFW event'leri viewport üzerindeyken
        `_captures_mouse` yüzünden atlanıyor; burada senkronize ediyoruz."""
        state = eng.input.state

        if item_hovered:
            state.buttons[0] = bool(imgui.is_mouse_down(imgui.MouseButton_.left))
            state.buttons[2] = bool(imgui.is_mouse_down(imgui.MouseButton_.middle))
            state.buttons[1] = bool(imgui.is_mouse_down(imgui.MouseButton_.right))
            state.mouse_pos.x = float(io.mouse_pos.x)
            state.mouse_pos.y = float(io.mouse_pos.y)

        mods = 0
        if io.key_ctrl: mods |= glfw.MOD_CONTROL
        if io.key_shift: mods |= glfw.MOD_SHIFT
        if io.key_alt: mods |= glfw.MOD_ALT
        state.modifiers = mods
        
    def _draw_panels(self) -> None:
        # ★ Viewport pencereleri
        for vp_panel in self._viewport_panels:
            vp_panel.draw()
        # Mevcut paneller
        for entry in self.panels.values():
            panel = entry["instance"]
            if getattr(panel, "visible", False):
                panel.draw()
        self.plane_source_dialog.draw()

    def _draw_dock_space(self) -> None:
        viewport = imgui.get_main_viewport()
        # print("main_viewport:",viewport.work_pos, viewport.work_size)
        imgui.set_next_window_pos(viewport.work_pos)
        imgui.set_next_window_size(viewport.work_size)
        # imgui.set_next_window_viewport(viewport.id)   # ← KALDIRILDI
        imgui.push_style_var(imgui.StyleVar_.window_rounding, 0.0)
        imgui.push_style_var(imgui.StyleVar_.window_border_size, 0.0)
        imgui.push_style_var(imgui.StyleVar_.window_padding, imgui.ImVec2(0, 0))

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
        imgui.end()

    def _consume_plane_completion(self):
        pdm = self.engine.plane_draw_mgr if self.engine else None
        if pdm is None or pdm.is_active or pdm.completed_plane is None:
            return
        plane = pdm.completed_plane
        pdm.completed_plane = None

        pm = self.panels.get("plane_manager", {}).get("instance")
        if pm is not None:
            pm._selected_name = plane.name
            pm.visible = True

        if self.engine and self.current_project:
            self.engine.update_geo(self.current_project)

    # ------------------------------------------------------------------
    def _render_scene(self, dt: float) -> None:
        w, h = self.window.fb_width, self.window.fb_height

        # ★ Tüm viewport'ları kendi FBO'larına render et
        if self.viewport_manager is not None:
            # for name, vp in self.viewport_manager.viewports.items():
            #     cam = vp.camera
            #     print(f"[VP] {name}: fbo={vp.fbo.w}x{vp.fbo.h} "
            #         f"pos=({cam.position.x:.1f},{cam.position.y:.1f},{cam.position.z:.1f}) "
            #         f"target=({cam.target.x:.1f},{cam.target.y:.1f},{cam.target.z:.1f}) "
            #         f"dist={cam.distance:.1f} "
            #         f"aspect={cam.aspect_ratio:.2f}")
            # print(f"[VP] model: frames={len(self.engine.math_model.frames)} "
            #     f"nodes={len(self.engine.math_model.nodes)} "
            #     f"areas={len(self.engine.math_model.areas)}")
            self.viewport_manager.render_all()

        # Ana GLFW framebuffer'ı temizle — ImGui docking arka planı
        glViewport(0, 0, w, h)
        glBindFramebuffer(GL_FRAMEBUFFER, 0)
        glClearColor(0.06, 0.07, 0.10, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        # GL state reset (ImGui için)
        glUseProgram(0)
        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_CULL_FACE)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def _toggle_2d(self) -> None:
        if not (self.engine and self.engine.renderer):
            return
        r = self.engine.renderer
        if r.projection != "plane_2d" and self.engine.plane_draw_mgr.is_active:
            self.engine.plane_draw_mgr.cancel()
        r.toggle_projection()

    def _active_working_plane(self):
        project = self.current_project
        if project is None or project.scene is None:
            return None
        return project.active_plane

    def _selected(self):
        if self.engine and self.engine.sel_mgr:
            return self.engine.sel_mgr.get_selected()
        return []

    # ------------------------------------------------------------------
    def _build_toolbar_commands(self) -> dict:
        cmds = {
            "new_project": self.actions.new_project,
            "open": self.actions.open_dialog,
            "save": self.actions.quick_save,
            "save_as": self.actions.save_as_dialog,
            "close_app": lambda: glfw.set_window_should_close(self.window.window, True),
            "s2k_import": self.actions.s2k_import,
            "s2k_export": self.actions.s2k_export,
            "draw_line": lambda: self.actions.toggle_draw("line"),
            "draw_poly": lambda: self.actions.toggle_draw("poly"),
            "draw_plane": self.actions.toggle_plane,
            "render_mode": lambda: self.engine.renderer.toggle_render_mode() if self.engine else None,
            "toggle_loads_vis": self.actions.toggle_loads,
            "local_axes": self.actions.toggle_local_axes,
            "show_only": self.actions.toggle_show_only,
            "convert_to_link": lambda: self.actions.convert_frames_to_links("DefaultLink"),
            "on_unit_change": self.actions.set_unit_system,
            "toggle_view_2d": self._toggle_2d,
            "vp_top":    lambda: self._open_viewport("top"),
            "vp_bottom": lambda: self._open_viewport("bottom"),
            "vp_front":  lambda: self._open_viewport("front"),
            "vp_back":   lambda: self._open_viewport("back"),
            "vp_left":   lambda: self._open_viewport("left"),
            "vp_right":  lambda: self._open_viewport("right"),
            "vp_iso":    lambda: self._open_viewport("iso"),
            "vp_iso_sw": lambda: self._open_viewport("iso_sw"),
            "vp_iso_se": lambda: self._open_viewport("iso_se"),
            "vp_iso_ne": lambda: self._open_viewport("iso_ne"),
            "vp_iso_nw": lambda: self._open_viewport("iso_nw"),
            "plane_3pt": lambda: self.engine.plane_draw_mgr.start_3pt(),
            "plane_2pt_z": lambda: self.engine.plane_draw_mgr.start_2pt_z(),
            "plane_from_element": lambda: self.plane_from_element_dialog.open(),
            "vp_close_all": self._close_all_viewports,
        }
        for name in self.panels:
            cmds[name] = (lambda n=name: self.actions.toggle_panel(n))
        return cmds

    def _build_panel_states(self) -> dict:
        states = {
            "draw_line": lambda: bool(self.engine and self.engine.draw_mgr and self.engine.draw_mgr.is_active),
            "draw_poly": lambda: bool(self.engine and self.engine.draw_mgr and self.engine.draw_mgr.is_active),
            "draw_plane": lambda: bool(self.engine and self.engine.plane_draw_mgr and self.engine.plane_draw_mgr.is_active),
            "local_axes": lambda: bool(self.engine and self.engine.scene and self.engine.scene.show_local_axes),
            "show_loads": self.actions.get_loads_visible,
            "show_only": lambda: self._show_only_ids is not None,
            "toggle_view_2d": lambda: bool(self.engine and self.engine.renderer and self.engine.renderer.projection == "plane_2d"),
        }
        for name, entry in self.panels.items():
            inst = entry["instance"]
            states[name] = (lambda i=inst: getattr(i, "visible", False))
        return states

    # ------------------------------------------------------------------
    def set_project(self, project: Project) -> None:
        self.current_project = project
        self.actions.wind_state()
        self._catalog = ProjectCatalog(project)

        if not self.engine or project.scene is None:
            return

        self.engine.set_scene(project)

        if self.inspector:
            self.inspector.set_catalog(self._catalog)
            self.inspector.set_project(project)

        self.engine.update_geo(project)

        if self.engine.grid and project.scene.grid:
            self.engine.grid.set_grid(project.scene.grid)
            self.engine.grid.mark_dirty()

        if self.engine.sel_mgr:
            self.engine.sel_mgr.clear()

        pm = self.panels.get("plane_manager", {}).get("instance")
        if pm is not None:
            pm.reset()

        bounds = self.engine._combined_bounds()
        if bounds is not None and self.viewport_manager is not None:
            for vp in self.viewport_manager.viewports.values():
                vp.camera.update_bounds(bounds.center, bounds.size)
                vp.camera.focus_on_model()

    def _toggle_2d(self) -> None:
        eng = self.engine
        if not eng or not eng.renderer:
            return
        if eng.plane_draw_mgr.is_active:
            eng.plane_draw_mgr.cancel()

        if eng.renderer.projection == "plane_2d":
            eng.exit_plane_2d()
            return

        project = self.current_project
        plane = project.active_plane if project else None
        if plane is None:
            plane = eng.default_xy_plane()
            if plane is not None and project is not None:
                project.activate_plane(plane)

        if plane is None:
            return
        eng.enter_plane_2d(plane)
        
    def _open_viewport(self, preset: str):
        """Toolbar'dan çağrılır. Yeni viewport açar."""
        if self.viewport_manager is None:
            return
        base_name = preset
        name = self.viewport_manager.next_name(base_name)
        vp = self.viewport_manager.create_viewport(
            name=name, width=800, height=600, preset=preset,
        )
        panel = ViewportPanel(self, name, self.viewport_manager, preset=preset)
        
        self._viewport_panels.append(panel)
        # Model varsa kamera odaklı gelsin (create_viewport zaten yapıyor)
        return vp

    def _close_all_viewports(self):
        if self.viewport_manager is None:
            return
        for name in list(self.viewport_manager.viewports.keys()):
            self.viewport_manager.remove_viewport(name)
        self._viewport_panels.clear()
        
    def shutdown(self) -> None:
        pass