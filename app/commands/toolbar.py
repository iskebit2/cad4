# app/commands/toolbar.py
from __future__ import annotations

from app.commands import project_commands as PC
from app.commands.registry import command, factory
from app.commands.result import CommandResult


@command(PC.ReloadToolbarLayout)
def _reload_toolbar_layout(app, cmd: PC.ReloadToolbarLayout) -> CommandResult:
    ui = getattr(app, "ui", None)
    toolbar = getattr(ui, "toolbar", None) if ui is not None else None
    if toolbar is None:
        return CommandResult(handled=False)

    toolbar._builder.layout_store.reload()
    toolbar._builder.shortcut_store._overrides = None
    toolbar._builder.shortcut_store.load()
    toolbar.refresh()
    return CommandResult(
        handled=True,
        message="Toolbar yerleşimi ve kısayollar diskten yeniden yüklendi.",
        level="info",
    )


@command(PC.ResetToolbarLayout)
def _reset_toolbar_layout(app, cmd: PC.ResetToolbarLayout) -> CommandResult:
    ui = getattr(app, "ui", None)
    toolbar = getattr(ui, "toolbar", None) if ui is not None else None
    if toolbar is None:
        return CommandResult(handled=False)

    toolbar._builder.layout_store.reset()
    toolbar.refresh()
    return CommandResult(
        handled=True,
        message="Toolbar yerleşimi varsayılana sıfırlandı.",
        level="info",
    )


@command(PC.SaveToolbarLayout)
def _save_toolbar_layout(app, cmd: PC.SaveToolbarLayout) -> CommandResult:
    ui = getattr(app, "ui", None)
    toolbar = getattr(ui, "toolbar", None) if ui is not None else None
    if toolbar is None:
        return CommandResult(handled=False)

    toolbar._builder.layout_store.save()
    return CommandResult(
        handled=True,
        message="Toolbar yerleşimi kaydedildi.",
        level="info",
    )


@factory("toolbar_reload")
def _f_toolbar_reload(args: list[str]):
    return PC.ReloadToolbarLayout()


@factory("toolbar_reset")
def _f_toolbar_reset(args: list[str]):
    return PC.ResetToolbarLayout()


@factory("toolbar_save")
def _f_toolbar_save(args: list[str]):
    return PC.SaveToolbarLayout()