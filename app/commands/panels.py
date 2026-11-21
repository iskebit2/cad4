
# app/commands/panels.py

from __future__ import annotations

from app.commands import project_commands as PC
from app.commands.registry import command, factory
from app.commands.result import CommandResult


def _get_panel(app, name: str):
    """Panel tanımını ve instance'ını birlikte döndürür."""

    reg = getattr(app, "panel_registry", None)

    if reg is None:
        return None, None

    spec = reg.get(name)
    if spec is None:
        return None, None

    instance = reg.instance(name)

    return spec, instance


def _prepare_panel(app, name: str, instance) -> None:
    """Panel açılmadan önce UI hazırlığını yapar."""

    ui = getattr(app, "ui", None)

    if ui is not None and hasattr(ui, "prepare_panel"):
        ui.prepare_panel(name, instance)


@command(PC.TogglePanel)
def _toggle_panel(app, cmd: PC.TogglePanel) -> CommandResult:
    spec, panel = _get_panel(app, cmd.name)

    if spec is None:
        reg = getattr(app, "panel_registry", None)
        if reg is None:
            return CommandResult(handled=False)

        return CommandResult(
            handled=True,
            message=f"Panel bulunamadı: '{cmd.name}'",
            level="warn",
        )

    if panel is None:
        return CommandResult(
            handled=True,
            message=f"Panel instance oluşturulmamış: '{cmd.name}'",
            level="warn",
        )

    if getattr(panel, "visible", False):
        panel.close()

        return CommandResult(
            handled=True,
            message=f"Panel kapatıldı: {spec.title}",
            level="info",
        )

    _prepare_panel(app, cmd.name, panel)
    panel.open()

    return CommandResult(
        handled=True,
        message=f"Panel açıldı: {spec.title}",
        level="info",
    )


@command(PC.OpenPanel)
def _open_panel(app, cmd: PC.OpenPanel) -> CommandResult:
    spec, panel = _get_panel(app, cmd.name)

    if spec is None:
        reg = getattr(app, "panel_registry", None)
        if reg is None:
            return CommandResult(handled=False)

        return CommandResult(
            handled=True,
            message=f"Panel bulunamadı: '{cmd.name}'",
            level="warn",
        )

    if panel is None:
        return CommandResult(
            handled=True,
            message=f"Panel instance oluşturulmamış: '{cmd.name}'",
            level="warn",
        )

    _prepare_panel(app, cmd.name, panel)
    panel.open(**cmd.kwargs)

    return CommandResult(handled=True)


@command(PC.ClosePanel)
def _close_panel(app, cmd: PC.ClosePanel) -> CommandResult:
    spec, panel = _get_panel(app, cmd.name)

    if spec is None:
        reg = getattr(app, "panel_registry", None)
        if reg is None:
            return CommandResult(handled=False)

        return CommandResult(
            handled=True,
            message=f"Panel bulunamadı: '{cmd.name}'",
            level="warn",
        )

    if panel is None:
        return CommandResult(
            handled=True,
            message=f"Panel instance oluşturulmamış: '{cmd.name}'",
            level="warn",
        )

    panel.close()

    return CommandResult(handled=True)


@factory("panel")
def _f_panel(args: list[str]):
    if len(args) != 1:
        return None

    return PC.TogglePanel(name=args[0].lower())
