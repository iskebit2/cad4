# app/commands/definitions.py
from __future__ import annotations
from core.commands import project_commands as PC
from app.commands.result import CommandResult


def register(reg):
    reg.register(PC.AddDefinition, _add)
    reg.register(PC.UpdateDefinition, _update)
    reg.register(PC.RemoveDefinition, _remove)
    reg.register(PC.RenameDefinition, _rename)


def _add(app, cmd: PC.AddDefinition) -> CommandResult:
    container = getattr(app.current_project, cmd.container_attr, None)
    if container is None:
        return CommandResult(handled=False)
    container[cmd.name] = cmd.obj
    return CommandResult(project_dirty=True)


def _update(app, cmd: PC.UpdateDefinition) -> CommandResult:
    container = getattr(app.current_project, cmd.container_attr, None)
    if container is None:
        return CommandResult(handled=False)
    obj = container.get(cmd.name)
    if obj is None:
        return CommandResult(handled=False)
    for k, v in cmd.changes.items():
        if k == "material_name":
            obj.material = app.current_project.materials.get(v) if v else None
        else:
            setattr(obj, k, v)
    if cmd.new_name and cmd.new_name != cmd.name:
        container[cmd.new_name] = container.pop(cmd.name)
    return CommandResult(project_dirty=True)


def _remove(app, cmd: PC.RemoveDefinition) -> CommandResult:
    container = getattr(app.current_project, cmd.container_attr, None)
    if container is None:
        return CommandResult(handled=False)
    container.pop(cmd.name, None)
    return CommandResult(project_dirty=True)


def _rename(app, cmd: PC.RenameDefinition) -> CommandResult:
    container = getattr(app.current_project, cmd.container_attr, None)
    if container is None or cmd.old_name not in container:
        return CommandResult(handled=False)
    container[cmd.new_name] = container.pop(cmd.old_name)
    return CommandResult(project_dirty=True)