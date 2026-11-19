# app/commands/file_ops.py
import zipfile

from app.commands.registry import command, factory
from app.commands.result import CommandResult
from app.commands import project_commands as PC


@command(PC.NewProject)
def _new(app, cmd: PC.NewProject) -> CommandResult:
    app.project_service.new()
    return CommandResult(project_dirty=True, handled=True)


# app/commands/file_ops.py
@command(PC.OpenProject)
def _open(app, cmd: PC.OpenProject) -> CommandResult:
    if cmd.path:
        try:
            app.project_service.load(cmd.path)
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            return CommandResult(
                handled=True,
                message=f"Proje açılamadı: {exc}",
                level="error",
            )
        return CommandResult(project_dirty=True, handled=True)
    ui = app.ui
    if ui is None:
        return CommandResult(handled=False, level="warn")
    def _on_pick(path: str):
        app.put_command(PC.OpenProject(path))
    ui.open_open_dialog(on_select=_on_pick)
    return CommandResult(handled=True)

@command(PC.SaveProject)
def _save(app, cmd: PC.SaveProject) -> CommandResult:
    path = cmd.path or app.project_service.file_path
    if path:
        app.project_service.save(path)
        return CommandResult(handled=True, message="Kaydedildi.", level="success")
    ui = app.ui
    if ui is None:
        return CommandResult(handled=False, level="warn")
    def _on_pick(p: str):
        app.put_command(PC.SaveProject(p))
    ui.open_save_dialog(on_select=_on_pick)
    return CommandResult(handled=True)

@command(PC.SaveProjectAs)
def _save_as(app, cmd: PC.SaveProjectAs) -> CommandResult:
    if cmd.path:
        app.project_service.save(cmd.path)
        return CommandResult(handled=True, message="Kaydedildi.", level="success")
    ui = app.ui
    if ui is None:
        return CommandResult(handled=False, level="warn")
    def _on_pick(p: str):
        app.put_command(PC.SaveProject(p))
    ui.open_save_dialog(on_select=_on_pick)
    return CommandResult(handled=True)


@command(PC.CloseProject)
def _close(app, cmd: PC.CloseProject) -> CommandResult:
    app.project_service.new()
    return CommandResult(project_dirty=True, handled=True)


@command(PC.ImportS2K)
def _import_s2k(app, cmd: PC.ImportS2K) -> CommandResult:
    if cmd.path:
        return CommandResult(handled=False, message="S2K import henüz bağlanmadı.", level="warn")
    return CommandResult(
        handled=True,
        followup=PC.OpenPanel("s2k_panel"),
        message="S2K panelinden içe alın.",
    )

@command(PC.ExportS2K)
def _export_s2k(app, cmd: PC.ExportS2K) -> CommandResult:
    if cmd.path:
        return CommandResult(handled=False, message="S2K export henüz bağlanmadı.", level="warn")
    return CommandResult(
        handled=True,
        followup=PC.OpenPanel("s2k_panel"),
        message="S2K panelinden dışa verin.",
    )


@factory("open")
def _f_open(args): return PC.OpenProject(args[0] if args else "")

@factory("save")
def _f_save(args): return PC.SaveProject(args[0] if args else None)

@factory("save_as")
def _f_save_as(args): return PC.SaveProjectAs(args[0] if args else "")

@factory("import_s2k")
def _f_import_s2k(args): return PC.ImportS2K(args[0] if args else "", "import")

@factory("export_s2k")
def _f_export_s2k(args): return PC.ExportS2K(args[0] if args else "")


@command(PC.QuitApp)
def _quit(app, cmd: PC.QuitApp) -> CommandResult:
    app.request_quit()
    return CommandResult(handled=True)