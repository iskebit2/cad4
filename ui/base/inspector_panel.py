# ui/base/inspector_panel.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from imgui_bundle import imgui

from app.settings.categories import Category


@dataclass
class InspectorContext:
    project: Any = None
    engine: Any = None
    app: Any = None
    selection: list = field(default_factory=list)
    primary: Any = None
    status: list[tuple[str, str]] = field(default_factory=list)

    def set_status(self, message: str, kind: str = "info") -> None:
        self.status.append((kind, message))

    def clear_status(self) -> None:
        self.status.clear()

    def commands(self):
        return getattr(self.app, "commands", None) if self.app else None

    def run(self, command_id: str, **kwargs) -> Any:
        cmds = self.commands()
        if cmds is None:
            return None
        return cmds.run(command_id, context=self, **kwargs)

    def can_run(self, command_id: str, **kwargs) -> bool:
        cmds = self.commands()
        if cmds is None:
            return False
        return cmds.can_run(command_id, context=self, **kwargs)


class InspectorPanel:
    __abstract__ = True
    panel_name: str | None = None
    title: str = ""
    category: Category = Category.TOOLS
    context: tuple[str, ...] = ()
    width: int = 520
    height: int = 640
    pos_first_use: tuple[float, float] | None = None
    preview_flags: dict[str, bool] | None = None

    app = None
    visible: bool = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.__dict__.get("panel_name"):
            cls.__abstract__ = False

    def __init__(self, app=None, **overrides):
        self.app = app
        self._preview_snapshot: dict[str, bool] | None = None
        self.ctx = InspectorContext(app=app)
        for key, value in overrides.items():
            setattr(self, key, value)

    def open(self, **kwargs) -> None:
        self.visible = True
        self._apply_preview(True)

    def close(self) -> None:
        self._apply_preview(False)
        self.visible = False

    def set_context(self, ctx: dict) -> None:
        for key in self.context:
            if key in ctx:
                setattr(self, key, ctx[key])
        self.ctx.project = ctx.get("project", getattr(self, "project", None))
        self.ctx.engine = ctx.get("engine", getattr(self, "engine", None))
        self._on_context_ready()

    def _on_context_ready(self) -> None:
        pass

    def _on_selection_changed(self, selection: list) -> None:
        self.ctx.selection = list(selection)
        self.ctx.primary = selection[0] if selection else None

    def draw(self) -> None:
        if not self.visible:
            return
        imgui.set_next_window_size(
            imgui.ImVec2(self.width, self.height),
            imgui.Cond_.first_use_ever,
        )
        if self.pos_first_use:
            imgui.set_next_window_pos(
                imgui.ImVec2(*self.pos_first_use),
                imgui.Cond_.first_use_ever,
            )
        win_id = f"{self.title}###{self.panel_name or id(self)}"
        expanded, opened = imgui.begin(win_id, True)
        if not opened:
            imgui.end()
            self.close()
            return
        if expanded:
            self.ctx.clear_status()
            self.draw_content()
            self._draw_status()
        imgui.end()

    def _draw_status(self) -> None:
        if not self.ctx.status:
            return
        imgui.separator()
        for kind, message in self.ctx.status:
            self._render_status(kind, message)

    @staticmethod
    def _render_status(kind: str, message: str) -> None:
        color = {
            "info": imgui.ImVec4(0.6, 0.8, 0.6, 1.0),
            "warn": imgui.ImVec4(1.0, 0.6, 0.3, 1.0),
            "error": imgui.ImVec4(1.0, 0.4, 0.4, 1.0),
        }.get(kind, imgui.ImVec4(0.7, 0.7, 0.7, 1.0))
        imgui.text_colored(color, message)

    def draw_content(self) -> None:
        raise NotImplementedError

    def _apply_preview(self, active: bool) -> None:
        flags = self.preview_flags
        if not flags:
            return
        eng = getattr(self.app, "engine", None) if self.app else None
        if eng is None:
            return
        show = getattr(eng, "show", None)
        if active:
            if self._preview_snapshot is None and isinstance(show, dict):
                self._preview_snapshot = {k: show.get(k, True) for k in flags}
            if isinstance(show, dict):
                for key, value in flags.items():
                    show[key] = bool(value)
        else:
            if self._preview_snapshot and isinstance(show, dict):
                for key, value in self._preview_snapshot.items():
                    show[key] = value
            self._preview_snapshot = None


CommandSpec = Callable[[InspectorContext], None]


@dataclass
class InspectorCommand:
    id: str
    label: str
    handler: CommandSpec
    icon: str | None = None
    tooltip: str = ""
    enabled: Callable[[InspectorContext], bool] | None = None
    visible: Callable[[InspectorContext], bool] | None = None


class CommandRegistry:
    def __init__(self) -> None:
        self._commands: dict[str, InspectorCommand] = {}

    def register(self, command: InspectorCommand) -> None:
        if command.id in self._commands:
            raise ValueError(f"Komut zaten kayıtlı: {command.id}")
        self._commands[command.id] = command

    def get(self, command_id: str) -> InspectorCommand | None:
        return self._commands.get(command_id)

    def all(self) -> list[InspectorCommand]:
        return list(self._commands.values())

    def run(self, command_id: str, *, context: InspectorContext, **kwargs) -> Any:
        command = self._commands.get(command_id)
        if command is None:
            raise KeyError(f"Komut bulunamadı: {command_id}")
        if command.enabled is not None and not command.enabled(context):
            return None
        return command.handler(context, **kwargs)

    def can_run(self, command_id: str, *, context: InspectorContext, **kwargs) -> bool:
        command = self._commands.get(command_id)
        if command is None:
            return False
        if command.visible is not None and not command.visible(context):
            return False
        if command.enabled is not None and not command.enabled(context):
            return False
        return True