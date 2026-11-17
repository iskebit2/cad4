# core/engine/hover_system.py
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.commands import project_commands as PC

if TYPE_CHECKING:
    from viewport.viewport import Viewport


class HoverSystem:
    THROTTLE = 0.05
    RETRY_ONCE = True

    def __init__(self, pick_pass, command_queue) -> None:
        self.pick_pass = pick_pass
        self.command_queue = command_queue
        self.element_id: int = 0
        self.element = None
        self.pointer: tuple[str, int, int] | None = None
        self._pending = False
        self._last_x = -1
        self._last_y = -1
        self._last_time = 0.0
        self._hover_retry = False

    def set_pick_pass(self, pick_pass) -> None:
        self.pick_pass = pick_pass

    def invalidate(self) -> None:
        self.element_id = 0
        self.element = None

    def clear(self) -> None:
        self.element_id = 0
        self.element = None
        self._last_x = -1
        self._last_y = -1

    def set_pointer(self, viewport_name: str, x: int, y: int) -> None:
        self.pointer = (viewport_name, int(x), int(y))

    def start_pick(self, x: float, y: float,
                   viewport: "Viewport | None" = None) -> None:
        if self.pick_pass is None:
            return
        now = time.time()
        if (now - self._last_time) < self.THROTTLE:
            return
        if (x, y) == (self._last_x, self._last_y):
            return
        if viewport is not None:
            ok = self.pick_pass.pick_async(
                int(x), int(y),
                source_fbo=viewport.fbo.fbo,
                viewport_size=(viewport.width, viewport.height),
            )
        else:
            ok = self.pick_pass.pick_async(x, y)
        if ok:
            self._last_x = x
            self._last_y = y
            self._last_time = now
            self._pending = True

    def check_pick_result(self) -> bool:
        if not self._pending:
            return False
        pick_id, px, py = self.pick_pass.check_pick()
        if pick_id is None:
            if not getattr(self.pick_pass, "pending_pick", False):
                self._pending = False
            return False
        self._pending = False

        if pick_id == 0 and self.RETRY_ONCE and not self._hover_retry:
            self._hover_retry = True
            self._last_x = -1
            self._last_y = -1
            return False

        was_retry = self._hover_retry
        self._hover_retry = False
        self._update_hover(int(pick_id), force=was_retry)
        return True

    def _update_hover(self, pick_id: int, force: bool = False) -> None:
        if not force and pick_id == self.element_id:
            return
        old = self.element_id
        self.element_id = pick_id
        self.element = None
        if force or old != pick_id:
            if self.command_queue:
                self.command_queue.put(PC.HoverChanged(pick_id))