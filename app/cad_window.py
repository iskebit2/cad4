# app/cad_window.py
from __future__ import annotations

from collections.abc import Callable
import glfw
from OpenGL.GL import glViewport
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class CadWindow:
    """Saf GLFW penceresi. ImGui, UIHost veya CadApp bilmez."""

    def __init__(self, width: int = 1200, height: int = 800, title: str = "CAD4"):
        self.width = width
        self.height = height
        self.title = title
        self.window = None
        self.fb_width = width
        self.fb_height = height

        self.on_resize: Callable[[int, int], None] | None = None
        self.on_key: Callable[[int, int, int, int], None] | None = None
        self.on_mouse_button: Callable[[int, int, int], None] | None = None
        self.on_mouse_move: Callable[[float, float], None] | None = None
        self.on_scroll: Callable[[float, float], None] | None = None
        self.on_char: Callable[[int], None] | None = None
        self.on_focus: Callable[[bool], None] | None = None

    def create(self) -> None:
        if not glfw.init():
            raise RuntimeError("GLFW başlatılamadı")

        glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
        glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
        glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
        glfw.window_hint(glfw.SAMPLES, 4)
        glfw.window_hint(glfw.VISIBLE, glfw.TRUE)
        glfw.window_hint(glfw.FOCUSED, glfw.TRUE)
        glfw.window_hint(glfw.RESIZABLE, glfw.TRUE)

        self.window = glfw.create_window(self.width, self.height, self.title, None, None)
        if not self.window:
            glfw.terminate()
            raise RuntimeError("GLFW penceresi oluşturulamadı")

        glfw.make_context_current(self.window)
        glfw.swap_interval(1)
        glfw.show_window(self.window)
        glfw.focus_window(self.window)

        self._wire_callbacks()
        glfw.poll_events()
        self.fb_width, self.fb_height = glfw.get_framebuffer_size(self.window)
        logger.info("[CadWindow] Hazır: %dx%d", self.fb_width, self.fb_height)

    def _wire_callbacks(self) -> None:
        w = self.window
        glfw.set_framebuffer_size_callback(w, self._cb_resize)
        glfw.set_key_callback(w, self._cb_key)
        glfw.set_mouse_button_callback(w, self._cb_mouse_button)
        glfw.set_cursor_pos_callback(w, self._cb_mouse_move)
        glfw.set_scroll_callback(w, self._cb_scroll)
        glfw.set_char_callback(w, self._cb_char)
        glfw.set_window_focus_callback(w, self._cb_focus)

    def _cb_resize(self, win, w: int, h: int) -> None:
        self.fb_width, self.fb_height = w, h
        glViewport(0, 0, w, h)
        if self.on_resize:
            self.on_resize(w, h)

    def _cb_key(self, win, key: int, scancode: int, action: int, mods: int) -> None:
        if self.on_key:
            self.on_key(key, scancode, action, mods)

    def _cb_mouse_button(self, win, button: int, action: int, mods: int) -> None:
        if self.on_mouse_button:
            self.on_mouse_button(button, action, mods)

    def _cb_mouse_move(self, win, x: float, y: float) -> None:
        if self.on_mouse_move:
            self.on_mouse_move(x, y)

    def _cb_scroll(self, win, xoff: float, yoff: float) -> None:
        if self.on_scroll:
            self.on_scroll(xoff, yoff)

    def _cb_char(self, win, codepoint: int) -> None:
        if self.on_char:
            self.on_char(codepoint)

    def _cb_focus(self, win, focused: bool) -> None:
        if self.on_focus:
            self.on_focus(bool(focused))

    def poll_events(self) -> None:
        glfw.poll_events()

    def swap_buffers(self) -> None:
        glfw.swap_buffers(self.window)

    def request_close(self) -> None:
        if self.window:
            glfw.set_window_should_close(self.window, True)

    def should_close(self) -> bool:
        return glfw.window_should_close(self.window)

    def shutdown(self) -> None:
        if self.window:
            glfw.destroy_window(self.window)
            self.window = None
        glfw.terminate()