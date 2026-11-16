# app/commands/engine_flags.py
from app.commands.result import CommandResult
from core.commands import project_commands as PC

def register(reg):
    reg.register(PC.Toggle2D, _toggle_2d)
    reg.register(PC.ToggleLoadsVisible, _loads)
    reg.register(PC.ToggleLocalAxes, _local_axes)
    reg.register(PC.ToggleRenderFlag, _render_flag)
    reg.register(PC.SetRenderMode, _render_mode)


def _toggle_2d(app, cmd: PC.Toggle2D) -> CommandResult:
    app.toggle_2d()
    return CommandResult(handled=True)


def _loads(app, cmd: PC.ToggleLoadsVisible) -> CommandResult:
    app.set_loads_visible(cmd.enabled)
    return CommandResult(handled=True)


def _local_axes(app, cmd: PC.ToggleLocalAxes) -> CommandResult:
    eng = app.engine
    if eng and eng.scene:
        eng.scene.show_local_axes = not eng.scene.show_local_axes
    return CommandResult(handled=True)


def _render_flag(app, cmd: PC.ToggleRenderFlag) -> CommandResult:
    if app.engine:
        app.engine.show[cmd.flag] = bool(cmd.value)
    return CommandResult(handled=True)


def _render_mode(app, cmd: PC.SetRenderMode) -> CommandResult:
    if app.engine and app.engine.renderer:
        app.engine.renderer.set_render_mode(cmd.mode)
    return CommandResult(handled=True)