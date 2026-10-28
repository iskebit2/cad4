from types import SimpleNamespace

import pytest
from imgui_bundle import imgui

from ui.joint_load_panel import JointLoadPanel
from ui.plane_plot_panel import PlanePlotPanel
from ui.render_settings_panel import RenderSettingsPanel
from ui.sd_convert_panel import SDConvertPanel
from ui.view_filter_panel import ViewFilterPanel
from ui.widgets.plane_2d_view import Plane2DView
from ui.zones_panel import ZonesPanel
from app.toolbar import Toolbar


class RecordingDrawList:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if not name.startswith("add_"):
            raise AttributeError(name)

        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))

        return record


def test_plane_plot_canvas_uses_imgui_vector_size(monkeypatch):
    sizes = []
    panel = PlanePlotPanel()
    panel.view2d.draw = lambda *args: None
    panel._draw_canvas_overlay = lambda *args: None
    panel._consume_view_clicks = lambda: None

    monkeypatch.setattr(imgui, "get_cursor_screen_pos", lambda: imgui.ImVec2(4, 8))
    monkeypatch.setattr(imgui, "get_window_draw_list", lambda: object())
    monkeypatch.setattr(
        imgui, "invisible_button",
        lambda label, size: sizes.append((label, size)),
    )

    panel._draw_canvas(320, 240)

    assert sizes == [("##pp_canvas_area", imgui.ImVec2(320, 240))]


def test_plane_plot_overlay_sets_cursor_with_imgui_vector(monkeypatch):
    panel = PlanePlotPanel()
    panel.view2d.hover = ("node", 5)
    panel.scene = SimpleNamespace(
        nodes={5: SimpleNamespace(label="N5")}
    )
    positions = []
    monkeypatch.setattr(
        imgui, "set_cursor_screen_pos", lambda pos: positions.append(pos)
    )
    monkeypatch.setattr(imgui, "text_colored", lambda *args: None)

    panel._draw_canvas_overlay((10, 20), (400, 300))

    assert positions == [imgui.ImVec2(110, 294)]


def test_sd_canvas_draw_list_and_item_sizes_use_imgui_vectors(monkeypatch):
    panel = SDConvertPanel()
    panel._polygon_points = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)]
    draw_list = RecordingDrawList()
    button_sizes = []

    monkeypatch.setattr(imgui, "get_content_region_avail", lambda: imgui.ImVec2(400, 400))
    monkeypatch.setattr(imgui, "get_cursor_screen_pos", lambda: imgui.ImVec2(5, 6))
    monkeypatch.setattr(imgui, "get_window_draw_list", lambda: draw_list)
    monkeypatch.setattr(imgui, "get_color_u32", lambda *args: 1)
    monkeypatch.setattr(imgui, "set_cursor_screen_pos", lambda pos: None)
    monkeypatch.setattr(
        imgui, "invisible_button",
        lambda label, size: button_sizes.append((label, size)),
    )
    monkeypatch.setattr(imgui, "get_io", lambda: SimpleNamespace(mouse_pos=(0, 0)))
    monkeypatch.setattr(imgui, "is_item_hovered", lambda: False)
    monkeypatch.setattr(imgui, "is_item_clicked", lambda button: False)

    panel._draw_edges_canvas()

    assert all(
        isinstance(point, imgui.ImVec2)
        for name, args, _ in draw_list.calls
        for point in args[:2]
        if name in {"add_rect", "add_rect_filled", "add_line"}
    )
    assert button_sizes == [
        ("##edges_canvas", imgui.ImVec2(400, 340))
    ]


def test_plane_2d_view_draw_list_uses_imgui_vector_points(monkeypatch):
    view = Plane2DView()
    view.show_grid = False
    view.show_axes = False
    view._handle_input = lambda *args: None
    draw_list = RecordingDrawList()

    view.draw(imgui, draw_list, (10, 20), (300, 180))

    name, args, _ = draw_list.calls[0]
    assert name == "add_rect_filled"
    assert args[:2] == (imgui.ImVec2(10, 20), imgui.ImVec2(310, 200))


def test_plane_2d_view_primitives_use_imgui_vector_points():
    view = Plane2DView()
    draw_list = RecordingDrawList()
    view._draw_axes(draw_list, lambda u, v: (u, v))
    view._element_uvs = lambda kind, eid: [(0, 0), (1, 0), (0, 1)]
    view._draw_element(draw_list, "area", 1, lambda u, v: (u, v))

    for name, args, _ in draw_list.calls:
        point_count = 3 if name == "add_triangle_filled" else (
            2 if name in {"add_line", "add_rect", "add_rect_filled"} else 1
        )
        assert all(isinstance(point, imgui.ImVec2) for point in args[:point_count])


def test_toolbar_styled_button_uses_imgui_bundle_style_var(monkeypatch):
    toolbar = Toolbar(commands={}, panel_states={})
    style_vars = []
    style_colors = []

    monkeypatch.setattr(imgui, "push_style_color", lambda *args: style_colors.append(args))
    monkeypatch.setattr(imgui, "pop_style_color", lambda *args: None)
    monkeypatch.setattr(imgui, "push_style_var", lambda *args: style_vars.append(args))
    monkeypatch.setattr(imgui, "pop_style_var", lambda *args: None)
    monkeypatch.setattr(imgui, "push_id", lambda *args: None)
    monkeypatch.setattr(imgui, "pop_id", lambda: None)
    monkeypatch.setattr(imgui, "button", lambda *args: False)

    toolbar._icon_button("test", label="Test", base_color=(0.2, 0.3, 0.4, 1.0))

    assert style_vars == [(imgui.StyleVar_.frame_rounding, 4.0)]
    assert len(style_colors) == 3


def test_zones_panel_uses_input_text_flags_position_and_table_outer_size(monkeypatch):
    panel = ZonesPanel()
    panel.wind_analysis_ref = {
        "directions": {"01": {"w_dir": (1.0, 0.0, 0.0)}},
        "active_direction": None,
    }
    input_calls = []
    monkeypatch.setattr(imgui, "collapsing_header", lambda *args: (True, True))
    monkeypatch.setattr(imgui, "push_id", lambda *args: None)
    monkeypatch.setattr(imgui, "pop_id", lambda: None)
    monkeypatch.setattr(imgui, "text_colored", lambda *args: None)
    monkeypatch.setattr(imgui, "same_line", lambda *args: None)
    monkeypatch.setattr(imgui, "push_item_width", lambda *args: None)
    monkeypatch.setattr(imgui, "pop_item_width", lambda: None)
    monkeypatch.setattr(imgui, "button", lambda *args: False)
    monkeypatch.setattr(
        imgui, "input_text",
        lambda *args: (input_calls.append(args) or (False, args[1])),
    )

    panel._draw_wind_directions()

    assert input_calls == [("##dir", "1.0, 0.0, 0.0")]

    panel._collect_zones = lambda: [SimpleNamespace(windplane={}, label="zone")]
    table_calls = []
    monkeypatch.setattr(
        imgui, "begin_table",
        lambda *args, **kwargs: table_calls.append((args, kwargs)) or False,
    )
    panel._draw_zone_table()

    assert table_calls[0][1]["outer_size"] == imgui.ImVec2(
        0, panel.ROW_HEIGHT * panel.VISIBLE_ROWS + 30
    )


@pytest.mark.parametrize(
    "panel_type", [JointLoadPanel, RenderSettingsPanel, SDConvertPanel]
)
def test_custom_panel_ends_window_after_content_raises(monkeypatch, panel_type):
    panel = panel_type()
    panel.visible = True
    ended = []

    def fail_content(*args):
        raise RuntimeError("content failure")

    monkeypatch.setattr(imgui, "set_next_window_size", lambda *args: None)
    monkeypatch.setattr(imgui, "begin", lambda *args: (True, True))
    monkeypatch.setattr(imgui, "end", lambda: ended.append(True))
    monkeypatch.setattr(panel, "_draw_panel_content", fail_content)

    with pytest.raises(RuntimeError, match="content failure"):
        panel.draw()

    assert ended == [True]


def test_view_filter_ends_child_when_panel_content_raises(monkeypatch):
    panel = ViewFilterPanel()
    panel.camera = object()
    ended = []
    monkeypatch.setattr(imgui, "begin_child", lambda *args: True)
    monkeypatch.setattr(imgui, "end_child", lambda: ended.append(True))

    def fail_group():
        raise RuntimeError("camera group failure")

    monkeypatch.setattr(panel, "_draw_camera_group", fail_group)

    with pytest.raises(RuntimeError, match="camera group failure"):
        panel.draw_content()

    assert ended == [True]
