import numpy as np

from render import snapsquare


def _draw(renderer, monkeypatch, hover_node):
    captured = {"vertices": None, "color": None}
    monkeypatch.setattr(
        snapsquare, "glBufferData",
        lambda target, size, data, usage: captured.update(vertices=data.copy()),
    )
    monkeypatch.setattr(
        snapsquare, "glUniform4f",
        lambda location, r, g, b, a: captured.update(color=(r, g, b, a)),
    )
    for name in (
        "glDisable", "glEnable", "glBlendFunc", "glUseProgram",
        "glBindVertexArray", "glBindBuffer", "glVertexAttribPointer",
        "glEnableVertexAttribArray", "glDrawArrays",
    ):
        monkeypatch.setattr(snapsquare, name, lambda *args: None)

    renderer.draw_snap(400, 300, 800, 600, hover_node=hover_node)
    return captured


def test_node_hover_snap_square_is_larger_and_blue(monkeypatch):
    renderer = snapsquare.SnapSquareRenderer.__new__(
        snapsquare.SnapSquareRenderer
    )
    renderer.shader = 1
    renderer.u_color_loc = 0
    renderer.vao = 1
    renderer.vbo = 1
    renderer.size = 0.01
    renderer.color = (1.0, 0.9, 0.0, 1.0)
    renderer.node_hover_size = 0.016
    renderer.node_hover_color = (0.2, 0.55, 1.0, 1.0)

    normal = _draw(renderer, monkeypatch, hover_node=False)
    node = _draw(renderer, monkeypatch, hover_node=True)

    normal_extent = np.ptp(normal["vertices"].reshape(-1, 2)[:, 1])
    node_extent = np.ptp(node["vertices"].reshape(-1, 2)[:, 1])
    assert node_extent > normal_extent
    assert normal["color"] == renderer.color
    assert node["color"] == renderer.node_hover_color


def test_non_node_snap_square_keeps_normal_appearance(monkeypatch):
    renderer = snapsquare.SnapSquareRenderer.__new__(
        snapsquare.SnapSquareRenderer
    )
    renderer.shader = 1
    renderer.u_color_loc = 0
    renderer.vao = 1
    renderer.vbo = 1
    renderer.size = 0.01
    renderer.color = (1.0, 0.9, 0.0, 1.0)
    renderer.node_hover_size = 0.016
    renderer.node_hover_color = (0.2, 0.55, 1.0, 1.0)

    regular_hover = _draw(renderer, monkeypatch, hover_node=False)

    assert regular_hover["color"] == renderer.color
    vertices = regular_hover["vertices"].reshape(-1, 2)
    assert np.isclose(np.ptp(vertices[:, 1]), 2 * renderer.size)
