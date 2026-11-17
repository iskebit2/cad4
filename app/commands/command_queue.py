# core/commands/command_queue.py
from __future__ import annotations
import queue
from typing import Any

class CommandQueue:
    def __init__(self) -> None:
        self._q: queue.Queue[Any] = queue.Queue()

    def put(self, command: Any) -> None:
        self._q.put(command)

    def drain(self) -> list[Any]:
        out = []
        while True:
            try:
                out.append(self._q.get_nowait())
            except queue.Empty:
                return out