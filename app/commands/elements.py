# app/commands/elements.py
from app.commands.result import CommandResult
from core.commands import project_commands as PC

def register(reg):
    reg.register(PC.UpdateElementFields, _update_fields)
    reg.register(PC.DeleteElements, _delete)
    reg.register(PC.AddNode, _add_node)
    reg.register(PC.AddFrame, _add_frame)


def _update_fields(app, cmd: PC.UpdateElementFields) -> CommandResult:
    el = app.current_project.math_model.get_element_by_unique_id(cmd.element_uid)
    if el is None:
        return CommandResult(handled=False)
    for k, v in cmd.changes.items():
        setattr(el, k, v)
    if hasattr(el, "mark_dirty"):
        el.mark_dirty()
    return CommandResult(geometry_dirty=True)


def _delete(app, cmd: PC.DeleteElements) -> CommandResult:
    model = app.current_project.math_model
    for uid in cmd.uids:
        el = model.get_element_by_unique_id(uid)
        if el is not None:
            model.remove_element(el)
    return CommandResult(geometry_dirty=True)


def _add_node(app, cmd: PC.AddNode) -> CommandResult:
    from domain.element import Node
    n = Node(cmd.x, cmd.y, cmd.z, label=cmd.label, restraint=cmd.restraint)
    app.current_project.math_model.add_node(n)
    return CommandResult(geometry_dirty=True)


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