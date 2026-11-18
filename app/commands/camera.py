# app/commands/camera.py
from app.commands.registry import command, factory
from app.commands.result import CommandResult
from app.commands import project_commands as PC


@command(PC.FitView)
def _fit(app, cmd: PC.FitView) -> CommandResult:
    app.view_service.fit_view()
    return CommandResult(handled=True)


@command(PC.ZoomExtents)
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