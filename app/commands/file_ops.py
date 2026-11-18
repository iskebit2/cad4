# app/commands/file_ops.py
from app.commands.registry import command, factory
from app.commands.result import CommandResult
from app.commands import project_commands as PC


@command(PC.NewProject)
def _new(app, cmd: PC.NewProject) -> CommandResult:
    app.project_service.new()
    return CommandResult(project_dirty=True, handled=True)


@command(PC.OpenProject)
def _open(app, cmd: PC.OpenProject) -> CommandResult:
    app.project_service.load(cmd.path)
    return CommandResult(project_dirty=True, handled=True)


@command(PC.SaveProject)
def _save(app, cmd: PC.SaveProject) -> CommandResult:
    path = cmd.path or app.project_service.file_path
    if not path:
        if app.ui is not None:
            app.ui.open_save_dialog()
        return CommandResult(handled=True, message="Kayıt yolu seçin", level="warn")
    app.project_service.save(path)
    return CommandResult(handled=True, message="Kaydedildi.", level="success")


@command(PC.SaveProjectAs)
def _save_as(app, cmd: PC.SaveProjectAs) -> CommandResult:
    if not cmd.path:
        return CommandResult(handled=False)
    app.project_service.save(cmd.path)
    return CommandResult(handled=True, message="Kaydedildi.", level="success")


@command(PC.CloseProject)
def _close(app, cmd: PC.CloseProject) -> CommandResult:
    app.project_service.new()
    return CommandResult(project_dirty=True, handled=True)


@command(PC.ImportS2K)
def _import_s2k(app, cmd: PC.ImportS2K) -> CommandResult:
    return CommandResult(handled=False, message="S2K import henüz bağlanmadı.", level="warn")


@command(PC.ExportS2K)
def _export_s2k(app, cmd: PC.ExportS2K) -> CommandResult:
    return CommandResult(handled=False, message="S2K export henüz bağlanmadı.", level="warn")


@factory("open")
def _f_open(args): return PC.OpenProject(args[0]) if args else None

@factory("save")
def _f_save(args): return PC.SaveProject(args[0] if args else None)

@factory("save_as")
def _f_save_as(args): return PC.SaveProjectAs(args[0]) if args else None

@factory("import_s2k")
def _f_import_s2k(args): return PC.ImportS2K(args[0]) if args else None

@factory("export_s2k")
def _f_export_s2k(args): return PC.ExportS2K(args[0]) if args else None

@command(PC.QuitApp)
def _quit(app, cmd: PC.QuitApp) -> CommandResult:
    app.request_quit()
    return CommandResult(handled=True)