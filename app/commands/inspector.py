from app.commands import project_commands as PC
from app.commands.registry import command
from app.commands.result import CommandResult


@command(PC.OpenInspector)
def _open_inspector(app, cmd: PC.OpenInspector) -> CommandResult:
    ui = app.ui
    inspector = ui.inspector if ui is not None else None
    if inspector is None:
        return CommandResult(
            handled=False,
            message="Inspector arayüzü hazır değil.",
            level="warn",
        )

    if app.engine and app.engine.sel_mgr:
        inspector.set_selection(list(app.engine.sel_mgr.get_selected()))
    inspector.open()
    return CommandResult(handled=True)
