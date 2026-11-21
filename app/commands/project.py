from __future__ import annotations

from app.commands import project_commands as PC
from app.commands.meta import CommandMeta
from app.commands.registry import command, factory
from app.commands.result import CommandResult
from app.settings.categories import Category
from domain.project import Project


@command(
    PC.NewProject,
    CommandMeta(
        label="Yeni Proje",
        icon="new_project",
        category=Category.FILE,
        default_shortcut="Ctrl+N",
        quick=True,
        tooltip="Yeni boş proje oluştur",
        visible_in_ui=True,
    ),
)
def _new_project(app, cmd: PC.NewProject) -> CommandResult:
    app.project_service.replace(Project(), path=None, model_text="MODEL: YENİ SAHNE")
    return CommandResult(handled=True, project_dirty=True, message="Yeni proje oluşturuldu.")


@command(
    PC.OpenProject,
    CommandMeta(
        label="Proje Aç...",
        icon="open_project",
        category=Category.FILE,
        default_shortcut="Ctrl+O",
        quick=True,
        tooltip="Kayıtlı .cd4 projesini aç",
        visible_in_ui=True,
    ),
)
def _open_project(app, cmd: PC.OpenProject) -> CommandResult:
    if not cmd.path:
        ui = getattr(app, "ui", None)
        if ui is not None and hasattr(ui, "open_open_dialog"):
            ui.open_open_dialog(lambda p: app.put_command(PC.OpenProject(p)))
            return CommandResult(handled=True)
        return CommandResult(handled=False)

    app.project_service.load(cmd.path)
    return CommandResult(handled=True, project_dirty=True, message=f"Proje açıldı: {cmd.path}")


@command(
    PC.SaveProject,
    CommandMeta(
        label="Kaydet",
        icon="save_project",
        category=Category.FILE,
        default_shortcut="Ctrl+S",
        quick=True,
        tooltip="Mevcut projeyi kaydet",
        visible_in_ui=True,
    ),
)
def _save_project(app, cmd: PC.SaveProject) -> CommandResult:
    if cmd.path:
        app.project_service.save(cmd.path)
        return CommandResult(handled=True, project_dirty=True, message=f"Kaydedildi: {cmd.path}")

    if app.project_service.save_current():
        return CommandResult(handled=True, project_dirty=True, message="Proje kaydedildi.")

    ui = getattr(app, "ui", None)
    if ui is not None and hasattr(ui, "open_save_dialog"):
        ui.open_save_dialog(lambda p: app.put_command(PC.SaveProjectAs(p)))
        return CommandResult(handled=True)
    return CommandResult(handled=False)


@command(
    PC.SaveProjectAs,
    CommandMeta(
        label="Farklı Kaydet...",
        icon="save_project_as",
        category=Category.FILE,
        default_shortcut="Ctrl+Shift+S",
        quick=False,
        tooltip="Projeyi yeni dosya adıyla kaydet",
        visible_in_ui=True,
    ),
)
def _save_project_as(app, cmd: PC.SaveProjectAs) -> CommandResult:
    if not cmd.path:
        ui = getattr(app, "ui", None)
        if ui is not None and hasattr(ui, "open_save_dialog"):
            ui.open_save_dialog(lambda p: app.put_command(PC.SaveProjectAs(p)))
            return CommandResult(handled=True)
        return CommandResult(handled=False)

    app.project_service.save(cmd.path)
    return CommandResult(handled=True, project_dirty=True, message=f"Farklı kaydedildi: {cmd.path}")


@command(
    PC.CloseProject,
    CommandMeta(
        label="Projeyi Kapat",
        icon="close_project",
        category=Category.FILE,
        default_shortcut="Ctrl+W",
        quick=False,
        tooltip="Aktif projeyi kapat ve sahneyi sıfırla",
        visible_in_ui=True,
    ),
)
def _close_project(app, cmd: PC.CloseProject) -> CommandResult:
    app.project_service.replace(Project(), path=None, model_text="MODEL: BOŞ SAHNE")
    return CommandResult(handled=True, project_dirty=True, message="Proje kapatıldı.")

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

@command(
    PC.QuitApp,
    CommandMeta(
        label="Çıkış",
        icon="quit_app",
        category=Category.FILE,
        default_shortcut="Alt+F4",
        quick=False,
        tooltip="Uygulamadan çık",
        visible_in_ui=True,
    ),
)
def _quit_app(app, cmd: PC.QuitApp) -> CommandResult:
    app.request_quit()
    return CommandResult(handled=True)


@command(PC.ReplaceProject)
def _replace(app, cmd: PC.ReplaceProject) -> CommandResult:
    if cmd.label:
        app.project_service.replace(cmd.project, path="", model_text=cmd.label)
    else:
        app.project_service.replace(cmd.project)
    return CommandResult(project_dirty=True, handled=True)


@command(PC.SetUnitSystem)
def _set_unit(app, cmd: PC.SetUnitSystem) -> CommandResult:
    app.project_service.set_unit_system(cmd.unit_system)
    return CommandResult(project_dirty=True, handled=True)


@factory("set_unit")
def _f_set_unit(args):
    return PC.SetUnitSystem(args[0]) if args else None


@factory("open_project")
def _f_open_project(args):
    return PC.OpenProject(args[0] if args else "")


@factory("save_project")
def _f_save_project(args):
    return PC.SaveProject(args[0] if args else None)


@factory("save_project_as")
def _f_save_project_as(args):
    return PC.SaveProjectAs(args[0] if args else "")