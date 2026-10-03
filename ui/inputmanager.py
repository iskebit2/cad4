# ui/inputmanager.py

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import glm
from logging_config import CadLogger
import numpy as np

from logging_config import CadLogger

logger = CadLogger.get(__name__)


# ============================================================================
# INPUT SABİTLERİ
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


@dataclass
class InputManager:

    mouse_pos: glm.vec2 = field(
        default_factory=lambda: glm.vec2(0, 0)
    )

    mouse_delta: glm.vec2 = field(
        default_factory=lambda: glm.vec2(0, 0)
    )

    mouse_wheel: float = 0.0

    mouse_world_pos: glm.vec3 = field(
        default_factory=lambda: glm.vec3(0, 0, 0)
    )

    mouse_world_valid: bool = False

    # ------------------------------------------------------------------------
    # Drag
    # ------------------------------------------------------------------------

    is_dragging: bool = False

    drag_start: Optional[Tuple[float, float]] = None

    drag_current: Optional[Tuple[float, float]] = None

    drag_threshold: float = 5.0

    # ------------------------------------------------------------------------
    # Keys / buttons
    # ------------------------------------------------------------------------

    keys: Dict[object, bool] = field(default_factory=dict)

    buttons: Dict[str, bool] = field(default_factory=dict)

    # ------------------------------------------------------------------------
    # Pick
    # ------------------------------------------------------------------------

    pick_request: bool = False

    # ------------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------------

    def __post_init__(self):
        self._last_x = 0.0
        self._last_y = 0.0

    # ========================================================================
    # MOUSE POSITION
    # ========================================================================

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
                    np.array(self.drag_start)
                    - np.array(self.drag_current)
                )

                if dist > self.drag_threshold:

                    self.is_dragging = True

                    logger.debug(
                        f"[Input] Drag started "
                        f"(distance={dist:.1f}px)"
                    )

    # ========================================================================
    # KEYBOARD
    # ========================================================================

    def set_key_state(self, key, state: bool):

        self.keys[key] = state

    def is_key_pressed(self, key) -> bool:

        return self.keys.get(key, False)

    # ========================================================================
    # MODIFIERS
    # ========================================================================

    def set_modifier_state(self, modifier: str, state: bool):

        if modifier == "shift":

            self.keys[KEY_LEFT_SHIFT] = state

        elif modifier == "ctrl":

            self.keys[KEY_LEFT_CONTROL] = state

        elif modifier == "alt":

            self.keys[KEY_LEFT_ALT] = state

    def update_modifiers(self, modifiers):

        """
        Kivy'nin on_key_down / on_key_up tarafından gönderilen
        modifier listesini InputManager'a aktarır.
        """

        self.keys[KEY_LEFT_SHIFT] = "shift" in modifiers
        self.keys[KEY_LEFT_CONTROL] = "ctrl" in modifiers
        self.keys[KEY_LEFT_ALT] = "alt" in modifiers

    def is_ctrl_pressed(self) -> bool:

        return (
            self.keys.get(KEY_LEFT_CONTROL, False)
            or
            self.keys.get(KEY_RIGHT_CONTROL, False)
        )

    def is_shift_pressed(self) -> bool:

        return (
            self.keys.get(KEY_LEFT_SHIFT, False)
            or
            self.keys.get(KEY_RIGHT_SHIFT, False)
        )

    def is_alt_pressed(self) -> bool:

        return (
            self.keys.get(KEY_LEFT_ALT, False)
            or
            self.keys.get(KEY_RIGHT_ALT, False)
        )

    # ========================================================================
    # MOUSE BUTTON
    # ========================================================================

    def set_button_state(self, button: str, state: bool):

        self.buttons[button] = state

        if button != MOUSE_BUTTON_LEFT:
            return

        # ------------------------------------------------------------
        # LEFT DOWN
        # ------------------------------------------------------------

        if state:

            self.drag_start = (
                self.mouse_pos.x,
                self.mouse_pos.y
            )

            self.drag_current = (
                self.mouse_pos.x,
                self.mouse_pos.y
            )

            self.is_dragging = False

            logger.debug(
                f"[Input] Left button pressed "
                f"at {self.drag_start}"
            )

        # ------------------------------------------------------------
        # LEFT UP
        # ------------------------------------------------------------

        else:

            if self.is_dragging:

                logger.debug(
                    "[Input] Drag ended"
                )

            else:

                logger.debug(
                    "[Input] Left button released"
                )

            self.drag_start = None
            self.drag_current = None
            self.is_dragging = False

    # ========================================================================
    # MARQUEE
    # ========================================================================

    def get_drag_rect(
        self
    ) -> Optional[Tuple[float, float, float, float]]:

        if (
            not self.is_dragging
            or self.drag_start is None
            or self.drag_current is None
        ):
            return None

        x1, y1 = self.drag_start
        x2, y2 = self.drag_current

        return (
            min(x1, x2),
            min(y1, y2),
            max(x1, x2),
            max(y1, y2),
        )

    def is_crossing_mode(self) -> bool:

        if (
            self.drag_start is None
            or self.drag_current is None
        ):
            return False

        return (
            self.drag_current[0]
            <
            self.drag_start[0]
        )

    def get_drag_mode_name(self) -> str:

        return (
            "CROSSING"
            if self.is_crossing_mode()
            else
            "WINDOW"
        )
