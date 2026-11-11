# app/cad_window.py
from __future__ import annotations

import os
import time
from collections.abc import Callable

import glfw
from imgui_bundle import imgui
from imgui_bundle.python_backends.glfw_backend import GlfwRenderer
from OpenGL.GL import glViewport

from logging_config import CadLogger

logger = CadLogger.get(__name__)


def _load_fonts(font_size: int = 16):
    io = imgui.get_io()
    win_fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    text_font = os.path.join(win_fonts, "segoeui.ttf")
    symbol_font = os.path.join(win_fonts, "seguisym.ttf")

    if not os.path.isfile(text_font):
        io.fonts.add_font_default()
        return None

    font_obj = io.fonts.add_font_from_file_ttf(text_font, font_size)

    if os.path.isfile(symbol_font):
        cfg = imgui.ImFontConfig()
        cfg.merge_mode = True
        io.fonts.add_font_from_file_ttf(symbol_font, font_size, cfg)

    return font_obj


def _apply_dark_theme() -> None:
    s = imgui.get_style()

    s.window_rounding = 6.0
    s.child_rounding = 4.0
    s.frame_rounding = 4.0
    s.popup_rounding = 6.0
    s.scrollbar_rounding = 6.0
    s.grab_rounding = 4.0

    s.window_padding = imgui.ImVec2(10, 10)
    s.frame_padding = imgui.ImVec2(8, 5)
    s.item_spacing = imgui.ImVec2(8, 6)
    s.item_inner_spacing = imgui.ImVec2(6, 4)
    s.indent_spacing = 18
    s.scrollbar_size = 12
    s.frame_border_size = 1.0
    s.window_border_size = 0.0

    def C(col, r, g, b, a=1.0):
        s.set_color_(col, imgui.ImVec4(r, g, b, a))

    C(imgui.Col_.text, 0.90, 0.90, 0.90)
    C(imgui.Col_.text_disabled, 0.50, 0.50, 0.50)
    C(imgui.Col_.window_bg, 0.13, 0.15, 0.20, 0.97)
    C(imgui.Col_.child_bg, 0.10, 0.12, 0.16)
    C(imgui.Col_.popup_bg, 0.11, 0.13, 0.18, 0.98)
    C(imgui.Col_.border, 0.30, 0.33, 0.40, 0.60)
    C(imgui.Col_.border_shadow, 0.00, 0.00, 0.00, 0.00)
    C(imgui.Col_.frame_bg, 0.15, 0.18, 0.24)
    C(imgui.Col_.frame_bg_hovered, 0.20, 0.24, 0.32)
    C(imgui.Col_.frame_bg_active, 0.24, 0.30, 0.40)
    C(imgui.Col_.title_bg, 0.10, 0.13, 0.18)
    C(imgui.Col_.title_bg_active, 0.16, 0.20, 0.28)
    C(imgui.Col_.title_bg_collapsed, 0.10, 0.13, 0.18, 0.70)
    C(imgui.Col_.scrollbar_bg, 0.10, 0.12, 0.16, 0.80)
    C(imgui.Col_.scrollbar_grab, 0.30, 0.36, 0.46)
    C(imgui.Col_.scrollbar_grab_hovered, 0.40, 0.48, 0.60)
    C(imgui.Col_.scrollbar_grab_active, 0.50, 0.60, 0.75)
    C(imgui.Col_.check_mark, 0.40, 0.90, 0.55)
    C(imgui.Col_.slider_grab, 0.35, 0.55, 0.85)
    C(imgui.Col_.slider_grab_active, 0.45, 0.65, 0.95)
    C(imgui.Col_.button, 0.20, 0.26, 0.34)
    C(imgui.Col_.button_hovered, 0.28, 0.36, 0.48)
    C(imgui.Col_.button_active, 0.35, 0.45, 0.60)
    C(imgui.Col_.header, 0.20, 0.28, 0.40)
    C(imgui.Col_.header_hovered, 0.28, 0.38, 0.52)
    C(imgui.Col_.header_active, 0.35, 0.48, 0.65)
    C(imgui.Col_.separator, 0.30, 0.33, 0.40, 0.60)
    C(imgui.Col_.separator_hovered, 0.40, 0.48, 0.60, 0.80)
    C(imgui.Col_.separator_active, 0.50, 0.60, 0.75)
    C(imgui.Col_.resize_grip, 0.40, 0.48, 0.60, 0.60)
    C(imgui.Col_.resize_grip_hovered, 0.55, 0.65, 0.80, 0.80)
    C(imgui.Col_.resize_grip_active, 0.65, 0.78, 0.95)
    C(imgui.Col_.text_link, 0.55, 0.75, 1.00)
    C(imgui.Col_.text_selected_bg, 0.30, 0.50, 0.80, 0.60)


class CadWindow:

    def __init__(self, width: int = 1280, height: int = 800, title: str = "CAD4"):
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
        logger.debug("Pencere hazır: %dx%d", self.fb_width, self.fb_height)

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
        logger.debug("[CadWindow] ImGui hazır (docking enabled, title-bar move only)")

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