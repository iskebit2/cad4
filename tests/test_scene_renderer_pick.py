from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
from OpenGL.GL import (
    GL_BLEND,
    GL_COLOR_ATTACHMENT1,
    GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST,
    GL_DEPTH_WRITEMASK,
    GL_FALSE,
    GL_TRUE,
)
from pyglm import glm

from render import scenerenderer


def test_id_pass_clears_depth_before_redrawing_geometry(monkeypatch):
    events = []

    class _Shader:
        def use(self):
            events.append("use_shader")

        def get_loc(self, name):
            return {"mvp": 0}.get(name, -1)

    class _Renderer:
        def __init__(self, name):
            self.name = name

        def render_simple(self, mvp, shader, alpha):
            events.append(
                ("draw", self.name, mvp is not None, shader is not None, alpha)
            )

    renderer = scenerenderer.SceneRenderer.__new__(
        scenerenderer.SceneRenderer
    )
    renderer.engine = SimpleNamespace(mrt=object(), pick_s=_Shader())
    renderer.show = {
        "area": True,
        "frame": True,
        "link": True,
        "node": True,
    }
    renderer.area_r = _Renderer("area")
    renderer.frame_r = _Renderer("frame")
    renderer.link_r = _Renderer("link")
    renderer.node_r = _Renderer("node")

    monkeypatch.setattr(
        scenerenderer,
        "glIsEnabled",
        Mock(side_effect=lambda capability: capability in {GL_DEPTH_TEST, GL_BLEND}),
    )
    monkeypatch.setattr(
        scenerenderer,
        "glGetBooleanv",
        Mock(side_effect=lambda name: GL_TRUE if name == GL_DEPTH_WRITEMASK else GL_FALSE),
    )
    monkeypatch.setattr(
        scenerenderer,
        "glDrawBuffer",
        lambda value: events.append(("draw_buffer", value)),
    )
    monkeypatch.setattr(
        scenerenderer,
        "glDepthMask",
        lambda value: events.append(("depth_mask", value)),
    )
    monkeypatch.setattr(
        scenerenderer, "glClear", lambda value: events.append(("clear", value))
    )
    monkeypatch.setattr(
        scenerenderer, "glEnable", lambda value: events.append(("enable", value))
    )
    monkeypatch.setattr(
        scenerenderer, "glDisable", lambda value: events.append(("disable", value))
    )
    uniform_matrix = Mock()
    monkeypatch.setattr(scenerenderer, "glUniformMatrix4fv", uniform_matrix)

    renderer._render_id_pass(glm.mat4(1.0))

    depth_clear = events.index(("clear", GL_DEPTH_BUFFER_BIT))
    first_draw = events.index(("draw", "area", True, True, 1.0))
    assert events.index(("draw_buffer", GL_COLOR_ATTACHMENT1)) < depth_clear
    assert depth_clear < first_draw
    assert ("disable", GL_BLEND) in events
    assert ("enable", GL_DEPTH_TEST) in events
    assert events[-3:] == [
        ("depth_mask", GL_TRUE),
        ("enable", GL_DEPTH_TEST),
        ("enable", GL_BLEND),
    ]
    assert isinstance(uniform_matrix.call_args.args[3], np.ndarray)
