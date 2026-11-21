# app/commands/elements.py
from __future__ import annotations

from app.commands import project_commands as PC
from app.commands.meta import CommandMeta
from app.commands.registry import command, factory
from app.commands.result import CommandResult
from app.settings.categories import Category


@command(
    PC.DeleteSelected,
    CommandMeta(
        label="Seçilileri Sil",
        icon="delete_selected",
        category=Category.EDIT,
        default_shortcut="Delete",
        quick=True,
        tooltip="Seçili elemanları sil",
        visible_in_ui=True,
    ),
)
def _delete_selected(app, cmd: PC.DeleteSelected) -> CommandResult:
    eng = app.engine
    ctrl = app.edit_controller
    if eng is None or eng.sel_mgr is None or ctrl is None:
        return CommandResult(handled=False)

    selected = list(eng.sel_mgr.get_selected())
    if not selected:
        return CommandResult(handled=True, message="Seçili eleman yok.", level="warn")

    res = ctrl.delete(selected)
    return CommandResult(
        handled=True,
        geometry_dirty=res.ok,
        message=res.message,
        level="info" if res.ok else "warn",
    )


@command(PC.ReplicateSelected)
def _replicate_selected(app, cmd: PC.ReplicateSelected) -> CommandResult:
    eng = app.engine
    ctrl = app.edit_controller
    if eng is None or eng.sel_mgr is None or ctrl is None:
        return CommandResult(handled=False)

    selected = list(eng.sel_mgr.get_selected())
    if not selected:
        return CommandResult(handled=True, message="Seçili eleman yok.", level="warn")

    res = ctrl.replicate(
        selected,
        dx=cmd.dx,
        dy=cmd.dy,
        dz=cmd.dz,
        count=cmd.count,
    )
    return CommandResult(
        handled=True,
        geometry_dirty=res.ok,
        message=res.message,
        level="success" if res.ok else "warn",
    )


@factory("replicate")
def _f_replicate(args: list[str]):
    if len(args) < 3 or len(args) > 4:
        return None
    if not all(_is_float(a) for a in args[:3]):
        return None
    if len(args) == 4 and not args[3].lstrip("-").isdigit():
        return None
    dx, dy, dz = float(args[0]), float(args[1]), float(args[2])
    count = int(args[3]) if len(args) == 4 else 1
    if count < 1:
        return None
    return PC.ReplicateSelected(dx=dx, dy=dy, dz=dz, count=count)


def _is_float(text: str) -> bool:
    s = text.strip()
    if s.startswith(("+", "-")):
        s = s[1:]
    parts = s.split(".")
    return len(parts) <= 2 and any(p.isdigit() for p in parts) and all(p.isdigit() or p == "" for p in parts)


@command(PC.DeleteElements)
def _delete(app, cmd: PC.DeleteElements) -> CommandResult:
    ctrl = app.edit_controller
    if ctrl is None or ctrl.scene is None:
        return CommandResult(handled=False)

    elements = [
        ctrl.scene.get_element_by_unique_id(uid)
        for uid in cmd.uids
    ]
    elements = [e for e in elements if e is not None]
    if not elements:
        return CommandResult(handled=True, message="Silinecek eleman bulunamadı.", level="warn")

    res = ctrl.delete(elements)
    return CommandResult(
        handled=True,
        geometry_dirty=res.ok,
        message=res.message,
        level="info" if res.ok else "warn",
    )


@command(PC.UpdateElementFields)
def _update_fields(app, cmd: PC.UpdateElementFields) -> CommandResult:
    el = app.current_project.math_model.get_element_by_unique_id(cmd.element_uid)
    if el is None:
        return CommandResult(handled=False)
    for k, v in cmd.changes.items():
        setattr(el, k, v)
    if hasattr(el, "mark_dirty"):
        el.mark_dirty()
    return CommandResult(geometry_dirty=True)


@command(PC.AddNode)
def _add_node(app, cmd: PC.AddNode) -> CommandResult:
    from domain.element import Node
    n = Node(cmd.x, cmd.y, cmd.z, label=cmd.label, restraint=cmd.restraint)
    app.current_project.math_model.add_node(n)
    return CommandResult(geometry_dirty=True)


@command(PC.AddFrame)
def _add_frame(app, cmd: PC.AddFrame) -> CommandResult:
    model = app.current_project.math_model
    ni = model.get_element_by_unique_id(cmd.node_i_uid)
    nj = model.get_element_by_unique_id(cmd.node_j_uid)
    if ni is None or nj is None:
        return CommandResult(handled=False)

    from domain.element import Frame

    section_obj = None
    if cmd.section_name:
        section_obj = app.current_project.sections.get(cmd.section_name)
        if section_obj is None:
            return CommandResult(handled=False)

    f = Frame(
        node_i=ni,
        node_j=nj,
        section=section_obj,
        rotation_deg=cmd.rotation_deg,
        label=cmd.label,
    )
    model.add_frame(f)
    return CommandResult(geometry_dirty=True)


@factory("add_node")
def _f_add_node(args: list[str]):
    if len(args) < 3 or not all(_is_float(a) for a in args[:3]):
        return None
    x, y, z = float(args[0]), float(args[1]), float(args[2])
    label = args[3] if len(args) > 3 else ""
    return PC.AddNode(x, y, z, label=label)


@factory("delete_selected")
def _f_delete_selected(args: list[str]):
    return PC.DeleteSelected()


@command(
    PC.ConvertFramesToLinks,
    CommandMeta(
        label="Çubukları Link'e Dönüştür",
        icon="convert_frames_to_links",
        category=Category.CONVERT,
        quick=False,
        tooltip="Seçili frame elemanlarını link elemanına dönüştür",
        visible_in_ui=True,
    ),
)
def _convert_frames_to_links(app, cmd: PC.ConvertFramesToLinks) -> CommandResult:
    from domain.element import Frame
    from tools import frame_to_link

    eng = app.engine
    ctrl = app.edit_controller
    if eng is None or eng.math_model is None or ctrl is None:
        return CommandResult(handled=False)

    frames = [e for e in ctrl.scene.get_selected() if isinstance(e, Frame)]
    if not frames:
        return CommandResult(handled=True, message="Seçili Frame yok", level="warn")

    report = frame_to_link.convert_frames_to_links(
        scene=ctrl.scene,
        project=app.project_service.project,
        frames=frames,
        link_prop_name=cmd.link_prop_name,
        delete_original=cmd.delete_original,
    )

    if app.visibility_service.show_only_ids is not None:
        removed = {f.unique_id for f in frames}
        app.visibility_service.show_only_ids -= removed
        app.visibility_service.show_only_ids.update(
            link.unique_id for link in report["new_links"]
        )

    if eng.sel_mgr:
        eng.sel_mgr.clear()

    n = len(report.get("new_links", []))
    return CommandResult(
        geometry_dirty=True,
        handled=True,
        message=f"{n} link oluşturuldu",
        level="success",
    )