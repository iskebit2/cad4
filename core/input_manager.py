# core/input_manager.py
"""
InputManager — anlık girdi durumu.

Sorumluluk:
  - Fare konumu, buton durumu, klavye/modifier durumlarını tutar.
  - Sorgu metotları sunar: is_shift_pressed, is_button_pressed, ...
  - Drag / marquee başlangıç-bitiş durumunu yönetir.

Sınır:
  - Backend'i BİLMEZ (GLFW, Kivy, Qt vs.).
  - Engine'i BİLMEZ (kamera, pick, seçim).
  - Sadece veri tutar ve sorgu yanıtlar.

Yazma kuralları:
  - update_modifiers(mods: dict)  → {'shift': bool, 'ctrl': bool, 'alt': bool}
  - set_button_state(name, state) → name: "left"/"right"/"middle"
  - update_mouse_position(x, y)

Okuma örnekleri:
  - is_shift_pressed()
  - is_button_pressed(MOUSE_BUTTON_LEFT)
  - mouse_pos, mouse_delta
"""
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import glm
import numpy as np


# ============================================================================
# SABİTLER
# ============================================================================
MOUSE_BUTTON_LEFT   = "left"
MOUSE_BUTTON_RIGHT  = "right"
MOUSE_BUTTON_MIDDLE = "middle"

# Modifier tuş isimleri (sol/sağ ayrımı içeride tutulur)
_SHIFT = "shift"
_CTRL  = "ctrl"
_ALT   = "alt"


# ============================================================================
# INPUT MANAGER
# ============================================================================
@dataclass
class InputManager:
    """Anlık girdi durumu. Backend bağımsız."""

    # --- Fare ---
    mouse_pos:        glm.vec2 = field(default_factory=lambda: glm.vec2(0, 0))
    mouse_delta:      glm.vec2 = field(default_factory=lambda: glm.vec2(0, 0))
    mouse_wheel:      float    = 0.0
    mouse_world_pos:  glm.vec3 = field(default_factory=lambda: glm.vec3(0, 0, 0))
    mouse_world_valid: bool    = False

    # --- Drag (marquee) ---
    is_dragging:    bool = False
    drag_start:     Optional[Tuple[float, float]] = None
    drag_current:   Optional[Tuple[float, float]] = None
    drag_threshold: float = 5.0

    # --- Buton ve tuş durumları ---
    buttons: Dict[str, bool]   = field(default_factory=dict)
    keys:    Dict[object, bool] = field(default_factory=dict)

    # --- Modifier durumları ---
    # Ayrı ayrı tutulur: "shift"/"ctrl"/"alt" (sol/sağ birleşik)
    modifiers: Dict[str, bool] = field(default_factory=lambda: {
        _SHIFT: False, _CTRL: False, _ALT: False,
    })

    # --- Pick ---
    pick_request: bool = False

    # ------------------------------------------------------------------
    def __post_init__(self):
        self._last_x = 0.0
        self._last_y = 0.0

    # ==================================================================
    # FARE KONUMU
    # ==================================================================
    def update_mouse_position(self, x: float, y: float):
        self.mouse_delta.x = x - self._last_x
        self.mouse_delta.y = y - self._last_y
        self.mouse_pos.x = x
        self.mouse_pos.y = y
        self._last_x = x
        self._last_y = y

        # Drag güncellemesi
        if self.drag_start is not None:
            self.drag_current = (x, y)
            if not self.is_dragging:
                d = np.linalg.norm(
                    np.array(self.drag_start) - np.array(self.drag_current)
                )
                if d > self.drag_threshold:
                    self.is_dragging = True

    # ==================================================================
    # MODIFIER'LAR
    # ==================================================================
    def update_modifiers(self, mods: dict):
        """
        Tek doğru format: dict.

        mods = {'shift': bool, 'ctrl': bool, 'alt': bool}
        Eksik anahtarlar False kabul edilir → yapışma imkânsız.
        """
        self.modifiers[_SHIFT] = bool(mods.get("shift", False))
        self.modifiers[_CTRL]  = bool(mods.get("ctrl",  False))
        self.modifiers[_ALT]   = bool(mods.get("alt",   False))

    def clear_modifiers(self):
        """Tüm modifier'ları sıfırla. Pencere fokus kaybında çağrılır."""
        self.modifiers[_SHIFT] = False
        self.modifiers[_CTRL]  = False
        self.modifiers[_ALT]   = False

    def is_shift_pressed(self) -> bool:
        return self.modifiers.get(_SHIFT, False)

    def is_ctrl_pressed(self) -> bool:
        return self.modifiers.get(_CTRL, False)

    def is_alt_pressed(self) -> bool:
        return self.modifiers.get(_ALT, False)

    # ==================================================================
    # KLAVYE (modifier DIŞI tuşlar)
    # ==================================================================
    def handle_key_down(self, key):
        self.keys[key] = True

    def handle_key_up(self, key):
        self.keys[key] = False

    def is_key_pressed(self, key) -> bool:
        return self.keys.get(key, False)

    # ==================================================================
    # FARE BUTONLARI
    # ==================================================================
    def set_button_state(self, button: str, state: bool):
        self.buttons[button] = state

        # Sol tuş için drag durumu
        if button != MOUSE_BUTTON_LEFT:
            return
        if state:
            self.drag_start = (self.mouse_pos.x, self.mouse_pos.y)
            self.drag_current = (self.mouse_pos.x, self.mouse_pos.y)
            self.is_dragging = False
        else:
            self.drag_start = None
            self.drag_current = None
            self.is_dragging = False

    def is_button_pressed(self, button: str) -> bool:
        return self.buttons.get(button, False)

    # ==================================================================
    # WHEEL
    # ==================================================================
    def add_wheel(self, delta: float):
        self.mouse_wheel += delta

    def consume_wheel(self) -> float:
        d = self.mouse_wheel
        self.mouse_wheel = 0.0
        return d

    # ==================================================================
    # DRAG / MARQUEE YARDIMCILARI
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

    # ==================================================================
    # PICK
    # ==================================================================
    def request_pick(self):
        self.pick_request = True

    def consume_pick_request(self) -> bool:
        v = self.pick_request
        self.pick_request = False
        return v