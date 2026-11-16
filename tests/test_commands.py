# tests/test_commands.py
from __future__ import annotations

import pytest

from app.commands.registry import CommandRegistry, build_registry
from app.commands.result import CommandResult
from core.commands import project_commands as PC
from domain.definition import Section
from domain.element import Frame, Node
from domain.math_model import MathModel
from domain.project import Project


# ---------------------------------------------------------------------------
# FAKE ALT YAPI
# ---------------------------------------------------------------------------

class FakeEngine:
    def __init__(self):
        self.show: dict[str, bool] = {"scene": True, "grid": True, "polygon": True,
                                       "lines": True, "labels": True, "interaction": True,
                                       "loads": True, "zones": True,
                                       "global_axis": True, "local_axes": True}
        self.math_model: MathModel | None = None
        self.scene = None
        self.cam = None
        self.renderer = None
        self.grid = None
        self.sel_mgr = None
        self.fit_view_calls = 0
        self.zoom_extents_calls = 0
        self.update_geo_calls = 0
        self.plane_draw_mgr = _FakePlaneDrawMgr()

    def fit_view(self):
        self.fit_view_calls += 1

    def zoom_extents(self):
        self.zoom_extents_calls += 1

    def update_geo(self, project):
        self.update_geo_calls += 1


class _FakePlaneDrawMgr:
    def __init__(self):
        self.is_active = False
        self.cancel_calls = 0

    def cancel(self):
        self.cancel_calls += 1
        self.is_active = False


class FakeSelectionManager:
    def __init__(self):
        self._selected: list = []
        self.clear_calls = 0

    def clear(self):
        self._selected.clear()
        self.clear_calls += 1

    def get_selected(self):
        return list(self._selected)

    def is_selected(self, el):
        return el in self._selected

    def select(self, el, additive=False):
        if not additive:
            self._selected = [el]
        elif el not in self._selected:
            self._selected.append(el)

    def select_multiple(self, elements, mode):
        # SelectionMode.REPLACE varsayımı
        self._selected = list(elements)


class FakeUIHost:
    def __init__(self):
        self.refresh_open_panels_calls = 0
        self.on_project_changed_calls = 0
        self.on_selection_changed_calls = 0
        self.on_wind_analysis_done_calls: list[str] = []
        self.on_unit_changed_calls = 0

    def refresh_open_panels(self):
        self.refresh_open_panels_calls += 1

    def on_project_changed(self):
        self.on_project_changed_calls += 1

    def on_selection_changed(self, selected):
        self.on_selection_changed_calls += 1

    def on_wind_analysis_done(self, key):
        self.on_wind_analysis_done_calls.append(key)

    def on_unit_changed(self):
        self.on_unit_changed_calls += 1


class FakeApp:
    """CadApp'in _drain_commands ve handler'lar için gereken yüzeyi."""

    def __init__(self):
        self.current_project = _fresh_project()
        self.engine = FakeEngine()
        self.engine.math_model = self.current_project.math_model
        self.engine.sel_mgr = FakeSelectionManager()
        self._ui_host = FakeUIHost()
        self.command_queue = _FakeCommandQueue()
        self._show_only_ids: set[int] | None = None
        self._hidden_ids: set[int] | None = None
        self._command_registry = build_registry()
        self.update_geo_invocations = 0

        # Handler'ların çağıracağı metotlar
        self.set_project_calls: list[Project] = []
        self.set_unit_system_calls: list = []
        self.set_loads_visible_calls: list[bool] = []
        self.toggle_2d_calls = 0
        self.show_entire_model_calls = 0

    # --- CadApp API taklidi ---
    def set_project(self, project):
        self.set_project_calls.append(project)
        self.current_project = project
        self.engine.math_model = project.math_model

    def set_unit_system(self, unit):
        self.set_unit_system_calls.append(unit)
        self.current_project.unit_system = unit

    def set_loads_visible(self, enabled):
        self.set_loads_visible_calls.append(bool(enabled))

    def toggle_2d(self):
        self.toggle_2d_calls += 1

    def show_entire_model(self):
        self.show_entire_model_calls += 1

    # --- _drain_commands BİREBİR kopyası (CadApp ile aynı mantık) ---
    def drain_commands(self):
        cmds = self.command_queue.drain()
        if not cmds:
            return

        geometry_dirty = False
        project_dirty = False

        for cmd in cmds:
            result = self._command_registry.dispatch(self, cmd)
            if not result.handled:
                continue
            geometry_dirty = geometry_dirty or result.geometry_dirty
            project_dirty = project_dirty or result.project_dirty

        if geometry_dirty and self.engine and self.current_project:
            self.engine.update_geo(self.current_project)
            self.update_geo_invocations += 1

        if project_dirty and self._ui_host is not None:
            self._ui_host.refresh_open_panels()


class _FakeCommandQueue:
    def __init__(self):
        self._items: list = []

    def put(self, cmd):
        self._items.append(cmd)

    def drain(self):
        items, self._items = self._items, []
        return items


def _fresh_project() -> Project:
    project = Project()
    project.math_model = MathModel()
    return project


# ---------------------------------------------------------------------------
# FIXTURES
# ---------------------------------------------------------------------------

@pytest.fixture
def app() -> FakeApp:
    return FakeApp()


@pytest.fixture
def registry() -> CommandRegistry:
    return build_registry()


def _dispatch(app, registry, cmd) -> CommandResult:
    return registry.dispatch(app, cmd)


# ---------------------------------------------------------------------------
# 1) CommandResult SÖZLEŞMESİ
# ---------------------------------------------------------------------------

class TestCommandResultContract:
    def test_default_values(self):
        r = CommandResult()
        assert r.geometry_dirty is False
        assert r.project_dirty is False
        assert r.handled is True

    def test_frozen(self):
        r = CommandResult(geometry_dirty=True)
        with pytest.raises(Exception):
            r.geometry_dirty = False


# ---------------------------------------------------------------------------
# 2) DEFINITIONS
# ---------------------------------------------------------------------------

class TestDefinitions:
    def test_add_section(self, app, registry):
        section = Section(name="S1")
        result = _dispatch(app, registry, PC.AddDefinition("sections", "S1", section))
        assert result.handled
        assert result.project_dirty
        assert not result.geometry_dirty
        assert app.current_project.sections["S1"] is section

    def test_add_unknown_container(self, app, registry):
        result = _dispatch(app, registry, PC.AddDefinition("nonexistent", "X", object()))
        assert not result.handled
        assert not result.project_dirty

    def test_update_section(self, app, registry):
        section = Section(name="S1")
        app.current_project.sections["S1"] = section
        result = _dispatch(app, registry, PC.UpdateDefinition("sections", "S1", {"name": "S1-updated"}))
        assert result.handled
        assert result.project_dirty
        assert section.name == "S1-updated"

    def test_update_renames_key(self, app, registry):
        section = Section(name="S1")
        app.current_project.sections["S1"] = section
        _dispatch(app, registry, PC.UpdateDefinition("sections", "S1",
                                                    {"name": "S2"}, new_name="S2"))
        assert "S1" not in app.current_project.sections
        assert "S2" in app.current_project.sections

    def test_update_unknown(self, app, registry):
        result = _dispatch(app, registry, PC.UpdateDefinition("sections", "NOPE", {"h": 1.0}))
        assert not result.handled

    def test_remove(self, app, registry):
        app.current_project.sections["S1"] = Section(name="S1")
        result = _dispatch(app, registry, PC.RemoveDefinition("sections", "S1"))
        assert result.handled
        assert "S1" not in app.current_project.sections

    def test_remove_unknown_no_error(self, app, registry):
        result = _dispatch(app, registry, PC.RemoveDefinition("sections", "NOPE"))
        assert result.handled

    def test_rename(self, app, registry):
        app.current_project.sections["S1"] = Section(name="S1")
        result = _dispatch(app, registry, PC.RenameDefinition("sections", "S1", "S2"))
        assert result.handled
        assert "S2" in app.current_project.sections
        assert "S1" not in app.current_project.sections


# ---------------------------------------------------------------------------
# 3) ELEMENTS
# ---------------------------------------------------------------------------

class TestElements:
    def test_add_node(self, app, registry):
        cmd = PC.AddNode(0.0, 1.0, 2.0, label="N1", restraint=None)
        result = _dispatch(app, registry, cmd)
        assert result.handled
        assert result.geometry_dirty
        model = app.current_project.math_model
        assert len(model.nodes) == 1
        node = list(model.nodes.values())[0]
        assert (node.x, node.y, node.z) == (0.0, 1.0, 2.0)

    def test_add_frame(self, app, registry):
        section = Section(name="S1")
        app.current_project.sections["S1"] = section

        n1 = Node(0.0, 0.0, 0.0, label="N1")
        n2 = Node(1.0, 0.0, 0.0, label="N2")
        model = app.current_project.math_model
        model.add_node(n1)
        model.add_node(n2)

        cmd = PC.AddFrame(n1.unique_id, n2.unique_id,
                        section_name="S1", rotation_deg=15.0, label="F1")
        result = _dispatch(app, registry, cmd)

        assert result.handled
        assert result.geometry_dirty
        assert not result.project_dirty
        assert len(model.frames) == 1

        frame = list(model.frames.values())[0]
        assert frame.node_i is n1
        assert frame.node_j is n2
        assert frame.section is section
        assert frame.rotation_deg == 15.0
        assert frame.label == "F1"
        assert frame.element_type == "Frame"


    def test_add_frame_unknown_section(self, app, registry):
        n1 = Node(0.0, 0.0, 0.0, label="N1")
        n2 = Node(1.0, 0.0, 0.0, label="N2")
        model = app.current_project.math_model
        model.add_node(n1)
        model.add_node(n2)

        cmd = PC.AddFrame(n1.unique_id, n2.unique_id,
                        section_name="NOPE", rotation_deg=0.0, label="F1")
        result = _dispatch(app, registry, cmd)

        assert not result.handled
        assert len(model.frames) == 0


    def test_add_frame_missing_node(self, app, registry):
        cmd = PC.AddFrame(999, 1000, section_name="S1", rotation_deg=0.0, label="F1")
        result = _dispatch(app, registry, cmd)
        assert not result.handled

    def test_update_element_fields(self, app, registry):
        node = Node(0.0, 0.0, 0.0, label="N1")
        app.current_project.math_model.add_node(node)
        cmd = PC.UpdateElementFields(node.unique_id, {"label": "N1-new"})
        result = _dispatch(app, registry, cmd)
        assert result.handled
        assert result.geometry_dirty
        assert node.label == "N1-new"

    def test_update_unknown_element(self, app, registry):
        cmd = PC.UpdateElementFields(999, {"label": "X"})
        result = _dispatch(app, registry, cmd)
        assert not result.handled

    def test_delete_elements(self, app, registry):
        node = Node(0.0, 0.0, 0.0, label="N1")
        app.current_project.math_model.add_node(node)
        cmd = PC.DeleteElements([node.unique_id])
        result = _dispatch(app, registry, cmd)
        assert result.handled
        assert result.geometry_dirty
        assert len(app.current_project.math_model.nodes) == 0


# ---------------------------------------------------------------------------
# 4) PROJECT
# ---------------------------------------------------------------------------

class TestProject:
    def test_replace_project(self, app, registry):
        new_project = _fresh_project()
        result = _dispatch(app, registry, PC.ReplaceProject(new_project))
        assert result.handled
        assert app.set_project_calls == [new_project]

    def test_set_unit_system(self, app, registry):
        from core.units import UnitSystem
        result = _dispatch(app, registry, PC.SetUnitSystem(UnitSystem.KN_M))
        assert result.handled
        assert app.set_unit_system_calls == [UnitSystem.KN_M]


# ---------------------------------------------------------------------------
# 5) VISIBILITY
# ---------------------------------------------------------------------------

class TestVisibility:
    def test_show_only(self, app, registry):
        result = _dispatch(app, registry, PC.ShowOnly([1, 2, 3]))
        assert result.handled
        assert result.geometry_dirty
        assert app._show_only_ids == {1, 2, 3}
        assert app.engine.math_model._render_filter == {1, 2, 3}

    def test_show_only_empty_clears(self, app, registry):
        app._show_only_ids = {1, 2}
        _dispatch(app, registry, PC.ShowOnly([]))
        assert app._show_only_ids is None
        assert app.engine.math_model._render_filter is None

    def test_hide_elements(self, app, registry):
        node = Node(0.0, 0.0, 0.0, label="N1")
        app.current_project.math_model.add_node(node)
        result = _dispatch(app, registry, PC.HideElements([node.unique_id]))
        assert result.handled
        assert result.geometry_dirty
        assert app._hidden_ids == {node.unique_id}
        assert getattr(node, "is_visible", getattr(node, "visible", True)) is False

    def test_show_entire_model(self, app, registry):
        result = _dispatch(app, registry, PC.ShowEntireModel())
        assert result.handled
        assert app.show_entire_model_calls == 1


# ---------------------------------------------------------------------------
# 6) CAMERA
# ---------------------------------------------------------------------------

class TestCamera:
    def test_fit_view(self, app, registry):
        result = _dispatch(app, registry, PC.FitView())
        assert result.handled
        assert app.engine.fit_view_calls == 1

    def test_zoom_extents(self, app, registry):
        result = _dispatch(app, registry, PC.ZoomExtents())
        assert result.handled
        assert app.engine.zoom_extents_calls == 1

    def test_set_camera_preset(self, app, registry):
        class _Cam:
            def __init__(self):
                self.presets: list[str] = []

            def set_view_preset(self, preset):
                self.presets.append(preset)

        cam = _Cam()
        app.engine.cam = cam
        result = _dispatch(app, registry, PC.SetCameraPreset("top"))
        assert result.handled
        assert cam.presets == ["top"]


# ---------------------------------------------------------------------------
# 7) ENGINE FLAGS
# ---------------------------------------------------------------------------

class TestEngineFlags:
    def test_toggle_2d(self, app, registry):
        result = _dispatch(app, registry, PC.Toggle2D())
        assert result.handled
        assert app.toggle_2d_calls == 1

    def test_toggle_loads(self, app, registry):
        result = _dispatch(app, registry, PC.ToggleLoadsVisible(True))
        assert result.handled
        assert app.set_loads_visible_calls == [True]

    def test_toggle_local_axes(self, app, registry):
        assert app.engine.show["local_axes"] is True
        _dispatch(app, registry, PC.ToggleLocalAxes())
        assert app.engine.show["local_axes"] is True  # scene üzerinden okunur

    def test_render_flag(self, app, registry):
        result = _dispatch(app, registry, PC.ToggleRenderFlag("grid", False))
        assert result.handled
        assert app.engine.show["grid"] is False

    def test_set_render_mode(self, app, registry):
        class _Renderer:
            def __init__(self):
                self.modes: list[str] = []

            def set_render_mode(self, mode):
                self.modes.append(mode)

        renderer = _Renderer()
        app.engine.renderer = renderer
        result = _dispatch(app, registry, PC.SetRenderMode("simple"))
        assert result.handled
        assert renderer.modes == ["simple"]


# ---------------------------------------------------------------------------
# 8) SELECTION
# ---------------------------------------------------------------------------

class TestSelection:
    def test_clear_selection(self, app, registry):
        node = Node(0.0, 0.0, 0.0, label="N1")
        app.engine.sel_mgr._selected = [node]
        result = _dispatch(app, registry, PC.ClearSelection())
        assert result.handled
        assert app.engine.sel_mgr.clear_calls == 1

    def test_select_elements_replace(self, app, registry):
        n1 = Node(0.0, 0.0, 0.0, label="N1")
        n2 = Node(1.0, 0.0, 0.0, label="N2")
        model = app.current_project.math_model
        model.add_node(n1)
        model.add_node(n2)

        result = _dispatch(app, registry, PC.SelectElements(
            [n1.unique_id, n2.unique_id], mode="replace"))
        assert result.handled
        assert set(e.unique_id for e in app.engine.sel_mgr.get_selected()) == {n1.unique_id, n2.unique_id}

    def test_select_elements_add_mode(self, app, registry):
        n1 = Node(0.0, 0.0, 0.0, label="N1")
        n2 = Node(1.0, 0.0, 0.0, label="N2")
        model = app.current_project.math_model
        model.add_node(n1)
        model.add_node(n2)
        app.engine.sel_mgr.select(n1)

        _dispatch(app, registry, PC.SelectElements([n2.unique_id], mode="add"))
        selected = app.engine.sel_mgr.get_selected()
        assert len(selected) == 2

    def test_select_elements_missing_engine(self, app, registry):
        app.engine.sel_mgr = None
        result = _dispatch(app, registry, PC.SelectElements([1, 2], mode="replace"))
        assert not result.handled


# ---------------------------------------------------------------------------
# 9) SIGNAL
# ---------------------------------------------------------------------------

class TestSignal:
    def test_refresh_geometry(self, app, registry):
        result = _dispatch(app, registry, PC.RefreshGeometry())
        assert result.handled
        assert result.geometry_dirty


# ---------------------------------------------------------------------------
# 10) DISPATCH — BİLİNMEYEN KOMUT
# ---------------------------------------------------------------------------

class TestUnknownCommand:
    def test_unknown(self, app, registry):
        class _Mystery:
            pass

        result = _dispatch(app, registry, _Mystery())
        assert not result.handled
        assert not result.geometry_dirty
        assert not result.project_dirty


# ---------------------------------------------------------------------------
# 11) _drain_commands AKIŞI
# ---------------------------------------------------------------------------

class TestDrainCommands:
    def test_empty_queue_no_side_effects(self, app):
        app.drain_commands()
        assert app.engine.update_geo_calls == 0
        assert app._ui_host.refresh_open_panels_calls == 0

    def test_geometry_dirty_calls_update_geo_once(self, app):
        app.command_queue.put(PC.AddNode(0.0, 0.0, 0.0, label="N1", restraint=None))
        app.command_queue.put(PC.AddNode(1.0, 0.0, 0.0, label="N2", restraint=None))
        app.drain_commands()
        assert app.engine.update_geo_calls == 1
        assert len(app.current_project.math_model.nodes) == 2

    def test_project_dirty_calls_refresh_panels(self, app):
        app.command_queue.put(PC.AddDefinition("sections", "S1", Section(name="S1")))
        app.drain_commands()
        assert app.engine.update_geo_calls == 0
        assert app._ui_host.refresh_open_panels_calls == 1

    def test_geometry_and_project_dirty(self, app):
        app.command_queue.put(PC.AddDefinition("sections", "S1", Section(name="S1")))
        app.command_queue.put(PC.AddNode(0.0, 0.0, 0.0, label="N1", restraint=None))
        app.drain_commands()
        assert app.engine.update_geo_calls == 1
        assert app._ui_host.refresh_open_panels_calls == 1

    def test_handled_false_skipped(self, app):
        class _Mystery:
            pass
        app.command_queue.put(_Mystery())
        app.command_queue.put(PC.AddNode(0.0, 0.0, 0.0, label="N1", restraint=None))
        app.drain_commands()
        assert app.engine.update_geo_calls == 1
        assert len(app.current_project.math_model.nodes) == 1

    def test_mixed_batch_aggregation(self, app):
        """Tek batch'te: 2 def + 1 element + 1 kamera → 1 update_geo, 1 refresh."""
        app.command_queue.put(PC.AddDefinition("sections", "S1", Section(name="S1")))
        app.command_queue.put(PC.AddDefinition("sections", "S2", Section(name="S2")))
        app.command_queue.put(PC.AddNode(0.0, 0.0, 0.0, label="N1", restraint=None))
        app.command_queue.put(PC.FitView())
        app.drain_commands()
        assert app.engine.update_geo_calls == 1
        assert app._ui_host.refresh_open_panels_calls == 1
        assert app.engine.fit_view_calls == 1
        assert len(app.current_project.math_model.nodes) == 1
        assert set(app.current_project.sections.keys()) == {"S1", "S2"}


# ---------------------------------------------------------------------------
# 12) REGISTRY KAPSAMI — her komut tipi kayıtlı mı
# ---------------------------------------------------------------------------

class TestRegistryCoverage:
    def test_all_pc_commands_have_handler(self, registry):
        """core.commands.project_commands içindeki her Command alt sınıfı
        registry'de kayıtlı olmalı. Yeni komut eklenirse bu test patlar."""
        import inspect
        from core.commands import base

        expected: set[type] = set()
        for name, obj in inspect.getmembers(PC, inspect.isclass):
            if obj is base.Command:
                continue
            if issubclass(obj, base.Command):
                expected.add(obj)

        registered = set(registry._handlers.keys())
        missing = expected - registered
        assert not missing, f"Handler eksik: {missing}"