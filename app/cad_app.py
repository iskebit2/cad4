# app/cad_app.py
import os
import queue
import threading
from OpenGL.GL import *
import glm
import glfw
import numpy as np

from app.cad_window import CadWindow
from core.gl_engine import Engine

from data.enums import UnitSystem, GridPlane, PolygonType
from domain.definition import GridPlaneDef
from domain.element import Frame, Polygon
from domain.project import Project
from tools.alignment_service import AlignmentService
from tools.load_balance_report import LoadBalanceReport
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
from ui.inspector_panel import InspectorPanel
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
        self.window = window
        self.engine = None
        self.initialized = False
        self._model_text = "MODEL: YENİ SAHNE"
        self.current_project = Project()
        self.current_file_path = None
        self.hover_visual_enabled = True
        self.show_loads = True
        self._wind_queue = queue.Queue()

        # Mouse / Event durum takibi (Eski EventRouter'dan taşındı)
        self._pending = []
        self._mouse_pressed = set()
        self._last_middle_click_time = 0.0
        self._middle_press_pos = (0.0, 0.0)
        self._middle_dragged = False

        # --- 1. MERKEZİ PANEL VE KOMUT KAYIT SÖZLÜĞÜ ---
        self.panels = {}
        self._init_registry()

        logger.debug(f"panels: {self.panels.keys()}")
        # UI Backend ve Pencere Callback Bağlantıları
        self.ui_backend = UiBackend(window.window)
        self.ui_backend.setup()
        window._wire_callbacks()

        window.on_key_down = self.on_key_down
        window.on_key_up = self.on_key_up
        window.on_mouse_button = self.on_mouse_button
        window.on_mouse_move = self.on_mouse_move
        window.on_scroll = self.on_scroll
        window.on_resize = self._on_resize
        window.on_char = self.on_char
        window.on_focus = self.on_window_focus

        # Toolbar'ı merkezi kayıttan üretilen komut ve durumlarla başlat
        self.toolbar = Toolbar(
            commands=self._build_toolbar_commands(),
            panel_states=self._build_panel_states(),
        )

        # Modüler ek bileşenler (Menü, Dialog vb.)
        self.main_menu = MainMenuPopup()
        self.file_dialog = ImGuiFileDialog()

        # Özel referans kolaylıkları (Registry'den hızlı erişim için)
        self.inspector = self.panels["inspector"]["instance"]
        self.visibility_panel = self.panels["visibility"]["instance"]
        self.view_filter = self.panels["view_filter"]["instance"]
        self.grid_panel = self.panels["grid"]["instance"]
        self.zones_panel = self.panels["wind"]["instance"]
        self.definition_panel = self.panels["definitions"]["instance"]
        self.project_info_panel = self.panels["project_info"]["instance"]
        self.project_config_panel = self.panels["project_config"]["instance"]
        self.analysis_panel = self.panels["analysis"]["instance"]
        self.report_panel = self.panels["report"]["instance"]
        self.load_assign_panel = self.panels["assign_area_load"]["instance"]
        self.frame_load_panel = self.panels["assign_frame_distributed_load"]["instance"]
        self.load_display_panel = self.panels["load_display_panel"]["instance"]
        self.plane_plot = self.panels["plane_plot"]["instance"]
        self.plane_manager_panel  = self.panels["plane_manager"]["instance"]

        # Panel özel callback bağlantıları
        # self.grid_panel.on_change = self._on_grid_change
        # self.grid_panel.on_work_plane_activate = self._on_work_plane_activate
        # self.inspector.on_apply = self._on_inspector_apply
        # self.visibility_panel.on_apply = self._on_visibility_applied
        # self.view_filter.on_apply = self._on_view_filter_apply
        # self.zones_panel.on_run_analysis = self._on_run_wind_analysis
        # self.zones_panel.on_select_direction = self.on_select_wind_direction
        # self.zones_panel.on_distribute = self._distribute_wind_zones_to_frames
        # self.load_assign_panel.on_apply = self._apply_load_to_selected_polygon

        
        

    # ==================================================================
    # MERKEZİ PANEL KAYIT SİSTEMİ (PANEL_REGISTRY)
    # ==================================================================
    def _init_registry(self):
        """Tüm panellerin ve komutların tek merkezden yönetildiği kayıt sözlüğü."""
        registry_def = {
            "s2k_import": {
                "class": S2KImportPanel,
                "title": "S2K İçe Aktarma",
                "toolbar": False,
                "shortcut": None,
                "visible": False,
                "category": "tools",
                "command": lambda: self.toggle_panel("s2k_import"),
            },
            "grid": {
                "class": GridPanel,
                "title": "Grid Ayarları",
                "toolbar": True,
                "shortcut": "CTRL+G",
                "visible": False,
                "category": "view",
                "command": lambda: self.toggle_panel("grid"),
            },
            "inspector": {
                "class": InspectorPanel,
                "title": "Özellikler (Inspector)",
                "toolbar": True,
                "shortcut": "CTRL+P",
                "visible": False,
                "category": "view",
                "command": lambda: self.toggle_panel("inspector"),
            },
            "visibility": {
                "class": VisibilityPanel,
                "title": "Görünürlük Paneli",
                "toolbar": True,
                "shortcut": None,
                "visible": False,
                "category": "view",
                "command": lambda: self.toggle_panel("visibility"),
            },
            "view_filter": {
                "class": ViewFilterPanel,
                "title": "Görünüm Filtresi",
                "toolbar": True,
                "shortcut": "F6",
                "visible": False,
                "category": "view",
                "command": lambda: self.toggle_panel("view_filter"),
            },
            "wind": {
                "class": ZonesPanel,
                "title": "Rüzgar Bölgeleri (Zones)",
                "toolbar": True,
                "shortcut": None,
                "visible": False,
                "category": "analysis",
                "command": lambda: self.toggle_panel("wind"),
            },
            "definitions": {
                "class": DefinitionPanel,
                "title": "Tanımlar (Definitions)",
                "toolbar": True,
                "shortcut": "CTRL+R",
                "visible": False,
                "category": "management",
                "command": lambda: self.toggle_panel("definitions"),
            },
            "project_info": {
                "class": ProjectInfoPanel,
                "title": "Proje Bilgileri",
                "toolbar": True,
                "shortcut": None,
                "visible": False,
                "category": "management",
                "command": lambda: self.toggle_panel("project_info"),
            },
            "project_config": {
                "class": ProjectConfigPanel,
                "title": "Proje Yapılandırması",
                "toolbar": True,
                "shortcut": None,
                "visible": False,
                "category": "management",
                "command": lambda: self.toggle_panel("project_config"),
            },
            "analysis": {
                "class": AnalysisManagerPanel,
                "title": "Analiz Yöneticisi",
                "toolbar": True,
                "shortcut": None,
                "visible": False,
                "category": "management",
                "command": lambda: self.toggle_panel("analysis"),
            },
            "report": {
                "class": ReportPanel,
                "title": "Raporlar",
                "toolbar": True,
                "shortcut": None,
                "visible": False,
                "category": "management",
                "command": lambda: self.toggle_panel("report"),
            },
            "assign_area_load": {
                "class": LoadAssignPanel,
                "title": "Alan Yükü Atama",
                "toolbar": True,
                "shortcut": None,
                "visible": False,
                "category": "loads",
                "command": lambda: self.toggle_panel("assign_area_load"),
            },
            "assign_frame_distributed_load": {
                "class": FrameLoadPanel,
                "title": "Çubuk Yayılı Yük Atama",
                "toolbar": True,
                "shortcut": None,
                "visible": False,
                "category": "loads",
                "command": lambda: self.toggle_panel("assign_frame_distributed_load"),
            },
            "load_display_panel": {
                "class": LoadDisplayPanel,
                "title": "Yük Görüntüleme Paneli",
                "toolbar": True,
                "shortcut": None,
                "visible": False,
                "category": "loads",
                "command": lambda: self.toggle_panel("load_display_panel"),
            },
            "plane_plot": {
                            "class": PlanePlotPanel,
                            "title": "Plane Plot (2D)",
                            "toolbar": False,
                            "shortcut": None,
                            "visible": False,
                            "category": "tools",
                            "command": lambda: self.toggle_panel("plane_plot"),
                        },
            "plane_manager": {
                            "class": PlaneManagerPanel,
                            "title": "Plane Manager",
                            "toolbar": True,
                            "shortcut": "F12",
                            "visible": False,
                            "category": "tools",
                            "command": lambda: self.toggle_panel("plane_manager"),
                        },

        }

        # Panel nesnelerini güvenli biçimde başlatıp sakla
        for name, cfg in registry_def.items():
            try:
                cls = cfg["class"]
                instance = cls()
                instance.app = self
                self.panels[name] = {
                    "instance": instance,
                    "title": cfg["title"],
                    "toolbar": cfg["toolbar"],
                    "shortcut": cfg.get("shortcut"),
                    "command": cfg["command"],
                }
            except Exception:
                logger.exception("Panel başlatılamadı: %s", name)

    def toggle_panel(self, name: str):
        """Kayıtlı bir paneli açar veya kapatır."""
        if name not in self.panels:
            return
        panel = self.panels[name]["instance"]
        if getattr(panel, "visible", False):
            panel.close()
        else:
            if hasattr(panel, "open"):
                panel.open()

    def _build_toolbar_commands(self) -> dict:
        """Toolbar butonları için merkezi kayıt komutlarını derler."""
        cmds = {
            "menu": lambda: self.main_menu.open() if hasattr(self, "main_menu") and self.main_menu else None,
            "open": lambda: self.file_dialog.open(mode="open", filters=[".cd4"], title="Proje Aç (.cd4)", initial_dir=os.getcwd(), on_select=self._load_project),
            "save": lambda: self.file_dialog.open(mode="save", filters=[".cd4"], title="Projeyi Kaydet (.cd4)", initial_dir=os.getcwd(), default_name="model_projesi.cd4", on_select=self._save_project),
            "draw": self._toggle_draw_mode,
            "on_unit_change": self.set_unit_system,
            
            # Kayıtlı panellerin komutları (Doğrudan PANEL_REGISTRY içindeki command'leri tetikler)
            "grid": self.panels["grid"]["command"],
            "inspector": self.panels["inspector"]["command"],
            "visibility": self.panels["visibility"]["command"],
            "view_filter": self.panels["view_filter"]["command"],
            "wind": self.panels["wind"]["command"],
            "definitions": self.panels["definitions"]["command"],
            "project_info": self.panels["project_info"]["command"],
            "project_config": self.panels["project_config"]["command"],
            "analysis": self.panels["analysis"]["command"],
            "report": self.panels["report"]["command"],
            "assign_area_load": self.panels["assign_area_load"]["command"],
            "assign_frame_distributed_load": self.panels["assign_frame_distributed_load"]["command"],
            "toggle_load_display_panel": self.panels["load_display_panel"]["command"],
            "plane_plot": self.panels["plane_plot"]["command"],
            "plane_manager": self.panels["plane_manager"]["command"],

            # Uygulama seviyesi ek komutlar
            
        }
        return cmds

    def _build_panel_states(self) -> dict:
        """Toolbar görünürlük ve durum lambaları için state sorguları."""
        states = {
            "grid": lambda: self.panels["grid"]["instance"].visible,
            "inspector": lambda: self.panels["inspector"]["instance"].visible,
            "visibility": lambda: self.panels["visibility"]["instance"].visible,
            "view_filter": lambda: self.panels["view_filter"]["instance"].visible,
            "wind": lambda: self.panels["wind"]["instance"].visible,
            "definitions": lambda: self.panels["definitions"]["instance"].visible,
            "project_info": lambda: self.panels["project_info"]["instance"].visible,
            "project_config": lambda: self.panels["project_config"]["instance"].visible,
            "analysis": lambda: self.panels["analysis"]["instance"].visible,
            "report": lambda: self.panels["report"]["instance"].visible,
            "assign_area_load": lambda: self.panels["assign_area_load"]["instance"].visible,
            "assign_frame_distributed_load": lambda: self.panels["assign_frame_distributed_load"]["instance"].visible,
            "load_display_panel": lambda: self.panels["load_display_panel"]["instance"].visible,
            "plane_plot": lambda: self.panels["plane_plot"]["instance"].visible,
            "smart_plane": lambda: getattr(self.engine, "active_smart_plane_mode", False) if self.engine else False,
            "local_axes": lambda: self.engine.scene.show_local_axes if self.engine and self.engine.scene else False,
            "local_axes_selected_only": lambda: self.engine.scene.show_local_axes_for_selected if self.engine and self.engine.scene else True,
            "show_loads": lambda: getattr(self.engine.renderer, "show_loads", True) if self.engine and self.engine.renderer else True,
            "plane_manager": lambda: self.panels["plane_manager"]["instance"].visible,
        }
        return states

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
            logger.info("[INIT] Engine başlıyor...")
            self.engine = Engine(w, h)
            self.engine.init_gl()
            self.engine.on_hover_changed_callback = self._on_hover_changed
            self.engine.sel_mgr.on_selection_changed = self._on_selection_changed
            self.initialized = True
            logger.info("Engine ilklendirildi.")

            if os.path.exists("test_proje2.cd4"):
                self._load_project("test_proje2.cd4")

        except Exception:
            logger.exception("INIT HATASI")
            self.initialized = True

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
            if self.engine.renderer:
                self.engine.renderer.update_geo(active_scene)
            active_scene.clear_dirty()
            
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

            if self.engine.active_smart_plane_mode:
                self.engine.smart_analyzer.render()
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
            import imgui
            io = imgui.get_io()
            io.keys_down[key] = True
        except Exception:
            pass
        self._pending.append(("key_down", (key, scancode, mods)))
        return True

    def on_key_up(self, key, scancode):
        try:
            import imgui
            io = imgui.get_io()
            io.keys_down[key] = False
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
        if self._mouse_over_ui():
            return

        x, y = self.window.get_mouse_pos()
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
            self.open_inspector(element)
        else:
            self.inspector.close()

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
        if eng is None:
            return
        self._sync_from_glfw_mods(mods)

        if self._keyboard_captured_by_ui():
            if key == glfw.KEY_ESCAPE:
                self._on_escape()
            return

        if eng.input:
            eng.input.handle_key_down(key)
        if eng.active_smart_plane_mode and eng.smart_analyzer.handle_key_press(key):
            return

        self._dispatch_key(key, eng)

    def _dispatch_key(self, key, eng):
        if key == glfw.KEY_ESCAPE:
            self._on_escape()
            return
        
        if key == glfw.KEY_F3:
            if eng.renderer:
                eng.renderer.toggle_render_mode()
            return
        if key == glfw.KEY_F4:
            eng.renderer.set_node_point_size(1.0); return
        if key == glfw.KEY_F5:
            eng.renderer.set_node_point_size(8.0); return
        if key == glfw.KEY_F6:
            self.toggle_panel("view_filter"); return
        if key == glfw.KEY_F7:
            eng.apply_plane_filter(None); return
        if key == glfw.KEY_F8:
            eng.cam.set_view_preset("front"); return
        if key == glfw.KEY_F9:
            eng.cam.set_view_preset("top"); return
        if key == glfw.KEY_F10:
            eng.cam.set_view_preset("right"); return
        if key == glfw.KEY_F11:
            if self._import_s2k():
                return
        if key == glfw.KEY_F12:
            self.toggle_panel("plane_manager")
            return
        if key == glfw.KEY_D:
            self._toggle_draw_mode(); return
        if key == glfw.KEY_C and eng.draw_mgr.is_active:
            eng.draw_mgr.close(); return
        if key == glfw.KEY_DELETE:
            deleted, rejected = eng.sel_mgr.delete_selected()
            logger.info("Silindi: %s, Reddedildi: %s", deleted, rejected)
            return
        if key == glfw.KEY_H and not eng.input.is_ctrl_pressed():
            self._toggle_selected_visibility(); return
        if key == glfw.KEY_L and not eng.input.is_ctrl_pressed():
            self._toggle_loads_visibility(); return
        if key == glfw.KEY_P and not eng.input.is_ctrl_pressed():
            self.print_(); return

        # Ctrl Kombinasyonları (Registry destekli kısayollar)
        if eng.input.is_ctrl_pressed():
            if key == glfw.KEY_Z:
                eng.sel_mgr.undo(); return
            if key == glfw.KEY_Y:
                eng.sel_mgr.redo(); return
            if key == glfw.KEY_N:
                self.open_new_element_dialog("node", defaults={"label": "N", "x": 0.0, "y": 0.0, "z": 0.0}, repeat=True) if hasattr(self, "open_new_element_dialog") else None
                return
            if key == glfw.KEY_F:
                return
            if key == glfw.KEY_P:
                self.toggle_panel("inspector"); return
            if key == glfw.KEY_R:
                self.toggle_panel("definitions"); return
            if key == glfw.KEY_G:
                self.toggle_panel("grid"); return
            if key == glfw.KEY_S:
                if eng.input.is_shift_pressed():
                    self._save_as_project()
                else:
                    self._quick_save()
                return
            if key == glfw.KEY_O:
                self._on_toolbar_open()
                return

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
        snap = self.engine.snap
        if snap is None or not getattr(self.engine, "hover_visual_enabled", True):
            return
        mx, my = self.engine.input.mouse_pos.x, self.engine.input.mouse_pos.y
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
        self.current_project = project
        if self.engine:
            self.engine.set_scene(project.scene)
            if hasattr(project, "grid") and project.grid and self.engine.grid:
                
                g_conf = project.grid
                
                self.engine.grid.set_coords(g_conf.x_coords, g_conf.y_coords, g_conf.z_coords)
                self.engine.grid.set_origin(g_conf.origin_x, g_conf.origin_y, g_conf.origin_z)
                for plane_name, vis in g_conf.planes_visibility.items():
                    try:
                        self.engine.grid.set_plane(GridPlane[plane_name], visible=vis)
                    except KeyError:
                        pass
                center, size = self.engine.grid.get_bounds()
                self.engine.cam.update_bounds(center, size)
                self.engine.cam.focus_on_model()
        self.inspector.scene = project.scene
        self.visibility_panel.scene = project.scene

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
        if not self.inspector.visible:
            return
        if len(selected_elements) == 1:
            self.inspector.open_element(selected_elements[0])
        elif len(selected_elements) > 1:
            self.inspector.open_multi(selected_elements)
        else:
            self.inspector.clear()

        if self.polygon_edit_panel.visible:
            polygons = [e for e in selected_elements if isinstance(e, Polygon)]
            if polygons:
                self.polygon_edit_panel.set_polygon(polygons[0])

    def _on_hover_changed(self, element):
        pass

    def dispatch_action(self, action_name: str, payload=None):
        """Tüm panellerin CadApp ile haberleştiği tek ve ortak kapı."""
        actions = {
            "run_wind": self._on_run_wind_analysis,
            "save_project": self._save_project,
            "update_geo": lambda: self.engine.renderer.update_geo(self.engine.scene),
            # ...
        }
        if action_name in actions:
            return actions[action_name]() if payload is None else actions[action_name](payload)

    def print_(self):
        print("grid_lines",self.current_project.grid, self.current_project.grid_lines)

    def _import_s2k(self):
        s2k_panel = self.panels["s2k_import"]["instance"]
        s2k_panel.on_import_complete = lambda proj: self.set_project(proj)
        s2k_panel.open()

    def _on_toolbar_open(self):
        self.file_dialog.open(
            mode="open",
            filters=[".cd4"],
            title="Proje Aç (.cd4)",
            initial_dir=os.getcwd(),
            on_select=self._load_project
        )

    def shutdown(self):
        self.ui_backend.shutdown()