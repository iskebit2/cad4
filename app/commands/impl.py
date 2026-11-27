# app/commands/impl.py
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

from app.commands.base import BulkPlan, Command, CommandResult, CommandMeta


# ---------------------------------------------------------------------------
# Domain yardımcıları
# ---------------------------------------------------------------------------

def _nodes(scene) -> dict[int, Any]:
    return getattr(scene, "nodes", {})

def _all_elements(scene):
    return getattr(scene, "all_elements", {}).values()

def _find_node(scene, ref: Any):
    if ref is None:
        return None
    nodes = _nodes(scene)
    if isinstance(ref, int):
        return nodes.get(ref)
    try:
        return nodes.get(int(ref))
    except (ValueError, TypeError):
        pass
    for n in nodes.values():
        if getattr(n, "label", None) == ref or getattr(n, "unique_id", None) == ref:
            return n
    return None

def _find_element(scene, uid: int):
    getter = getattr(scene, "get_element_by_unique_id", None)
    if getter:
        return getter(uid)
    for el in _all_elements(scene):
        if getattr(el, "unique_id", None) == uid:
            return el
    return None

def _mark_dirty(element) -> None:
    marker = getattr(element, "mark_dirty", None)
    if callable(marker):
        marker()


# ---------------------------------------------------------------------------
# Proje komutları
# ---------------------------------------------------------------------------

@dataclass
class NewProject(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        from domain.project import Project
        self._app.project_service.replace(Project(), path=None, model_text="MODEL: YENİ SAHNE")
        return CommandResult(project_dirty=True, message="Yeni proje oluşturuldu.")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class OpenProject(Command):
    path: str = ""

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        if not self.path:
            ui = getattr(self._app, "ui", None)
            if ui is not None and hasattr(ui, "open_open_dialog"):
                ui.open_open_dialog(
                    lambda p: self._app.put_command(OpenProject(p))
                )
                return CommandResult(handled=True)
            return CommandResult(handled=False, message="Yol belirtilmedi", level="warn")
        self._app.project_service.load(self.path)
        return CommandResult(project_dirty=True, message=f"Proje açıldı: {self.path}")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class SaveProject(Command):
    path: str | None = None

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        svc = self._app.project_service
        if self.path:
            svc.save(self.path)
            return CommandResult(project_dirty=True, message=f"Kaydedildi: {self.path}")
        if svc.save_current():
            return CommandResult(project_dirty=True, message="Proje kaydedildi.")
        ui = getattr(self._app, "ui", None)
        if ui is not None and hasattr(ui, "open_save_dialog"):
            ui.open_save_dialog(
                lambda p: self._app.put_command(SaveProject(p))
            )
            return CommandResult(handled=True)
        return CommandResult(handled=False, message="Kayıt yolu yok", level="warn")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class SaveProjectAs(Command):
    path: str = ""

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        if not self.path:
            ui = getattr(self._app, "ui", None)
            if ui is not None and hasattr(ui, "open_save_dialog"):
                ui.open_save_dialog(
                    lambda p: self._app.put_command(SaveProjectAs(p))
                )
                return CommandResult(handled=True)
            return CommandResult(handled=False, message="Kayıt yolu yok", level="warn")
        self._app.project_service.save(self.path)
        return CommandResult(project_dirty=True, message=f"Farklı kaydedildi: {self.path}")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class CloseProject(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        from domain.project import Project
        self._app.project_service.replace(Project(), path=None, model_text="MODEL: BOŞ SAHNE")
        return CommandResult(project_dirty=True, message="Proje kapatıldı.")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class SetUnitSystem(Command):
    unit_system: Any = None
    reason: str = ""
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        self._app.project_service.set_unit_system(self.unit_system)
        return CommandResult(project_dirty=True, message=f"Birim: {self.unit_system}")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class ReplaceProject(Command):
    project: Any = None
    label: str = ""

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        if self.label:
            self._app.project_service.replace(self.project, path="", model_text=self.label)
        else:
            self._app.project_service.replace(self.project)
        return CommandResult(project_dirty=True, message="Proje değiştirildi.")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


# ---------------------------------------------------------------------------
# Node / Element komutları
# ---------------------------------------------------------------------------

@dataclass
class AddNode(Command):
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    label: str = ""
    restraint: Any = None

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        self._app = None
        if self._app is None:
            return CommandResult(handled=False, message="Uygulama bağlı değil.", level="error")
        project = getattr(self._app, "current_project", None)
        if project is None:
            return CommandResult(handled=False, message="Proje yok.", level="warn")
        self._scene = project.math_model
        from domain.element import Node
        node = Node(self.x, self.y, self.z, label=self.label or None, restraint=self.restraint)
        self._scene.add_element(node) if hasattr(self._scene, "add_element") else self._scene.add_node(node)
        self._created = node
        return CommandResult(geometry_dirty=True, message=f"Node eklendi: {node.unique_id}")

    def undo(self) -> None:
        if self._created is None or self._scene is None:
            return
        if hasattr(self._scene, "remove_element"):
            self._scene.remove_element(self._created)
        else:
            self._scene.nodes.pop(getattr(self._created, "unique_id", None), None)

    def __post_init__(self) -> None:
        self._app = None
        self._scene = None
        self._created = None


@dataclass
class AddFrame(Command):
    node_i_uid: int = 0
    node_j_uid: int = 0
    section_name: str = ""
    rotation_deg: float = 0.0
    label: str = ""

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error

        from domain.element import Frame
        ni = _find_node(self._scene, self.node_i_uid)
        nj = _find_node(self._scene, self.node_j_uid)
        if ni is None or nj is None:
            return CommandResult(handled=False, message="Node bulunamadı", level="warn")
        section = self._app.current_project.sections.get(self.section_name) if self.section_name else None
        frame = Frame(ni, nj, section=section, rotation_deg=self.rotation_deg, label=self.label or None)
        self._scene.add_frame(frame)
        self._created = frame
        return CommandResult(geometry_dirty=True, message="Frame eklendi.")

    def undo(self) -> None:
        self._scene.remove_element(self._created) if hasattr(self._scene, "remove_element") else self._scene.frames.pop(self._created.unique_id, None)

    def __post_init__(self) -> None:
        self._app = None
        self._scene = None
        self._created = None


@dataclass
class AddArea(Command):
    node_uids: list[int] = field(default_factory=list)
    thickness: float = 0.0
    label: str = ""

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error

        from domain.element import Area
        if len(self.node_uids) < 3 or len(set(self.node_uids)) != len(self.node_uids):
            return CommandResult(handled=False, message="En az 3 farklı node gerekli", level="warn")
        if not math.isfinite(self.thickness) or self.thickness < 0:
            return CommandResult(handled=False, message="Kalınlık geçersiz", level="warn")
        nodes = [_find_node(self._scene, uid) for uid in self.node_uids]
        if any(n is None for n in nodes):
            return CommandResult(handled=False, message="Node bulunamadı", level="warn")
        area = Area(nodes, thickness=self.thickness, label=self.label or None)
        self._scene.add_area(area)
        self._created = area
        return CommandResult(geometry_dirty=True, message="Area eklendi.")

    def undo(self) -> None:
        self._scene.remove_element(self._created) if hasattr(self._scene, "remove_element") else self._scene.areas.pop(self._created.unique_id, None)

    def __post_init__(self) -> None:
        self._app = None
        self._scene = None
        self._created = None


@dataclass
class AddLink(Command):
    node_i_uid: int = 0
    node_j_uid: int = 0
    prop_name: str = "LINK1"
    label: str = ""

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error

        from domain.element import Link
        ni = _find_node(self._scene, self.node_i_uid)
        nj = _find_node(self._scene, self.node_j_uid)
        if ni is None or nj is None:
            return CommandResult(handled=False, message="Node bulunamadı", level="warn")
        link = Link(ni, nj, propname=self.prop_name, label=self.label or None)
        self._scene.add_link(link)
        self._created = link
        return CommandResult(geometry_dirty=True, message="Link eklendi.")

    def undo(self) -> None:
        self._scene.remove_element(self._created) if hasattr(self._scene, "remove_element") else self._scene.links.pop(self._created.unique_id, None)

    def __post_init__(self) -> None:
        self._app = None
        self._scene = None
        self._created = None


@dataclass
class DeleteElements(Command):
    uids: list[int] = field(default_factory=list)

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error

        self._deleted = []
        self._rejected = []
        for uid in self.uids:
            el = _find_element(self._scene, uid)
            if el is None:
                continue
            if not self._scene.remove_element(el):
                self._rejected.append(el)
            else:
                self._deleted.append(el)
        msg = f"{len(self._deleted)} silindi"
        if self._rejected:
            msg += f", {len(self._rejected)} reddedildi"
        return CommandResult(geometry_dirty=bool(self._deleted), message=msg,
                             level="success" if self._deleted else "warn")

    def undo(self) -> None:
        for el in self._deleted:
            self._scene.restore_element(el)

    def __post_init__(self) -> None:
        self._app = None
        self._scene = None
        self._deleted: list[Any] = []
        self._rejected: list[Any] = []


@dataclass
class DeleteSelected(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error

        selected = list(self._app.engine.sel_mgr.get_selected()) if self._app.engine else []
        if not selected:
            return CommandResult(handled=True, message="Seçili eleman yok", level="warn")
        self._deleted = []
        for el in selected:
            if self._scene.remove_element(el):
                self._deleted.append(el)
        if self._app.engine and self._app.engine.sel_mgr:
            self._app.engine.sel_mgr.clear()
        return CommandResult(geometry_dirty=bool(self._deleted),
                             message=f"{len(self._deleted)} silindi",
                             level="success" if self._deleted else "warn")

    def undo(self) -> None:
        for el in self._deleted:
            self._scene.restore_element(el)

    def __post_init__(self) -> None:
        self._app = None
        self._scene = None
        self._deleted: list[Any] = []


@dataclass
class UpdateElementFields(Command):
    element_uid: int = 0
    changes: dict[str, Any] = field(default_factory=dict)

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error

        el = _find_element(self._scene, self.element_uid)
        if el is None:
            return CommandResult(handled=False, message="Eleman bulunamadı", level="warn")
        self._before = {k: getattr(el, k, None) for k in self.changes}
        for k, v in self.changes.items():
            setattr(el, k, v)
        _mark_dirty(el)
        return CommandResult(geometry_dirty=True, message=f"{len(self.changes)} alan güncellendi")

    def undo(self) -> None:
        el = _find_element(self._scene, self.element_uid)
        for k, v in self._before.items():
            setattr(el, k, v)
        _mark_dirty(el)

    def __post_init__(self) -> None:
        self._app = None
        self._scene = None
        self._before: dict[str, Any] = {}


@dataclass
class ReplicateSelected(Command):
    dx: float = 0.0
    dy: float = 0.0
    dz: float = 0.0
    count: int = 1

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error

        from domain.element import Frame, Node
        selected = list(self._app.engine.sel_mgr.get_selected()) if self._app.engine else []
        if not selected:
            return CommandResult(handled=False, message="Seçili eleman yok", level="warn")

        self._created_nodes = []
        self._created_elements = []

        for step in range(1, max(1, self.count) + 1):
            ox, oy, oz = self.dx * step, self.dy * step, self.dz * step
            node_map: dict[int, Any] = {}

            for el in selected:
                if isinstance(el, Node):
                    new = Node(el.x + ox, el.y + oy, el.z + oz)
                    if self._scene.add_element(new):
                        node_map[el.unique_id] = new
                        self._created_nodes.append(new)

            for el in selected:
                if isinstance(el, Frame):
                    ni = node_map.get(el.node_i.unique_id)
                    nj = node_map.get(el.node_j.unique_id)
                    if ni and nj:
                        new = Frame(ni, nj, section=el.section)
                        if self._scene.add_element(new):
                            self._created_elements.append(new)

        total = len(self._created_nodes) + len(self._created_elements)
        return CommandResult(
            geometry_dirty=bool(total),
            message=f"{self.count}x çoğaltıldı ({total} eleman)",
            level="success" if total else "warn",
        )

    def undo(self) -> None:
        for el in reversed(self._created_elements):
            self._scene.remove_element(el)
        for n in reversed(self._created_nodes):
            self._scene.remove_element(n)

    def __post_init__(self) -> None:
        self._app = None
        self._scene = None
        self._created_nodes: list[Any] = []
        self._created_elements: list[Any] = []


# ---------------------------------------------------------------------------
# Tanım (definition) komutları
# ---------------------------------------------------------------------------

@dataclass
class AddDefinition(Command):
    container_attr: str = ""
    name: str = ""
    obj: Any = None

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error

        container = getattr(self._project, self.container_attr, None)
        if container is None:
            return CommandResult(handled=False, message="Container yok", level="warn")
        container[self.name] = self.obj
        return CommandResult(project_dirty=True, message=f"{self.name} eklendi")

    def undo(self) -> None:
        getattr(self._project, self.container_attr).pop(self.name, None)

    def __post_init__(self) -> None:
        self._app = None
        self._project = None


@dataclass
class RemoveDefinition(Command):
    container_attr: str = ""
    name: str = ""

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error

        container = getattr(self._project, self.container_attr, None)
        if container is None or self.name not in container:
            return CommandResult(handled=False, message="Bulunamadı", level="warn")
        self._removed = container.pop(self.name)
        return CommandResult(project_dirty=True, message=f"{self.name} silindi")

    def undo(self) -> None:
        getattr(self._project, self.container_attr)[self.name] = self._removed

    def __post_init__(self) -> None:
        self._app = None
        self._project = None
        self._removed = None


@dataclass
class RenameDefinition(Command):
    container_attr: str = ""
    old_name: str = ""
    new_name: str = ""

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error

        container = getattr(self._project, self.container_attr, None)
        if container is None or self.old_name not in container:
            return CommandResult(handled=False, message="Bulunamadı", level="warn")
        if self.new_name in container:
            return CommandResult(handled=False, message=f"{self.new_name} zaten var", level="warn")
        container[self.new_name] = container.pop(self.old_name)
        return CommandResult(project_dirty=True, message=f"{self.old_name} → {self.new_name}")

    def undo(self) -> None:
        container = getattr(self._project, self.container_attr)
        container[self.old_name] = container.pop(self.new_name)

    def __post_init__(self) -> None:
        self._app = None
        self._project = None


# ---------------------------------------------------------------------------
# Bulk update
# ---------------------------------------------------------------------------

@dataclass
class BulkUpdate(Command):
    plans: list[BulkPlan] = field(default_factory=list)
    setter: Callable[[Any, str, Any], None] | None = None

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        for plan in self.plans:
            for f, v in plan.after.items():
                self.setter(plan.element, f, v)
            _mark_dirty(plan.element)
        return CommandResult(geometry_dirty=bool(self.plans),
                             message=f"{len(self.plans)} eleman güncellendi")

    def undo(self) -> None:
        for plan in reversed(self.plans):
            for f in reversed(list(plan.before.keys())):
                self.setter(plan.element, f, plan.before[f])
            _mark_dirty(plan.element)

    def __post_init__(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Görünüm / kamera
# ---------------------------------------------------------------------------

@dataclass
class FitView(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error

        self._app.view_service.fit_view()
        return CommandResult(handled=True)

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class ZoomExtents(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error

        self._app.view_service.zoom_extents()
        return CommandResult(handled=True)

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class SetCameraPreset(Command):
    preset: str = "iso"

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error

        self._app.view_service.set_camera_preset(self.preset)
        return CommandResult(handled=True, message=f"Kamera: {self.preset}")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class Toggle2D(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error

        self._app.view_service.toggle_2d()
        return CommandResult(handled=True)

    def undo(self) -> None:
        self._app.view_service.toggle_2d()

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class ToggleLocalAxes(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error

        scene = getattr(self._app.engine, "scene", None)
        if scene is None:
            return CommandResult(handled=False, message="Scene yok", level="warn")
        scene.show_local_axes = not scene.show_local_axes
        return CommandResult(handled=True)

    def undo(self) -> None:
        self.execute()

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class ToggleRenderFlag(Command):
    flag: str = ""
    value: bool = False

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        if self._app.engine:
            self._app.engine.show[self.flag] = self.value
        return CommandResult(handled=True)

    def undo(self) -> None:
        if self._app.engine:
            self._app.engine.show[self.flag] = not self.value

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class SetRenderMode(Command):
    mode: str = "shaded"

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        if self._app.engine and self._app.engine.renderer:
            self._app.engine.renderer.set_render_mode(self.mode)
        return CommandResult(handled=True)

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class ToggleRenderMode(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        if self._app.engine and self._app.engine.renderer:
            self._app.engine.renderer.toggle_render_mode()
        return CommandResult(handled=True)

    def undo(self) -> None:
        self.execute()

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class OpenViewport(Command):
    preset: str = "iso"

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        ui = getattr(self._app, "ui", None)
        if ui is None:
            return CommandResult(handled=False, message="UI yok", level="warn")
        vp = ui.open_viewport(self.preset)
        if vp is None:
            return CommandResult(handled=False, message="Viewport açılamadı", level="warn")
        return CommandResult(handled=True, message=f"Viewport: {vp.name}")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


# ---------------------------------------------------------------------------
# Seçim / görünürlük
# ---------------------------------------------------------------------------

@dataclass
class ClearSelection(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        if self._app.engine and self._app.engine.sel_mgr:
            self._app.engine.sel_mgr.clear()
        return CommandResult(handled=True)

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class SelectElements(Command):
    uids: list[int] = field(default_factory=list)
    mode: str = "replace"

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        eng = self._app.engine
        if not eng or not eng.sel_mgr:
            return CommandResult(handled=False)
        from core.selection_policy import SelectionMode
        els = [_find_element(self._app.current_project.math_model, u) for u in self.uids]
        els = [e for e in els if e is not None]
        if self.mode == "replace":
            eng.sel_mgr.select_multiple(els, mode=SelectionMode.REPLACE)
        elif self.mode == "add":
            for e in els:
                eng.sel_mgr.select(e, additive=True)
        else:
            for e in els:
                if eng.sel_mgr.is_selected(e):
                    eng.sel_mgr.select(e, additive=True)
        return CommandResult(handled=True, message=f"{len(els)} seçildi")

    def undo(self) -> None:
        if self._app.engine and self._app.engine.sel_mgr:
            self._app.engine.sel_mgr.clear()

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class ShowOnly(Command):
    uids: list[int] | None = None

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        uids = self.uids
        if uids is None and self._app.engine and self._app.engine.sel_mgr:
            uids = [getattr(e, "unique_id", None) for e in self._app.engine.sel_mgr.get_selected()]
            uids = [u for u in uids if u is not None]
        if not uids:
            return CommandResult(handled=True, message="Gösterilecek eleman yok", level="warn")
        self._prev = getattr(self._app.visibility_service, "show_only_ids", None)
        if not self._app.visibility_service.show_only(uids):
            return CommandResult(handled=True, message="Güncellenemedi", level="warn")
        if self._app.engine:
            self._app.engine.clear_hover()
        return CommandResult(geometry_dirty=True, message=f"{len(uids)} izole edildi")

    def undo(self) -> None:
        if self._prev is None:
            self._app.visibility_service.show_all()
        else:
            self._app.visibility_service.show_only(list(self._prev))

    def __post_init__(self) -> None:
        self._app = None
        self._prev: list[int] | None = None


@dataclass
class HideElements(Command):
    uids: list[int] = field(default_factory=list)

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        if not self.uids:
            return CommandResult(handled=True, message="Gizlenecek eleman yok", level="warn")
        if not self._app.visibility_service.hide(self.uids):
            return CommandResult(handled=True, message="Gizlenemedi", level="warn")
        if self._app.engine:
            self._app.engine.clear_hover()
        return CommandResult(geometry_dirty=True, message=f"{len(self.uids)} gizlendi")

    def undo(self) -> None:
        self._app.visibility_service.show(self.uids)

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class ShowEntireModel(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        self._app.visibility_service.show_all()
        if self._app.engine:
            self._app.engine.clear_hover()
        return CommandResult(geometry_dirty=True, message="Tüm model görünür")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


# @dataclass
# class ToggleLoadsVisible(Command):
#     enabled: bool | None = None

#     def execute(self) -> CommandResult:
#         if (error := self._resolve()) is not None:
#             return error
#         state = self._app.visibility_service.toggle_loads_visible(self.enabled)
#         return CommandResult(handled=True, message=f"Yük görünürlüğü: {'Açık' if state else 'Kapalı'}")

#     def undo(self) -> None:
#         self._app.visibility_service.toggle_loads_visible(not self.enabled if self.enabled is not None else None)

#     def __post_init__(self) -> None:
#         self._app = None


# ---------------------------------------------------------------------------
# Çizim / düzenleme aksiyonları
# ---------------------------------------------------------------------------

@dataclass
class StartDrawTool(Command):
    mode: str = "line"

    _MODES = {
        "line": "line", "poly": "sequential", "polygon": "sequential",
        "sequential": "sequential", "rect": "rectangle", "rectangle": "rectangle",
        "single": "single_point", "single_point": "single_point",
    }

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        eng = self._app.engine
        if eng is None or eng.draw_mgr is None:
            return CommandResult(handled=False, message="Draw manager yok", level="warn")
        mode = self._MODES.get(self.mode.lower().strip())
        if mode is None:
            return CommandResult(handled=True, message=f"Geçersiz mod: {self.mode}", level="warn")
        eng.draw_mgr.start(mode=mode)
        return CommandResult(handled=True, message=f"Çizim modu: {mode}")

    def undo(self) -> None:
        if self._app.engine and self._app.engine.draw_mgr:
            self._app.engine.draw_mgr.cancel()

    def __post_init__(self) -> None:
        self._app = None

@dataclass
class StartDrawLine(StartDrawTool):
    mode: str = "line"

@dataclass
class StartDrawPoly(StartDrawTool):
    mode: str = "poly"

@dataclass
class CommitDrawnElement(Command):
    element: Any = None

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        from domain.line import Line
        from domain.polygon import Polygon
        if self.element is None:
            return CommandResult(handled=False, message="Eleman yok", level="warn")
        project = self._app.current_project
        if isinstance(self.element, Line):
            project.add_line(self.element)
        elif isinstance(self.element, Polygon):
            project.add_polygon(self.element)
        else:
            return CommandResult(handled=False, message=f"Desteklenmeyen: {type(self.element).__name__}", level="warn")
        self._sync()
        return CommandResult(geometry_dirty=True, message=f"{type(self.element).__name__} oluşturuldu")

    def undo(self) -> None:
        from domain.line import Line
        from domain.polygon import Polygon
        project = self._app.current_project
        if isinstance(self.element, Line):
            project.lines.pop(getattr(self.element, "unique_id", None), None)
        elif isinstance(self.element, Polygon):
            project.polygons.pop(getattr(self.element, "unique_id", None), None)
        self._sync()

    def _sync(self) -> None:
        eng = self._app.engine
        if eng is None:
            return
        eng.update_geo(self._app.current_project)
        pr = getattr(eng, "presentation_renderer", None)
        if pr is not None and hasattr(self._app.current_project, "polygons"):
            pr.update_polygons(list(self._app.current_project.polygons.values()))

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class Undo(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        return self._app.edit_controller.commands.undo()

    def undo(self) -> None:
        self._app.edit_controller.commands.redo()

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class Redo(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        return self._app.edit_controller.commands.redo()

    def undo(self) -> None:
        self._app.edit_controller.commands.undo()

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class RefreshGeometry(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        project = self._app.current_project
        for el in getattr(project.math_model, "all_elements", {}).values():
            _mark_dirty(el)
        project.math_model.mark_dirty()
        project.math_model.refresh_bounds()
        if getattr(project, "scene", None):
            project.scene.mark_dirty()
            project.scene.refresh_bounds()
        return CommandResult(geometry_dirty=True, handled=True)

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class PropagateGeometryChange(Command):
    node_uids: list[int] = field(default_factory=list)

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        model = self._app.engine.math_model if self._app.engine else None
        if model is None:
            return CommandResult(handled=False)
        nodes = []
        for uid in self.node_uids:
            n = _find_node(model, uid)
            if n:
                nodes.append(n)
        if not nodes:
            model.mark_dirty()
            return CommandResult(geometry_dirty=True, handled=True)
        cascade = getattr(model, "invalidate_dependents_of_nodes", None)
        count = cascade(nodes) if callable(cascade) else 0
        model.mark_dirty()
        return CommandResult(geometry_dirty=count > 0,
                             message=f"{count} bağlı eleman güncellendi" if count else "")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


# ---------------------------------------------------------------------------
# Panel / UI
# ---------------------------------------------------------------------------

@dataclass
class TogglePanel(Command):
    name: str = ""

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        spec = self._get_spec()
        if spec is None:
            return CommandResult(handled=True, message=f"Panel bulunamadı: {self.name}", level="warn")
        panel = self._app.panel_registry.instance(self.name)
        if panel is None:
            return CommandResult(handled=True, message=f"Panel instance yok: {self.name}", level="warn")
        if getattr(panel, "visible", False):
            panel.close()
            return CommandResult(handled=True, message=f"Panel kapatıldı: {spec.title}")
        self._prepare(panel)
        panel.open()
        return CommandResult(handled=True, message=f"Panel açıldı: {spec.title}")

    def undo(self) -> None:
        panel = self._app.panel_registry.instance(self.name) if self._app.panel_registry else None
        if panel and getattr(panel, "visible", False):
            panel.close()

    def _get_spec(self):
        reg = getattr(self._app, "panel_registry", None)
        return reg.get(self.name) if reg else None

    def _prepare(self, panel) -> None:
        ui = getattr(self._app, "ui", None)
        if ui is not None and hasattr(ui, "prepare_panel"):
            ui.prepare_panel(self.name, panel)

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class OpenPanel(Command):
    name: str = ""
    kwargs: dict[str, Any] = field(default_factory=dict)

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        reg = getattr(self._app, "panel_registry", None)
        if reg is None:
            return CommandResult(handled=False)
        spec = reg.get(self.name)
        if spec is None:
            return CommandResult(handled=True, message=f"Panel bulunamadı: {self.name}", level="warn")
        panel = reg.instance(self.name)
        if panel is None:
            return CommandResult(handled=True, message=f"Panel instance yok: {self.name}", level="warn")
        ui = getattr(self._app, "ui", None)
        if ui is not None and hasattr(ui, "prepare_panel"):
            ui.prepare_panel(self.name, panel)
        panel.open(**self.kwargs)
        return CommandResult(handled=True, message=f"Panel açıldı: {spec.title}")

    def undo(self) -> None:
        reg = getattr(self._app, "panel_registry", None)
        panel = reg.instance(self.name) if reg else None
        if panel and getattr(panel, "visible", False):
            panel.close()

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class ClosePanel(Command):
    name: str = ""

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        reg = getattr(self._app, "panel_registry", None)
        if reg is None:
            return CommandResult(handled=False)
        panel = reg.instance(self.name)
        if panel is None:
            return CommandResult(handled=True, message=f"Panel yok: {self.name}", level="warn")
        panel.close()
        return CommandResult(handled=True, message=f"Panel kapatıldı: {self.name}")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class OpenInspector(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        ui = getattr(self._app, "ui", None)
        inspector = getattr(ui, "inspector", None) if ui else None
        if inspector is None:
            return CommandResult(handled=False, message="Inspector yok", level="warn")
        if self._app.engine and self._app.engine.sel_mgr:
            inspector.set_selection(list(self._app.engine.sel_mgr.get_selected()))
        inspector.open()
        return CommandResult(handled=True)

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class HoverChanged(Command):
    pick_id: int = 0

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        eng = self._app.engine
        if eng is None or eng.hover is None:
            return CommandResult(handled=True)
        for _spec, panel in self._app.panel_registry.visible_instances():
            hook = getattr(panel, "on_hover_changed", None)
            if callable(hook):
                hook(eng.hover.element_id, eng.hover.element)
        return CommandResult(handled=True)

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


# ---------------------------------------------------------------------------
# Toolbar / layout
# ---------------------------------------------------------------------------

@dataclass
class ReloadToolbarLayout(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        toolbar = self._toolbar()
        if toolbar is None:
            return CommandResult(handled=False)
        toolbar.reload_layout()
        return CommandResult(handled=True, message="Toolbar yeniden yüklendi")

    def undo(self) -> None:
        pass

    def _toolbar(self):
        ui = getattr(self._app, "ui", None)
        return getattr(ui, "toolbar", None) if ui else None

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class ResetToolbarLayout(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        toolbar = getattr(getattr(self._app, "ui", None), "toolbar", None)
        if toolbar is None:
            return CommandResult(handled=False)
        toolbar.reset_layout()
        return CommandResult(handled=True, message="Toolbar sıfırlandı")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class SaveToolbarLayout(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        toolbar = getattr(getattr(self._app, "ui", None), "toolbar", None)
        if toolbar is None:
            return CommandResult(handled=False)
        toolbar.save_layout()
        return CommandResult(handled=True, message="Toolbar kaydedildi")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


# ---------------------------------------------------------------------------
# Plane araçları
# ---------------------------------------------------------------------------

@dataclass
class StartPlane3pt(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        pdm = getattr(self._app.engine, "plane_draw_mgr", None) if self._app.engine else None
        if pdm is None:
            return CommandResult(handled=False)
        if pdm.is_active:
            pdm.cancel()
        pdm.start_3pt()
        return CommandResult(handled=True)

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class StartPlane2ptZ(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        pdm = getattr(self._app.engine, "plane_draw_mgr", None) if self._app.engine else None
        if pdm is None:
            return CommandResult(handled=False)
        if pdm.is_active:
            pdm.cancel()
        pdm.start_2pt_z()
        return CommandResult(handled=True)

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


# ---------------------------------------------------------------------------
# S2K import/export
# ---------------------------------------------------------------------------

@dataclass
class ImportS2K(Command):
    path: str = ""
    mode: str = "import"

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        if self.path:
            return CommandResult(handled=False, message="S2K import bağlı değil", level="warn")
        return CommandResult(handled=True, followup=OpenPanel("s2k_panel"),
                             message="S2K panelinden içe alın.")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class ExportS2K(Command):
    path: str = ""

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        if self.path:
            return CommandResult(handled=False, message="S2K export bağlı değil", level="warn")
        return CommandResult(handled=True, followup=OpenPanel("s2k_panel"),
                             message="S2K panelinden dışa verin.")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


@dataclass
class QuitApp(Command):
    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        self._app.request_quit()
        return CommandResult(handled=True)

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None


# ---------------------------------------------------------------------------
# ConvertFramesToLinks
# ---------------------------------------------------------------------------

@dataclass
class ConvertFramesToLinks(Command):
    link_prop_name: str = "DefaultLink"
    delete_original: bool = True

    def execute(self) -> CommandResult:
        if (error := self._resolve()) is not None:
            return error
        from domain.element import Frame
        from tools import frame_to_link
        eng = self._app.engine
        ctrl = self._app.edit_controller
        if eng is None or eng.math_model is None or ctrl is None:
            return CommandResult(handled=False)
        frames = [e for e in ctrl.scene.get_selected() if isinstance(e, Frame)]
        if not frames:
            return CommandResult(handled=True, message="Seçili Frame yok", level="warn")
        report = frame_to_link.convert_frames_to_links(
            scene=ctrl.scene,
            project=self._app.current_project,
            frames=frames,
            link_prop_name=self.link_prop_name,
            delete_original=self.delete_original,
        )
        if self._app.visibility_service.show_only_ids is not None:
            removed = {f.unique_id for f in frames}
            self._app.visibility_service.show_only_ids -= removed
            self._app.visibility_service.show_only_ids.update(
                link.unique_id for link in report["new_links"]
            )
        if eng.sel_mgr:
            eng.sel_mgr.clear()
        n = len(report.get("new_links", []))
        return CommandResult(geometry_dirty=True, handled=True,
                             message=f"{n} link oluşturuldu", level="success")

    def undo(self) -> None:
        pass

    def __post_init__(self) -> None:
        self._app = None

