# app/cad_app.py
import os
import queue
import threading
from typing import Dict, Optional
from OpenGL.GL import *
import glm
import glfw
import imgui
import numpy as np

from app.cad_window import CadWindow
from core.gl_engine import Engine

from data.enums import UnitSystem, GridPlane, PolygonType
from domain.definition import GridPlaneDef, Section
from domain.element import Frame, Node, Polygon
from domain.project import Project
from tools import frame_to_link
from tools.alignment_service import AlignmentService
from tools.s2kloader import S2KLoader
from tools.wind_service import WindSceneAdapter
from tools.wind_zone_distribution_service import WindZoneDistributionService
from tools.frame_load_service import FrameLoadService
from ui.adapters import values_to_element
from ui.plane_plot_panel import PlanePlotPanel
from ui.toolbar import Toolbar
from ui.main_menu import MainMenuPopup
from ui.file_dialog import ImGuiFileDialog
from ui.visibility_panel import VisibilityPanel
from ui.view_filter_panel import ViewFilterPanel
from ui.zones_panel import ZonesPanel
from ui.definition_panel import DefinitionPanel
from ui.project_panels import ProjectInfoPanel, ProjectConfigPanel, AnalysisManagerPanel, ReportPanel
from ui.grid_panel import GridPanel
from ui.imgui_backend import UiBackend
from ui.load_assign_panel import LoadAssignPanel
from ui.frame_load_panel import FrameLoadPanel
from ui.load_display_panel import LoadDisplayPanel
from ui.polygon_edit_panel import PolygonEditPanel
from ui.plane_manager_panel import PlaneManagerPanel
from ui.s2k_import_panel import S2KImportPanel
from inspector import InspectorWindow
from inspector.catalog_project import ProjectCatalog
from core.plane_draw_manager import PlaneDrawManager

from app.panel_registry import PANEL_SPECS

from core.input_manager import (
    MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT, MOUSE_BUTTON_MIDDLE,
)

from logging_config import CadLogger
logger = CadLogger.get(__name__)


class CadApp:
    """
    CadApp — Tek Merkezli Event, Panel ve Komut Mimarisi.
    EventRouter ve dağınık callback/panel yönetimini tek bir PANEL_REGISTRY altında toplar.
    """

    MIDDLE_DOUBLE_CLICK_INTERVAL = 0.25
    MIDDLE_DOUBLE_CLICK_MAX_DRAG = 4.0

    def __init__(self, window: CadWindow):
        # --- 1. Temel durum ---
        self.window = window
        self.engine = None
        self.inspector = None
        self.initialized = False

        self.current_project = Project()
        self.current_file_path = None
        self._model_text = "MODEL: YENİ SAHNE"

        self.section_catalog: Dict[str, Section] = {}

        self.hover_visual_enabled = True
        self.show_loads = True

        # --- 2. Mouse / event durumu ---
        self._pending = []
        self._mouse_pressed = set()
        self._last_middle_click_time = 0.0
        self._middle_press_pos = (0.0, 0.0)
        self._middle_dragged = False

        # --- 3. Merkezi kayıtlar (panels, shortcuts, actions) ---
        self._init_registry()      # -> self.panels, self._shortcut_map, self.<panel_name>
        self._init_shortcuts()     # -> self._key_shortcuts
        self._init_actions()       # -> self._actions

        # --- 4. UI backend ve pencere callback bağlantıları ---
        self.ui_backend = UiBackend(window.window)
        self.ui_backend.setup()
        window._wire_callbacks()

        window.on_key_down      = self.on_key_down
        window.on_key_up        = self.on_key_up
        window.on_mouse_button  = self.on_mouse_button
        window.on_mouse_move    = self.on_mouse_move
        window.on_scroll        = self.on_scroll
        window.on_resize        = self._on_resize
        window.on_char          = self.on_char
        window.on_focus         = self.on_window_focus

        # --- 5. Toolbar (registry'den türetilmiş komut ve state'lerle) ---
        self.toolbar = Toolbar(
            commands=self._build_toolbar_commands(),
            panel_states=self._build_panel_states(),
        )

        # --- 6. Modüler ek bileşenler ---
        self.main_menu  = MainMenuPopup()
        self.file_dialog = ImGuiFileDialog()
        if self.inspector:    
            self.inspector.set_scene(self.current_project.scene)
            self.inspector.set_catalog(ProjectCatalog(self.current_project))

        self._load_section_catalog()
        self._show_only_ids: Optional[set] = None
        
    # ==================================================================
    # MERKEZİ PANEL KAYIT SİSTEMİ (PANEL_REGISTRY)
    # ==================================================================
    def _init_registry(self):
        self.panels = {}
        self._panels_by_category = {}
        self._shortcut_map = {}

        for name, cls, title, category, toolbar, shortcut in PANEL_SPECS:
            try:
                inst = cls()
                inst.app = self
            except Exception:
                logger.exception("Panel başlatılamadı: %s", name)
                continue

            entry = {
                "instance": inst,
                "title": title,
                "category": category,
                "toolbar": toolbar,
                "shortcut": shortcut,
            }
            self.panels[name] = entry
            self._panels_by_category.setdefault(category, []).append(name)
            if shortcut:
                self._shortcut_map[shortcut] = name

        for name, entry in self.panels.items():
            setattr(self, name, entry["instance"])

        # ── YENİ: S2K import paneli callback'ini kalıcı bağla ──
        s2k_entry = self.panels.get("s2k_import")
        if s2k_entry:
            s2k_entry["instance"].on_import_complete = self._on_s2k_import_complete
            logger.info("[CadApp] s2k_import.on_import_complete kalıcı bağlandı")

        sec_entry = self.panels.get("section_panel")
        if sec_entry:
            sec_entry["instance"].on_section_changed = self._on_section_changed

    def toggle_panel(self, name: str):
        entry = self.panels.get(name)
        if not entry:
            return
        p = entry["instance"]
        p.close() if getattr(p, "visible", False) else p.open()

    def _on_s2k_import_complete(self, project: Project):
        """S2K paneli import bitince buraya döner."""
        scn = project.scene
        logger.info(f"[CadApp] S2K import tamamlandı: "
                    f"nodes={len(getattr(scn,'nodes',{}))}, "
                    f"frames={len(getattr(scn,'frames',{}))}")
        self.set_project(project)
        self._model_text = f"MODEL: S2K import ({len(getattr(scn,'frames',{}))} çubuk)"

    # ==================================================================
    # ENGINE BAŞLATMA VE FRAME DÖNGÜSÜ
    # ==================================================================
    def _ensure_engine(self):
        if self.initialized:
            return
        w, h = self.window.fb_width, self.window.fb_height
        if w <= 1 or h <= 1:
            return
        try:
            self.engine = Engine(w, h)
            self.engine.init_gl()
            self.engine.on_hover_changed_callback = self._on_hover_changed
            self.engine.sel_mgr.on_selection_changed = self._on_selection_changed
            self.engine.plane_draw_mgr = PlaneDrawManager(self.engine)
            if self.engine.renderer:
                self.engine.renderer.set_plane_draw_mgr(self.engine.plane_draw_mgr)
            self.initialized = True

            # Lazy bind: init öncesi yüklenen projeyi bağla
            if self.current_project:
                self.set_project(self.current_project)

            # test_file = "test_model.cd4"
            # if os.path.exists(test_file) and not self.current_project.scene.nodes:
            #     self._load_project(test_file)

        except Exception:
            logger.exception("INIT HATASI")
            self.initialized = True

    def _load_section_catalog(self):
        from pathlib import Path
        from data.section_catalog import load_catalog_from_dir

        data_dir = Path(__file__).parent.parent / "data"
        try:
            self.section_catalog = load_catalog_from_dir(data_dir)
            logger.info(f"[CadApp] Kesit kataloğu: {len(self.section_catalog)} kesit")
        except Exception:
            logger.exception("[CadApp] Katalog yüklenemedi")
            self.section_catalog = {}
            
    def frame(self, dt):
        self._ensure_engine()
        if not self.initialized:
            return

        self.ui_backend.begin_frame()

        draw_active = bool(self.engine and self.engine.draw_mgr and self.engine.draw_mgr.is_active)
        current_unit = self.current_project.unit_system if self.current_project else None
        
        # 1. Toolbar ve Ana Arayüz
        self.toolbar.draw(model_text=self._model_text, draw_active=draw_active, current_unit=current_unit)
        self.file_dialog.draw()

        # 2. Bekleyen Event'lerin İşlenmesi
        self.process_pending()
        
        # 3. Rüzgar Analizi Kuyruk Kontrolü
        # self._process_wind_queue()

        # 4. Sahne Güncelleme (Dirty Kontrolü)
        active_scene = self.engine.scene if self.engine else None
        if active_scene and hasattr(active_scene, 'is_dirty') and active_scene.is_dirty():
            logger.debug(f"[CadApp] DIRTY -> update_geo çağırıyorum")
            if self.engine.renderer:
                self.engine.renderer.update_geo(active_scene)
            active_scene.clear_dirty()
            logger.debug(f"[CadApp] update_geo bitti, _is_dirty={active_scene._is_dirty}")
            
        # 4.5 Plane Çizimi
        if self.engine and self.engine.renderer:
            pm_entry = self.panels.get("plane_manager")
            pm = pm_entry["instance"] if pm_entry else None
            if pm is not None and getattr(pm, "visible", False):
                self.engine.renderer.selected_plane = pm._selected_plane()
            else:
                self.engine.renderer.selected_plane = None
        # 5. Sahne Çizimi
        self._render_scene(dt)


        # 6. Kayıtlı Panellerin Otomatik Döngüyle Çizilmesi
        self._draw_panels()

        self.ui_backend.end_frame()

        # 7. Bekleyen Pick Sonucu Kontrolü
        if self.engine and self.engine.pending_pick_check:
            self.engine.check_pick_result()

    def _draw_panels(self):
        """Tüm kayıtlı panelleri ve menüleri güvenle çizer."""
        self.main_menu.draw()
        for p_info in self.panels.values():
            panel = p_info["instance"]
            if hasattr(panel, "draw"):
                if hasattr(panel, "visible") and panel.visible:
                    panel.draw()

    def _render_scene(self, dt):
        w, h = self.window.fb_width, self.window.fb_height
        glViewport(0, 0, w, h)

        try:
            glEnable(GL_DEPTH_TEST)
            glClearColor(0.08, 0.10, 0.16, 1.0)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            self.engine.renderer.set_dt(dt)
            self.engine.renderer.render(self.engine.cam)
            
            self._draw_snap_indicator(w, h)

            if self.engine.draw_mgr.is_active:
                mvp = (self.engine.cam.get_projection_matrix() @ self.engine.cam.get_view_matrix())
                self.engine.draw_mgr.render_preview(mvp, self.engine.preview_s)

            if self.engine and getattr(self.engine, "plane_draw_mgr", None):
                pdm = self.engine.plane_draw_mgr
                if pdm.is_active:
                    self._draw_pdm_hud(pdm)

        finally:
            glViewport(0, 0, w, h)
            glUseProgram(0)
            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
            glDisable(GL_DEPTH_TEST)
            glDisable(GL_CULL_FACE)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    # ==================================================================
    # EVENT YÖNETİMİ & EVENTROUTER ENTEGRASYONU
    # ==================================================================
    def _mods_to_dict(self, glfw_mods: int) -> dict:
        return {
            "shift": bool(glfw_mods & glfw.MOD_SHIFT),
            "ctrl":  bool(glfw_mods & glfw.MOD_CONTROL),
            "alt":   bool(glfw_mods & glfw.MOD_ALT),
        }

    def _read_mods_from_glfw(self) -> dict:
        w = self.window.window
        mods = 0
        if (glfw.get_key(w, glfw.KEY_LEFT_SHIFT) == glfw.PRESS or glfw.get_key(w, glfw.KEY_RIGHT_SHIFT) == glfw.PRESS):
            mods |= glfw.MOD_SHIFT
        if (glfw.get_key(w, glfw.KEY_LEFT_CONTROL) == glfw.PRESS or glfw.get_key(w, glfw.KEY_RIGHT_CONTROL) == glfw.PRESS):
            mods |= glfw.MOD_CONTROL
        if (glfw.get_key(w, glfw.KEY_LEFT_ALT) == glfw.PRESS or glfw.get_key(w, glfw.KEY_RIGHT_ALT) == glfw.PRESS):
            mods |= glfw.MOD_ALT
        return self._mods_to_dict(mods)

    def _sync_modifiers(self):
        eng = self.engine
        if eng is None or eng.input is None:
            return
        eng.input.update_modifiers(self._read_mods_from_glfw())

    def _mouse_over_ui(self) -> bool:
        try:
            import imgui
            return imgui.get_io().want_capture_mouse
        except Exception:
            return False

    def _keyboard_captured_by_ui(self) -> bool:
        try:
            import imgui
            return imgui.get_io().want_capture_keyboard
        except Exception:
            return False

    def on_char(self, codepoint):
        try:
            import imgui
            io = imgui.get_io()
            io.add_input_character(codepoint)
        except Exception:
            pass
        return True

    def on_key_down(self, key, scancode, mods):
        try:
            io = imgui.get_io()
            io.keys_down[key] = True       # bu çalışır (index erişimi)
        except Exception:
            pass

        # Modifier'ları DOĞRUDAN mods'tan oku (glfw garanti eder)
        try:
            io = imgui.get_io()
            io.key_ctrl  = bool(mods & glfw.MOD_CONTROL)
            io.key_shift = bool(mods & glfw.MOD_SHIFT)
            io.key_alt   = bool(mods & glfw.MOD_ALT)
            io.key_super = bool(mods & glfw.MOD_SUPER)
        except Exception:
            pass

        self._pending.append(("key_down", (key, scancode, mods)))
        return True

    def on_key_up(self, key, scancode):
        
        try:
            io = imgui.get_io()
            io.keys_down[key] = False
        except Exception:
            pass

        # Sadece o modifier bırakıldıysa False yap
        try:
            io = imgui.get_io()
            if key in (glfw.KEY_LEFT_CONTROL, glfw.KEY_RIGHT_CONTROL):
                io.key_ctrl = False
            elif key in (glfw.KEY_LEFT_SHIFT, glfw.KEY_RIGHT_SHIFT):
                io.key_shift = False
            elif key in (glfw.KEY_LEFT_ALT, glfw.KEY_RIGHT_ALT):
                io.key_alt = False
            elif key in (glfw.KEY_LEFT_SUPER, glfw.KEY_RIGHT_SUPER):
                io.key_super = False
        except Exception:
            pass

        self._pending.append(("key_up", (key, scancode)))
        return True

    def on_mouse_button(self, button, action, mods):
        self._pending.append(("button", (button, action, mods)))
        return True

    def on_mouse_move(self, x, y):
        self._pending.append(("move", (x, y)))
        return True

    def on_scroll(self, xoffset, yoffset):
        try:
            import imgui
            io = imgui.get_io()
            io.mouse_wheel += yoffset
        except Exception:
            pass
        self._pending.append(("scroll", (xoffset, yoffset)))
        return True

    def on_window_focus(self, focused: bool):
        if not focused:
            eng = self.engine
            if eng and eng.input:
                eng.input.clear_modifiers()

    def process_pending(self):
        if not self._pending:
            return
        events = self._pending
        self._pending = []
        for kind, args in events:
            try:
                if kind == "move":
                    self._handle_move(*args)
                elif kind == "button":
                    self._handle_button(*args)
                elif kind == "scroll":
                    self._handle_scroll(*args)
                elif kind == "key_down":
                    self._handle_key_down(*args)
                elif kind == "key_up":
                    self._handle_key_up(*args)
            except Exception:
                logger.exception("Event işleme hatası: %s %s", kind, args)

    def _sync_from_glfw_mods(self, mods: int):
        eng = self.engine
        if eng and eng.input:
            eng.input.update_modifiers(self._mods_to_dict(mods))

    def _handle_button(self, button, action, mods):
        eng = self.engine
        if eng is None:
            return
        self._sync_from_glfw_mods(mods)

        x, y = self.window.get_mouse_pos()

        # UI yakaladıysa geç
        if self._mouse_over_ui():
            return

        # Plane Draw aktifse tıklamayı öncelikli olarak PDM yönlendirsin
        pdm = getattr(eng, "plane_draw_mgr", None)
        if pdm is not None and pdm.is_active:
            if action == glfw.PRESS and button == glfw.MOUSE_BUTTON_LEFT:
                if pdm.on_mouse_click(x, y):
                    return

        if button == glfw.MOUSE_BUTTON_LEFT:
            kivy_btn, name = MOUSE_BUTTON_LEFT, "left"
        elif button == glfw.MOUSE_BUTTON_RIGHT:
            kivy_btn, name = MOUSE_BUTTON_RIGHT, "right"
        elif button == glfw.MOUSE_BUTTON_MIDDLE:
            kivy_btn, name = MOUSE_BUTTON_MIDDLE, "middle"
        else:
            return

        if eng.input:
            eng.input.update_mouse_position(x, y)
            eng.input.set_button_state(kivy_btn, action == glfw.PRESS)

        if action == glfw.PRESS:
            self._mouse_pressed.add(name)
            self._on_down(name, x, y)
        elif action == glfw.RELEASE:
            self._mouse_pressed.discard(name)
            self._on_up(name, x, y)

    def _on_down(self, name, x, y):
        eng = self.engine
        if eng.active_smart_plane_mode:
            eng.smart_analyzer.handle_mouse_click((x, y))
            return

        if name == "middle":
            self._middle_down(x, y)
        elif name == "right":
            self._right_down()
        elif name == "left":
            self._left_down(x, y)

    def _on_up(self, name, x, y):
        eng = self.engine
        if name == "left":
            self._left_up(x, y)
        elif name == "right":
            eng.pending_pick_check = False
        elif name == "middle":
            eng.pending_pick_check = False
            eng.clear_hover()

    def _left_down(self, x, y):
        eng = self.engine
        
        
        if eng.draw_mgr.is_active:
            eng.draw_mgr.on_mouse_click(x, y)
            return
        if eng.input.is_shift_pressed():
            return
        eng.marquee.start_selection(x, y)
        eng.update_world_pos(x, y)
        eng.start_hover_pick(int(x), int(y))

    def _left_up(self, x, y):
        eng = self.engine
        if eng.draw_mgr.is_active or eng.input.is_shift_pressed():
            return
        if eng.marquee.is_active:
            was_drag = eng.marquee.end_selection()
            if not was_drag:
                ctrl = eng.input.is_ctrl_pressed()
                eng.handle_pick_from_hover(ctrl)

    def _right_down(self):
        eng = self.engine
        element = eng.renderer.get_element_from_id(eng.hover_id) if eng.hover_id > 0 else None
        if element:
            self.toggle_panel("inspector")
        

    def _middle_down(self, x, y):
        eng = self.engine
        eng.pending_pick_check = False
        eng.clear_hover()

        now = glfw.get_time() if hasattr(glfw, "get_time") else threading.time()
        import time
        now = time.time()
        if now - self._last_middle_click_time < self.MIDDLE_DOUBLE_CLICK_INTERVAL:
            self._last_middle_click_time = 0.0
            eng.fit_view()
            return
        self._last_middle_click_time = now
        self._middle_press_pos = (x, y)
        self._middle_dragged = False

    def _handle_move(self, x, y):
        eng = self.engine
        if eng is None or self._mouse_over_ui():
            return

        if eng.input:
            eng.input.update_mouse_position(x, y)
        dx = eng.input.mouse_delta.x if eng.input else 0
        dy = eng.input.mouse_delta.y if eng.input else 0

        self._sync_modifiers()

        # --- PDM: her zaman hover pick + PDM hover, ama diğer işlemler atlanır ---
        pdm = getattr(eng, "plane_draw_mgr", None)
        if pdm and pdm.is_active:
            # PDM kendi hover'ını hesaplasın
            pdm.on_mouse_move(x, y)
            # 3D sahne hover'ı da çalışsın (highlight, snap)
            eng.update_world_pos(x, y)
            eng.start_hover_pick(int(x), int(y))
            # Camera/marquee/draw_mgr atlanır
            return

        # --- Normal akış (PDM yok) ---
        if "middle" in self._mouse_pressed:
            self._middle_move(dx, dy, x, y)
            return
        if "left" in self._mouse_pressed and eng.input.is_shift_pressed():
            eng.cam.orbit(dx, dy)
            if eng.hover_id != 0:
                eng.clear_hover()
            return
        if eng.draw_mgr.is_active:
            eng.draw_mgr.on_mouse_move(x, y)
            return
        if "right" in self._mouse_pressed:
            return
        if eng.marquee and eng.marquee.is_active:
            eng.marquee.update_selection(x, y)
            return

        eng.update_world_pos(x, y)
        eng.start_hover_pick(int(x), int(y))

        if eng.active_smart_plane_mode:
            view = np.array(eng.cam.get_view_matrix(), dtype=float)
            proj = np.array(eng.cam.get_projection_matrix(), dtype=float)
            eng.smart_analyzer.handle_mouse_move((x, y), view, proj, (self.window.fb_width, self.window.fb_height))
        
    def _middle_move(self, dx, dy, x, y):
        eng = self.engine
        if not self._middle_dragged:
            px, py = self._middle_press_pos
            if ((x - px) ** 2 + (y - py) ** 2) ** 0.5 > self.MIDDLE_DOUBLE_CLICK_MAX_DRAG:
                self._middle_dragged = True
                self._last_middle_click_time = 0.0

        if eng.input.is_ctrl_pressed():
            eng.cam.orbit(dx, dy)
        else:
            eng.cam.pan(dx, dy)
        eng.pending_pick_check = False
        eng.clear_hover()

    def _handle_scroll(self, xoffset, yoffset):
        eng = self.engine
        if eng is None or self._mouse_over_ui():
            return
        if yoffset > 0:
            eng.cam.zoom(1.0)
        elif yoffset < 0:
            eng.cam.zoom(-1.0)

    def _handle_key_down(self, key, scancode, mods):
        eng = self.engine
        if not eng:
            return

        self._sync_from_glfw_mods(mods)

        logger.info(f"[KeyDown] key={key} ctrl={eng.input.is_ctrl_pressed() if eng.input else '?'} "
                f"ui_captured={self._keyboard_captured_by_ui()}")
        
        if self._keyboard_captured_by_ui():
            if key == glfw.KEY_ESCAPE:
                self._on_escape()
            return

        pdm = getattr(eng, "plane_draw_mgr", None)
        if pdm and pdm.is_active and pdm.on_key_press(key):
            return

        if eng.input:
            eng.input.handle_key_down(key)

        if eng.active_smart_plane_mode and eng.smart_analyzer.handle_key_press(key):
            return

        self._dispatch_key(key, eng)

    def _init_shortcuts(self):
        """Registry shortcut -> (key, needs_ctrl, needs_shift) eşlemesi (bir kez)."""
        self._key_shortcuts = {}
        for shortcut, panel_name in self._shortcut_map.items():
            parts = shortcut.split("+")
            key_name = parts[-1]
            mods = set(p.upper() for p in parts[:-1])
            glfw_key = getattr(glfw, f"KEY_{key_name}", None)
            if glfw_key is None:
                logger.warning("Geçersiz kısayol: %s", shortcut)
                continue
            self._key_shortcuts[glfw_key] = (panel_name, "CTRL" in mods, "SHIFT" in mods)

    def _build_toolbar_commands(self) -> dict:
        cmds = {
            "new_project":       self._new_project,
            "open":              self._on_toolbar_open,
            "save":              self._quick_save,
            "save_as":           self._save_as_project,
            "s2k_import":        self._import_s2k,
            "close_app":         lambda: glfw.set_window_should_close(self.window.window, True),
            "draw":              self._toggle_draw_mode,
            "plane_draw":        self._toggle_plane_draw,
            "on_unit_change":    self.set_unit_system,
            "render_mode":       lambda: self.engine.renderer.toggle_render_mode() if self.engine else None,
            "toggle_loads_vis":  self._toggle_loads_visibility,
            "local_axes":        self._toggle_local_axes,
            "show_only":         self.toggle_show_only,
            "convert_to_link": lambda: self.convert_selected_frames_to_links("DefaultLink"),
        }
        for name in self.panels:
            cmds[name] = (lambda n=name: self.toggle_panel(n))

        return cmds

    def _new_project(self):
        from domain.project import Project
        self.set_project(Project())
        self.current_file_path = None
        self._model_text = "MODEL: YENİ SAHNE"
        logger.info("[File] Yeni proje oluşturuldu")

    def _build_panel_states(self) -> dict:
        states = {
            "smart_plane":       lambda: bool(self.engine and self.engine.active_smart_plane_mode),
            "plane_draw_active": lambda: bool(self.engine and getattr(self.engine, "plane_draw_mgr", None) and self.engine.plane_draw_mgr.is_active),
            "local_axes":        lambda: bool(self.engine and self.engine.scene and self.engine.scene.show_local_axes),
            "show_loads":        lambda: bool(self.engine and self.engine.renderer and self.engine.renderer.show.get('loads', True)),
            "show_only": lambda: self._show_only_ids is not None,
        }
        for name in self.panels:
            states[name] = (lambda n=name: getattr(self.panels[n]["instance"], "visible", False))
        return states

    def _toggle_local_axes(self):
        if self.engine and self.engine.scene:
            self.engine.scene.show_local_axes = not self.engine.scene.show_local_axes

    def _toggle_loads_visibility(self):
        if self.engine and self.engine.renderer:
            # Senin kurduğun sözlük üzerinden durumu tersine çeviriyoruz
            current = self.engine.renderer.show.get('loads', True)
            self.engine.renderer.show['loads'] = not current
            self.show_loads = not current  # CadApp state'i ile senkron tutalım
            logger.info(f"[Loads] Görünürlük değiştirildi: {self.engine.renderer.show['loads']}")

    def _import_s2k_direct(self):
        """Panel/callback/registry atla — doğrudan loader → set_project."""
        import os
        from tools.s2kloader import S2KLoader
        from domain.project import Project

        candidates = [
            os.path.join(os.getcwd(), "tests", "eski_.s2k"),
            r"D:\Program\cad4\tests\eski_.s2k",
        ]
        s2k_path = next((p for p in candidates if os.path.exists(p)), None)
        if not s2k_path:
            logger.error(f"[Direct] Dosya yok. Denenen: {candidates}")
            return

        logger.info(f"[Direct] === BAŞLADI: {s2k_path} ===")
        try:
            loader = S2KLoader(s2k_path)
            project = Project()
            project = loader.load(project)

            scn = project.scene
            logger.info(f"[Direct] Loader OK: nodes={len(getattr(scn,'nodes',{}))}, "
                        f"frames={len(getattr(scn,'frames',{}))}, "
                        f"areas={len(getattr(scn,'areas',{}))}")

            if not scn or not getattr(scn, 'frames', None):
                logger.error("[Direct] Sahne boş!")
                return

            # KRİTİK: engine.scene == project.scene olmalı
            logger.info(f"[Direct] ÖNCE engine.scene id = {id(self.engine.scene) if self.engine else 'YOK'}")
            logger.info(f"[Direct] YENİ project.scene id = {id(project.scene)}")

            logger.info("[Direct] set_project çağrılıyor...")
            self.set_project(project)
            logger.info("[Direct] set_project TAMAMLANDI")

            logger.info(f"[Direct] SONRA engine.scene id = {id(self.engine.scene) if self.engine else 'YOK'}")
            logger.info(f"[Direct] engine.scene is project.scene = {self.engine.scene is project.scene}")

            # bbox — kameranın nereye bakması gerektiğini doğrula
            nodes = list(scn.nodes.values())
            xs = [n.x for n in nodes]; ys = [n.y for n in nodes]; zs = [n.z for n in nodes]
            logger.info(f"[Direct] bbox X[{min(xs):.0f}, {max(xs):.0f}] "
                        f"Y[{min(ys):.0f}, {max(ys):.0f}] "
                        f"Z[{min(zs):.0f}, {max(zs):.0f}]")

            self._model_text = f"MODEL: eski_.s2k ({len(scn.frames)} çubuk)"
            logger.info("[Direct] === BİTTİ ===")
        except Exception:
            logger.exception("[Direct] HATA")

    def _dispatch_key(self, key, eng):
        if key == glfw.KEY_ESCAPE:
            return self._on_escape()

        # ── F10: Doğrudan S2K import testi ──
        if key == glfw.KEY_F10:
            self._import_s2k_direct()
            return
        
        # Registry kısayollarını kontrol et (Ctrl+G, Ctrl+P, F6, F12 vb.)
        entry = self._key_shortcuts.get(key)
        if entry:
            panel_name, needs_ctrl, needs_shift = entry
            if eng.input.is_ctrl_pressed() == needs_ctrl and eng.input.is_shift_pressed() == needs_shift:
                self.toggle_panel(panel_name)
                return

        # Doğrudan Tuş Kısayolları
        if key == glfw.KEY_F3:  eng.renderer.toggle_render_mode(); return
        if key == glfw.KEY_F11: self._import_s2k(); return
        if key == glfw.KEY_D and not eng.input.is_ctrl_pressed(): self._toggle_draw_mode(); return
        if key == glfw.KEY_W and eng.input.is_shift_pressed():    self._toggle_plane_draw(); return
        if key == glfw.KEY_C and eng.draw_mgr.is_active:          eng.draw_mgr.close(); return
        if key == glfw.KEY_L and not eng.input.is_ctrl_pressed(): self._toggle_loads_visibility(); return
        if key == glfw.KEY_DELETE:
            deleted, rejected = eng.sel_mgr.delete_selected()
            logger.info("Silindi: %s, Reddedildi: %s", deleted, rejected); return

        # Ctrl Kısayolları
        if eng.input.is_ctrl_pressed():
            if key == glfw.KEY_J : self.toggle_show_only(); return
            if key == glfw.KEY_Z: eng.sel_mgr.undo(); return
            if key == glfw.KEY_Y: eng.sel_mgr.redo(); return
            if key == glfw.KEY_S:
                return self._save_as_project() if eng.input.is_shift_pressed() else self._quick_save()
            if key == glfw.KEY_O: return self._on_toolbar_open()
            if key == glfw.KEY_E: self._export_s2k(); return

    def _handle_key_up(self, key, scancode):
        eng = self.engine
        if eng is None:
            return
        if eng.input:
            eng.input.handle_key_up(key)
        self._sync_modifiers()

    def _on_escape(self):
        eng = self.engine
        if eng is None:
            return
        pdm = getattr(eng, "plane_draw_mgr", None)
        if pdm and pdm.is_active:
            pdm._step_back()
            return
        if eng.draw_mgr.is_active:
            eng.draw_mgr.cancel()
            return
        if eng.marquee and eng.marquee.is_active:
            eng.marquee.cancel_selection()
            eng.clear_hover()
            return
        eng.pending_pick_check = False
        eng.clear_hover()
        eng.sel_mgr.clear()

    # ==================================================================
    # YARDIMCI METOTLAR VE İŞLEM SERVİSLERİ
    # ==================================================================
    def _toggle_draw_mode(self):
        if self.engine and self.engine.draw_mgr:
            if self.engine.draw_mgr.is_active:
                self.engine.draw_mgr.close()
            else:
                self.engine.draw_mgr.start()

    def _draw_snap_indicator(self, w, h):
        if not self.engine:
            return
        snap = self.engine.snap
        if snap is None or not getattr(self.engine, "hover_visual_enabled", True):
            return
        mx, my = self.engine.input.mouse_pos.x, self.engine.input.mouse_pos.y
        if not self.engine.draw_mgr:
            return
        if self.engine.draw_mgr.is_active or self.engine.hover_id > 0:
            snap.draw_snap(mx, my, w, h, active=True)

    def _on_resize(self, w, h):
        if self.engine:
            self.engine.resize(max(1, w), max(1, h))

    def _load_project(self, path: str):
        try:
            project = Project.load(path)
            self.set_project(project)
            if self.engine:
                self.engine.fit_view()
                self.engine.sel_mgr.clear()
            self._model_text = f"MODEL: {os.path.basename(path)}"
            self.current_file_path = path
            
            logger.info("[File] Proje yüklendi: %s", path)
        except Exception:
            logger.exception("Proje yükleme hatası")

    def set_unit_system(self, unit_system: UnitSystem):
        if self.current_project:
            self.current_project.unit_system = unit_system
        logger.info(f"[Units] Birim sistemi değiştirildi: {unit_system.name}")
        if self.engine and self.engine.grid:
            self.engine.grid.rebuild_all()

    def set_project(self, project: Project):
        logger.info(f"[set_project] BAŞLADI, engine={self.engine is not None}, "
                    f"project.scene id={id(project.scene)}")
        self.current_project = project

        if not self.engine:
            logger.warning("[set_project] ENGINE YOK — sahne bağlanmadı!")
            return

        if project.scene is None:
            logger.warning("[set_project] project.scene None!")
            return

        scn = project.scene
        logger.info(f"[set_project] Yeni sahne: "
                    f"nodes={len(getattr(scn,'nodes',{}))}, "
                    f"frames={len(getattr(scn,'frames',{}))}, "
                    f"areas={len(getattr(scn,'areas',{}))}")

        logger.info("[set_project] 1) engine.set_scene çağrılıyor...")
        self.engine.set_scene(scn)
        logger.info(f"[set_project]    engine.scene id={id(self.engine.scene)}, "
                    f"aynı mı={self.engine.scene is scn}")

        if hasattr(self, "inspector") and self.inspector:
            self.inspector.set_scene(scn)
            self.inspector.set_catalog(ProjectCatalog(project))

        logger.info("[set_project] 2) update_geo çağrılıyor...")
        if self.engine.renderer:
            try:
                self.engine.renderer.update_geo(scn)
                logger.info("[set_project]    update_geo OK")
            except Exception:
                logger.exception("[set_project]    update_geo HATA")
        else:
            logger.error("[set_project]    renderer YOK!")


        # 3) Grid senkronizasyonu
        if getattr(project, "grid", None) and self.engine.grid:
            g = project.grid
            self.engine.grid.set_coords(g.x_coords, g.y_coords, g.z_coords)
            self.engine.grid.set_origin(g.origin_x, g.origin_y, g.origin_z)
            for plane_name, vis in g.planes_visibility.items():
                try:
                    self.engine.grid.set_plane(GridPlane[plane_name], visible=vis)
                except KeyError:
                    pass
            # center, size = self.engine.grid.get_bounds()
            # self.engine.cam.update_bounds(center, size)
            # self.engine.cam.focus_on_model()
        else:
            # Grid tanımı olmasa bile kamerayı sahneye sığdır
            self.engine.fit_view()

        # 4) Selection temizle
        if self.engine.sel_mgr:
            self.engine.sel_mgr.clear()

        logger.info("[CadApp] set_project tamamlandı.")

    def _save_project(self, path: str):
        try:
            if self.current_project:
                self.current_project.save(path)
                self.current_file_path = path
                self._model_text = f"MODEL: {os.path.basename(path)}"
                logger.info("[File] Proje kaydedildi: %s", path)
        except Exception:
            logger.exception("Proje kaydetme hatası")

    def _quick_save(self):
        if not self.current_file_path:
            self._on_toolbar_save()
        else:
            self._save_project(self.current_file_path)

    def _save_as_project(self):
        self._on_toolbar_save()

    def _get_selected_frames(self):
        if not self.engine or not self.engine.scene:
            return []
        return [e for e in self.engine.scene.get_selected() if isinstance(e, Frame)]

    def _on_selection_changed(self, selected_elements):
        if self.engine and self.engine.renderer:
            self.engine.renderer.update_sel()
        if self.inspector:
            self.inspector.set_selection(selected_elements)
        if self._show_only_ids is not None:
            return

    def _on_hover_changed(self, element):
        pass

    def dispatch_action(self, action_name: str, payload=None):
        handler = self._actions.get(action_name)
        if handler is None:
            logger.warning("Bilinmeyen action: %s", action_name)
            return None
        try:
            return handler(payload) if payload is not None else handler()
        except Exception:
            logger.exception("Action hatası: %s", action_name)
            return None

    def _init_actions(self):
        self._actions = {
            # "run_wind":     self._on_run_wind_analysis,
            "save_project": self._save_project,
            "update_geo":   self._on_update_geo,
        }

    def _on_update_geo(self):
        if self.engine and self.engine.renderer and self.engine.scene:
            self.engine.renderer.update_geo(self.engine.scene)

    def print_(self):
        print("\nprint")
        for name, sec in self.current_project.sections.items():
            print(f"key={name!r}  name={sec.name!r}  type={sec.profile_type}")


    def _import_s2k(self):
        self.toggle_panel("s2k_import")

    def _export_s2k(self):
        if self.engine is None:
            return
        from tools.s2k_exporter import S2KExporter

        selected = self.engine.scene.get_selected()
        text = S2KExporter.export(self.current_project, selected_elements=selected)
        with open("model.s2k", "w", encoding="utf-8") as f:
            f.write(text)
       
    def _on_toolbar_open(self):
        self.file_dialog.open(mode="open", filters=[".cd4"], title="Proje Aç (.cd4)", initial_dir=os.getcwd(), on_select=self._load_project)

    def _on_toolbar_save(self):
        self.file_dialog.open(mode="save", filters=[".cd4"], title="Projeyi Kaydet (.cd4)", initial_dir=os.getcwd(), default_name="model_projesi.cd4", on_select=self._save_project)

    def _toggle_plane_draw(self):
        if self.engine is None:
            return
        pdm = getattr(self.engine, "plane_draw_mgr", None)
        if pdm is None:
            return
        if pdm.is_active:
            pdm.cancel()
            logger.info("[CadApp] Plane draw kapatıldı")
        else:
            # Modal mod — tüm panelleri kapat
            for name, entry in self.panels.items():
                p = entry["instance"]
                if hasattr(p, "visible") and p.visible and hasattr(p, "close"):
                    try:
                        p.close()
                    except Exception:
                        pass
            pdm.start()
            logger.info("[CadApp] Plane draw modu aktif — paneller kapatıldı")

    def _draw_pdm_hud(self, pdm):
        import imgui
        stage_text = {
            pdm.STAGE_P0: "p0: İlk noktayı seç",
            pdm.STAGE_P1: "p1: U vektörünü belirle",
            pdm.STAGE_P2: "p2: V vektörünü belirle",
            pdm.STAGE_DEPTH_PLUS: f"depth_plus: mouse yukarı/aşağı ({pdm.depth_plus:.0f}mm) — tıkla → sonraki",
            pdm.STAGE_DEPTH_MINUS: f"depth_minus: mouse aşağı/yukarı ({pdm.depth_minus:.0f}mm) — tıkla → onayla",
        }.get(pdm.stage, "")

        io = imgui.get_io()
        w, h = io.display_size
        imgui.set_next_window_position(w / 2 - 200, 20)
        imgui.set_next_window_size(400, 40)
        imgui.push_style_var(imgui.STYLE_WINDOW_PADDING, (8, 8))
        expanded, _ = imgui.begin("##pdm_hud", False,
                                imgui.WINDOW_NO_TITLE_BAR | imgui.WINDOW_NO_RESIZE |
                                imgui.WINDOW_NO_SCROLLBAR | imgui.WINDOW_NO_INPUTS)
        if expanded:
            imgui.text_colored(stage_text, 1.0, 0.9, 0.4, 1.0)
        imgui.end()
        imgui.pop_style_var()

    def _on_section_changed(self):
        """Kesit panelinde bir değişiklik oldu — sahneyi ve renderer'ı güncelle."""
        if not self.engine or not self.engine.scene:
            return
        scn = self.engine.scene
        scn.mark_dirty()
        if self.engine.renderer:
            self.engine.renderer.update_geo(scn)
            scn.clear_dirty()
        logger.info("[CadApp] Kesit değişikliği sahneye yansıtıldı")

    def toggle_show_only(self):
        """Toolbar butonu: seçili eleman(lar)ı izole et / normal görünüme dön."""
        if self.engine is None or self.engine.scene is None:
            return

        scn = self.engine.scene

        # --- TEŞHİS ---
        n_sel = sum(1 for e in scn.all_elements.values() if e.is_selected)
        logger.info(
            f"[ShowOnly] scene: frames={len(scn.frames)}, nodes={len(scn.nodes)}, "
            f"areas={len(scn.areas)}, selected={n_sel}"
        )

        if self._show_only_ids is None:
            # GİRİŞ: mevcut seçimi al
            selected = scn.get_selected()   # Scene'de bu metod var mı? yoksa:
            # selected = [e for e in scn.frames.values() if e.is_selected] + ...
            if not selected:
                logger.warning("[ShowOnly] Seçili eleman yok — işlem iptal")
                return
            self._show_only_ids = {e.unique_id for e in selected}
            logger.info(f"[ShowOnly] {len(self._show_only_ids)} eleman izole edildi")
        else:
            # ÇIKIŞ: normal görünüm
            self._show_only_ids = None
            logger.info("[ShowOnly] Normal görünüme dönüldü")

        # Filtreyi scene'e uygula
        scn._render_filter = self._show_only_ids
        if self._show_only_ids is not None:
            # Show-only modunda kamera sabit kalsın (fit_view çağırma)
            self.engine.renderer.update_geo(scn)
            # NOT: engine.set_scene içindeki fit_view çağrısını atlıyoruz
        else:
            # Normal moda dönerken kamerayı tekrar fit et
            self.engine.set_scene(scn)   # bu update_geo + fit_view çağırır

    def convert_selected_frames_to_links(
        self,
        link_prop_name: str = "DefaultLink",
        delete_original: bool = True,
    ):
        
        if not self.engine or not self.engine.scene:
            return

        scn = self.engine.scene
        frames = [e for e in scn.get_selected() if isinstance(e, Frame)]
        if not frames:
            logger.warning("[Frame→Link] Seçili frame yok")
            return
        
        report = frame_to_link.convert_frames_to_links(
            scene=scn,
            project=self.current_project,
            frames=frames,
            link_prop_name=link_prop_name,
            delete_original=delete_original,
        )

        # Show-only modundaysa filtre güncelle
        if self._show_only_ids is not None:
            removed = {f.unique_id for f in frames}
            self._show_only_ids -= removed
            self._show_only_ids.update(l.unique_id for l in report["new_links"])
            scn._render_filter = self._show_only_ids

        if self.engine.sel_mgr:
            self.engine.sel_mgr.clear()

        logger.warning(
    f"[Frame→Link] SONRA: scene.links={len(scn.links)}, "
    f"scene.frames={len(scn.frames)}, "
    f"show_only={'aktif' if self._show_only_ids else 'yok'}, "
    f"filter={self._show_only_ids}"
)
        
    def shutdown(self):
        self.ui_backend.shutdown()