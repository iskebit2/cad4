from types import SimpleNamespace

import numpy as np
import pytest

from core.units import UnitSystem, convert_project_units
from domain.definition import GridPlaneDef
from domain.element import Area, Frame, Node, Polygon
from domain.plane import Plane
from domain.project import Project
from data.serializer import _decode, _encode
from tools.gridsystem import GridSystem


@pytest.mark.parametrize(
    ("orientation", "p1", "p2", "normal"),
    [
        ("XY", (1.0, 2.0, 3.0), (4.0, 6.0, 3.0), (0.0, 0.0, 1.0)),
        ("XZ", (1.0, 2.0, 3.0), (4.0, 2.0, 6.0), (0.0, 1.0, 0.0)),
        ("YZ", (1.0, 2.0, 3.0), (1.0, 6.0, 6.0), (1.0, 0.0, 0.0)),
    ],
)
def test_two_point_plane_contains_compatible_points(orientation, p1, p2, normal):
    plane = Plane.from_2_points(p1, p2, orientation)

    assert np.isclose(plane.distance(p1), 0.0)
    assert np.isclose(plane.distance(p2), 0.0)
    assert np.allclose(plane.normal, normal)


def test_two_point_plane_rejects_incompatible_orientation_and_invalid_input():
    with pytest.raises(ValueError, match="not compatible"):
        Plane.from_2_points((0, 0, 0), (1, 0, 1), "XY")
    with pytest.raises(ValueError, match="distinct"):
        Plane.from_2_points((1, 2, 3), (1, 2, 3), "XY")
    with pytest.raises(ValueError, match="YZ"):
        Plane.from_2_points((0, 0, 0), (1, 1, 0), "YZ")


@pytest.mark.parametrize(
    ("grid_plane", "expected_origin", "expected_bounds"),
    [
        ("XY", (10.0, 20.0, 33.0), (1.0, 8.0, 2.0, 10.0)),
        ("XZ", (10.0, 22.0, 30.0), (1.0, 8.0, 3.0, 6.0)),
        ("YZ", (11.0, 20.0, 30.0), (2.0, 10.0, 3.0, 6.0)),
    ],
)
def test_grid_plane_reuses_existing_origin_axes_and_extents(
    grid_plane, expected_origin, expected_bounds
):
    grid = SimpleNamespace(
        origin_x=10.0,
        origin_y=20.0,
        origin_z=30.0,
        x_coords=[1.0, 4.0, 8.0],
        y_coords=[2.0, 5.0, 10.0],
        z_coords=[3.0, 4.0, 6.0],
    )

    plane = Plane.from_grid(grid, grid_plane)

    assert np.allclose(plane.origin, expected_origin)
    assert plane.boundary == expected_bounds


@pytest.mark.parametrize(
    ("orientation", "coordinates", "expected_axis", "expected_offsets"),
    [
        ("XY", "z_coords", "z", [3.0, 4.0, 6.0]),
        ("XZ", "y_coords", "y", [2.0, 5.0, 10.0]),
        ("YZ", "x_coords", "x", [1.0, 4.0, 8.0]),
    ],
)
def test_grid_levels_create_one_plane_at_each_project_coordinate(
    orientation, coordinates, expected_axis, expected_offsets
):
    grid = SimpleNamespace(
        origin_x=10.0,
        origin_y=20.0,
        origin_z=30.0,
        x_coords=[1.0, 4.0, 8.0],
        y_coords=[2.0, 5.0, 10.0],
        z_coords=[3.0, 4.0, 6.0],
    )

    assert Plane.grid_levels(grid, orientation) == expected_offsets
    for offset in expected_offsets:
        plane = Plane.from_grid(
            grid, orientation, grid_coordinate=offset,
            depth_minus=500.0, depth_plus=500.0,
        )
        axis_index = {"x": 0, "y": 1, "z": 2}[expected_axis]
        expected_origin = [10.0, 20.0, 30.0]
        expected_origin[axis_index] += offset
        assert np.allclose(plane.origin, expected_origin)
        assert plane.depth == (500.0, 500.0)


@pytest.mark.parametrize(
    ("unit_system", "expected_depth"),
    [
        (UnitSystem.N_MM, 500.0),
        (UnitSystem.KGF_CM, 50.0),
        (UnitSystem.N_M, 0.5),
    ],
)
def test_default_grid_plane_depth_is_500_mm_in_project_units(
    unit_system, expected_depth
):
    assert Plane.default_grid_plane_depth(unit_system) == pytest.approx(expected_depth)


def test_grid_user_plane_reuses_definition_bounds():
    user_plane = GridPlaneDef(
        name="Inclined",
        origin=(3.0, 4.0, 5.0),
        normal=(0.0, 1.0, 1.0),
        u_axis=(1.0, 0.0, 0.0),
        spacing_u=2.0,
        spacing_v=3.0,
        count_u=4,
        count_v=5,
    )
    grid = SimpleNamespace(get_user_plane=lambda name: user_plane if name == "Inclined" else None)

    plane = Plane.from_grid(grid, "user::Inclined")

    assert np.allclose(plane.origin, user_plane.origin)
    assert plane.boundary == (-8.0, 8.0, -15.0, 15.0)


def test_project_grid_user_plane_definitions_survive_serialization(tmp_path):
    project = Project()
    definition = GridPlaneDef(
        name="Roof",
        origin=(2.0, 3.0, 4.0),
        normal=(0.0, 0.0, 1.0),
        u_axis=(0.0, 1.0, 0.0),
        spacing_u=250.0,
        spacing_v=300.0,
        count_u=4,
        count_v=5,
    )
    project.grid.user_planes.append(definition)

    decoded = _decode(_encode(project.grid))

    assert len(decoded.user_planes) == 1
    assert isinstance(decoded.user_planes[0], GridPlaneDef)
    assert decoded.user_planes[0].name == "Roof"
    assert Plane.from_grid(
        SimpleNamespace(get_user_plane=lambda name: decoded.user_planes[0] if name == "Roof" else None),
        "Roof",
    ).boundary == (-1000.0, 1000.0, -1500.0, 1500.0)

    filepath = tmp_path / "custom-grid.cd4"
    project.save(str(filepath))
    restored = Project.load(str(filepath))
    assert restored.grid.user_planes[0].name == "Roof"


def test_project_user_grid_plane_lengths_follow_project_unit_changes():
    project = Project()
    project.grid.user_planes.append(
        GridPlaneDef(
            name="Roof",
            origin=(1000.0, 2000.0, 3000.0),
            spacing_u=500.0,
            spacing_v=250.0,
        )
    )

    convert_project_units(project, UnitSystem.KN_M)

    definition = project.grid.user_planes[0]
    assert definition.origin == (1.0, 2.0, 3.0)
    assert definition.spacing_u == 0.5
    assert definition.spacing_v == 0.25


def test_grid_system_replaces_user_grids_from_project_definitions(monkeypatch):
    grid = GridSystem(None)
    rebuilt = []
    monkeypatch.setattr(grid, "rebuild_all", lambda: rebuilt.append(True))
    project_plane = GridPlaneDef(name="Roof")

    grid.set_user_planes([project_plane])

    assert grid.user_planes == [project_plane]
    assert grid.get_user_plane("Roof") is project_plane
    assert rebuilt == [True]

    grid.set_user_planes([])
    assert grid.user_planes == []
    assert grid.get_user_plane("Roof") is None


def test_selected_frame_uses_local_13_and_local_12_planes():
    frame = Frame(
        Node(0.0, 0.0, 0.0),
        Node(10.0, 0.0, 0.0),
        section=None,
    )
    axes = frame.get_local_axes()

    plane_13 = Plane.from_element(frame)
    plane_12 = Plane.from_element(frame, frame_local_12=True)

    assert np.allclose(plane_13.x_axis, tuple(axes[0]))
    assert np.allclose(plane_13.y_axis, tuple(axes[2]))
    assert np.allclose(plane_12.x_axis, tuple(axes[0]))
    assert np.allclose(plane_12.y_axis, tuple(axes[1]))
    assert np.allclose(plane_13.origin, frame.node_i.coords)
    assert np.allclose(plane_12.origin, frame.node_i.coords)


@pytest.mark.parametrize("element_type", [Area, Polygon])
def test_selected_surface_uses_planar_geometry_and_rejects_nonplanar(element_type):
    nodes = [
        Node(0.0, 0.0, 0.0),
        Node(2.0, 0.0, 0.0),
        Node(2.0, 2.0, 0.0),
        Node(0.0, 2.0, 0.0),
    ]
    element = (
        Area(nodes, thickness=1.0)
        if element_type is Area
        else Polygon(nodes)
    )

    plane = Plane.from_element(element)

    assert all(abs(plane.distance(node.coords)) < 1e-12 for node in nodes)
    nodes[-1].z = 1.0
    with pytest.raises(ValueError, match="düzlemsel değil"):
        Plane.from_element(element)


def test_selected_invalid_element_is_rejected():
    with pytest.raises(TypeError, match="Frame, Area, or Polygon"):
        Plane.from_element(Node(0.0, 0.0, 0.0))

    zero_length_frame = Frame(
        Node(1.0, 2.0, 3.0),
        Node(1.0, 2.0, 3.0),
        section=None,
    )
    with pytest.raises(ValueError, match="length"):
        Plane.from_element(zero_length_frame)
