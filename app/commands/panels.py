# app/commands/panels.py
from __future__ import annotations

from app.commands import project_commands as PC
from app.commands.registry import command, factory
from app.commands.result import CommandResult


@command(PC.TogglePanel)
def _toggle_panel(app, cmd: PC.TogglePanel) -> CommandResult:
    reg = getattr(app, "panel_registry", None)
    if reg is None:
        return CommandResult(handled=False)

    entry = reg.get(cmd.name)
    if entry is None:
        return CommandResult(handled=True, message=f"Panel bulunamadı: '{cmd.name}'", level="warn")

    if getattr(entry.instance, "visible", False):
        entry.instance.close()
        return CommandResult(handled=True, message=f"Panel kapatıldı: {entry.title}", level="info")

    if getattr(app, "ui", None) is not None and hasattr(app.ui, "prepare_panel"):
        app.ui.prepare_panel(cmd.name, entry.instance)
    entry.instance.open()
    return CommandResult(handled=True, message=f"Panel açıldı: {entry.title}", level="info")


@command(PC.OpenPanel)
def _open_panel(app, cmd: PC.OpenPanel) -> CommandResult:
    reg = getattr(app, "panel_registry", None)
    if reg is None:
        return CommandResult(handled=False)

    entry = reg.get(cmd.name)
    if entry is None:
        return CommandResult(handled=True, message=f"Panel bulunamadı: '{cmd.name}'", level="warn")

    if getattr(app, "ui", None) is not None and hasattr(app.ui, "prepare_panel"):
        app.ui.prepare_panel(cmd.name, entry.instance)
    entry.instance.open(**cmd.kwargs)
    return CommandResult(handled=True)


@command(PC.ClosePanel)
def _close_panel(app, cmd: PC.ClosePanel) -> CommandResult:
    reg = getattr(app, "panel_registry", None)
    if reg is None:
        return CommandResult(handled=False)

    entry = reg.get(cmd.name)
    if entry is None:
        return CommandResult(handled=True, message=f"Panel bulunamadı: '{cmd.name}'", level="warn")

    entry.instance.close()
    return CommandResult(handled=True)


@factory("panel")
def _f_panel(args: list[str]):
    if len(args) != 1:
        return None
    return PC.TogglePanel(name=args[0].lower())