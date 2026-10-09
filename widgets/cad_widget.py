# widgets/cad_widget.py
"""
KivyCADWidget — Kivy ile PureKivyEngine arasında köprü.

Sorumluluğu SADECE:
  - Kivy widget yaşam döngüsü (init, resize, canvas)
  - Event'leri Engine API'sine yönlendirme
  - Panel aç/kapa
"""

import time

from kivy.config import Config
Config.set("input", "mouse", "mouse,disable_multitouch")

from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import Callback
from kivy.core.window import Window
from OpenGL.GL import (
    glEnable, glDisable, glClear, glClearColor, glViewport, glScissor,
    glUseProgram, glBindVertexArray, glBindBuffer, glBlendFunc,
    glGetIntegerv,
    GL_SCISSOR_TEST, GL_DEPTH_TEST, GL_CULL_FACE, GL_BLEND,
    GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT,
    GL_ARRAY_BUFFER, GL_ELEMENT_ARRAY_BUFFER,
    GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA,
    GL_VIEWPORT,
)

from core.gl_engine import PureKivyEngine
from core.input_manager import (
    MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT, MOUSE_BUTTON_MIDDLE,
)
from gui.panel_view_filter import ViewFilterPanel
from widgets.event_router import EventRouter
from widgets.panel_manager import PanelManager

from logging_config import CadLogger
logger = CadLogger.get(__name__)


class KivyCADWidget(Widget):

    MIDDLE_DOUBLE_CLICK_INTERVAL = 0.25
    MIDDLE_DOUBLE_CLICK_MAX_DRAG = 4.0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.engine = None
        self.initialized = False
        self.last_time = time.time()
        self.pressed_keys = set()

        self._last_middle_click_time = 0
        self._middle_press_pos = (0, 0)
        self._middle_dragged = False

        # Panel yönetimi
        self.panels = PanelManager(self)
        self.properties_panel = None   # dışarıdan set edilir
        self.view_panel = self.panels.create_view_filter_panel(
            on_apply=self._on_view_filter_apply,
        )

        # Event yönlendirici
        self.router = EventRouter(self)

        # Canvas
        with self.canvas:
            self.callback = Callback(self._draw_gl)

        # Bindings
        self.bind(size=self._on_widget_resize, pos=self._on_widget_resize)

        Window.bind(
            on_key_down=self._on_key_down,
            on_key_up=self._on_key_up,
            mouse_pos=self._on_global_mouse_move,
        )

        Clock.schedule_interval(self.update, 1.0 / 60.0)

    # ------------------------------------------------------------------
    # ENGINE LIFECYCLE
    # ------------------------------------------------------------------
    def _ensure_engine(self):
        """Engine'i bir kez oluştur."""
        if self.initialized:
            return
        if self.width <= 1 or self.height <= 1:
            return

        try:
            logger.info("[INIT] Engine başlıyor...")
            self.engine = PureKivyEngine(int(self.width), int(self.height))
            self.engine.init_gl()
            self.engine.on_hover_changed_callback = self._on_hover_changed
            self.engine.sel_mgr.on_selection_changed = self._on_selection_changed

            if self.properties_panel is not None:
                self.properties_panel.controller = self.engine.edit

            if self.view_panel is not None:
                self.view_panel.set_camera(self.engine.cam)

            self.initialized = True
            logger.info("Kivy OpenGL Engine Başarıyla İlklendirildi!")
        except Exception:
            import traceback
            logger.exception("INIT HATASI")
            traceback.print_exc()
            self.initialized = True

    # ------------------------------------------------------------------
    # RENDER
    # ------------------------------------------------------------------
    def _draw_gl(self, instr):
        self._ensure_engine()
        if not self.initialized:
            return

        # Panel açıksa sadece panel güncellensin, sahne çizilmesin
        if self.panels.is_any_open():
            return

        current_time = time.time()
        dt = current_time - self.last_time
        self.last_time = current_time

        w, h = int(self.width), int(self.height)
        if w <= 0 or h <= 0:
            return

        win_w, win_h = Window.size
        x, y = int(self.x), int(win_h - self.y - h)

        glEnable(GL_SCISSOR_TEST)
        glScissor(x, y, w, h)
        glViewport(x, y, w, h)

        try:
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
                    w, h,
                    active=(snap_node is not None),
                )
        finally:
            glDisable(GL_SCISSOR_TEST)
            glViewport(0, 0, int(win_w), int(win_h))
            glUseProgram(0)
            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
            glDisable(GL_DEPTH_TEST)
            glDisable(GL_CULL_FACE)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    # ------------------------------------------------------------------
    # RESIZE
    # ------------------------------------------------------------------
    def _on_widget_resize(self, *args):
        if self.engine:
            self.engine.resize(max(1, int(self.width)), max(1, int(self.height)))
        self.panels.reposition_all()

    # ------------------------------------------------------------------
    # FRAME LOOP
    # ------------------------------------------------------------------
    def update(self, dt):
        if self.engine and self.engine.pending_pick_check:
            self.engine.check_pick_result()
        self.canvas.ask_update()

    # ------------------------------------------------------------------
    # INPUT — EventRouter'a devredilir
    # ------------------------------------------------------------------
    def _on_key_down(self, window, key, scancode, codepoint, modifiers):
        if self.engine and self.engine.input:
            self.engine.input.handle_key_down(key, modifiers)
        self.pressed_keys.add(key)
        return self.router.on_key_down(key, scancode, codepoint, modifiers)

    def _on_key_up(self, window, key, scancode):
        self.pressed_keys.discard(key)
        if self.engine and self.engine.input:
            self.engine.input.handle_key_up(key)   # ← tek satır

    def on_touch_down(self, touch):
        if self.panels.is_any_open():
            if self.panels.collide(touch.pos):
                return super().on_touch_down(touch)
            return False
        return self.router.on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.panels.is_any_open():
            if self.panels.collide(touch.pos):
                return super().on_touch_move(touch)
            return False
        return self.router.on_touch_move(touch)

    def on_touch_up(self, touch):
        if self.panels.is_any_open():
            if self.panels.collide(touch.pos):
                return super().on_touch_up(touch)
            return False
        return self.router.on_touch_up(touch)

    def _on_global_mouse_move(self, window, pos):
        if self.panels.is_any_open():
            return
        self.router.on_global_mouse_move(pos)

    # ------------------------------------------------------------------
    # PANEL / SELECTION CALLBACKS
    # ------------------------------------------------------------------
    def _on_view_filter_apply(self, camera):
        if not self.engine:
            return
        self.engine.renderer.apply_plane_filter(camera)
        if self.engine.scene:
            self.engine.renderer.update_geo(self.engine.scene)
        self.canvas.ask_update()

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