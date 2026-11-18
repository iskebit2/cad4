# app/commands/project.py
from app.commands.registry import command, factory
from app.commands.result import CommandResult
from app.commands import project_commands as PC


@command(PC.ReplaceProject)
def _replace(app, cmd: PC.ReplaceProject) -> CommandResult:
    app.project_service.replace(cmd.project)
    return CommandResult(project_dirty=True, handled=True)


@command(PC.SetUnitSystem)
def _set_unit(app, cmd: PC.SetUnitSystem) -> CommandResult:
    app.project_service.set_unit_system(cmd.unit_system)
    return CommandResult(project_dirty=True, handled=True)


@factory("set_unit")
def _f_set_unit(args): return PC.SetUnitSystem(args[0]) if args else None