# app/commands/engine_flags.py
from app.commands.registry import command, factory
from app.commands.result import CommandResult
from app.commands import project_commands as PC


@command(PC.HoverChanged)
def _hover(app, cmd: PC.HoverChanged) -> CommandResult:
    if app.ui is not None:
        app.ui.on_hover_changed(cmd.element_id)
    return CommandResult(handled=True)


@command(PC.StartDrawTool)
def _start_draw(app, cmd: PC.StartDrawTool) -> CommandResult:
    eng = app.engine
    if not eng or not eng.draw_mgr:
        return CommandResult(handled=False)
    if eng.draw_mgr.is_active:
        eng.draw_mgr.cancel()
        return CommandResult(handled=True)
    eng.draw_mgr.start(mode=cmd.mode)
    return CommandResult(handled=True)


@command(PC.StartPlaneTool)
def _start_plane(app, cmd: PC.StartPlaneTool) -> CommandResult:
    pdm = getattr(app.engine, "plane_draw_mgr", None) if app.engine else None
    if pdm is None:
        return CommandResult(handled=False)
    if pdm.is_active:
        pdm.cancel()
    else:
        pdm.start_3pt()
    return CommandResult(handled=True)


@command(PC.Undo)
def _undo(app, cmd: PC.Undo) -> CommandResult:
    ctrl = getattr(app, "edit_controller", None)
    if ctrl is None:
        return CommandResult(handled=False)
    r = ctrl.undo()
    return CommandResult(
        geometry_dirty=r.ok,
        handled=True,
        message=r.message,
        level="info" if r.ok else "warn",
    )


@command(PC.Redo)
def _redo(app, cmd: PC.Redo) -> CommandResult:
    ctrl = getattr(app, "edit_controller", None)
    if ctrl is None:
        return CommandResult(handled=False)
    r = ctrl.redo()
    return CommandResult(
        geometry_dirty=r.ok,
        handled=True,
        message=r.message,
        level="info" if r.ok else "warn",
    )


@command(PC.Toggle2D)
def _toggle_2d(app, cmd: PC.Toggle2D) -> CommandResult:
    app.toggle_2d()
    return CommandResult(handled=True)


@command(PC.ToggleLoadsVisible)
def _loads(app, cmd: PC.ToggleLoadsVisible) -> CommandResult:
    current = app.get_loads_visible()
    target = (not current) if cmd.enabled is None else bool(cmd.enabled)
    app.set_loads_visible(target)
    return CommandResult(handled=True)


@command(PC.ToggleLocalAxes)
def _local_axes(app, cmd: PC.ToggleLocalAxes) -> CommandResult:
    eng = app.engine
    if eng and eng.scene:
        eng.scene.show_local_axes = not eng.scene.show_local_axes
    return CommandResult(handled=True)


@command(PC.ToggleRenderFlag)
def _render_flag(app, cmd: PC.ToggleRenderFlag) -> CommandResult:
    if app.engine:
        app.engine.show[cmd.flag] = bool(cmd.value)
    return CommandResult(handled=True)


@command(PC.SetRenderMode)
def _render_mode(app, cmd: PC.SetRenderMode) -> CommandResult:
    if app.engine and app.engine.renderer:
        app.engine.renderer.set_render_mode(cmd.mode)
    return CommandResult(handled=True)


@factory("set_render_mode")
def _f_set_render_mode(args: list[str]):
    return PC.SetRenderMode(args[0]) if args else None


@factory("toggle_flag")
def _f_toggle_flag(args: list[str]):
    if len(args) < 2:
        return None
    value = args[1].lower() in ("1", "true", "on", "yes")
    return PC.ToggleRenderFlag(args[0], value)


@factory("start_draw")
def _f_start_draw(args: list[str]):
    return PC.StartDrawTool(args[0] if args else "line")