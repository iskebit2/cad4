from types import SimpleNamespace

from render import scenerenderer
from render.scenerenderer import SceneRenderer


class _SectionRendererStub:
    instances = []

    def __init__(self, **kwargs):
        self.show = {"polygon": True, "lines": True}
        self.model_mat = object()
        self.render_mode = "simple"
        self.use_lights = True
        self.assoc_preview = None
        self.cam = None
        self.update_calls = []
        self.render_calls = []
        self.instances.append(self)

    def set_engine(self, engine):
        self.engine = engine

    def set_cam(self, camera):
        self.cam = camera

    def set_lighting(self, lighting):
        self.lighting = lighting

    def update_geo(self, model):
        self.update_calls.append(model)

    def render(self, camera, target_fbo, force_id_pass=False):
        self.render_calls.append((camera, target_fbo, force_id_pass))


def _scene_renderer_stub():
    renderer = object.__new__(SceneRenderer)
    renderer.engine = object()
    renderer.math_model_renderer = SimpleNamespace(
        pick_s=object(),
        standard_shader=object(),
        node_shader=object(),
        simple_shader=object(),
        overlay_shader=object(),
        axes_shader=object(),
        w=640,
        h=480,
        show={"polygon": True, "lines": True},
        model_mat=object(),
        render_mode="simple",
        use_lights=True,
        assoc_preview=None,
    )
    model = object()
    renderer.presentation_renderer = SimpleNamespace(
        math_model=model,
        scene=SimpleNamespace(lighting=object()),
    )
    renderer._section_renderers = {}
    return renderer, model


def test_section_renderer_is_reused_per_viewport_and_refreshed_on_plane_change(
    monkeypatch,
):
    _SectionRendererStub.instances.clear()
    monkeypatch.setattr(
        scenerenderer, "MathModelRenderer", _SectionRendererStub,
    )
    renderer, model = _scene_renderer_stub()
    camera = SimpleNamespace(
        section_normal=(0.0, 0.0, 1.0),
        section_origin=(0.0, 0.0, 0.0),
        section_min=-10.0,
        section_max=10.0,
    )

    first = renderer._section_renderer_for("Plane A", camera)
    same = renderer._section_renderer_for("Plane A", camera)
    other = renderer._section_renderer_for("Plane B", camera)

    assert first is same
    assert other is not first
    assert len(_SectionRendererStub.instances) == 2
    assert first.update_calls == [model]

    camera.section_max = 20.0
    refreshed = renderer._section_renderer_for("Plane A", camera)

    assert refreshed is first
    assert first.update_calls == [model, model]
    assert len(_SectionRendererStub.instances) == 2


def test_section_viewport_renders_with_its_cached_renderer(monkeypatch):
    _SectionRendererStub.instances.clear()
    monkeypatch.setattr(
        scenerenderer, "MathModelRenderer", _SectionRendererStub,
    )
    renderer, _ = _scene_renderer_stub()
    engine = SimpleNamespace(
        show={
            "presentation_any": False,
            "scene": True,
            "polygon": True,
            "lines": True,
        },
        scene=None,
        math_model=renderer.presentation_renderer.math_model,
        w=640,
        h=480,
        active_wind_vector=None,
    )
    renderer.presentation_renderer.show = {"polygon": True, "lines": True}
    renderer.engine = engine
    camera = SimpleNamespace(
        section_active=True,
        section_normal=(0.0, 0.0, 1.0),
        section_origin=(0.0, 0.0, 0.0),
        section_min=-10.0,
        section_max=10.0,
    )

    renderer.render(camera, target_fbo=42, force_id_pass=True, viewport_name="Plane")

    cached = renderer._section_renderers["Plane"][1]
    assert cached.render_calls == [(camera, 42, True)]
