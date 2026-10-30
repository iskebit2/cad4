from types import SimpleNamespace

from app import toolbar as toolbar_module
from ui import plane_plot_panel as plot_module
from ui.widgets import plane_2d_tools as tools_module
from ui.widgets.plane_2d_view import (
    Plane2DView,
    _element_intersects_rect,
    _point_in_polygon,
)
from ui.widgets.plane_2d_tools import PlaceDistLoadTool


class _InputContext:
    def __init__(self, x=50.0, y=50.0, *, clicked=(), down=(), released=()):
        self.io = SimpleNamespace(
            mouse_pos=(x, y),
            mouse_wheel=0.0,
            key_ctrl=False,
            key_shift=False,
            key_space=False,
        )
        self.clicked = set(clicked)
        self.down = set(down)
        self.released = set(released)

    def get_io(self):
        return self.io

    def is_mouse_clicked(self, button):
        return button in self.clicked

    def is_mouse_down(self, button):
        return button in self.down

    def is_mouse_released(self, button):
        return button in self.released

    def is_key_down(self, key):
        return False


def test_2d_pan_tracks_screen_drag_after_view_rotation():
    view = Plane2DView()
    view.zoom = 2.0
    view.view_rotation = 90.0
    view._panning = True
    view._pan_anchor = (20.0, 30.0)
    ctx = _InputContext(30.0, 40.0, down=(2,))

    view._handle_input(ctx, 0.0, 0.0, 100.0, 100.0, lambda u, v: (u, v), lambda x, y: (x, y))

    assert view.pan == (5.0, -5.0)
    shifted_to_screen, _ = view._factory(0.0, 0.0, 100.0, 100.0)
    before = shifted_to_screen(0.0, 0.0)
    view.pan = (0.0, 0.0)
    base_to_screen, _ = view._factory(0.0, 0.0, 100.0, 100.0)
    after = base_to_screen(0.0, 0.0)
    assert (before[0] - after[0], before[1] - after[1]) == (10.0, 10.0)


def test_fit_to_content_centers_bounds_after_view_rotation():
    view = Plane2DView()
    view._bounds = (10.0, 20.0, 30.0, 40.0)
    view.view_rotation = 90.0

    view.fit_to_content(100.0, 100.0)

    to_screen, _ = view._factory(0.0, 0.0, 100.0, 100.0)
    center = to_screen(15.0, 35.0)
    assert center == (50.0, 50.0)


def test_2d_click_emits_hit_for_panel_selection():
    view = Plane2DView()
    view._hit_test = lambda *_: ("frame", 42)
    to_screen = lambda u, v: (u, v)
    from_screen = lambda x, y: (x, y)

    press = _InputContext(50.0, 50.0, clicked=(0,), down=(0,))
    view._handle_input(press, 0.0, 0.0, 100.0, 100.0, to_screen, from_screen)
    assert view._rubber

    release = _InputContext(50.0, 50.0, released=(0,))
    view._handle_input(release, 0.0, 0.0, 100.0, 100.0, to_screen, from_screen)

    assert view.clicked == ("frame", 42)
    assert not view.clicked_empty


def test_rubber_selects_frames_crossing_selection_rectangle():
    frame = object()
    calls = []
    view = Plane2DView()
    view.scene = SimpleNamespace(frames={7: frame})
    view.sel_mgr = SimpleNamespace(
        select_multiple=lambda elements, mode: calls.append((elements, mode))
    )
    view._iter_assoc_ids = lambda: iter((("frame", 7),))
    view._element_uvs = lambda *_: [(-5.0, 5.0), (15.0, 5.0)]
    view._kind_id_to_element = lambda _kind, _eid: frame
    view._mods_getter = lambda: (False, False)
    view._rubber_start = (0.0, 4.0)
    view._rubber_end = (4.0, 8.0)

    view._finish_rubber(lambda u, v: (u, v))

    assert len(calls) == 1
    assert calls[0][0] == [frame]


def test_plane_plot_routes_click_to_shared_selection_manager():
    element = object()
    calls = []
    panel = plot_module.PlanePlotPanel()
    panel.app = SimpleNamespace(
        engine=SimpleNamespace(
            sel_mgr=SimpleNamespace(
                select_only=lambda value: calls.append(value)
            )
        )
    )
    panel._kind_id_to_element = lambda _kind, _eid: element
    panel.view2d.clicked = ("frame", 7)
    panel.view2d._mods_getter = lambda: (False, False)

    panel._consume_view_clicks()

    assert calls == [element]
    assert panel.view2d.clicked is None


def test_area_and_crossing_frame_are_hit_by_selection_geometry():
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]

    assert _point_in_polygon((5.0, 5.0), square)
    assert not _point_in_polygon((12.0, 5.0), square)
    assert _element_intersects_rect("frame", [(-5.0, 5.0), (15.0, 5.0)], (0.0, 4.0, 1.0, 6.0))
    assert _element_intersects_rect("area", square, (4.0, 4.0, 6.0, 6.0))


def test_toolbar_icon_fallback_uses_visible_label_and_size(monkeypatch):
    seen = {}
    fake_imgui = SimpleNamespace(
        button=lambda label, size: seen.update(label=label, size=size) or False,
        ImVec2=lambda x, y: SimpleNamespace(x=x, y=y),
        push_id=lambda *_: None,
        pop_id=lambda: None,
        is_item_hovered=lambda: False,
    )
    monkeypatch.setattr(toolbar_module, "imgui", fake_imgui)
    toolbar = toolbar_module.Toolbar.__new__(toolbar_module.Toolbar)
    toolbar.icon_mgr = SimpleNamespace(get_texture=lambda _name: None)

    toolbar._icon_button("test", fallback="Plane Manager")

    assert seen["label"] == "Plane Ma.."
    assert seen["size"].x > 16.0
    assert seen["size"].y == 24.0


def test_selected_tool_form_renders_once_in_separate_window(monkeypatch):
    calls = []

    class Tool:
        def is_active(self):
            return False

        def draw_ui(self, plane, scene):
            calls.append((plane, scene))

    fake_imgui = SimpleNamespace(
        set_next_window_size=lambda *_: None,
        set_next_window_pos=lambda *_: None,
        Cond_=SimpleNamespace(first_use_ever=0),
        ImVec2=lambda x, y: (x, y),
        begin=lambda *_: (True, True),
        end=lambda: None,
    )
    monkeypatch.setattr(plot_module, "imgui", fake_imgui)
    panel = plot_module.PlanePlotPanel()
    panel._tool_form_open = True
    panel.view2d.active_tool_obj = Tool()
    panel._scene = lambda: "scene"

    panel._draw_tool_form_window()

    assert calls == [(None, "scene")]


def test_dist_load_form_apply_button_updates_selected_frame(monkeypatch):
    class FakeImgui:
        ImVec4 = lambda *_: None

        @staticmethod
        def __getattr__(name):
            return lambda *_args, **_kwargs: None

    fake_imgui = FakeImgui()
    fake_imgui.button = lambda label, *_: label == "Apply"
    fake_imgui.begin_combo = lambda *_: False
    fake_imgui.input_float = lambda _label, value, *_: (False, value)
    fake_imgui.input_text = lambda _label, value, *_: (False, value)
    fake_imgui.checkbox = lambda _label, value, *_: (False, value)
    monkeypatch.setattr(tools_module, "imgui", fake_imgui)

    frame = SimpleNamespace(
        unique_id=9,
        label="F9",
        dist_load_sets={},
        mark_dirty=lambda: None,
    )
    scene = SimpleNamespace(
        frames={9: frame},
        mark_dirty=lambda: None,
    )
    tool = PlaceDistLoadTool(
        _pending={"frame_id": 9},
        q1=3.0,
        q2=5.0,
    )

    tool.draw_ui(None, scene)

    applied = frame.dist_load_sets["DEAD"]
    assert len(applied.segments) == 1
    assert (applied.segments[0].x1, applied.segments[0].x2) == (0.0, 1.0)
    assert (applied.segments[0].q1, applied.segments[0].q2) == (3.0, 5.0)
    assert not tool.is_active()
