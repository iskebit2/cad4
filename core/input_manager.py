# core/input_manager.py

from __future__ import annotations

import time
from dataclasses import dataclass, field

import glfw
from pyglm import glm


LEFT = 0
RIGHT = 1
MIDDLE = 2


@dataclass
class InputState:
    mouse_pos: glm.vec2 = field(default_factory=lambda: glm.vec2(0, 0))
    mouse_delta: glm.vec2 = field(default_factory=lambda: glm.vec2(0, 0))
    mouse_world_pos: glm.vec3 = field(default_factory=lambda: glm.vec3(0, 0, 0))
    mouse_world_valid: bool = False
    drag_start: tuple[float, float] | None = None
    drag_current: tuple[float, float] | None = None
    is_dragging: bool = False
    drag_threshold: float = 5.0
    buttons: dict[int, bool] = field(default_factory=dict)
    keys: dict[int, bool] = field(default_factory=dict)
    modifiers: int = 0


class InputManager:

    def __init__(self):
        self.state = InputState()
        self._handlers: list = []
        self._fallback = None
        self._bindings: dict[tuple[int, int], callable] = {}
        self._last_click = {LEFT: 0.0, MIDDLE: 0.0}
        self._last_pos = {LEFT: (0.0, 0.0), MIDDLE: (0.0, 0.0)}
        self._captures_mouse = lambda: False
        self._captures_keyboard = lambda: False
        self._global_escape = None

    def set_global_escape(self, fn) -> None:
        self._global_escape = fn
        
    def set_capture_callbacks(self, mouse_fn, keyboard_fn) -> None:
        self._captures_mouse = mouse_fn
        self._captures_keyboard = keyboard_fn

    def register(self, handler) -> None:
        if handler not in self._handlers:
            self._handlers.append(handler)

    def set_fallback(self, handler) -> None:
        self._fallback = handler

    def bind(self, key: int, mods: int, action) -> None:
        self._bindings[(key, mods)] = action

    def is_shift(self) -> bool:
        return bool(self.state.modifiers & glfw.MOD_SHIFT)

    def is_ctrl(self) -> bool:
        return bool(self.state.modifiers & glfw.MOD_CONTROL)

    def is_alt(self) -> bool:
        return bool(self.state.modifiers & glfw.MOD_ALT)

    def on_mouse_button(self, button: int, action: int, mods: int) -> None:
        if self._captures_mouse():
            return
        self.state.modifiers = mods
        x, y = self.state.mouse_pos.x, self.state.mouse_pos.y

        if action == glfw.PRESS:
            self.state.buttons[button] = True
            if button in (LEFT, MIDDLE):
                self.state.drag_start = (x, y)
                self.state.drag_current = (x, y)
                self.state.is_dragging = False
            if self._double_click(button, x, y):
                return
            if self._dispatch("handle_click", x, y, button):
                return
            if self._fallback:
                self._fallback.handle_click(x, y, button)
        else:
            self.state.buttons[button] = False
            if button in (LEFT, MIDDLE):
                self.state.drag_start = None
                self.state.drag_current = None
                self.state.is_dragging = False
            if self._dispatch("handle_release", x, y, button):
                return
            if self._fallback:
                self._fallback.handle_release(x, y, button)

    def on_mouse_move(self, x: float, y: float) -> None:
        if self._captures_mouse():
            return
        dx = x - self.state.mouse_pos.x
        dy = y - self.state.mouse_pos.y
        self.state.mouse_delta = glm.vec2(dx, dy)
        self.state.mouse_pos = glm.vec2(x, y)

        if self.state.drag_start is not None:
            self.state.drag_current = (x, y)
            if not self.state.is_dragging:
                ddx = x - self.state.drag_start[0]
                ddy = y - self.state.drag_start[1]
                if (ddx * ddx + ddy * ddy) ** 0.5 > self.state.drag_threshold:
                    self.state.is_dragging = True

        if self._dispatch("handle_move", x, y, dx, dy):
            return
        if self._fallback:
            self._fallback.handle_move(x, y, dx, dy)

    def on_key(self, key: int, action: int, mods: int) -> None:
        if action == glfw.PRESS and key == glfw.KEY_ESCAPE:
            if self._global_escape is not None:
                self._global_escape()
                return
            
        if action == glfw.PRESS:
            if self._captures_keyboard():
                return
            self.state.modifiers = mods
            self.state.keys[key] = True
            if self._dispatch("handle_key", key, mods):
                return
            bound = self._bindings.get((key, mods))
            if bound is not None:
                bound()
                return
            if self._fallback:
                self._fallback.handle_key(key, mods)
        else:
            self.state.keys[key] = False

    def on_scroll(self, delta: float) -> None:
        if self._captures_keyboard():
            return
        if self._dispatch("handle_scroll", delta):
            return
        if self._fallback:
            self._fallback.handle_scroll(delta)

    def _dispatch(self, method: str, *args) -> bool:
        for h in self._handlers:
            if not getattr(h, "is_active", False):
                continue
            fn = getattr(h, method, None)
            if fn is not None and fn(*args):
                return True
        return False

    def _double_click(self, button: int, x: float, y: float) -> bool:
        if button not in (LEFT, MIDDLE):
            return False
        now = time.monotonic()
        interval = 0.3 if button == LEFT else 0.25
        dt = now - self._last_click[button]
        px, py = self._last_pos[button]
        dist = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
        is_double = dt < interval and dist < 5.0
        self._last_click[button] = 0.0 if is_double else now
        self._last_pos[button] = (x, y)
        return is_double

    def dispatch_move(self, x: float, y: float, dx: float, dy: float) -> bool:
        """Sırayla handler'lara ilet."""
        for h in self._handlers:
            if not getattr(h, "is_active", False):
                continue
            fn = getattr(h, "handle_move", None)
            if callable(fn) and fn(x, y, dx, dy):
                return True
        if self._fallback and hasattr(self._fallback, "handle_move"):
            return bool(self._fallback.handle_move(x, y, dx, dy))
        return False

    def dispatch_click(self, x: float, y: float, button: int) -> bool:
        for h in self._handlers:
            if not getattr(h, "is_active", False):
                continue
            fn = getattr(h, "handle_click", None)
            if callable(fn) and fn(x, y, button):
                return True
        if self._fallback and hasattr(self._fallback, "handle_click"):
            return bool(self._fallback.handle_click(x, y, button))
        return False

    def dispatch_release(self, x: float, y: float, button: int) -> bool:
        for h in self._handlers:
            if not getattr(h, "is_active", False):
                continue
            fn = getattr(h, "handle_release", None)
            if callable(fn) and fn(x, y, button):
                return True
        if self._fallback and hasattr(self._fallback, "handle_release"):
            return bool(self._fallback.handle_release(x, y, button))
        return False

    def dispatch_key(self, key: int, mods: int) -> bool:
        # Escape özel
        if key == glfw.KEY_ESCAPE and self._global_escape:
            if self._global_escape():
                return True
        for h in self._handlers:
            if not getattr(h, "is_active", False):
                continue
            fn = getattr(h, "handle_key", None)
            if callable(fn) and fn(key, mods):
                return True
        if self._fallback and hasattr(self._fallback, "handle_key"):
            return bool(self._fallback.handle_key(key, mods))
        return False

    def dispatch_scroll(self, delta: float) -> bool:
        for h in self._handlers:
            if not getattr(h, "is_active", False):
                continue
            fn = getattr(h, "handle_scroll", None)
            if callable(fn) and fn(delta):
                return True
        if self._fallback and hasattr(self._fallback, "handle_scroll"):
            return bool(self._fallback.handle_scroll(delta))
        return False