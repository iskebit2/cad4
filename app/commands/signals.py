# app/commands/signals.py
from app.commands.result import CommandResult
from core.commands import project_commands as PC

def register(reg):
    reg.register(PC.RefreshGeometry, _refresh)


def _refresh(app, cmd: PC.RefreshGeometry) -> CommandResult:
    return CommandResult(geometry_dirty=True, handled=True)