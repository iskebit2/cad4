# app/commands/elements.py
from app.commands.registry import command, factory
from app.commands.result import CommandResult
from app.commands import project_commands as PC


@command(PC.DeleteSelected)
def _delete_selected(app, cmd: PC.DeleteSelected) -> CommandResult:
    eng = app.engine
    if not eng or not eng.sel_mgr:
        return CommandResult(handled=False)
    selected = list(eng.sel_mgr.get_selected())
    if not selected:
        return CommandResult(handled=True)
    model = app.current_project.math_model
    for el in selected:
        model.remove_element(el)
    eng.sel_mgr.clear()
    return CommandResult(geometry_dirty=True)


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


@command(PC.DeleteElements)
def _delete(app, cmd: PC.DeleteElements) -> CommandResult:
    model = app.current_project.math_model
    for uid in cmd.uids:
        el = model.get_element_by_unique_id(uid)
        if el is not None:
            model.remove_element(el)
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
    if len(args) < 3:
        return None
    try:
        x, y, z = float(args[0]), float(args[1]), float(args[2])
    except ValueError:
        return None
    label = args[3] if len(args) > 3 else ""
    return PC.AddNode(x, y, z, label=label)


@factory("delete_selected")
def _f_delete_selected(args: list[str]):
    return PC.DeleteSelected()