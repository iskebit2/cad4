from types import SimpleNamespace

import glm
import numpy as np

from core.plane_draw_manager import PlaneDrawManager
from domain.element import Node


def _manager():
    camera = SimpleNamespace(
        target=glm.vec3(0, 0, 0),
        position=glm.vec3(0, 0, 10),
        get_view_matrix=lambda: glm.mat4(1),
        get_projection_matrix=lambda: glm.mat4(1),
    )
    engine = SimpleNamespace(cam=camera, w=100, h=100)
    manager = PlaneDrawManager.__new__(PlaneDrawManager)
    manager.engine = engine
    manager.p0 = Node(0, 0, 0)
    manager.p1 = None
    manager.p2 = None
    manager.hover_node = None
    manager._mouse_pos = (75, 25)
    manager.stage = manager.STAGE_P1
    manager._line_vao = 1
    manager._line_vbo = 1
    manager._tri_vao = 1
    manager._tri_vbo = 1
    return manager


def test_p0_to_p1_preview_tracks_cursor_and_draws_arrow():
    manager = _manager()
    captured = []
    manager._upload_and_draw = lambda *args: captured.append(args)

    point = manager._preview_point()
    manager._draw_lines(None, 0, None)

    assert np.allclose(point, (0.5, 0.5, 0.0))
    vertices = captured[0][2].reshape(-1, 3)
    assert captured[0][3] == 0x0001
    assert captured[0][4] == 6
    assert np.allclose(vertices[:2], ((0, 0, 0), point))
    assert np.allclose(vertices[2], point)
    assert np.allclose(vertices[4], point)
    assert not np.allclose(vertices[2], vertices[3])
    assert not np.allclose(vertices[4], vertices[5])


def test_p1_to_p2_preview_builds_perpendicular_rectangle():
    manager = _manager()
    manager.p1 = Node(2, 0, 0)
    point = np.array((2.0, 1.0, 0.0))

    preview_v = manager._preview_v_perp(point)
    captured = []
    manager._upload_and_draw = lambda *args: captured.append(args)
    manager._draw_plane_quad(None, 0, preview_v=preview_v)

    quad_vertices = captured[0][2].reshape(-1, 3)
    assert np.allclose(preview_v, (0, 1, 0))
    assert np.allclose(
        quad_vertices,
        ((0, 0, 0), (2, 0, 0), (2, 1, 0),
         (0, 0, 0), (2, 1, 0), (0, 1, 0)),
    )


def test_hovered_node_is_used_as_preview_endpoint():
    manager = _manager()
    manager.hover_node = Node(3, 4, 5)

    assert np.allclose(manager._preview_point(), (3, 4, 5))
