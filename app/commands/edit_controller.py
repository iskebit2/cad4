# app/commands/edit_controller.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.commands.base import BulkPlan, CommandManager, CommandResult
from app.commands.impl import (
    AddArea, AddFrame, AddLink, AddNode,
    AddDefinition, RemoveDefinition, RenameDefinition,
    BulkUpdate, DeleteElements, UpdateElementFields,
)


@dataclass
class EditResult:
    ok: bool
    element: Any = None
    message: str = ""
    created: bool = False


class EditController:
    def __init__(self, app) -> None:
        self._app = app
        self.commands = CommandManager(max_history=100)
        self.commands.add_listener(self._on_result)

    @property
    def scene(self):
        return self._app.current_project.math_model

    def _on_result(self, result: CommandResult) -> None:
        if result.geometry_dirty:
            try:
                self.scene.mark_dirty()
            except Exception:
                pass

    def create(self, element_type: str, values: dict[str, Any]) -> EditResult:
        et = element_type.lower().strip()
        cmd = self._build_create(et, values)
        if cmd is None:
            return EditResult(False, message=f"Bilinmeyen tip: {et}")
        result = self.commands.execute(cmd)
        return EditResult(result.handled, element=getattr(cmd, "_created", None),
                          message=result.message, created=result.handled)

    def update(self, element, new_values: dict[str, Any]) -> EditResult:
        if element is None:
            return EditResult(False, message="Eleman yok")
        before, after = {}, {}
        for f, raw in new_values.items():
            old = getattr(element, f, None)
            if old != raw:
                before[f] = old
                after[f] = raw
        if not after:
            return EditResult(True, element=element, message="Değişiklik yok")
        cmd = UpdateElementFields(
            element_uid=getattr(element, "unique_id", 0),
            changes=after,
        )
        result = self.commands.execute(cmd)
        return EditResult(result.handled, element=element, message=result.message)

    def delete(self, elements) -> EditResult:
        if not elements:
            return EditResult(False, message="Eleman yok")
        if not isinstance(elements, (list, tuple)):
            elements = [elements]
        uids = [getattr(e, "unique_id", None) for e in elements]
        uids = [u for u in uids if u is not None]
        cmd = DeleteElements(uids=uids)
        result = self.commands.execute(cmd)
        return EditResult(result.handled, message=result.message)

    def undo(self) -> EditResult:
        result = self.commands.undo()
        return EditResult(result.handled, message=result.message)

    def redo(self) -> EditResult:
        result = self.commands.redo()
        return EditResult(result.handled, message=result.message)

    def bulk_update(self, elements, changes: dict[str, Any]) -> EditResult:
        if not elements:
            return EditResult(False, message="Eleman yok")
        plans = []
        for e in elements:
            before, after = {}, {}
            for f, raw in changes.items():
                old = getattr(e, f, None)
                if old != raw:
                    before[f] = old
                    after[f] = raw
            if after:
                plans.append(BulkPlan(e, before, after))
        if not plans:
            return EditResult(True, message="Değişiklik yok")
        cmd = BulkUpdate(plans=plans, setter=lambda el, f, v: setattr(el, f, v))
        result = self.commands.execute(cmd)
        return EditResult(result.handled, message=result.message)

    def replicate(self, elements, dx: float, dy: float, dz: float, count: int = 1) -> EditResult:
        from app.commands.impl import ReplicateSelected
        if not elements:
            return EditResult(False, message="Seçili eleman yok")
        cmd = ReplicateSelected(dx=dx, dy=dy, dz=dz, count=count)
        result = self.commands.execute(cmd)
        return EditResult(result.handled, message=result.message, created=result.handled)

    def _build_create(self, et: str, values: dict[str, Any]):
        if et == "node":
            return AddNode(
                x=float(values.get("x", 0.0)),
                y=float(values.get("y", 0.0)),
                z=float(values.get("z", 0.0)),
                label=values.get("label", ""),
            )
        if et == "frame":
            return AddFrame(
                node_i_uid=int(values.get("node_i_id") or values.get("node_i") or 0),
                node_j_uid=int(values.get("node_j_id") or values.get("node_j") or 0),
                section_name=values.get("section_name", ""),
                rotation_deg=float(values.get("rotation_deg", 0.0)),
                label=values.get("label", ""),
            )
        if et == "link":
            return AddLink(
                node_i_uid=int(values.get("node_i_id") or values.get("node_i") or 0),
                node_j_uid=int(values.get("node_j_id") or values.get("node_j") or 0),
                prop_name=values.get("propname", "LINK1"),
                label=values.get("label", ""),
            )
        if et == "area":
            return AddArea(
                node_uids=list(values.get("nodes", [])),
                thickness=float(values.get("thickness", 0.0)),
                label=values.get("label", ""),
            )
        return None