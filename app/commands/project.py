# app/commands/project.py
from app.commands.result import CommandResult
from core.commands import project_commands as PC

def register(reg):
    reg.register(PC.ReplaceProject, _replace)
    reg.register(PC.SetUnitSystem, _set_unit)


def _replace(app, cmd: PC.ReplaceProject) -> CommandResult:
    app.set_project(cmd.project)
    return CommandResult(handled=True)


def _set_unit(app, cmd: PC.SetUnitSystem) -> CommandResult:
    app.set_unit_system(cmd.unit_system)
    return CommandResult(handled=True)