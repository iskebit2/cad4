# tests/test_commands.py
from __future__ import annotations

import dataclasses
import sys
import types
from typing import Any
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Sahte app / domain — CAD4 gerçek modüllerini taklit eder
# ---------------------------------------------------------------------------

class FakeNode:
    _next_id = 1
    def __init__(self, x=0.0, y=0.0, z=0.0, label=None, restraint=None):
        self.unique_id = FakeNode._next_id
        FakeNode._next_id += 1
        self.x, self.y, self.z = x, y, z
        self.label = label
        self.restraint = restraint
    def mark_dirty(self): self._dirty = True


class FakeFrame:
    _next_id = 1
    def __init__(self, ni, nj, section=None, rotation_deg=0.0, label=None):
        self.unique_id = FakeFrame._next_id
        FakeFrame._next_id += 1
        self.node_i, self.node_j = ni, nj
        self.section = section
        self.rotation_deg = rotation_deg
        self.label = label
    def mark_dirty(self): self._dirty = True


class FakeArea:
    _next_id = 1
    def __init__(self, nodes, thickness=0.0, label=None):
        self.unique_id = FakeArea._next_id
        FakeArea._next_id += 1
        self.nodes = list(nodes)
        self.thickness = thickness
        self.label = label
    def mark_dirty(self): self._dirty = True


class FakeLink:
    _next_id = 1
    def __init__(self, ni, nj, propname="", label=None):
        self.unique_id = FakeLink._next_id
        FakeLink._next_id += 1
        self.node_i, self.node_j = ni, nj
        self.propname = propname
        self.label = label
    def mark_dirty(self): self._dirty = True


class FakeMathModel:
    def __init__(self):
        self.nodes: dict[int, Any] = {}
        self.frames: dict[int, Any] = {}
        self.areas: dict[int, Any] = {}
        self.links: dict[int, Any] = {}
        self.all_elements: dict[int, Any] = {}
        self._dirty = False
        self._bounds_dirty = False

    def _store(self, el, container):
        container[el.unique_id] = el
        self.all_elements[el.unique_id] = el

    def add_element(self, el):
        if isinstance(el, FakeNode): self._store(el, self.nodes)
        elif isinstance(el, FakeFrame): self._store(el, self.frames)
        elif isinstance(el, FakeArea): self._store(el, self.areas)
        elif isinstance(el, FakeLink): self._store(el, self.links)
        else: return False
        return True

    def add_node(self, n): return self.add_element(n)
    def add_frame(self, f): return self.add_element(f)
    def add_area(self, a): return self.add_element(a)
    def add_link(self, l): return self.add_element(l)

    def remove_element(self, el):
        uid = getattr(el, "unique_id", None)
        if uid is None or uid not in self.all_elements:
            return False
        self.all_elements.pop(uid, None)
        for c in (self.nodes, self.frames, self.areas, self.links):
            c.pop(uid, None)
        return True

    def restore_element(self, el):
        if isinstance(el, FakeNode): self.nodes[el.unique_id] = el
        elif isinstance(el, FakeFrame): self.frames[el.unique_id] = el
        elif isinstance(el, FakeArea): self.areas[el.unique_id] = el
        elif isinstance(el, FakeLink): self.links[el.unique_id] = el
        self.all_elements[el.unique_id] = el
        return True

    def get_element_by_unique_id(self, uid):
        return self.all_elements.get(uid)

    def mark_dirty(self): self._dirty = True
    def refresh_bounds(self): self._bounds_dirty = True
    def invalidate_dependents_of_nodes(self, nodes): return len(nodes)


class FakeSelectionManager:
    def __init__(self):
        self._selected: list[Any] = []
    def get_selected(self): return list(self._selected)
    def clear(self): self._selected.clear()
    def select(self, el, additive=False):
        if additive and el not in self._selected:
            self._selected.append(el)
        elif not additive:
            self._selected = [el]
    def select_multiple(self, els, mode=None): self._selected = list(els)
    def is_selected(self, el): return el in self._selected


class FakeProject:
    def __init__(self):
        self.math_model = FakeMathModel()
        self.sections: dict[str, Any] = {}
        self.materials: dict[str, Any] = {}
        self.lines: dict[int, Any] = {}
        self.polygons: dict[int, Any] = {}
        self.scene = FakeMathModel()

    def add_line(self, line): self.lines[line.unique_id] = line
    def add_polygon(self, poly): self.polygons[poly.unique_id] = poly


class FakeVisibilityService:
    def __init__(self):
        self.show_only_ids: set[int] | None = None
        self.hidden: set[int] = set()
        self.loads_visible = False
    def show_only(self, uids): self.show_only_ids = set(uids); return True
    def show_all(self): self.show_only_ids = None; self.hidden.clear()
    def hide(self, uids): self.hidden.update(uids); return True
    def show(self, uids): self.hidden -= set(uids)
    def toggle_loads_visible(self, enabled=None):
        self.loads_visible = (not self.loads_visible) if enabled is None else enabled
        return self.loads_visible


class FakeEngine:
    def __init__(self, model):
        self.math_model = model
        self.sel_mgr = FakeSelectionManager()
        self.hover = None
        self.draw_mgr = MagicMock()
        self.plane_draw_mgr = MagicMock(is_active=False)
        self.renderer = MagicMock()
        self.scene = MagicMock(show_local_axes=False)
        self.show: dict[str, bool] = {}
        self.update_geo = MagicMock()
        self.presentation_renderer = MagicMock()
    def clear_hover(self): self.hover = None


class FakeViewService:
    def __init__(self):
        self.fit_view = MagicMock()
        self.zoom_extents = MagicMock()
        self.set_camera_preset = MagicMock()
        self.toggle_2d = MagicMock()


class FakeProjectService:
    def __init__(self, project):
        self.project = project
        self.load = MagicMock()
        self.save = MagicMock()
        self.save_current = MagicMock(return_value=True)
        self.replace = MagicMock()
        self.set_unit_system = MagicMock()


class FakePanelRegistry:
    def __init__(self):
        self._specs: dict[str, Any] = {}
        self._instances: dict[str, Any] = {}
    def get(self, name): return self._specs.get(name)
    def instance(self, name): return self._instances.get(name)
    def visible_instances(self): return [(self._specs[n], self._instances[n]) for n in self._instances if getattr(self._instances[n], "visible", False)]


class FakeApp:
    def __init__(self):
        self.current_project = FakeProject()
        self.project_service = FakeProjectService(self.current_project)
        self.engine = FakeEngine(self.current_project.math_model)
        self.edit_controller = None
        self.view_service = FakeViewService()
        self.visibility_service = FakeVisibilityService()
        self.panel_registry = FakePanelRegistry()
        self.ui = MagicMock()
        self.request_quit = MagicMock()

    def put_command(self, cmd): pass


# ---------------------------------------------------------------------------
# Domain modüllerini sys.modules'a enjekte et
# ---------------------------------------------------------------------------

def _install_fake_domain():
    domain = types.ModuleType("domain")
    element = types.ModuleType("domain.element")
    element.Node = FakeNode
    element.Frame = FakeFrame
    element.Area = FakeArea
    element.Link = FakeLink
    project_mod = types.ModuleType("domain.project")
    project_mod.Project = FakeProject
    line_mod = types.ModuleType("domain.line")
    line_mod.Line = type("Line", (), {"unique_id": 0})
    polygon_mod = types.ModuleType("domain.polygon")
    polygon_mod.Polygon = type("Polygon", (), {"unique_id": 0, "nodes": []})
    sys.modules.update({
        "domain": domain,
        "domain.element": element,
        "domain.project": project_mod,
        "domain.line": line_mod,
        "domain.polygon": polygon_mod,
    })


_install_fake_domain()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    FakeNode._next_id = 1
    FakeFrame._next_id = 1
    FakeArea._next_id = 1
    FakeLink._next_id = 1
    a = FakeApp()
    from app.commands.impl import bind_app
    bind_app(a)
    from app.commands.edit_controller import EditController
    a.edit_controller = EditController(a)
    return a


# ---------------------------------------------------------------------------
# Testler
# ---------------------------------------------------------------------------

def test_command_manager_execute_and_undo(app):
    from app.commands.impl import AddNode
    ctrl = app.edit_controller
    res = ctrl.commands.execute(AddNode(x=1, y=2, z=3))
    assert res.handled
    assert len(app.current_project.math_model.nodes) == 1
    ctrl.commands.undo()
    assert len(app.current_project.math_model.nodes) == 0
    ctrl.commands.redo()
    assert len(app.current_project.math_model.nodes) == 1


def test_add_node_undo_restores(app):
    from app.commands.impl import AddNode
    ctrl = app.edit_controller
    node = AddNode(x=5, y=5, z=5)
    ctrl.commands.execute(node)
    uid = node._created.unique_id
    assert uid in app.current_project.math_model.nodes
    ctrl.commands.undo()
    assert uid not in app.current_project.math_model.nodes


def test_add_frame_requires_nodes(app):
    from app.commands.impl import AddFrame
    ctrl = app.edit_controller
    res = ctrl.commands.execute(AddFrame(node_i_uid=999, node_j_uid=998))
    assert not res.handled
    assert len(app.current_project.math_model.frames) == 0


def test_add_area_validation(app):
    from app.commands.impl import AddArea
    ctrl = app.edit_controller
    res = ctrl.commands.execute(AddArea(node_uids=[1, 2]))
    assert not res.handled
    res = ctrl.commands.execute(AddArea(node_uids=[1, 2, 2]))
    assert not res.handled
    res = ctrl.commands.execute(AddArea(node_uids=[1, 2, 3], thickness=-1))
    assert not res.handled


def test_delete_and_undo(app):
    from app.commands.impl import AddNode, DeleteElements
    ctrl = app.edit_controller
    n1, n2 = AddNode(x=0), AddNode(x=1)
    ctrl.commands.execute(n1)
    ctrl.commands.execute(n2)
    uids = [n1._created.unique_id, n2._created.unique_id]
    res = ctrl.commands.execute(DeleteElements(uids=uids))
    assert res.handled
    assert len(app.current_project.math_model.nodes) == 0
    ctrl.commands.undo()
    assert len(app.current_project.math_model.nodes) == 2


def test_update_element_fields(app):
    from app.commands.impl import AddNode, UpdateElementFields
    ctrl = app.edit_controller
    n = AddNode(x=0, y=0, z=0)
    ctrl.commands.execute(n)
    uid = n._created.unique_id
    ctrl.commands.execute(UpdateElementFields(element_uid=uid, changes={"x": 10.0}))
    assert app.current_project.math_model.nodes[uid].x == 10.0
    ctrl.commands.undo()
    assert app.current_project.math_model.nodes[uid].x == 0.0


def test_undo_stack_integrity_on_failure(app):
    from app.commands.base import Command, CommandManager, CommandResult

    class Broken(Command):
        def execute(self): return CommandResult(handled=True)
        def undo(self): raise RuntimeError("boom")

    mgr = CommandManager()
    mgr.execute(Broken())
    assert mgr.can_undo
    res = mgr.undo()
    assert not res.handled
    assert mgr.can_undo
    assert not mgr.can_redo


def test_undo_empty(app):
    from app.commands.base import CommandManager
    mgr = CommandManager()
    res = mgr.undo()
    assert not res.handled
    res = mgr.redo()
    assert not res.handled


def test_factory_parse_primitives(app):
    from app.commands.impl import AddNode
    from app.commands.registry import _parse_scalar
    assert _parse_scalar("42", int) == 42
    assert _parse_scalar("3.14", float) == 3.14
    assert _parse_scalar("true", bool) is True
    assert _parse_scalar("0", bool) is False
    assert _parse_scalar("evet", bool) is True
    assert _parse_scalar("hayır", bool) is False
    assert _parse_scalar("hello", str) == "hello"


def test_factory_parse_list_int(app):
    from app.commands.registry import _parse_scalar
    result = _parse_scalar("1,2,3", list[int])
    assert result == [1, 2, 3]


def test_registry_auto_factory(app):
    from app.commands.registry import get_registry
    from app.commands.impl import AddNode
    reg = get_registry()
    reg.register(AddNode)
    cmd = reg.build("add_node", ["1.0", "2.0", "3.0"])
    assert cmd is not None
    assert cmd.x == 1.0
    assert cmd.y == 2.0
    assert cmd.z == 3.0


def test_registry_list_int_factory(app):
    from app.commands.registry import get_registry
    from app.commands.impl import DeleteElements
    reg = get_registry()
    reg.register(DeleteElements)
    cmd = reg.build("delete_elements", ["1,2,3"])
    assert cmd is not None
    assert cmd.uids == [1, 2, 3]


def test_visibility_hide_show(app):
    from app.commands.impl import HideElements, ShowEntireModel
    ctrl = app.edit_controller
    ctrl.commands.execute(HideElements(uids=[1, 2]))
    assert app.visibility_service.hidden == {1, 2}
    ctrl.commands.execute(ShowEntireModel())
    assert app.visibility_service.hidden == set()


def test_toggle_2d_undo(app):
    from app.commands.impl import Toggle2D
    ctrl = app.edit_controller
    ctrl.commands.execute(Toggle2D())
    assert app.view_service.toggle_2d.call_count == 1
    ctrl.commands.undo()
    assert app.view_service.toggle_2d.call_count == 2


def test_selection_replace(app):
    from app.commands.impl import AddNode, SelectElements
    ctrl = app.edit_controller
    n1, n2 = AddNode(), AddNode()
    ctrl.commands.execute(n1)
    ctrl.commands.execute(n2)
    res = ctrl.commands.execute(SelectElements(uids=[n1._created.unique_id], mode="replace"))
    assert res.handled
    assert app.engine.sel_mgr.get_selected() == [n1._created]


def test_definition_add_remove_undo(app):
    from app.commands.impl import AddDefinition, RemoveDefinition
    ctrl = app.edit_controller
    ctrl.commands.execute(AddDefinition(container_attr="sections", name="S1", obj="section_obj"))
    assert "S1" in app.current_project.sections
    ctrl.commands.undo()
    assert "S1" not in app.current_project.sections
    ctrl.commands.execute(AddDefinition(container_attr="sections", name="S2", obj="x"))
    ctrl.commands.execute(RemoveDefinition(container_attr="sections", name="S2"))
    assert "S2" not in app.current_project.sections
    ctrl.commands.undo()
    assert "S2" in app.current_project.sections


def test_rename_definition_collision(app):
    from app.commands.impl import AddDefinition, RenameDefinition
    ctrl = app.edit_controller
    ctrl.commands.execute(AddDefinition(container_attr="sections", name="A", obj=1))
    ctrl.commands.execute(AddDefinition(container_attr="sections", name="B", obj=2))
    res = ctrl.commands.execute(RenameDefinition(container_attr="sections", old_name="A", new_name="B"))
    assert not res.handled
    assert app.current_project.sections["A"] == 1


def test_update_definition_edit_rename_undo_redo(app):
    from types import SimpleNamespace

    from app.commands.impl import AddDefinition, UpdateDefinition

    ctrl = app.edit_controller
    definition = SimpleNamespace(name="A", value=1)
    ctrl.commands.execute(AddDefinition(
        container_attr="sections", name="A", obj=definition,
    ))
    command = UpdateDefinition(
        container_attr="sections",
        name="A",
        changes={"name": "B", "value": 2},
        new_name="B",
    )

    result = ctrl.commands.execute(command)
    assert result.handled
    assert app.current_project.sections == {"B": definition}
    assert (definition.name, definition.value) == ("B", 2)

    ctrl.commands.undo()
    assert app.current_project.sections == {"A": definition}
    assert (definition.name, definition.value) == ("A", 1)

    ctrl.commands.redo()
    assert app.current_project.sections == {"B": definition}
    assert (definition.name, definition.value) == ("B", 2)


def test_bulk_update(app):
    from app.commands.impl import AddNode
    ctrl = app.edit_controller
    n1, n2 = AddNode(), AddNode()
    ctrl.commands.execute(n1)
    ctrl.commands.execute(n2)
    nodes = [n1._created, n2._created]
    res = ctrl.bulk_update(nodes, {"x": 99.0})
    assert res.ok
    assert all(n.x == 99.0 for n in nodes)
    ctrl.commands.undo()
    assert all(n.x == 0.0 for n in nodes)


def test_edit_controller_create_node(app):
    ctrl = app.edit_controller
    res = ctrl.create("node", {"x": 1.0, "y": 2.0, "z": 3.0, "label": "N1"})
    assert res.ok and res.created
    assert len(app.current_project.math_model.nodes) == 1


def test_edit_controller_create_frame_missing_nodes(app):
    ctrl = app.edit_controller
    res = ctrl.create("frame", {"node_i_id": 999, "node_j_id": 998})
    assert not res.ok


def test_registry_catalog(app):
    from app.commands.registry import get_registry
    from app.commands.impl import AddNode, DeleteElements
    reg = get_registry()
    reg.register(AddNode)
    reg.register(DeleteElements)
    catalog = dict(reg.catalog())
    assert "add_node" in catalog
    assert "delete_elements" in catalog
    assert catalog["add_node"]


def test_meta_registration(app):
    from app.commands.registry import get_registry
    from app.commands.impl import register_all, FitView, Undo
    reg = get_registry()
    register_all(reg)
    meta = reg.get_meta(FitView)
    assert meta is not None
    assert meta.label == "Tüm Modeli Sığdır"
    meta = reg.get_meta(Undo)
    assert meta.default_shortcut == "Ctrl+Z"


def test_followup_open_panel(app):
    from app.commands.impl import ImportS2K, OpenPanel
    ctrl = app.edit_controller
    res = ctrl.commands.execute(ImportS2K(path=""))
    assert res.handled
    assert isinstance(res.followup, OpenPanel)
    assert res.followup.name == "s2k_panel"


def test_command_manager_listener(app):
    from app.commands.impl import AddNode
    received = []
    app.edit_controller.commands.add_listener(lambda r: received.append(r))
    app.edit_controller.commands.execute(AddNode(x=1))
    assert len(received) == 1
    assert received[0].geometry_dirty


def test_command_manager_max_history(app):
    from app.commands.base import CommandManager, Command, CommandResult
    class Noop(Command):
        def execute(self): return CommandResult()
        def undo(self): pass
    mgr = CommandManager(max_history=3)
    for _ in range(5):
        mgr.execute(Noop())
    assert len(mgr._undo) == 3


def test_replicate_selected(app):
    from app.commands.impl import AddNode, SelectElements, ReplicateSelected
    ctrl = app.edit_controller
    n = AddNode(x=0, y=0, z=0)
    ctrl.commands.execute(n)
    app.engine.sel_mgr.select(n._created)
    res = ctrl.commands.execute(ReplicateSelected(dx=10, dy=0, dz=0, count=2))
    assert res.handled
    assert len(app.current_project.math_model.nodes) == 3


def test_propagate_geometry(app):
    from app.commands.impl import AddNode, PropagateGeometryChange
    ctrl = app.edit_controller
    n = AddNode()
    ctrl.commands.execute(n)
    res = ctrl.commands.execute(PropagateGeometryChange(node_uids=[n._created.unique_id]))
    assert res.handled


def test_refresh_geometry(app):
    from app.commands.impl import AddNode, RefreshGeometry
    ctrl = app.edit_controller
    n = AddNode()
    ctrl.commands.execute(n)
    res = ctrl.commands.execute(RefreshGeometry())
    assert res.handled
    assert res.geometry_dirty


def test_start_draw_invalid_mode(app):
    from app.commands.impl import StartDrawTool
    ctrl = app.edit_controller
    res = ctrl.commands.execute(StartDrawTool(mode="bogus"))
    assert res.handled
    assert res.level == "warn"


def test_start_draw_valid_mode(app):
    from app.commands.impl import StartDrawTool
    ctrl = app.edit_controller
    res = ctrl.commands.execute(StartDrawTool(mode="line"))
    assert res.handled
    app.engine.draw_mgr.start.assert_called_once_with(mode="line")


def test_redo_after_new_command_clears(app):
    from app.commands.impl import AddNode, DeleteElements
    ctrl = app.edit_controller
    n1 = AddNode()
    ctrl.commands.execute(n1)
    ctrl.commands.undo()
    assert ctrl.commands.can_redo
    ctrl.commands.execute(AddNode())
    assert not ctrl.commands.can_redo