# app/commands/view_ops.py
from __future__ import annotations

from app.commands import project_commands as PC
from app.commands.meta import CommandMeta
from app.commands.registry import command, factory
from app.commands.result import CommandResult
from app.settings.categories import Category


@command(
    PC.OpenViewport,
    CommandMeta(
        label="Viewport Aç",
        icon="layout",
        category=Category.VIEW,
        quick=False,
        tooltip="Yeni viewport aç",
        visible_in_ui=False,
    ),
)
def _open_viewport(app, cmd: PC.OpenViewport) -> CommandResult:
    ui = getattr(app, "ui", None)
    if ui is None:
        return CommandResult(handled=False, message="UI hazır değil", level="warn")
    vp = ui.open_viewport(cmd.preset)
    if vp is None:
        return CommandResult(handled=False, message="Viewport açılamadı", level="warn")
    return CommandResult(handled=True, message=f"Viewport açıldı: {vp.name}")


@factory("open_viewport")
def _f_open_viewport(args: list[str]):
    if not args:
        return PC.OpenViewport("iso")
    return PC.OpenViewport(args[0].lower())