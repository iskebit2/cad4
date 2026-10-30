from types import SimpleNamespace

import numpy as np
from pyglm import glm

from core.camera import Camera
from core.gl_engine import Engine
from core.input_manager import InputManager
from domain.plane import Plane
from domain.project import Project


def _engine(plane=None, bounds=None):
    engine = Engine(800, 600)
    engine.cam = Camera(target=glm.vec3(0.0, 0.0, 0.0), distance=10.0)
    engine.cam.set_aspect(800, 600)
    engine.input = InputManager()
    engine.set_working_plane_provider(lambda: plane)
    center, size = bounds or (np.zeros(3), 200.0)
    engine.renderer = SimpleNamespace(
        get_bounds=lambda: (np.asarray(center, dtype=float), size)
    )
    return engine


def test_screen_to_world_keeps_global_xy_fallback_without_active_plane():
    engine = _engine()

    point = engine.screen_to_world(400, 300)

    assert point is not None
    assert np.allclose(np.array(point), (0.0, 0.0, 0.0), atol=1e-4)


def test_screen_coordinates_intersect_active_plane_and_store_local_uv():
    plane = Plane.from_axis_offset("x", 0.0)
    engine = _engine(plane)

    result = engine.screen_to_working_plane(400, 300)

    assert result is not None
    point, coords = result
    assert np.allclose(np.array(point), (0.0, 0.0, 0.0), atol=1e-4)
    assert np.allclose((coords.x, coords.y), (0.0, 0.0), atol=1e-4)

    engine.update_world_pos(400, 300)

    assert engine.input.mouse_plane_valid
    assert np.allclose(
        np.array(engine.input.mouse_plane_pos), (0.0, 0.0, 0.0), atol=1e-4
    )
    assert np.allclose(
        (engine.input.mouse_plane_coords.x, engine.input.mouse_plane_coords.y),
        (0.0, 0.0),
        atol=1e-4,
    )
    assert np.allclose(
        np.array(engine.input.mouse_world_pos), (0.0, 0.0, 0.0), atol=1e-4
    )


def test_screen_to_working_plane_returns_none_for_parallel_ray():
    plane = Plane.from_axis_offset("x", 0.0)
    engine = _engine(plane)
    engine.cam.pitch = 90.0
    engine.cam.yaw = 0.0
    engine.cam.up = glm.vec3(0.0, 1.0, 0.0)
    engine.cam._invalidate()

    assert engine.screen_to_working_plane(400, 300) is None


def test_working_plane_constraints_apply_grid_then_ortho():
    coords = Engine.constrain_working_plane_coordinates(
        (4.0, 7.0),
        grid_coordinates=([0.0, 5.0, 10.0], [0.0, 5.0, 10.0]),
        orthogonal_origin=(0.0, 0.0),
    )

    assert coords == (5.0, 0.0)


def test_screen_input_uses_configured_grid_and_ortho_constraints():
    plane = Plane.from_axis_offset("z", 0.0)
    engine = _engine(plane)
    engine.input.working_plane_grid_coordinates = ((100.0,), (100.0,))
    engine.input.working_plane_orthogonal_origin = (0.0, 0.0)

    hit = engine.screen_to_working_plane(400, 300)

    assert hit is not None
    _, coords = hit
    assert np.allclose((coords.x, coords.y), (100.0, 0.0))


def test_project_plane_activation_drives_engine_working_coordinates():
    project = Project()
    plane = Plane.from_axis_offset("z", 0.0, name="XY Working Plane")
    project.plane_mgr.add(plane)
    engine = _engine()
    engine.set_working_plane_provider(lambda: project.plane_mgr.active_plane)

    project.plane_mgr.activate(plane)
    assert engine.active_working_plane is plane
    assert engine.screen_to_working_plane(400, 300) is not None

    project.plane_mgr.deactivate()
    assert engine.active_working_plane is None
    assert engine.screen_to_working_plane(400, 300) is None
    assert engine.screen_to_world(400, 300) is not None


def test_focus_plane_fits_boundary_and_orients_camera_to_plane():
    plane = Plane.from_3_points(
        (10.0, 20.0, 30.0),
        (10.0, 40.0, 30.0),
        (10.0, 20.0, 40.0),
    )
    plane.u_min, plane.u_max = -100.0, 100.0
    plane.v_min, plane.v_max = -50.0, 50.0
    engine = _engine(plane)

    assert engine.focus_plane(plane)

    position = np.array(engine.cam.position, dtype=float)
    target = np.array(engine.cam.target, dtype=float)
    assert np.allclose(target, plane.to_3d((0.0, 0.0)))
    assert np.allclose(
        (position - target) / np.linalg.norm(position - target),
        plane.normal,
        atol=1e-8,
    )
    assert engine.cam.view_mode == "ORTHO"
    assert np.isclose(engine.cam.distance, 172.5)


def test_orbit_leaves_plane_view_using_world_up():
    camera = Camera()
    camera.look_at_plane(
        (0.0, 0.0, 0.0),
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, 0.0, 1.0),
        fit_radius=100.0,
    )

    camera.orbit(5.0, 3.0)

    assert camera.view_preset is None
    assert np.allclose(np.array(camera.up), (0.0, 0.0, 1.0))
