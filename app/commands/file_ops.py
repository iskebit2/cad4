# app/commands/file_ops.py
from app.commands.registry import command, factory
from app.commands.result import CommandResult
from app.commands import project_commands as PC


@command(PC.NewProject)
def _new(app, cmd: PC.NewProject) -> CommandResult:
    from domain.project import Project
    app.set_project(Project())
    app.current_file_path = None
    app._model_text = "MODEL: YENİ SAHNE"
    return CommandResult(project_dirty=True, handled=True)


@command(PC.OpenProject)
def _open(app, cmd: PC.OpenProject) -> CommandResult:
    import os
    from domain.project import Project
    project = Project.load(cmd.path)
    app.set_project(project)
    app.current_file_path = cmd.path
    app._model_text = f"MODEL: {os.path.basename(cmd.path)}"
    if app.engine:
        app.engine.fit_view()
        if app.engine.sel_mgr:
            app.engine.sel_mgr.clear()
    return CommandResult(project_dirty=True, handled=True)


@command(PC.SaveProject)
def _save(app, cmd: PC.SaveProject) -> CommandResult:
    import os
    path = cmd.path or app.current_file_path
    if not path:
        return CommandResult(
            handled=True,
            message="Kayıt yolu yok. Farklı kaydet açılıyor.",
            level="warn",
            followup=PC.SaveProjectAs(""),
        )
    app.current_project.save(path)
    app.current_file_path = path
    app._model_text = f"MODEL: {os.path.basename(path)}"
    return CommandResult(handled=True, message="Kaydedildi.", level="success")


@command(PC.SaveProjectAs)
def _save_as(app, cmd: PC.SaveProjectAs) -> CommandResult:
    import os
    if not cmd.path:
        return CommandResult(handled=False)
    app.current_project.save(cmd.path)
    app.current_file_path = cmd.path
    app._model_text = f"MODEL: {os.path.basename(cmd.path)}"
    return CommandResult(handled=True, message="Kaydedildi.", level="success")


@command(PC.CloseProject)
def _close(app, cmd: PC.CloseProject) -> CommandResult:
    from domain.project import Project
    app.set_project(Project())
    app.current_file_path = None
    app._model_text = "MODEL: NEW SCENE"
    return CommandResult(project_dirty=True, handled=True)


@command(PC.ImportS2K)
def _import_s2k(app, cmd: PC.ImportS2K) -> CommandResult:
    return CommandResult(
        handled=False,
        message="S2K import henüz bağlanmadı.",
        level="warn",
    )


@command(PC.ExportS2K)
def _export_s2k(app, cmd: PC.ExportS2K) -> CommandResult:
    return CommandResult(
        handled=False,
        message="S2K export henüz bağlanmadı.",
        level="warn",
    )


@factory("open")
def _f_open(args: list[str]):
    return PC.OpenProject(args[0]) if args else None


@factory("save")
def _f_save(args: list[str]):
    return PC.SaveProject(args[0] if args else None)


@factory("save_as")
def _f_save_as(args: list[str]):
    return PC.SaveProjectAs(args[0]) if args else None


@factory("import_s2k")
def _f_import_s2k(args: list[str]):
    return PC.ImportS2K(args[0]) if args else None


@factory("export_s2k")
def _f_export_s2k(args: list[str]):
    return PC.ExportS2K(args[0]) if args else None