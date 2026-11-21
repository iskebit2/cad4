# app/commands/camera.py
from __future__ import annotations

from app.commands import project_commands as PC
from app.commands.meta import CommandMeta
from app.commands.registry import command, factory
from app.commands.result import CommandResult
from app.settings.categories import Category


@command(
    PC.FitView,
    CommandMeta(
        label="Tüm Modeli Sığdır",
        icon="fit_view",
        category=Category.VIEW,
        default_shortcut="F",
        quick=True,
        tooltip="Modeli görünüme sığdır",
        visible_in_ui=True,
    ),
)
def _fit(app, cmd: PC.FitView) -> CommandResult:
    app.view_service.fit_view()
    return CommandResult(handled=True)


@command(
    PC.ZoomExtents,
    CommandMeta(
        label="Sınırlara Yaklaş",
        icon="zoom_extents",
        category=Category.VIEW,
        default_shortcut="Ctrl+Shift+F",
        quick=False,
        tooltip="Sınırları yenile ve sığdır",
        visible_in_ui=True,
    ),
)
def _zoom(app, cmd: PC.ZoomExtents) -> CommandResult:
    app.view_service.zoom_extents()
    return CommandResult(handled=True)


@command(PC.SetCameraPreset)
def _preset(app, cmd: PC.SetCameraPreset) -> CommandResult:
    app.view_service.set_camera_preset(cmd.preset)
    return CommandResult(handled=True)


@factory("set_preset")
def _set_preset(args: list[str]):
    return PC.SetCameraPreset(args[0]) if args else None