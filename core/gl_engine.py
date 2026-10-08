# core/gl_engine.py

from kivy.config import Config
Config.set("input", "mouse", "mouse,disable_multitouch")

import time
from pathlib import Path
import glm
from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import Callback, Rectangle, Color, Fbo
from kivy.core.window import Window
from OpenGL.GL import *

import render.shaderprogram as shaderprogram
from render.shaderprogram import ShaderProgram
from core.camera import Camera
from domain.scene import Scene
from ui.inputmanager import (
    InputManager,
    MOUSE_BUTTON_LEFT,
    MOUSE_BUTTON_RIGHT,
    MOUSE_BUTTON_MIDDLE,
)
from core.selection_policy import SelectionPolicy
from tools.gridsystem import GridSystem
from render.scenerenderer import SceneRenderer
from core.selection_manager import SelectionManager
from core.marquee_selector import MarqueeSelector
from tools.loader import ModelLoader
from core.draw_manager import DrawManager
from ui.snapsquare import SnapSquareRenderer

# ─── (1) YENİ IMPORT ───
from core.edit.edit_controller import EditController

from logging_config import CadLogger
logger = CadLogger.get(__name__)

logger.info(".... GL_VERSION: %s", glGetString(GL_VERSION))


SHADER_DIR = Path(shaderprogram.__file__).resolve().parent / "shaders"


# ============================================================
# ENGINE
# ============================================================

class PureKivyEngine:
    """GLFW ve ImGui'den arındırılmış render motoru."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.pending_anim = False
        self.loading = False

        self.shaders = {}
        self.hover_id = 0
        self.hover_element_type = None
        self.hover_enabled = True
        self.last_hover_x = -1
        self.last_hover_y = -1
        self.last_hover_time = 0
        self.hover_throttle = 0.05
        self.pending_pick_check = False

        self.cam = self.input = None
        self.scene = None
        self.renderer = None
        self.pick_pass = None
        self.sel_mgr = None
        self.marquee = None
        self.loader = None
        self.draw_mgr = None
        self.snap = None
        self.edit = None          # ─── (2) YENİ: EditController ───

    def init_gl(self):
        self._init_shaders()
        self._init_camera()
        self._init_components()

    def _init_shaders(self):
        shader_list = ["pick", "standard", "node", "simple", "2d_overlay", "preview", "grid"]
        for name in shader_list:
            v = SHADER_DIR / f"{name}.vert"
            f = SHADER_DIR / f"{name}.frag"
            try:
                self.shaders[name] = ShaderProgram(name, str(v), str(f))
            except Exception as e:
                logger.exception("Shader yükleme hatası (%s)", name)
                self.shaders[name] = None

        self.pick_s = self.shaders.get("pick")
        self.standard_s = self.shaders.get("standard")
        self.node_s = self.shaders.get("node")
        self.simple_s = self.shaders.get("simple")
        self.overlay_s = self.shaders.get("2d_overlay")
        self.preview_s = self.shaders.get("preview")
        self.grid_s = self.shaders.get("grid")

    def _init_camera(self):
        self.cam = Camera()
        self.cam.set_aspect(self.w, self.h)
        self.cam.pitch = 30.0
        self.cam.yaw = -45.0
        self.cam.distance = 50.0
        self.cam._update_position()

    def _init_components(self):
        self.scene = Scene()
        self.input = InputManager()
        self.sel_policy = SelectionPolicy(self.input)
        self.grid = GridSystem(self.grid_s)
        self.snap = SnapSquareRenderer()

        self.renderer = SceneRenderer(
            pick_s=self.pick_s,
            standard_s=self.standard_s,
            node_s=self.node_s,
            simple_s=self.simple_s,
            overlay_s=self.overlay_s,
            w=self.w, h=self.h,
        )
        self.renderer.set_cam(self.cam)
        self.renderer.set_grid(self.grid)
        self.renderer.set_snap(self.snap)
        self.renderer.set_engine(self)

        self.pick_pass = self.renderer.pick_pass
        self.sel_mgr = SelectionManager(self.renderer)
        self.marquee = MarqueeSelector(self, self.sel_mgr, self.sel_policy)
        self.renderer.set_marquee(self.marquee)
        self.loader = ModelLoader(self)
        self.draw_mgr = DrawManager(self)

        # ─── (3) YENİ: EditController ───
        self.edit = EditController(self)

    def resize(self, w, h):
        self.w, self.h = max(1, w), max(1, h)
        if self.cam:
            self.cam.set_aspect(self.w, self.h)
        if self.renderer:
            self.renderer.resize(self.w, self.h)
        if self.pick_pass:
            self.pick_pass.set_viewport(self.w, self.h)

    def _handle_pick_from_hover(self, ctrl=False):
        if self.hover_id > 0 and self.renderer and self.renderer.pick_pass:
            element = self.renderer.get_element_from_id(self.hover_id)
            if element:
                self.sel_mgr.select(element, additive=ctrl)

    def _get_element_type_from_element(self, element):
        if element is None:
            return None
        if hasattr(element, 'element_type'):
            return element.element_type
        class_name = element.__class__.__name__.lower()
        for key in ('node', 'frame', 'area', 'link', 'polygon'):
            if key in class_name:
                return key
        return None

    def _get_priority_from_type(self, element_type):
        if element_type is None or not isinstance(element_type, str):
            return -1
        priority_map = {'node': 2, 'frame': 1, 'area': 0, 'link': 0, 'polygon': 0}
        return priority_map.get(element_type.lower(), -1)

    def _clear_hover(self):
        self.hover_id = 0
        self.hover_element_type = None
        self.input.mouse_world_valid = False

    def _update_hover(self, pick_id):
        if pick_id == self.hover_id:
            return
        self.hover_id = pick_id

        if pick_id > 0:
            element = self.renderer.get_element_from_id(pick_id)
            if element is None:
                self._clear_hover()
                return
            element_type = self._get_element_type_from_element(element)
            self.hover_element_type = element_type

            if element_type == 'node' and hasattr(element, 'x'):
                self.input.mouse_world_pos = glm.vec3(element.x, element.y, element.z)
                self.input.mouse_world_valid = True
        else:
            self._clear_hover()

    def _check_pick_result(self):
        if not self.pending_pick_check:
            return False
        try:
            pick_id, _, _ = self.renderer.check_pick()
            if pick_id is not None:
                self.pending_pick_check = False
                self._update_hover(pick_id)
                return True
            else:
                if not self.renderer.pick_pass.pending_pick:
                    self.pending_pick_check = False
        except Exception as e:
            logger.error(f"Pick kontrolü hatası: {e}")
            self.pending_pick_check = False
        return False

    def _start_hover_pick(self, x, y):
        if not self.renderer or not self.renderer.pick_pass:
            return
        current_time = time.time()
        if (current_time - self.last_hover_time) < self.hover_throttle:
            return
        if x == self.last_hover_x and y == self.last_hover_y:
            return

        success = self.renderer.pick_async(x, y)
        if success:
            self.last_hover_x = x
            self.last_hover_y = y
            self.last_hover_time = current_time
            self.pending_pick_check = True

    def _update_world_pos(self, x, y):
        if not self.cam or not self.input:
            return
        if self.hover_id > 0 and self.hover_element_type == 'node':
            return

        v = self.cam.get_view_matrix()
        p = self.cam.get_projection_matrix()
        nx = 2 * x / self.w - 1
        ny = 1 - 2 * y / self.h
        inv = glm.inverse(p * v)

        near = inv * glm.vec4(nx, ny, -1, 1)
        far = inv * glm.vec4(nx, ny, 1, 1)
        near = glm.vec3(near) / near.w
        far = glm.vec3(far) / far.w
        direction = glm.normalize(far - near)

        if abs(direction.z) > 1e-6:
            t = -near.z / direction.z
            if t > 0:
                self.input.mouse_world_pos = near + direction * t
                self.input.mouse_world_valid = True
                return
        self.input.mouse_world_valid = False

    def enable_hover(self, enabled=True):
        self.hover_enabled = enabled
        if not enabled and self.hover_id != 0:
            self.hover_id = 0
            self.hover_element_type = None

    def load_model(self, builder):
        self.scene = builder.scene
        self.renderer.update_geo(self.scene)
        self.fit_view()

    def fit_view(self):
        if not self.renderer:
            return
        self.renderer._update_bounds_from_nodes()
        c, s = self.renderer.get_bounds()
        self.cam.update_bounds(c, s)
        self.cam.focus_on_model()

    def clear_scene(self):
        self.scene = Scene()
        self.renderer.set_scene(self.scene)
        for r in [self.renderer.frame_r, self.renderer.node_r,
                  self.renderer.area_r, self.renderer.link_r,
                  self.renderer.polygon_r]:
            r.elements = []

    def set_scene(self, scene):
        self.scene = scene
        self.renderer.update_geo(self.scene)
        self.fit_view()


# ============================================================
# WIDGET
# ============================================================

class KivyCADWidget(Widget):

    MIDDLE_DOUBLE_CLICK_INTERVAL = 0.25
    MIDDLE_DOUBLE_CLICK_MAX_DRAG = 4.0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.engine = None
        self.initialized = False
        self.properties_panel = None

        self.last_time = time.time()
        self.pressed_keys = set()

        self._last_middle_click_time = 0
        self._middle_press_pos = (0, 0)
        self._middle_dragged = False

        with self.canvas:
            self.callback = Callback(self._draw_gl)

        self.bind(size=self._on_widget_resize, pos=self._on_widget_resize)

        Window.bind(
            on_key_down=self._on_key_down,
            on_key_up=self._on_key_up,
            mouse_pos=self._on_global_mouse_move,
        )

        Clock.schedule_interval(self.update, 1.0 / 60.0)
    @staticmethod
    def _is_modal_open():
        from kivy.uix.popup import Popup
        from kivy.uix.modalview import ModalView
        from kivy.core.window import Window

        # ⬇️ Basit cache: her 100ms'de bir yeniden tara
        import time
        now = time.time()
        cache = KivyCADWidget._modal_cache
        if now - cache.get("t", 0) < 0.1:
            return cache.get("v", False)

        result = False
        for top in Window.children:
            try:
                for w in top.walk():
                    if isinstance(w, (Popup, ModalView)) and w.parent is not None:
                        result = True
                        break
                if result:
                    break
            except Exception:
                continue

        KivyCADWidget._modal_cache = {"t": now, "v": result}
        return result

    _modal_cache = {}
    
    def _draw_gl(self, instr):
        if not self.initialized:
            if self.width <= 1 or self.height <= 1:
                return
            self.engine = PureKivyEngine(int(self.width), int(self.height))
            self.engine.init_gl()
            self.engine.on_hover_changed_callback = self._on_hover_changed
            self.engine.sel_mgr.on_selection_changed = self._on_selection_changed

            # ─── (4) YENİ: panel controller'ı bağla ───
            if self.properties_panel is not None:
                self.properties_panel.controller = self.engine.edit

            self.initialized = True
            logger.info("Kivy OpenGL Engine Başarıyla İlklendirildi!")
            return

        current_time = time.time()
        dt = current_time - self.last_time
        self.last_time = current_time

        if not self.engine.loading:
            self._frames = getattr(self, '_frames', 0) + 1
            self._fps_time = getattr(self, '_fps_time', 0) + dt
            if self._fps_time >= 1.0:
                fps = self._frames / self._fps_time
                self._frames = 0
                self._fps_time = 0

        if self.engine.pending_anim:
            self.engine.renderer.start_anim(4)
            self.engine.pending_anim = False

        w = int(self.width)
        h = int(self.height)

        if w <= 0 or h <= 0:
            return

        win_w, win_h = Window.size
        x = int(self.x)
        y = int(win_h - self.y - h)

        glViewport(x, y, w, h)

        glEnable(GL_DEPTH_TEST)
        glClearColor(0.08, 0.10, 0.16, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        self.engine.renderer.set_dt(dt)
        self.engine.renderer.render(self.engine.cam)

        if self.engine.draw_mgr.is_active:
            mvp = (self.engine.cam.get_projection_matrix()
                @ self.engine.cam.get_view_matrix())
            self.engine.draw_mgr.render_preview(mvp, self.engine.preview_s)

        if self.engine.snap is not None and self.engine.draw_mgr.is_active:
            snap_node = self.engine.draw_mgr.hover_node

            self.engine.snap.draw_snap(
                self.engine.input.mouse_pos.x,
                self.engine.input.mouse_pos.y,
                w,
                h,
                active=(snap_node is not None),
            )

        glUseProgram(0)
        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_CULL_FACE)
        glDisable(GL_SCISSOR_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def _on_widget_resize(self, *args):
        if self.engine:
            w = max(1, int(self.width))
            h = max(1, int(self.height))
            self.engine.resize(w, h)

    def _fit_view(self):
        if self.engine:
            self.engine.fit_view()

    def _on_key_down(self, window, key, scancode, codepoint, modifiers):
        # ⬇️ YENİ: Modal açıkken kısayolları devre dışı bırak
        if self._is_modal_open():
            # Sadece ESC'ye izin ver (modal kapatabilsin)
            if key == 27:
                return False   # Event'i modal'a bırak
            return True        # Diğer tuşları yut
        
        self.pressed_keys.add(key)

        if self.engine and self.engine.input:
            self.engine.input.update_modifiers(modifiers)

        # ---- F3: render modu ----
        if key == 284:
            if self.engine:
                mode = self.engine.renderer.toggle_render_mode()
                logger.info(f"Render mode: {mode}")
            return True

        # ---- D: Draw Modunu Aç/Kapat (Toggle) ----
        if key == 100:  # 'd' tuşu
            if self.engine:
                if self.engine.draw_mgr.is_active:
                    self.engine.draw_mgr.close()
                    logger.info("Çizim Modu Kapatıldı (D)")
                else:
                    self.engine.draw_mgr.start()
                    logger.info("Çizim Modu Başlatıldı (D)")
            return True

        # ---- C: draw modu kapat ----
        if key == 99:
            if self.engine and self.engine.draw_mgr.is_active:
                self.engine.draw_mgr.close()
                return True

        # ---- ESC ----
        if key == 27:
            return self._handle_escape()

        # ---- Delete ----
        if key == 127:
            if self.engine:
                deleted, rejected = self.engine.sel_mgr.delete_selected()
                logger.info(f"Silindi: {deleted}, Reddedildi: {rejected}")
            return True

        # ---- Ctrl+Z ----
        if key == 122 and 'ctrl' in modifiers:
            if self.engine:
                success = self.engine.sel_mgr.undo()
                if success:
                    logger.info("Geri alındı")
                else:
                    logger.info("Geri alınacak işlem yok")
            return True

        # ---- Ctrl+Y ----
        if key == 121 and 'ctrl' in modifiers:
            if self.engine:
                success = self.engine.sel_mgr.redo()
                if success:
                    logger.info("Yeniden yapıldı")
                else:
                    logger.info("Yeniden yapılacak işlem yok")
            return True

        # ─── (5) DEĞİŞTİ: Ctrl+P test bloğu kaldırıldı,
        #     yerine Ctrl+N (yeni node) ve Ctrl+F (yeni frame) ───

        # ---- Ctrl+N: yeni node formu ----
        if key == 110 and 'ctrl' in modifiers:
            if self.properties_panel is not None:
                self.properties_panel.show_new_element(
                    "node",
                    defaults={
                        "label": "N",
                        "x": 0.0, "y": 0.0, "z": 0.0,
                    },
                    repeat=True,          # ← ardışık ekleme
                )
            return True

        # ---- Ctrl+F: yeni frame formu ----
        if key == 102 and 'ctrl' in modifiers:
            if self.properties_panel is not None:
                self.properties_panel.show_new_element("frame", defaults={
                    "label": "F1",
                    "node_i_id": "",
                    "node_j_id": "",
                    "section_name": "",
                })
            return True

        return False

    def _handle_escape(self):
        if not self.engine:
            return True

        if self.properties_panel and self.properties_panel.opacity > 0:
            self.properties_panel.hide()
            return True

        if self.engine.draw_mgr.is_active:
            self.engine.draw_mgr.cancel()
            return True

        if self.engine.marquee and self.engine.marquee.is_active:
            self.engine.marquee.cancel_selection()
            self.engine._clear_hover()
            return True

        if self.engine.pending_pick_check:
            self.engine.pending_pick_check = False

        self.engine._clear_hover()
        self.engine.sel_mgr.clear()
        return True

    def _on_key_up(self, window, key, scancode):
        self.pressed_keys.discard(key)

        if self.engine and self.engine.input:
            if key in (303, 304):
                self.engine.input.set_modifier_state("shift", False)
            elif key in (305, 306):
                self.engine.input.set_modifier_state("ctrl", False)
            elif key in (307, 308):
                self.engine.input.set_modifier_state("alt", False)

    def on_touch_up(self, touch):
        # ⬇️ YENİ: Modal açıkken hiçbir şey yapma
        if self._is_modal_open():
            return False
        if touch.grab_current is not self:
            return False

        x = touch.x - self.x
        y = self.height - (touch.y - self.y)

        if touch.button == 'left':
            self._on_left_up(x, y)

        elif touch.button == 'right':
            self.engine.input.set_button_state(MOUSE_BUTTON_RIGHT, False)

        elif touch.button == 'middle':
            self.engine.input.set_button_state(MOUSE_BUTTON_MIDDLE, False)
            self.engine.pending_pick_check = False
            self.engine._clear_hover()

        touch.ungrab(self)
        return True
    
    def on_touch_move(self, touch):
        # ⬇️ YENİ: Modal açıkken hiçbir şey yapma
        if self._is_modal_open():
            return False
        if touch.grab_current is not self or not self.engine:
            return False

        x = touch.x - self.x
        y = self.height - (touch.y - self.y)

        dx = touch.dx
        dy = -touch.dy

        self.engine.input.update_mouse_position(x, y)

        # 1. ORTA TUŞ: Pan / Orbit (Çizim modunda olsak bile öncelikli)
        if touch.button == 'middle':
            self._on_middle_move(dx, dy, x, y)
            return True

        # 2. SHIFT + SOL TIK: Kamera Orbit (Döndürme)
        if touch.button == 'left' and self.engine.input.is_shift_pressed():
            self.engine.cam.orbit(dx, dy)
            if self.engine.hover_id != 0:
                self.engine._clear_hover()
            return True

        # 3. ÇİZİM MODU: Sadece kamera hareketi yapılmıyorsa çizim önizlemesini/snapping'i güncelle
        if self.engine.draw_mgr.is_active:
            self.engine.draw_mgr.on_mouse_move(x, y)
            return True

        if touch.button == 'right':
            return True

        if self.engine.marquee and self.engine.marquee.is_active:
            self.engine.marquee.update_selection(x, y)
            return True

        self.engine._update_world_pos(x, y)
        self.engine._start_hover_pick(int(x), int(y))
        return True

    def on_touch_down(self, touch):
        # ⬇️ YENİ: Modal açıkken hiçbir şey yapma
        if self._is_modal_open():
            return False
        
        if not self.collide_point(*touch.pos) or not self.engine:
            return False

        x = touch.x - self.x
        y = self.height - (touch.y - self.y)

        touch.grab(self)
        self.engine.input.update_mouse_position(x, y)

        if touch.button == 'scrollup':
            self.engine.cam.zoom(-1.0)
            touch.ungrab(self)
            return True
        if touch.button == 'scrolldown':
            self.engine.cam.zoom(1.0)
            touch.ungrab(self)
            return True

        # Orta tuş (Pan / Orbit) çizim modundan bağımsız her zaman çalışmalı
        if touch.button == 'middle':
            self._on_middle_down(x, y, touch)
            return True

        if touch.button == 'right':
            self.engine.input.set_button_state(MOUSE_BUTTON_RIGHT, True)

            element = None
            if self.engine.hover_id > 0:
                element = self.engine.renderer.get_element_from_id(self.engine.hover_id)

            if self.properties_panel:
                if element:
                    self.properties_panel.show_element(element)
                else:
                    self.properties_panel.hide()

            return True

        if touch.button == 'left':
            self._on_left_down(x, y)
            return True

        return True

    def _on_middle_down(self, x, y, touch):
        self.engine.input.set_button_state(MOUSE_BUTTON_MIDDLE, True)
        self.engine.pending_pick_check = False
        self.engine._clear_hover()

        now = time.time()

        if (now - self._last_middle_click_time) < self.MIDDLE_DOUBLE_CLICK_INTERVAL:
            self._last_middle_click_time = 0
            self._fit_view()
            touch.ungrab(self)
            return

        self._last_middle_click_time = now
        self._middle_press_pos = (x, y)
        self._middle_dragged = False

    def _on_left_down(self, x, y):
        self.engine.input.set_button_state(MOUSE_BUTTON_LEFT, True)

        if self.engine.draw_mgr.is_active:
            self.engine.draw_mgr.on_mouse_click(x, y)
            return

        if self.engine.input.is_shift_pressed():
            return

        self.engine.marquee.start_selection(x, y)
        self.engine._update_world_pos(x, y)
        self.engine._start_hover_pick(int(x), int(y))


    def _on_middle_move(self, dx, dy, x, y):
        if not self._middle_dragged:
            px, py = self._middle_press_pos
            if ((x - px) ** 2 + (y - py) ** 2) ** 0.5 > self.MIDDLE_DOUBLE_CLICK_MAX_DRAG:
                self._middle_dragged = True
                self._last_middle_click_time = 0

        if self.engine.input.is_ctrl_pressed():
            self.engine.cam.orbit(dx, dy)
        else:
            self.engine.cam.pan(dx, dy)

        self.engine.pending_pick_check = False
        self.engine._clear_hover()


    def _on_left_up(self, x, y):
        self.engine.input.set_button_state(MOUSE_BUTTON_LEFT, False)

        if self.engine.draw_mgr.is_active:
            return

        if self.engine.input.is_shift_pressed():
            return

        if self.engine.marquee.is_active:
            was_drag = self.engine.marquee.end_selection()
            if not was_drag:
                ctrl = self.engine.input.is_ctrl_pressed()
                self.engine._handle_pick_from_hover(ctrl)
                self._update_properties_panel()

    def update(self, dt):
        if self.engine and self.engine.pending_pick_check:
            self.engine._check_pick_result()
        self.canvas.ask_update()

    def _on_global_mouse_move(self, window, pos):
        # ⬇️ YENİ: Modal açıkken CAD widget fareyi güncellemesin
        if self._is_modal_open():
            return
        if not self.engine:
            return
        if not self.collide_point(*pos):
            return

        x = pos[0] - self.x
        y = self.height - (pos[1] - self.y)

        if self.engine.draw_mgr.is_active:
            self.engine.input.update_mouse_position(x, y)
            self.engine.draw_mgr.on_mouse_move(x, y)

    def _on_selection_changed(self, selected_elements):
        if not self.properties_panel:
            return
        if self.properties_panel.opacity == 0:
            return

        if not selected_elements:
            self.properties_panel.hide()
        elif len(selected_elements) == 1:
            self.properties_panel.show_element(selected_elements[0])
        else:
            self.properties_panel.show_selection_summary(selected_elements)

    def _on_hover_changed(self, element):
        if not self.properties_panel or self.properties_panel.opacity == 0:
            return

        if element is not None:
            self.properties_panel.show_element(element)
        else:
            selected = self.engine.sel_mgr.get_selected()
            if len(selected) == 1:
                self.properties_panel.show_element(selected[0])
            elif len(selected) > 1:
                self.properties_panel.show_selection_summary(selected)
            else:
                self.properties_panel.hide()

    def _update_properties_panel(self):
        if not self.properties_panel:
            return
        if self.properties_panel.opacity == 0:
            return

        selected = self.engine.sel_mgr.get_selected()

        if not selected:
            self.properties_panel.hide()
        elif len(selected) == 1:
            self.properties_panel.show_element(selected[0])
        else:
            self.properties_panel.show_selection_summary(selected)