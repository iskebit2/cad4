# app/commands/signals.py
from app.commands.registry import command
from app.commands.result import CommandResult
from app.commands import project_commands as PC

@command(PC.RefreshGeometry)
def _refresh(app, cmd: PC.RefreshGeometry) -> CommandResult:
    return CommandResult(geometry_dirty=True, handled=True)