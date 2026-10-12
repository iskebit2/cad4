# app/cad_window.py


"""
GLFW penceresi + main loop.
Kivy'deki Window + Clock.schedule_interval(1/60) işini yapar.
"""
import time
import glfw
from OpenGL.GL import glViewport

from logging_config import CadLogger
logger = CadLogger.get(__name__)


class CadWindow:

    def __init__(self, width=1280, height=800, title="CAD4"):
        self.width = width
        self.height = height
        self.title = title

        self.window = None
        self.fb_width = width
        self.fb_height = height
        self.dpi_scale = 1.0

        self.on_focus = None

        # Callback'ler (dışarıdan set edilir)
        self.on_resize     = None    # (w, h)
        self.on_key_down   = None    # (key, scancode, mods)
        self.on_key_up     = None    # (key, scancode)
        self.on_mouse_button = None # (button, action, mods)
        self.on_mouse_move   = None # (x, y)
        self.on_scroll       = None # (xoffset, yoffset)
        self.on_char         = None # (codepoint)

        self._last_mouse = (0.0, 0.0)
        self._time_last = time.time()

        

    def _cb_focus(self, win, focused):
        if callable(self.on_focus):
            self.on_focus(bool(focused))

    def on_char(self, codepoint):
        pass

    # ------------------------------------------------------------------
    def create(self):
        if not glfw.init():
            raise RuntimeError("GLFW başlatılamadı")

        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.SAMPLES, 4)
        glfw.window_hint(glfw.VISIBLE, glfw.TRUE)
        glfw.window_hint(glfw.FOCUSED, glfw.TRUE)
        glfw.window_hint(glfw.RESIZABLE, glfw.TRUE)
        glfw.window_hint(glfw.FOCUS_ON_SHOW, glfw.TRUE)

        self.window = glfw.create_window(
            self.width, self.height, self.title, None, None
        )
        if not self.window:
            glfw.terminate()
            raise RuntimeError("GLFW penceresi oluşturulamadı")

        glfw.make_context_current(self.window)
        glfw.swap_interval(1)
        glfw.show_window(self.window)
        glfw.focus_window(self.window)

        self._wire_callbacks()

        # Pencere gerçekten aktif olana kadar bekle
        for _ in range(10):
            glfw.poll_events()
            time.sleep(0.01)

        self.fb_width, self.fb_height = glfw.get_framebuffer_size(self.window)
        logger.info("Pencere oluşturuldu: %dx%d", self.fb_width, self.fb_height)
        return self.window

    # ------------------------------------------------------------------
    def _wire_callbacks(self):
        w = self.window

        glfw.set_framebuffer_size_callback(w, self._cb_resize)
        glfw.set_key_callback(w, self._cb_key)
        glfw.set_mouse_button_callback(w, self._cb_mouse_button)
        glfw.set_cursor_pos_callback(w, self._cb_mouse_move)
        glfw.set_scroll_callback(w, self._cb_scroll)
        
        glfw.set_char_callback(w, self._cb_char)
        glfw.set_window_focus_callback(self.window, self._cb_focus)

        # #logger.debug("GLFW callback'leri başarıyla bağlandı.")

    def _cb_resize(self, win, w, h):
        self.fb_width, self.fb_height = w, h
        if callable(self.on_resize):
            self.on_resize(w, h)

    def _cb_key(self, win, key, scancode, action, mods):
        if action == glfw.PRESS and callable(self.on_key_down):
            self.on_key_down(key, scancode, mods)
        elif action == glfw.RELEASE and callable(self.on_key_up):
            self.on_key_up(key, scancode)

    def _cb_mouse_button(self, win, button, action, mods):
        if callable(self.on_mouse_button):
            self.on_mouse_button(button, action, mods)

    def _cb_mouse_move(self, win, x, y):
        # GLFW ve ImGui aynı sistemi kullanır: sol üst köşe, y aşağı
        self._last_mouse = (x, y)
        if callable(self.on_mouse_move):
            self.on_mouse_move(x, y)

    def _cb_scroll(self, win, xoff, yoff):
        if callable(self.on_scroll):
            self.on_scroll(xoff, yoff)

    def _cb_char(self, win, codepoint):
        
        if callable(self.on_char):
            self.on_char(codepoint)

    # ------------------------------------------------------------------
    def get_mouse_pos(self):
        x, y = glfw.get_cursor_pos(self.window)
        return x, y

    def get_mouse_button(self, button):
        return glfw.get_mouse_button(self.window, button)

    def is_key_pressed(self, key):
        return glfw.get_key(self.window, key) == glfw.PRESS

    # ------------------------------------------------------------------
    def should_close(self):
        return glfw.window_should_close(self.window)

    def swap_buffers(self):
        glfw.swap_buffers(self.window)

    def poll_events(self):
        glfw.poll_events()

    # ------------------------------------------------------------------
    def run(self, frame_callback, target_fps=60):
        target_dt = 1.0 / target_fps

        while not self.should_close():
            now = time.time()
            dt = now - self._time_last
            self._time_last = now

            glfw.poll_events()
            frame_callback(dt)
            self.swap_buffers()

            elapsed = time.time() - now
            if elapsed < target_dt:
                time.sleep(target_dt - elapsed)

    # ------------------------------------------------------------------
    def shutdown(self):
        if self.window:
            glfw.destroy_window(self.window)
            self.window = None
        glfw.terminate()