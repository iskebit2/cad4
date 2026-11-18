# app/commands/visibility.py
from app.commands.registry import command, factory
from app.commands.result import CommandResult
from app.commands import project_commands as PC


@command(PC.ShowOnly)
def _show_only(app, cmd: PC.ShowOnly) -> CommandResult:
    uids = cmd.uids
    # uids None ise (örneğin terminalden argümansız `show_only` yazıldıysa) aktif seçimi al
    if uids is None and app.engine and app.engine.sel_mgr:
        uids = [
            getattr(e, "unique_id", None)
            for e in app.engine.sel_mgr.get_selected()
            if getattr(e, "unique_id", None) is not None
        ]

    if not uids:
        return CommandResult(handled=True, message="Gösterilecek seçili eleman yok.", level="warn")

    if not app.visibility_service.show_only(uids):
        return CommandResult(handled=True, message="Görünürlük güncellenemedi.", level="warn")

    if app.engine:
        app.engine.clear_hover()

    return CommandResult(
        handled=True,
        geometry_dirty=True,
        message=f"{len(uids)} eleman izole edildi.",
    )


@command(PC.HideElements)
def _hide(app, cmd: PC.HideElements) -> CommandResult:
    uids = cmd.uids
    if not uids and app.engine and app.engine.sel_mgr:
        uids = [
            getattr(e, "unique_id", None)
            for e in app.engine.sel_mgr.get_selected()
            if getattr(e, "unique_id", None) is not None
        ]

    if not uids:
        return CommandResult(handled=True, message="Gizlenecek seçili eleman yok.", level="warn")

    if not app.visibility_service.hide(uids):
        return CommandResult(handled=True, message="Elemanlar gizlenemedi.", level="warn")

    # Gizlenen elemanları seçim ve hover'dan çıkar
    if app.engine:
        app.engine.clear_hover()
        if app.engine.sel_mgr:
            hidden_set = set(uids)
            remaining = [
                e for e in app.engine.sel_mgr.get_selected()
                if getattr(e, "unique_id", None) not in hidden_set
            ]
            from core.selection_policy import SelectionMode
            app.engine.sel_mgr.select_multiple(remaining, mode=SelectionMode.REPLACE)

    return CommandResult(
        handled=True,
        geometry_dirty=True,
        message=f"{len(uids)} eleman gizlendi.",
    )


@command(PC.ShowEntireModel)
def _show_all(app, cmd: PC.ShowEntireModel) -> CommandResult:
    app.visibility_service.show_all()
    if app.engine:
        app.engine.clear_hover()
    return CommandResult(
        handled=True,
        geometry_dirty=True,
        message="Tüm model görünür yapıldı.",
    )


@factory("show_only")
def _f_show_only(args):
    if not args:
        return PC.ShowOnly(None)
    try:
        return PC.ShowOnly([int(a) for a in args])
    except ValueError:
        return None


@factory("hide")
def _f_hide(args):
    if not args:
        return PC.HideElements([])
    try:
        return PC.HideElements([int(a) for a in args])
    except ValueError:
        return None


@factory("show_all")
def _f_show_all(args):
    return PC.ShowEntireModel()