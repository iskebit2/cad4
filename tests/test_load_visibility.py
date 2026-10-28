from types import SimpleNamespace

from app.cad_app import CadApp
from domain.definition import FrameDistributedLoad, LoadSegment
from ui.load_display_panel import LoadDisplayPanel


class FakeLoadRenderer:
    def __init__(self):
        self.enabled = False
        self.updates = []
        self.show_frame_loads = True
        self.show_point_loads = True
        self.active_pattern = None

    def update(self, scene, camera_scale=1.0, scene_size=1.0):
        self.updates.append((scene, camera_scale, scene_size))


class FakeRenderer:
    def __init__(self):
        self.load_renderer = FakeLoadRenderer()
        self.size = 10.0
        self.geo_updates = []

    def set_loads_enabled(self, enabled):
        self.load_renderer.enabled = bool(enabled)

    def _compute_cam_scale(self):
        return 2.0

    def update_geo(self, scene):
        self.geo_updates.append(scene)


class FakeScene:
    def __init__(self):
        self.frames = {}
        self.nodes = {}
        self.dirty = False

    def mark_dirty(self):
        self.dirty = True

    def clear_dirty(self):
        self.dirty = False


class FakeFrame:
    def __init__(self):
        self.dist_load_sets = {}
        self.dist_loads = []
        self.dirty = False

    def mark_dirty(self):
        self.dirty = True


def _app_with_load_panel():
    app = CadApp.__new__(CadApp)
    app.engine = SimpleNamespace(renderer=FakeRenderer(), scene=FakeScene())
    app.load_display_panel = LoadDisplayPanel()
    app.load_display_panel.set_context(
        {"scene": app.engine.scene, "renderer": app.engine.renderer}
    )
    return app


def test_load_display_context_and_toolbar_share_canonical_state():
    app = _app_with_load_panel()

    app._toggle_loads_visibility()
    assert app.load_display_panel.show_loads is True
    assert app.engine.renderer.load_renderer.enabled is True

    app._toggle_loads_visibility()
    assert app.load_display_panel.show_loads is False
    assert app.engine.renderer.load_renderer.enabled is False


def test_applying_new_frame_load_enables_and_refreshes_load_rendering():
    app = _app_with_load_panel()
    frame = FakeFrame()
    app.engine.scene.frames[1] = frame
    load_set = FrameDistributedLoad(
        pattern_name="LIVE",
        segments=[LoadSegment(0.0, 1.0, 2.0, 3.0)],
    )

    app._apply_frame_distributed_load([frame], load_set)

    assert frame.dist_load_sets["LIVE"] is not load_set
    assert frame.dist_load_sets["LIVE"].segments[0].q2 == 3.0
    assert [load.pattern_name for load in frame.dist_loads] == ["LIVE"]
    assert frame.dirty is True
    assert app.load_display_panel.show_loads is True
    assert app.engine.renderer.load_renderer.enabled is True
    assert app.engine.renderer.load_renderer.updates[-1] == (
        app.engine.scene, 2.0, 10.0
    )
    assert app.engine.renderer.geo_updates == [app.engine.scene]
    assert app.engine.scene.dirty is False


def test_render_settings_callbacks_are_wired_to_load_panel():
    app = _app_with_load_panel()
    render_settings = SimpleNamespace()
    app.panels = {"render_settings": {"instance": render_settings}}

    app._wire_panel_hooks()

    render_settings.set_loads_visible(True)
    assert app.load_display_panel.show_loads is True
    assert render_settings.get_loads_visible() is True
