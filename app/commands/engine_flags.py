# app/commands/engine_flags.py
from __future__ import annotations

from app.commands import project_commands as PC
from app.commands.meta import CommandMeta
from app.commands.registry import command, factory
from app.commands.result import CommandResult
from app.settings.categories import Category


@command(PC.HoverChanged)
def _hover(app, cmd: PC.HoverChanged) -> CommandResult:
    eng = app.engine
    if eng is None or eng.hover is None:
        return CommandResult(handled=True)

    hover = eng.hover
    for _spec, panel in app.panel_registry.visible_instances():
        hook = getattr(panel, "on_hover_changed", None)
        if callable(hook):
            hook(hover.element_id, hover.element)

    return CommandResult(handled=True)


@command(PC.StartPlaneTool)
def _start_plane(app, cmd: PC.StartPlaneTool) -> CommandResult:
    pdm = getattr(app.engine, "plane_draw_mgr", None) if app.engine else None
    if pdm is None:
        return CommandResult(handled=False)
    if pdm.is_active:
        pdm.cancel()
    else:
        pdm.start_3pt()
    return CommandResult(handled=True)


@command(
    PC.Undo,
    CommandMeta(
        label="Geri Al",
        icon="undo",
        category=Category.EDIT,
        default_shortcut="Ctrl+Z",
        quick=True,
        tooltip="Son işlemi geri al",
        visible_in_ui=True,
    ),
)
def _undo(app, cmd: PC.Undo) -> CommandResult:
    ctrl = getattr(app, "edit_controller", None)
    if ctrl is None:
        return CommandResult(handled=False)
    r = ctrl.undo()
    return CommandResult(
        geometry_dirty=r.ok,
        handled=True,
        message=r.message,
        level="info" if r.ok else "warn",
    )


@command(
    PC.Redo,
    CommandMeta(
        label="Yinele",
        icon="redo",
        category=Category.EDIT,
        default_shortcut="Ctrl+Y",
        quick=True,
        tooltip="Geri alınan işlemi yinele",
        visible_in_ui=True,
    ),
)
def _redo(app, cmd: PC.Redo) -> CommandResult:
    ctrl = getattr(app, "edit_controller", None)
    if ctrl is None:
        return CommandResult(handled=False)
    r = ctrl.redo()
    return CommandResult(
        geometry_dirty=r.ok,
        handled=True,
        message=r.message,
        level="info" if r.ok else "warn",
    )


@command(
    PC.Toggle2D,
    CommandMeta(
        label="2D / 3D Geçişi",
        icon="toggle2_d",
        category=Category.VIEW,
        default_shortcut="F2",
        quick=False,
        tooltip="2D düzlem ve 3D görünüm arasında geçiş yap",
        visible_in_ui=False,
        check_state=lambda app: bool(
            app and app.viewport_manager and app.viewport_manager.active and app.viewport_manager.active.is_2d
        ),
    ),
)
def _toggle_2d(app, cmd: PC.Toggle2D) -> CommandResult:
    app.view_service.toggle_2d()
    return CommandResult(handled=True)


@command(
    PC.ToggleLocalAxes,
    CommandMeta(
        label="Yerel Eksenler",
        icon="toggle_local_axes",
        category=Category.VIEW,
        quick=False,
        tooltip="Eleman yerel eksenlerini göster/gizle",
        visible_in_ui=False,
        check_state=lambda app: bool(app and app.engine and app.engine.scene and app.engine.scene.show_local_axes),
    ),
)
def _local_axes(app, cmd: PC.ToggleLocalAxes) -> CommandResult:
    eng = app.engine
    if eng and eng.scene:
        eng.scene.show_local_axes = not eng.scene.show_local_axes
    return CommandResult(handled=True)


@command(PC.ToggleRenderFlag)
def _render_flag(app, cmd: PC.ToggleRenderFlag) -> CommandResult:
    if app.engine:
        app.engine.show[cmd.flag] = bool(cmd.value)
    return CommandResult(handled=True)


@command(PC.SetRenderMode)
def _render_mode(app, cmd: PC.SetRenderMode) -> CommandResult:
    if app.engine and app.engine.renderer:
        app.engine.renderer.set_render_mode(cmd.mode)
    return CommandResult(handled=True)


@factory("set_render_mode")
def _f_set_render_mode(args: list[str]):
    return PC.SetRenderMode(args[0]) if args else None


@factory("toggle_flag")
def _f_toggle_flag(args: list[str]):
    if len(args) < 2:
        return None
    value = args[1].lower() in ("1", "true", "on", "yes")
    return PC.ToggleRenderFlag(args[0], value)


@command(
    PC.StartPlane3pt,
    CommandMeta(
        label="3 Nokta ile Düzlem",
        icon="start_plane3pt",
        category=Category.DRAW,
        quick=False,
        tooltip="3 nokta seçerek çalışma düzlemi oluştur",
        visible_in_ui=True,
    ),
)
def _start_plane_3pt(app, cmd: PC.StartPlane3pt) -> CommandResult:
    pdm = getattr(app.engine, "plane_draw_mgr", None) if app.engine else None
    if pdm is None:
        return CommandResult(handled=False)
    if pdm.is_active:
        pdm.cancel()
    pdm.start_3pt()
    return CommandResult(handled=True)


@command(
    PC.StartPlane2ptZ,
    CommandMeta(
        label="2 Nokta + Z Düzlem",
        icon="start_plane2pt_z",
        category=Category.DRAW,
        quick=False,
        tooltip="2 nokta ve Z ekseni ile dikey çalışma düzlemi oluştur",
        visible_in_ui=True,
    ),
)
def _start_plane_2pt_z(app, cmd: PC.StartPlane2ptZ) -> CommandResult:
    pdm = getattr(app.engine, "plane_draw_mgr", None) if app.engine else None
    if pdm is None:
        return CommandResult(handled=False)
    if pdm.is_active:
        pdm.cancel()
    pdm.start_2pt_z()
    return CommandResult(handled=True)


@command(
    PC.ToggleRenderMode,
    CommandMeta(
        label="Render Modu (Shaded/Simple)",
        icon="toggle_render_mode",
        category=Category.VIEW,
        default_shortcut="F4",
        quick=False,
        tooltip="Shaded ve Simple çizim modları arasında geçiş yap",
        visible_in_ui=False,
    ),
)
def _toggle_render_mode(app, cmd: PC.ToggleRenderMode) -> CommandResult:
    eng = app.engine
    if eng and eng.renderer:
        eng.renderer.toggle_render_mode()
    return CommandResult(handled=True)