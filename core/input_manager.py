# core/input_manager.py
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

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
    def __init__(self) -> None:
        self.state = InputState()
        self._handlers: list = []
        self._fallback = None
        self._bindings: dict[tuple[int, int], Callable] = {}
        self._last_click = {LEFT: 0.0, RIGHT: 0.0, MIDDLE: 0.0}
        self._last_pos = {LEFT: (0.0, 0.0), RIGHT: (0.0, 0.0), MIDDLE: (0.0, 0.0)}
        self._captures_mouse: Callable[[], bool] | bool = False
        self._captures_keyboard: Callable[[], bool] | bool = False
        self._global_escape: Callable | None = None
        self._context_pick_handler: Callable | None = None

    def set_global_escape(self, fn: Callable | None) -> None:
        self._global_escape = fn

    def set_capture_callbacks(
        self,
        mouse_fn: Callable[[], bool] | bool,
        keyboard_fn: Callable[[], bool] | bool,
    ) -> None:
        self._captures_mouse = mouse_fn
        self._captures_keyboard = keyboard_fn

    def _is_mouse_captured(self) -> bool:
        return bool(self._captures_mouse()) if callable(self._captures_mouse) else bool(self._captures_mouse)

    def _is_keyboard_captured(self) -> bool:
        return bool(self._captures_keyboard()) if callable(self._captures_keyboard) else bool(self._captures_keyboard)

    def register(self, handler) -> None:
        if handler not in self._handlers:
            self._handlers.append(handler)

    def set_fallback(self, handler) -> None:
        self._fallback = handler

    def bind(self, key: int, mods: int, action: Callable) -> None:
        self._bindings[(key, mods)] = action

    def clear_bindings(self) -> None:
        self._bindings.clear()

    def has_binding(self, key: int, mods: int) -> bool:
        clean_mods = mods & (glfw.MOD_SHIFT | glfw.MOD_CONTROL | glfw.MOD_ALT | glfw.MOD_SUPER)
        return (key, clean_mods) in self._bindings

    def is_shift(self) -> bool:
        return bool(self.state.modifiers & glfw.MOD_SHIFT)

    def is_ctrl(self) -> bool:
        return bool(self.state.modifiers & glfw.MOD_CONTROL)

    def is_alt(self) -> bool:
        return bool(self.state.modifiers & glfw.MOD_ALT)

    def on_mouse_button(self, button: int, action: int, mods: int) -> None:
        if self._is_mouse_captured():
            return
        self.state.modifiers = mods
        x, y = self.state.mouse_pos.x, self.state.mouse_pos.y

        if action == glfw.PRESS:
            self.state.buttons[button] = True
            if button in (LEFT, RIGHT, MIDDLE):
                self.state.drag_start = (x, y)
                self.state.drag_current = (x, y)
                self.state.is_dragging = False

            if self._check_double_click(button, x, y):
                if self.dispatch_double_click(x, y, button):
                    return

            self.dispatch_click(x, y, button)
        elif action == glfw.RELEASE:
            self.state.buttons[button] = False
            if button in (LEFT, RIGHT, MIDDLE):
                self.state.drag_start = None
                self.state.drag_current = None
                self.state.is_dragging = False
            self.dispatch_release(x, y, button)

    def on_mouse_move(self, x: float, y: float) -> None:
        dx = x - self.state.mouse_pos.x
        dy = y - self.state.mouse_pos.y
        self.state.mouse_delta = glm.vec2(dx, dy)
        self.state.mouse_pos = glm.vec2(x, y)

        if self._is_mouse_captured():
            return

        if self.state.drag_start is not None:
            self.state.drag_current = (x, y)
            if not self.state.is_dragging:
                ddx = x - self.state.drag_start[0]
                ddy = y - self.state.drag_start[1]
                if (ddx * ddx + ddy * ddy) ** 0.5 > self.state.drag_threshold:
                    self.state.is_dragging = True

        self.dispatch_move(x, y, dx, dy)

    def on_key(self, key: int, action: int, mods: int) -> None:
        clean_mods = mods & (glfw.MOD_SHIFT | glfw.MOD_CONTROL | glfw.MOD_ALT | glfw.MOD_SUPER)
        self.state.modifiers = clean_mods

        if action == glfw.RELEASE:
            self.state.keys[key] = False
            return

        if action not in (glfw.PRESS, glfw.REPEAT):
            return

        self.state.keys[key] = True

        if key == glfw.KEY_ESCAPE and self._global_escape is not None:
            if self._global_escape():
                return

        if self._is_keyboard_captured():
            is_function_key = glfw.KEY_F1 <= key <= glfw.KEY_F25
            has_command_mod = bool(clean_mods & (glfw.MOD_CONTROL | glfw.MOD_ALT | glfw.MOD_SUPER))
            if not (is_function_key or has_command_mod) or not self.has_binding(key, clean_mods):
                return

        if self.dispatch_key(key, clean_mods):
            return

        if action == glfw.PRESS:
            bound = self._bindings.get((key, clean_mods))
            if bound is not None:
                bound()

    def on_scroll(self, delta: float) -> None:
        if self._is_mouse_captured():
            return
        self.dispatch_scroll(delta)

    def _check_double_click(self, button: int, x: float, y: float) -> bool:
        if button not in (LEFT, RIGHT, MIDDLE):
            return False
        now = time.monotonic()
        interval = 0.3 if button in (LEFT, RIGHT) else 0.25
        dt = now - self._last_click[button]
        px, py = self._last_pos[button]
        dist = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
        is_double = dt < interval and dist < 5.0
        self._last_click[button] = 0.0 if is_double else now
        self._last_pos[button] = (x, y)
        return is_double

    def set_context_pick_handler(self, handler: Callable | None) -> None:
        self._context_pick_handler = handler

    def dispatch_click(self, x: float, y: float, button: int) -> bool:
        if self._context_pick_handler is not None and self._context_pick_handler(x, y, button):
            return True

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

    def dispatch_move(self, x: float, y: float, dx: float, dy: float) -> bool:
        for h in self._handlers:
            if not getattr(h, "is_active", False):
                continue
            fn = getattr(h, "handle_move", None)
            if callable(fn) and fn(x, y, dx, dy):
                return True
        if self._fallback and hasattr(self._fallback, "handle_move"):
            return bool(self._fallback.handle_move(x, y, dx, dy))
        return False

    def dispatch_key(self, key: int, mods: int) -> bool:
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

    def dispatch_double_click(self, x: float, y: float, button: int) -> bool:
        for h in self._handlers:
            if not getattr(h, "is_active", False):
                continue
            fn = getattr(h, "handle_double_click", None)
            if callable(fn) and fn(x, y, button):
                return True
        if self._fallback and hasattr(self._fallback, "handle_double_click"):
            return bool(self._fallback.handle_double_click(x, y, button))
        return False