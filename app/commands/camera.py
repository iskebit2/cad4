# app/commands/camera.py
from app.commands.registry import command, factory
from app.commands.result import CommandResult
from app.commands import project_commands as PC


@command(PC.FitView)
def _fit(app, cmd: PC.FitView) -> CommandResult:
    if app.engine:
        app.engine.fit_view()
    return CommandResult(handled=True)


@command(PC.ZoomExtents)
def _zoom(app, cmd: PC.ZoomExtents) -> CommandResult:
    if app.engine:
        app.engine.zoom_extents()
    return CommandResult(handled=True)


@command(PC.SetCameraPreset)
def _preset(app, cmd: PC.SetCameraPreset) -> CommandResult:
    if app.engine and app.engine.cam:
        app.engine.cam.set_view_preset(cmd.preset)
    return CommandResult(handled=True)


@command(PC.ToggleRenderMode)
def _toggle_render_mode(app, cmd: PC.ToggleRenderMode) -> CommandResult:
    if app.engine and app.engine.renderer:
        app.engine.renderer.toggle_render_mode()
    return CommandResult(handled=True)


@factory("set_preset")
def _set_preset(args: list[str]):
    return PC.SetCameraPreset(args[0]) if args else None