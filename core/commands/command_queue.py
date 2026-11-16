# core/commands/command_queue.py
"""UI thread → CadApp.tick arasında komut kuyruğu.

Thread-safe. UI Host kendi thread'inden put() yapar, CadApp ana thread'de
drain() yapar ve komutları uygular.
"""
from __future__ import annotations

import queue
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.commands.project_commands import Command


class CommandQueue:
    def __init__(self) -> None:
        self._q: queue.Queue[Command] = queue.Queue()

    def put(self, command: "Command") -> None:
        self._q.put(command)

    def drain(self) -> list["Command"]:
        out: list[Command] = []
        while True:
            try:
                out.append(self._q.get_nowait())
            except queue.Empty:
                return out