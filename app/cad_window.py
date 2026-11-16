# app/cad_window.py
from __future__ import annotations


import time
from collections.abc import Callable

import glfw
from imgui_bundle import imgui
from imgui_bundle.python_backends.glfw_backend import GlfwRenderer
from OpenGL.GL import glViewport
from assets.themes import _load_fonts, _apply_dark_theme
from logging_config import CadLogger
logger = CadLogger.get(__name__)



class CadWindow:

    def __init__(self, width: int = 1200, height: int = 800, title: str = "CAD4"):
        self.width = width
        self.height = height
        self.title = title

        self.window = None
        self.imgui_backend: GlfwRenderer | None = None

        self.fb_width = width
        self.fb_height = height
        self.dpi_scale = 1.0

        self.on_resize: Callable[[int, int], None] | None = None
        self.on_key: Callable[[int, int, int, int], None] | None = None
        self.on_mouse_button: Callable[[int, int, int], None] | None = None
        self.on_mouse_move: Callable[[float, float], None] | None = None
        self.on_scroll: Callable[[float, float], None] | None = None
        self.on_char: Callable[[int], None] | None = None
        self.on_focus: Callable[[bool], None] | None = None

        self.is_shortcut_registered: Callable[[int, int], bool] | None = None

        self._time_last = time.time()

    # ------------------------------------------------------------------
    def create(self) -> None:
        self._init_glfw()
        self._init_imgui()

        for _ in range(10):
            glfw.poll_events()
            time.sleep(0.01)

        self.fb_width, self.fb_height = glfw.get_framebuffer_size(self.window)
        logger.info("Pencere hazır: %dx%d", self.fb_width, self.fb_height)

    def _init_glfw(self) -> None:
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

    def _init_imgui(self) -> None:
        imgui.create_context()
        io = imgui.get_io()
        io.config_flags |= imgui.ConfigFlags_.docking_enable
        io.config_windows_move_from_title_bar_only = True   # ★ sadece başlıktan sürükle
        _load_fonts(font_size=16)
        self.imgui_backend = GlfwRenderer(self.window, attach_callbacks=False)
        self._wire_callbacks()
        _apply_dark_theme()
        logger.info("[CadWindow] ImGui hazır (docking enabled, title-bar move only)")

    # ------------------------------------------------------------------
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
        if callable(self.on_resize):
            self.on_resize(w, h)

    def _cb_key(self, win, key: int, scancode: int, action: int, mods: int) -> None:
        if self.imgui_backend:
            self.imgui_backend.keyboard_callback(win, key, scancode, action, mods)

        io = imgui.get_io()
        
        # CapsLock, NumLock gibi yan bitleri temizleyip sadece gerçek modifikatörleri alıyoruz
        clean_mods = mods & (glfw.MOD_SHIFT | glfw.MOD_CONTROL | glfw.MOD_ALT | glfw.MOD_SUPER)
        
        # Motorun binding listesinde bu tuş var mı dinamik olarak soruyoruz
        is_shortcut = False
        if callable(self.is_shortcut_registered):
            is_shortcut = self.is_shortcut_registered(key, clean_mods)

        # Eğer ImGui klavyeyi yakalamışSA VE bu tuş bizim input_bindings'de 
        # tanımladığımız bir kısayol DEĞİLSE yut; kısayolsa motora gönder!
        if io.want_capture_keyboard and not is_shortcut:
            return

        if callable(self.on_key):
            self.on_key(key, scancode, action, mods)

    def _cb_mouse_button(self, win, button: int, action: int, mods: int) -> None:
        if self.imgui_backend:
            self.imgui_backend.mouse_button_callback(win, button, action, mods)
        if callable(self.on_mouse_button):
            self.on_mouse_button(button, action, mods)

    def _cb_mouse_move(self, win, x: float, y: float) -> None:
        if self.imgui_backend:
            self.imgui_backend.mouse_callback(win, x, y)
        if callable(self.on_mouse_move):
            self.on_mouse_move(x, y)

    def _cb_scroll(self, win, xoff: float, yoff: float) -> None:
        if self.imgui_backend:
            self.imgui_backend.scroll_callback(win, xoff, yoff)
        if callable(self.on_scroll):
            self.on_scroll(xoff, yoff)

    def _cb_char(self, win, codepoint: int) -> None:
        if self.imgui_backend:
            self.imgui_backend.char_callback(win, codepoint)
        if callable(self.on_char):
            self.on_char(codepoint)

    def _cb_focus(self, win, focused: bool) -> None:
        if callable(self.on_focus):
            self.on_focus(bool(focused))

    # ------------------------------------------------------------------
    def run(self, frame_callback: Callable[[float], None], target_fps: int = 60) -> None:
        target_dt = 1.0 / target_fps
        self._time_last = time.time()

        while not self.should_close():
            now = time.time()
            dt = now - self._time_last
            self._time_last = now

            glfw.poll_events()
            self.imgui_backend.process_inputs()

            imgui.new_frame()
            frame_callback(dt)
            imgui.render()

            w, h = glfw.get_framebuffer_size(self.window)
            glViewport(0, 0, w, h)
            self.imgui_backend.render(imgui.get_draw_data())
            glfw.swap_buffers(self.window)

            elapsed = time.time() - now
            if elapsed < target_dt:
                time.sleep(target_dt - elapsed)

    # ------------------------------------------------------------------
    def get_mouse_pos(self) -> tuple[float, float]:
        return glfw.get_cursor_pos(self.window)

    def is_key_pressed(self, key: int) -> bool:
        return glfw.get_key(self.window, key) == glfw.PRESS

    def should_close(self) -> bool:
        return glfw.window_should_close(self.window)

    # ------------------------------------------------------------------
    def shutdown(self) -> None:
        if self.imgui_backend:
            self.imgui_backend.shutdown()
            self.imgui_backend = None

        if self.window:
            glfw.destroy_window(self.window)
            self.window = None

        glfw.terminate()