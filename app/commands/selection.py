# app/commands/selection.py
from app.commands.registry import command, factory
from app.commands.result import CommandResult
from app.commands import project_commands as PC


@command(PC.ClearSelection)
def _clear(app, cmd: PC.ClearSelection) -> CommandResult:
    if app.engine and app.engine.sel_mgr:
        app.engine.sel_mgr.clear()
    return CommandResult(handled=True)


@command(PC.SelectElements)
def _select(app, cmd: PC.SelectElements) -> CommandResult:
    eng = app.engine
    if not eng or not eng.sel_mgr:
        return CommandResult(handled=False)
    els = [eng.math_model.get_element_by_unique_id(u) for u in cmd.uids]
    els = [e for e in els if e is not None]
    from core.selection_policy import SelectionMode
    if cmd.mode == "replace":
        eng.sel_mgr.select_multiple(els, mode=SelectionMode.REPLACE)
    elif cmd.mode == "add":
        for e in els:
            if not eng.sel_mgr.is_selected(e):
                eng.sel_mgr.select(e, additive=True)
    elif cmd.mode == "toggle":
        for e in els:
            eng.sel_mgr.select(e, additive=True)
    return CommandResult(handled=True)


@factory("select")
def _f_select(args: list[str]):
    if not args:
        return None
    try:
        uids = [int(a) for a in args]
    except ValueError:
        return None
    return PC.SelectElements(uids)