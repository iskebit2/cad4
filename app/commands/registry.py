# app/commands/registry.py
from __future__ import annotations
from typing import TYPE_CHECKING, Callable

from core.commands.base import Command
from app.commands.result import CommandResult

if TYPE_CHECKING:
    from app.cad_app import CadApp

CommandHandler = Callable[["CadApp", Command], CommandResult]


class CommandRegistry:
    def __init__(self) -> None:
        self._handlers: dict[type, CommandHandler] = {}

    def register(self, cmd_type: type, handler: CommandHandler) -> None:
        self._handlers[cmd_type] = handler

    def dispatch(self, app: "CadApp", cmd: Command) -> CommandResult:
        handler = self._handlers.get(type(cmd))
        if handler is None:
            return CommandResult(handled=False)
        return handler(app, cmd)


def build_registry() -> CommandRegistry:
    reg = CommandRegistry()
    from app.commands import definitions, elements, project, visibility
    from app.commands import camera, engine_flags, selection, signals  # ← signals burada

    definitions.register(reg)
    elements.register(reg)
    project.register(reg)
    visibility.register(reg)
    camera.register(reg)
    engine_flags.register(reg)
    selection.register(reg)
    signals.register(reg)   # ← BU SATIR EKSİK OLABİLİR

    return reg