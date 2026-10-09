# core/input_manager.py
"""
InputManager — Klavye, fare, modifier durumlarını tutar.
Sadece veri + sorgu. Kivy'den bağımsız.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import glm
import numpy as np

from logging_config import CadLogger
logger = CadLogger.get(__name__)


# ============================================================================
# SABİTLER
# ============================================================================

MOUSE_BUTTON_LEFT = "left"
MOUSE_BUTTON_RIGHT = "right"
MOUSE_BUTTON_MIDDLE = "middle"

KEY_LEFT_CONTROL = "left_ctrl"
KEY_RIGHT_CONTROL = "right_ctrl"
KEY_LEFT_SHIFT = "left_shift"
KEY_RIGHT_SHIFT = "right_shift"
KEY_LEFT_ALT = "left_alt"
KEY_RIGHT_ALT = "right_alt"


# Kivy keycode → modifier adı eşlemesi
_KEYCODE_TO_MODIFIER = {
    303: "shift", 304: "shift",     # L/R shift
    305: "ctrl",  306: "ctrl",      # L/R ctrl
    307: "alt",   308: "alt",       # L/R alt
}


@dataclass
class InputManager:

    # --- Fare ---
    mouse_pos: glm.vec2 = field(default_factory=lambda: glm.vec2(0, 0))
    mouse_delta: glm.vec2 = field(default_factory=lambda: glm.vec2(0, 0))
    mouse_wheel: float = 0.0
    mouse_world_pos: glm.vec3 = field(default_factory=lambda: glm.vec3(0, 0, 0))
    mouse_world_valid: bool = False

    # --- Drag ---
    is_dragging: bool = False
    drag_start: Optional[Tuple[float, float]] = None
    drag_current: Optional[Tuple[float, float]] = None
    drag_threshold: float = 5.0

    # --- Tuşlar / butonlar ---
    keys: Dict[object, bool] = field(default_factory=dict)
    buttons: Dict[str, bool] = field(default_factory=dict)

    # --- Pick ---
    pick_request: bool = False

    # ------------------------------------------------------------------
    # INIT
    # ------------------------------------------------------------------
    def __post_init__(self):
        self._last_x = 0.0
        self._last_y = 0.0

    # ==================================================================
    # FARE POZİSYONU
    # ==================================================================
    def update_mouse_position(self, x: float, y: float):
        self.mouse_delta.x = x - self._last_x
        self.mouse_delta.y = y - self._last_y

        self.mouse_pos.x = x
        self.mouse_pos.y = y

        self._last_x = x
        self._last_y = y

        if self.drag_start is not None:
            self.drag_current = (x, y)
            if not self.is_dragging:
                dist = np.linalg.norm(
                    np.array(self.drag_start) - np.array(self.drag_current))
                if dist > self.drag_threshold:
                    self.is_dragging = True

    # ==================================================================
    # KLAVYE
    # ==================================================================
    def set_key_state(self, key, state: bool):
        """Belirli bir tuşun durumunu ayarla (Kivy keycode veya string)."""
        self.keys[key] = state

    def is_key_pressed(self, key) -> bool:
        return self.keys.get(key, False)

    def handle_key_down(self, key, modifiers=None):
        """
        KivyCADWidget._on_key_down tarafından çağrılır.
        key: Kivy keycode (int)
        modifiers: Kivy modifier listesi
        """
        self.keys[key] = True
        if modifiers is not None:
            self.update_modifiers(modifiers)

    def handle_key_up(self, key):
        """
        KivyCADWidget._on_key_up tarafından çağrılır.
        key: Kivy keycode (int)
        """
        self.keys[key] = False

        # Modifier ise onu da bırak
        mod = _KEYCODE_TO_MODIFIER.get(key)
        if mod is not None:
            self.set_modifier_state(mod, False)

    # ==================================================================
    # MODIFIERS
    # ==================================================================
    def set_modifier_state(self, modifier: str, state: bool):
        """modifier: 'shift' | 'ctrl' | 'alt'"""
        if modifier == "shift":
            self.keys[KEY_LEFT_SHIFT] = state
        elif modifier == "ctrl":
            self.keys[KEY_LEFT_CONTROL] = state
        elif modifier == "alt":
            self.keys[KEY_LEFT_ALT] = state

    def update_modifiers(self, modifiers):
        """
        Kivy'nin on_key_down/on_key_up tarafından gönderilen
        modifier listesini InputManager'a aktarır.
        modifiers: ['shift', 'ctrl', 'alt'] gibi liste
        """
        self.keys[KEY_LEFT_SHIFT] = "shift" in modifiers
        self.keys[KEY_LEFT_CONTROL] = "ctrl" in modifiers
        self.keys[KEY_LEFT_ALT] = "alt" in modifiers

    def is_ctrl_pressed(self) -> bool:
        return (
            self.keys.get(KEY_LEFT_CONTROL, False)
            or self.keys.get(KEY_RIGHT_CONTROL, False)
        )

    def is_shift_pressed(self) -> bool:
        return (
            self.keys.get(KEY_LEFT_SHIFT, False)
            or self.keys.get(KEY_RIGHT_SHIFT, False)
        )

    def is_alt_pressed(self) -> bool:
        return (
            self.keys.get(KEY_LEFT_ALT, False)
            or self.keys.get(KEY_RIGHT_ALT, False)
        )

    # ==================================================================
    # FARE BUTONU
    # ==================================================================
    def set_button_state(self, button: str, state: bool):
        self.buttons[button] = state

        if button != MOUSE_BUTTON_LEFT:
            return

        if state:
            # LEFT DOWN → drag başlangıcı
            self.drag_start = (self.mouse_pos.x, self.mouse_pos.y)
            self.drag_current = (self.mouse_pos.x, self.mouse_pos.y)
            self.is_dragging = False
        else:
            # LEFT UP → drag bitişi
            self.drag_start = None
            self.drag_current = None
            self.is_dragging = False

    def is_button_pressed(self, button: str) -> bool:
        return self.buttons.get(button, False)

    # ==================================================================
    # MOUSE WHEEL
    # ==================================================================
    def add_wheel(self, delta: float):
        """Scroll olayında çağrılır. delta: +1 veya -1."""
        self.mouse_wheel += delta

    def consume_wheel(self) -> float:
        """Scroll değerini oku ve sıfırla."""
        d = self.mouse_wheel
        self.mouse_wheel = 0.0
        return d

    # ==================================================================
    # MARQUEE / DRAG
    # ==================================================================
    def get_drag_rect(self) -> Optional[Tuple[float, float, float, float]]:
        if (not self.is_dragging
                or self.drag_start is None
                or self.drag_current is None):
            return None

        x1, y1 = self.drag_start
        x2, y2 = self.drag_current
        return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))

    def is_crossing_mode(self) -> bool:
        if self.drag_start is None or self.drag_current is None:
            return False
        return self.drag_current[0] < self.drag_start[0]

    def get_drag_mode_name(self) -> str:
        return "CROSSING" if self.is_crossing_mode() else "WINDOW"

    # ==================================================================
    # PICK
    # ==================================================================
    def request_pick(self):
        self.pick_request = True

    def consume_pick_request(self) -> bool:
        v = self.pick_request
        self.pick_request = False
        return v