from __future__ import annotations

import ctypes
import time
from collections import deque
from collections.abc import Callable

import glfw
import numpy as np
from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_COLOR_BUFFER_BIT, GL_DYNAMIC_DRAW, GL_FALSE,
    GL_FLOAT, GL_FRAGMENT_SHADER, GL_LINES, GL_TRIANGLES, GL_VERTEX_SHADER,
    glAttachShader, glBindBuffer, glBindVertexArray, glBufferData,
    glClear, glClearColor, glCompileShader, glCreateProgram, glCreateShader,
    glDeleteBuffers, glDeleteProgram, glDeleteShader, glDeleteVertexArrays,
    glDrawArrays, glEnableVertexAttribArray, glGenBuffers, glGenVertexArrays,
    glGetUniformLocation, glLineWidth, glLinkProgram, glShaderSource,
    glUniform3f, glUseProgram, glVertexAttribPointer, glViewport,
)

_VERT_SRC = """
#version 330 core
layout (location = 0) in vec2 aPos;
void main() {
    gl_Position = vec4(aPos, 0.0, 1.0);
}
"""

_FRAG_SRC = """
#version 330 core
out vec4 FragColor;
uniform vec3 uColor;
void main() {
    FragColor = vec4(uColor, 1.0);
}
"""


class DebugButton:
    def __init__(self, label: str, ndc_rect: tuple[float, float, float, float], color: tuple[float, float, float], on_click: Callable[[], None]):
        self.label = label
        self.rect = ndc_rect  # (x0, y0, x1, y1)
        self.base_color = color
        self.on_click = on_click
        self.active = False
        self.hovered = False

    def contains(self, nx: float, ny: float) -> bool:
        x0, y0, x1, y1 = self.rect
        return x0 <= nx <= x1 and y0 <= ny <= y1


class GlfwDebugOverlay:
    def __init__(self, width: int, height: int):
        self.width = max(1, width)
        self.height = max(1, height)

        self.mouse_x = 0.0
        self.mouse_y = 0.0
        self.last_click_x = 0.0
        self.last_click_y = 0.0
        self.buttons_down: dict[int, bool] = {0: False, 1: False, 2: False}
        self.scroll_accum = 0.0
        self.mods = 0
        self.focused = True
        self.events: deque[str] = deque(maxlen=12)

        self.on_attach_engine: Callable[[], None] | None = None
        self.on_attach_ui: Callable[[], None] | None = None
        self.on_test_command: Callable[[], None] | None = None

        self.ui_buttons: list[DebugButton] = [
            DebugButton(
                "[1] CAD_APP + ENGINE BAGLA (F9)",
                (-0.92, 0.72, -0.34, 0.88),
                (0.18, 0.45, 0.85),
                self._trigger_engine,
            ),
            DebugButton(
                "[2] IMGUI UI_HOST BAGLA (F10)",
                (-0.29, 0.72, 0.29, 0.88),
                (0.55, 0.30, 0.80),
                self._trigger_ui,
            ),
            DebugButton(
                "[3] ENGINE TEST KOMUTU (F11)",
                (0.34, 0.72, 0.92, 0.88),
                (0.85, 0.48, 0.15),
                self._trigger_test,
            ),
        ]

        self._prog = 0
        self._vao = 0
        self._vbo = 0
        self._u_color = -1
        self._init_gl()
        self.log("ASAMA 1 HAZIR: Sadece GLFW + Input aktif. Butonlara tikla veya F9/F10 bas.")

    def _init_gl(self) -> None:
        vs = glCreateShader(GL_VERTEX_SHADER)
        glShaderSource(vs, _VERT_SRC)
        glCompileShader(vs)

        fs = glCreateShader(GL_FRAGMENT_SHADER)
        glShaderSource(fs, _FRAG_SRC)
        glCompileShader(fs)

        self._prog = glCreateProgram()
        glAttachShader(self._prog, vs)
        glAttachShader(self._prog, fs)
        glLinkProgram(self._prog)
        glDeleteShader(vs)
        glDeleteShader(fs)

        self._u_color = glGetUniformLocation(self._prog, "uColor")
        self._vao = glGenVertexArrays(1)
        self._vbo = glGenBuffers(1)

        glBindVertexArray(self._vao)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 8, ctypes.c_void_p(0))
        glBindVertexArray(0)

    def _trigger_engine(self) -> None:
        if self.ui_buttons[0].active:
            self.log("Engine zaten bagli.")
            return
        if self.on_attach_engine:
            self.on_attach_engine()
            self.ui_buttons[0].active = True
            self.log("ASAMA 2 TAMAM: CadApp + Engine baglandi!")

    def _trigger_ui(self) -> None:
        if not self.ui_buttons[0].active:
            self._trigger_engine()
        if self.ui_buttons[1].active:
            return
        if self.on_attach_ui:
            self.on_attach_ui()
            self.ui_buttons[1].active = True
            self.log("ASAMA 3 TAMAM: ImGui UIHost baglandi!")

    def _trigger_test(self) -> None:
        if not self.ui_buttons[0].active:
            self.log("UYARI: Once [1] Engine'i baglamalisin!")
            return
        if self.on_test_command:
            self.on_test_command()
            self.log("TEST: Engine uzerinden FitView/Komut tetiklendi.")

    def log(self, msg: str) -> None:
        stamp = f"{time.perf_counter() % 1000:06.2f}s"
        line = f"[{stamp}] {msg}"
        self.events.appendleft(line)
        print(line, flush=True)

    def _to_ndc(self, x: float, y: float) -> tuple[float, float]:
        nx = (x / self.width) * 2.0 - 1.0
        ny = 1.0 - (y / self.height) * 2.0
        return nx, ny

    def resize(self, w: int, h: int) -> None:
        self.width = max(1, w)
        self.height = max(1, h)

    def on_mouse_move(self, x: float, y: float) -> None:
        self.mouse_x = x
        self.mouse_y = y
        nx, ny = self._to_ndc(x, y)
        for btn in self.ui_buttons:
            btn.hovered = btn.contains(nx, ny)

    def on_mouse_button(self, button: int, action: int, mods: int) -> bool:
        self.mods = mods
        pressed = action == glfw.PRESS
        self.buttons_down[button] = pressed

        if pressed:
            self.last_click_x = self.mouse_x
            self.last_click_y = self.mouse_y
            nx, ny = self._to_ndc(self.mouse_x, self.mouse_y)
            if button == glfw.MOUSE_BUTTON_LEFT:
                for btn in self.ui_buttons:
                    if btn.contains(nx, ny):
                        self.log(f"BUTON TIKLANDI -> {btn.label}")
                        btn.on_click()
                        return True

        btn_name = {0: "SOL", 1: "SAG", 2: "ORTA"}.get(button, f"BTN_{button}")
        self.log(f"MOUSE {btn_name} {'DOWN' if pressed else 'UP'} ({self.mouse_x:.0f}, {self.mouse_y:.0f})")
        return False

    def on_scroll(self, xoff: float, yoff: float) -> None:
        self.scroll_accum = max(-10.0, min(10.0, self.scroll_accum + yoff))
        self.log(f"SCROLL y={yoff:+.1f}")

    def on_key(self, key: int, scancode: int, action: int, mods: int) -> bool:
        self.mods = mods
        if action == glfw.PRESS:
            name = glfw.get_key_name(key, scancode) or f"KEY_{key}"
            self.log(f"KEY PRESS: {name.upper()} (code={key}, mods={mods})")
            if key == glfw.KEY_F9:
                self._trigger_engine()
                return True
            if key == glfw.KEY_F10:
                self._trigger_ui()
                return True
            if key == glfw.KEY_F11:
                self._trigger_test()
                return True
        return False

    def render(self, clear_bg: bool = True) -> None:
        glViewport(0, 0, self.width, self.height)
        if clear_bg:
            glClearColor(0.08, 0.10, 0.14, 1.0)
            glClear(GL_COLOR_BUFFER_BIT)

        glUseProgram(self._prog)
        glBindVertexArray(self._vao)
        glLineWidth(2.0)

        if clear_bg:
            grid = []
            for i in range(-8, 9, 2):
                v = i / 10.0
                grid.extend([v, -1.0, v, 1.0, -1.0, v, 1.0, v])
            self._draw(grid, GL_LINES, (0.15, 0.18, 0.24))

        # 3 Adım Kontrol Butonları
        for btn in self.ui_buttons:
            x0, y0, x1, y1 = btn.rect
            if btn.active:
                col = (0.15, 0.72, 0.35)  # Bağlandı -> Yeşil
            elif btn.hovered:
                col = tuple(min(1.0, c + 0.18) for c in btn.base_color)
            else:
                col = btn.base_color
            self._draw_rect(x0, y0, x1, y1, col)
            self._draw_border(x0, y0, x1, y1, (0.90, 0.92, 0.96))

        # Sol Alt: Mouse Tuş Durumları [SOL] [ORTA] [SAG]
        for idx, b_id in enumerate((0, 2, 1)):
            x0 = -0.92 + idx * 0.11
            c = (0.20, 0.90, 0.40) if self.buttons_down.get(b_id) else (0.22, 0.25, 0.32)
            self._draw_rect(x0, -0.92, x0 + 0.09, -0.84, c)

        # Modifiers: [SHIFT] [CTRL] [ALT]
        for idx, flag in enumerate((glfw.MOD_SHIFT, glfw.MOD_CONTROL, glfw.MOD_ALT)):
            x0 = -0.52 + idx * 0.11
            c = (0.95, 0.70, 0.15) if (self.mods & flag) else (0.22, 0.25, 0.32)
            self._draw_rect(x0, -0.92, x0 + 0.09, -0.84, c)

        # Fare Crosshair
        nx, ny = self._to_ndc(self.mouse_x, self.mouse_y)
        self._draw([nx - 0.04, ny, nx + 0.04, ny, nx, ny - 0.06, nx, ny + 0.06], GL_LINES, (1.0, 0.95, 0.20))

        glBindVertexArray(0)
        glUseProgram(0)

    def _draw_rect(self, x0: float, y0: float, x1: float, y1: float, color: tuple[float, float, float]) -> None:
        self._draw([x0, y0, x1, y0, x1, y1, x0, y0, x1, y1, x0, y1], GL_TRIANGLES, color)

    def _draw_border(self, x0: float, y0: float, x1: float, y1: float, color: tuple[float, float, float]) -> None:
        self._draw([x0, y0, x1, y0, x1, y0, x1, y1, x1, y1, x0, y1, x0, y1, x0, y0], GL_LINES, color)

    def _draw(self, verts: list[float], mode: int, color: tuple[float, float, float]) -> None:
        arr = np.array(verts, dtype=np.float32)
        glUniform3f(self._u_color, *color)
        glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, arr.nbytes, arr, GL_DYNAMIC_DRAW)
        glDrawArrays(mode, 0, len(arr) // 2)

    def cleanup(self) -> None:
        if self._vbo:
            glDeleteBuffers(1, [self._vbo])
        if self._vao:
            glDeleteVertexArrays(1, [self._vao])
        if self._prog:
            glDeleteProgram(self._prog)