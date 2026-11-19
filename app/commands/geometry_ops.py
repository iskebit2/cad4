# app/commands/geometry_ops.py
from __future__ import annotations

from app.commands.registry import command
from app.commands.result import CommandResult
from app.commands import project_commands as PC


@command(PC.PropagateGeometryChange)
def _propagate_geometry(app, cmd: PC.PropagateGeometryChange) -> CommandResult:
    model = app.engine.math_model if app.engine else None
    if model is None:
        return CommandResult(handled=True)

    # uid → node
    nodes = []
    uid_set = set(cmd.node_uids or ())
    if uid_set:
        for n in getattr(model, "nodes", ()) or ():
            if getattr(n, "unique_id", None) in uid_set:
                nodes.append(n)
    else:
        mark = getattr(model, "mark_dirty", None)
        if callable(mark):
            mark()
        return CommandResult(handled=True, geometry_dirty=True)

    if not nodes:
        return CommandResult(handled=True)

    cascade = getattr(model, "invalidate_dependents_of_nodes", None)
    if callable(cascade):
        count = cascade(nodes)
    else:
        count = _fallback_cascade(model, nodes)

    mark = getattr(model, "mark_dirty", None)
    if callable(mark):
        mark()

    return CommandResult(
        handled=True,
        geometry_dirty=count > 0,
        message=f"{count} bağlı eleman güncellendi" if count else "",
    )


def _fallback_cascade(model, nodes) -> int:
    node_set = set(nodes)
    count = 0
    for frame in getattr(model, "frames", ()) or ():
        if (getattr(frame, "node_i", None) in node_set
                or getattr(frame, "node_j", None) in node_set):
            m = getattr(frame, "mark_dirty", None)
            if callable(m):
                m()
            count += 1
    for area in getattr(model, "areas", ()) or ():
        if any(n in node_set for n in (getattr(area, "nodes", ()) or ())):
            m = getattr(area, "mark_dirty", None)
            if callable(m):
                m()
            count += 1
    for poly in getattr(model, "polygons", ()) or ():
        if any(n in node_set for n in (getattr(poly, "nodes", ()) or ())):
            m = getattr(poly, "mark_dirty", None)
            if callable(m):
                m()
            count += 1
    return count