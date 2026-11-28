# core/commands/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
import queue
from typing import Any, Callable, Literal


Level = Literal["info", "success", "warn", "error"]
_CURRENT_APP: list[Any] = [None]
def get_current_app() -> Any:
    return _CURRENT_APP[0]

def bind_app(app: Any) -> None:
    _CURRENT_APP[0] = app

@dataclass(frozen=True)
class CommandResult:
    geometry_dirty: bool = False
    project_dirty: bool = False
    handled: bool = True
    message: str = ""
    level: Level = "info"
    followup: Any = None


class Command(ABC):
    @abstractmethod
    def execute(self) -> CommandResult: ...

    @abstractmethod
    def undo(self) -> None: ...

    def redo(self) -> CommandResult:
        return self.execute()

    @property
    def name(self) -> str:
        return type(self).__name__

    def _resolve(self) -> CommandResult | None:
        self._app = get_current_app()
        if self._app is None:
            return CommandResult(handled=False, message="Uygulama bağlı değil.", level="error")
        project = getattr(self._app, "current_project", None)
        if project is None:
            return CommandResult(handled=False, message="Proje yok.", level="warn")
        self._project = project
        self._scene = project.math_model
        return None


@dataclass(frozen=True)
class CommandMeta:
    label: str
    icon: str = ""
    category: str = "Tools"
    default_shortcut: str = ""
    tooltip: str = ""
    quick: bool = False
    visible_in_ui: bool = False
    check_state: Callable[[Any], bool] | None = None
    factory: Callable[[list[str]], Any | None] | None = None


class CommandManager:
    def __init__(self, max_history: int = 100) -> None:
        self._undo: deque[Command] = deque(maxlen=max_history)
        self._redo: deque[Command] = deque(maxlen=max_history)
        self._listeners: list[Callable[[CommandResult], None]] = []

    def execute(self, cmd: Command) -> CommandResult:
        result = cmd.execute()
        if result.handled:
            self._undo.append(cmd)
            self._redo.clear()
        self._notify(result)
        return result

    def undo(self) -> CommandResult:
        if not self._undo:
            return CommandResult(handled=False, message="Geri alınacak işlem yok", level="warn")
        cmd = self._undo[-1]
        try:
            cmd.undo()
        except Exception as exc:
            return CommandResult(handled=False, message=f"Geri alınamadı: {exc}", level="error")
        self._undo.pop()
        self._redo.append(cmd)
        result = CommandResult(message=f"Geri alındı: {cmd.name}", level="info")
        self._notify(result)
        return result

    def redo(self) -> CommandResult:
        if not self._redo:
            return CommandResult(handled=False, message="Yinelenecek işlem yok", level="warn")
        cmd = self._redo[-1]
        try:
            result = cmd.redo()
        except Exception as exc:
            return CommandResult(handled=False, message=f"Yinelenemedi: {exc}", level="error")
        self._redo.pop()
        self._undo.append(cmd)
        self._notify(result)
        return result

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def add_listener(self, callback: Callable[[CommandResult], None]) -> None:
        self._listeners.append(callback)

    def _notify(self, result: CommandResult) -> None:
        for cb in self._listeners:
            cb(result)


@dataclass(frozen=True)
class BulkPlan:
    element: Any
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)

class CommandQueue:
    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue()

    def put(self, command) -> None:
        self._q.put(command)

    def drain(self) -> list:
        out = []
        while True:
            try:
                out.append(self._q.get_nowait())
            except queue.Empty:
                return out

_COMMAND_BY_TYPE: dict[type, type[Command]] = {}
def command_for(payload_type: type) -> type[Command] | None:
    return _COMMAND_BY_TYPE.get(payload_type)






# def command(payload_type: type):
#     def decorator(fn: Callable[[Any, Any], CommandResult]) -> type[Command]:
#         if payload_type in _COMMAND_BY_TYPE:
#             raise ValueError(
#                 f"command: {payload_type.__name__} için zaten komut kayıtlı."
#             )

#         class _FnCommand(Command):
#             def __init__(self, payload: Any) -> None:
#                 self.payload = payload
#                 self._app = _CURRENT_APP[0]

#             def execute(self) -> CommandResult:
#                 self._app = _CURRENT_APP[0]
#                 return fn(self._app, self.payload)

#             def undo(self) -> None:
#                 pass

#             @property
#             def name(self) -> str:
#                 return f"{payload_type.__name__}"

#         _FnCommand.__name__ = f"{payload_type.__name__}Command"
#         _FnCommand.__qualname__ = _FnCommand.__name__
#         _FnCommand.__payload_type__ = payload_type
#         _COMMAND_BY_TYPE[payload_type] = _FnCommand
#         return _FnCommand

#     return decorator


