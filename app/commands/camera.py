# app/commands/camera.py
from app.commands.result import CommandResult
from core.commands import project_commands as PC

def register(reg):
    reg.register(PC.FitView, _fit)
    reg.register(PC.ZoomExtents, _zoom)
    reg.register(PC.SetCameraPreset, _preset)


def _fit(app, cmd: PC.FitView) -> CommandResult:
    if app.engine:
        app.engine.fit_view()
    return CommandResult(handled=True)


def _zoom(app, cmd: PC.ZoomExtents) -> CommandResult:
    if app.engine:
        app.engine.zoom_extents()
    return CommandResult(handled=True)


def _preset(app, cmd: PC.SetCameraPreset) -> CommandResult:
    if app.engine and app.engine.cam:
        app.engine.cam.set_view_preset(cmd.preset)
    return CommandResult(handled=True)