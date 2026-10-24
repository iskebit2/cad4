# core/input_manager.py

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

_SHIFT = "shift"
_CTRL  = "ctrl"
_ALT   = "alt"


# ============================================================================
# INPUT MANAGER
# ============================================================================
@dataclass
class InputManager:
    """
    Anlık girdi durumu + küçük karar mantığı. Backend bağımsız.

    - "Ne oldu?" sorusunu yanıtlar (buton basılı, drag eşiği aşıldı,
      middle double-click oldu).
    - "Ne yapacağım?" sorusunu **yanıtlamaz** — o cad_app'in işi
      (kamerayı çevir, marquee bitir, panel aç).
    """

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
    buttons: Dict[str, bool]    = field(default_factory=dict)
    keys:    Dict[object, bool] = field(default_factory=dict)

    # --- Modifier durumları (sol/sağ birleşik) ---
    modifiers: Dict[str, bool] = field(default_factory=lambda: {
        _SHIFT: False, _CTRL: False, _ALT: False,
    })

    # --- Pick ---
    pick_request: bool = False

    # ------------------------------------------------------------------
    # Middle-click politika sabitleri (public — cad_app override edebilir)
    # ------------------------------------------------------------------
    middle_double_click_interval: float = 0.25
    middle_double_click_max_drag: float = 4.0

    # ------------------------------------------------------------------
    # İç durumlar (dataclass init'te yok, __post_init__'te kurulur)
    # ------------------------------------------------------------------
    _last_x: float = field(default=0.0, init=False, repr=False)
    _last_y: float = field(default=0.0, init=False, repr=False)

    _middle_click_time: float = field(default=0.0, init=False, repr=False)
    _middle_press_pos:  Tuple[float, float] = field(
        default=(0.0, 0.0), init=False, repr=False,
    )
    _middle_dragged:    bool = field(default=False, init=False, repr=False)

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
        Tek format: dict.
        mods = {'shift': bool, 'ctrl': bool, 'alt': bool}
        Eksik anahtarlar False → yapışma imkânsız.
        """
        self.modifiers[_SHIFT] = bool(mods.get("shift", False))
        self.modifiers[_CTRL]  = bool(mods.get("ctrl",  False))
        self.modifiers[_ALT]   = bool(mods.get("alt",   False))

    def clear_modifiers(self):
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
    # KLAVYE
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
    # DRAG / MARQUEE
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

    # ==================================================================
    # MIDDLE-CLICK STATE MACHINE
    # ==================================================================
    def begin_middle_click(self, x: float, y: float, now: float) -> bool:
        """
        Middle butona basıldığında çağrılır.

        Dönüş:
            True  → bu bir DOUBLE CLICK; çağıran `fit_view()` gibi
                    bir eylem yapar. Press state güncellenmez.
            False → normal press; press pos ve drag bayrağı kurulur.
        """
        if now - self._middle_click_time < self.middle_double_click_interval:
            self._middle_click_time = 0.0
            return True

        self._middle_click_time = now
        self._middle_press_pos = (x, y)
        self._middle_dragged = False
        return False

    def update_middle_drag(self, x: float, y: float) -> bool:
        """
        Middle basılıyken her harekette çağrılır.

        Dönüş:
            True  → drag eşiği bu adımda aşıldı; double click iptal edildi.
            False → drag eşiği aşılmadı (veya zaten aşılmıştı).
        """
        if self._middle_dragged:
            return False

        px, py = self._middle_press_pos
        dist = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
        if dist > self.middle_double_click_max_drag:
            self._middle_dragged = True
            self._middle_click_time = 0.0
            return True
        return False

    def is_middle_dragged(self) -> bool:
        """Debug/UI için: middle drag aktif mi?"""
        return self._middle_dragged

    def reset_middle_click(self):
        """Panel/preview iptali gibi durumlarda state'i temizle."""
        self._middle_click_time = 0.0
        self._middle_press_pos = (0.0, 0.0)
        self._middle_dragged = False