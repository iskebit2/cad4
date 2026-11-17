# app/commands/visibility.py
from app.commands.registry import command, factory
from app.commands.result import CommandResult
from app.commands import project_commands as PC


@command(PC.ShowOnly)
def _show_only(app, cmd: PC.ShowOnly) -> CommandResult:
    app._show_only_ids = set(cmd.uids) if cmd.uids else None
    eng = app.engine
    if eng and eng.math_model:
        eng.math_model._render_filter = app._show_only_ids
    return CommandResult(geometry_dirty=True)


@command(PC.HideElements)
def _hide(app, cmd: PC.HideElements) -> CommandResult:
    if app._hidden_ids is None:
        app._hidden_ids = set()
    app._hidden_ids.update(cmd.uids)
    eng = app.engine
    if eng and eng.math_model:
        for el in eng.math_model.all_elements.values():
            if el.unique_id in app._hidden_ids:
                if hasattr(el, "is_visible"):
                    el.is_visible = False
                elif hasattr(el, "visible"):
                    el.visible = False
    return CommandResult(geometry_dirty=True)


@command(PC.ShowEntireModel)
def _show_all(app, cmd: PC.ShowEntireModel) -> CommandResult:
    app.show_entire_model()
    return CommandResult(handled=True)


@factory("show_only")
def _f_show_only(args: list[str]):
    if not args:
        return PC.ShowOnly(None)
    try:
        return PC.ShowOnly([int(a) for a in args])
    except ValueError:
        return None


@factory("hide")
def _f_hide(args: list[str]):
    if not args:
        return None
    try:
        return PC.HideElements([int(a) for a in args])
    except ValueError:
        return None