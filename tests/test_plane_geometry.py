import numpy as np
import pytest

from domain.plane import Plane


def test_world_local_transform_is_orthonormal_and_reversible():
    plane = Plane.from_3_points(
        (1.0, 2.0, 3.0),
        (3.0, 2.0, 4.0),
        (0.0, 5.0, 4.0),
    )
    local = np.array((12.5, -7.25, 4.0))

    world = plane.local_to_world(local)

    assert np.allclose(plane.world_to_local(world), local)
    assert np.isclose(np.linalg.norm(plane.x_axis), 1.0)
    assert np.isclose(np.linalg.norm(plane.y_axis), 1.0)
    assert np.isclose(np.dot(plane.x_axis, plane.y_axis), 0.0)
    assert np.isclose(np.dot(plane.x_axis, plane.normal), 0.0)
    assert np.isclose(np.dot(plane.y_axis, plane.normal), 0.0)


def test_project_and_contains_use_plane_coordinates_and_depth():
    plane = Plane(
        origin=(0.0, 0.0, 0.0),
        normal=(0.0, 0.0, 1.0),
        u=(1.0, 0.0, 0.0),
        v=(0.0, 1.0, 0.0),
        u_min=-1.0,
        u_max=1.0,
        v_min=-2.0,
        v_max=2.0,
        depth_minus=3.0,
        depth_plus=4.0,
    )

    assert np.allclose(plane.project((2.0, 3.0, 10.0)), (2.0, 3.0, 0.0))
    assert plane.boundary == (-1.0, 1.0, -2.0, 2.0)
    assert plane.depth == (3.0, 4.0)
    assert plane.contains((1.0, 2.0, 4.0))
    assert plane.contains((-1.0, -2.0, -3.0))
    assert not plane.contains((1.01, 0.0, 0.0))
    assert not plane.contains((0.0, 0.0, 4.01))
    assert not plane.contains((0.0, 0.0, -3.01))


def test_intersect_ray_returns_forward_hit_and_none_for_no_unique_forward_hit():
    plane = Plane.from_axis_offset("z", 0.0)

    hit = plane.intersect_ray((2.0, 3.0, 5.0), (0.0, 0.0, -2.0))

    assert np.allclose(hit, (2.0, 3.0, 0.0))
    assert plane.intersect_ray((0.0, 0.0, 1.0), (1.0, 0.0, 0.0)) is None
    assert plane.intersect_ray((0.0, 0.0, 1.0), (0.0, 0.0, 1.0)) is None


@pytest.mark.parametrize(
    ("origin", "normal", "u"),
    [
        ((0.0, 0.0), (0.0, 0.0, 1.0), None),
        ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), None),
        ((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 0.0, 2.0)),
    ],
)
def test_constructor_rejects_invalid_coordinate_frames(origin, normal, u):
    with pytest.raises(ValueError):
        Plane(origin=origin, normal=normal, u=u)


def test_ray_rejects_zero_direction():
    plane = Plane.from_axis_offset("z", 0.0)

    with pytest.raises(ValueError, match="direction"):
        plane.intersect_ray((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
