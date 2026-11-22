# app/commands/signals.py
from app.commands.registry import command
from app.commands.result import CommandResult
from app.commands import project_commands as PC

@command(PC.RefreshGeometry)
def _refresh(app, cmd: PC.RefreshGeometry) -> CommandResult:
    project = getattr(app, "current_project", None)
    if project is not None and getattr(project, "math_model", None) is not None:
        for el in project.math_model.all_elements.values():
            if hasattr(el, "mark_dirty"):
                el.mark_dirty()
        project.math_model.mark_dirty()
        project.math_model.refresh_bounds()
    if project is not None and getattr(project, "scene", None) is not None:
        project.scene.mark_dirty()
        project.scene.refresh_bounds()
    return CommandResult(geometry_dirty=True, handled=True)