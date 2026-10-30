from types import SimpleNamespace

import glfw
import numpy as np

from core.units import UnitSystem
from data.enums import GridPlane
from domain.definition import GridPlaneDef
from domain.element import Frame, Node
from domain.project import Project
from ui.grid_panel import GridPanel
from ui.plane_manager_panel import (
    PlaneManagerPanel,
    SRC_2PT,
    SRC_ELEMENT,
    SRC_GRID,
)


def _panel(project, grid=None):
    renderer = SimpleNamespace(selected_plane=None)
    engine = SimpleNamespace(
        scene=project.scene,
        grid=grid,
        renderer=renderer,
    )
    panel = PlaneManagerPanel()
    panel.app = SimpleNamespace(current_project=project, engine=engine)
    return panel, renderer


def test_grid_source_preview_keeps_existing_grid_boundary():
    project = Project()
    project.grid.origin_x = 10.0
    project.grid.origin_y = 20.0
    project.grid.origin_z = 30.0
    project.grid.x_coords = [0.0, 20.0]
    project.grid.y_coords = [0.0, 30.0]
    project.grid.z_coords = [0.0, 40.0]
    project.scene.add_node(Node(-100.0, -200.0, -300.0))
    project.scene.add_node(Node(100.0, 200.0, 300.0))
    grid = SimpleNamespace(
        planes={GridPlane.XY: {"visible": True}},
        user_planes=[],
        origin_x=10.0,
        origin_y=20.0,
        origin_z=30.0,
        x_coords=[0.0, 20.0],
        y_coords=[0.0, 30.0],
        z_coords=[0.0, 40.0],
    )
    panel, renderer = _panel(project, grid)
    panel._new_source = SRC_GRID
    panel._grid_plane_name = "XY"

    panel._refresh_preview()

    assert panel._preview is not None
    assert np.allclose(panel._preview.origin, (10.0, 20.0, 30.0))
    assert panel._preview.boundary == (0.0, 20.0, 0.0, 30.0)
    assert renderer.selected_plane is panel._preview


def test_grid_source_lists_and_builds_every_engine_grid_user_plane(monkeypatch):
    user_plane = GridPlaneDef(
        name="Roof",
        origin=(10.0, 20.0, 30.0),
        normal=(0.0, 0.0, 1.0),
        u_axis=(0.0, 1.0, 0.0),
        spacing_u=250.0,
        spacing_v=300.0,
        count_u=4,
        count_v=5,
    )
    grid = SimpleNamespace(
        planes={GridPlane.XY: {"visible": True}},
        user_planes=[user_plane],
        origin_x=0.0,
        origin_y=0.0,
        origin_z=0.0,
        x_coords=[0.0, 1000.0],
        y_coords=[0.0, 1000.0],
        z_coords=[0.0, 1000.0],
        get_user_plane=lambda name: user_plane if name == "Roof" else None,
    )
    project = Project()
    project.grid.user_planes.append(user_plane)
    panel, _ = _panel(project, grid)
    panel._new_source = SRC_GRID
    panel._grid_plane_name = "user::Roof"
    shown = []

    class FakeImGui:
        @staticmethod
        def text(*_args):
            pass

        @staticmethod
        def same_line(*_args):
            pass

        @staticmethod
        def begin_combo(_label, preview):
            shown.append(preview)
            return True

        @staticmethod
        def selectable(label, _selected):
            shown.append(label)
            return False, False

        @staticmethod
        def set_item_default_focus():
            pass

        @staticmethod
        def end_combo():
            pass

    monkeypatch.setattr("ui.plane_manager_panel.imgui", FakeImGui)

    panel._draw_grid_source()
    plane = panel._build_from_grid()

    assert "Kullanıcı: Roof" in shown
    assert plane.name == "Plane_Grid_Roof"
    assert np.allclose(plane.origin, user_plane.origin)
    assert plane.boundary == (-1000.0, 1000.0, -1500.0, 1500.0)


def test_plane_manager_builds_selected_project_grid_level_with_project_depth():
    project = Project()
    project.unit_system = UnitSystem.N_M
    project.grid.origin_x = 10.0
    project.grid.origin_y = 20.0
    project.grid.origin_z = 30.0
    project.grid.x_coords = [0.0, 20.0]
    project.grid.y_coords = [0.0, 30.0, 60.0]
    project.grid.z_coords = [0.0, 40.0]
    panel, _ = _panel(project)
    panel._new_source = SRC_GRID
    panel._grid_plane_name = "grid::XZ::30.0"
    panel._pv_depth_minus = panel._pv_depth_plus = 0.5

    plane = panel._build_from_grid()

    assert plane is not None
    assert np.allclose(plane.origin, (10.0, 50.0, 30.0))
    assert plane.depth == (0.5, 0.5)


def test_grid_panel_creates_plane_from_project_grid_and_activates_it():
    project = Project()
    project.grid.origin_z = 100.0
    project.grid.x_coords = [0.0, 2000.0]
    project.grid.y_coords = [0.0, 3000.0]
    project.grid.z_coords = [0.0, 500.0, 1000.0]
    project.unit_system = UnitSystem.N_M
    panel = GridPanel()
    panel.app = SimpleNamespace(current_project=project)
    panel._grid_plane_orientation = "XY"
    panel._grid_plane_coordinate = 1000.0

    panel._create_project_grid_plane(activate=True)

    assert len(project.planes) == 1
    plane = next(iter(project.planes.values()))
    assert np.allclose(plane.origin, (0.0, 0.0, 1100.0))
    assert plane.boundary == (0.0, 2000.0, 0.0, 3000.0)
    assert plane.depth == (0.5, 0.5)
    assert project.plane_mgr.active_plane is plane


def test_two_point_source_validates_selected_orientation():
    project = Project()
    first = Node(0.0, 0.0, 0.0)
    second = Node(10.0, 0.0, 0.0)
    project.scene.add_node(first)
    project.scene.add_node(second)
    panel, _ = _panel(project)
    panel._new_source = SRC_2PT
    panel._picked_nodes = [first.unique_id, second.unique_id]

    panel._refresh_preview()

    assert panel._preview is not None
    assert np.allclose(panel._preview.normal, (0.0, 0.0, 1.0))

    panel._two_point_orientation = "YZ"
    panel._refresh_preview()

    assert panel._preview is None
    assert "not compatible" in panel._preview_error


def test_selected_frame_preview_toggles_local_plane_with_t_key():
    project = Project()
    first = Node(0.0, 0.0, 0.0)
    second = Node(10.0, 0.0, 0.0)
    project.scene.add_node(first)
    project.scene.add_node(second)
    frame = Frame(first, second, section=None)
    project.scene.add_frame(frame)
    frame.is_selected = True
    panel, renderer = _panel(project)
    panel.visible = True
    panel._form_open = True
    panel._new_source = SRC_ELEMENT
    panel._picked_element_id = frame.unique_id

    panel._refresh_preview()
    local_13 = panel._preview

    assert local_13 is not None
    assert panel.on_key_press(glfw.KEY_T)
    local_12 = panel._preview

    assert local_12 is not None
    assert not np.allclose(local_13.normal, local_12.normal)
    assert renderer.selected_plane is local_12

    panel.close()

    assert renderer.selected_plane is None
    assert panel._preview is None
