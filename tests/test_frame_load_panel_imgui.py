from imgui_bundle import imgui

from domain.definition import LoadSegment
from ui import frame_load_panel


class StrictDrawList:
    def __init__(self):
        self.calls = 0

    def _check_points(self, *points):
        assert all(isinstance(point, imgui.ImVec2) for point in points)
        self.calls += 1

    def add_rect_filled(self, p_min, p_max, color, rounding=0.0, flags=0):
        self._check_points(p_min, p_max)

    def add_rect(
        self, p_min, p_max, color, rounding=0.0, flags=0, thickness=1.0
    ):
        self._check_points(p_min, p_max)

    def add_line(self, p1, p2, color, thickness=1.0):
        self._check_points(p1, p2)

    def add_quad_filled(self, p1, p2, p3, p4, color):
        self._check_points(p1, p2, p3, p4)

    def add_circle_filled(self, center, radius, color, num_segments=0):
        self._check_points(center)

    def add_circle(self, center, radius, color, num_segments=0, thickness=1.0):
        self._check_points(center)

    def add_text(self, pos, color, text, text_end=None):
        self._check_points(pos)


def test_frame_load_canvas_uses_imgui_bundle_api(monkeypatch):
    draw_list = StrictDrawList()
    canvas_size = []
    monkeypatch.setattr(
        frame_load_panel.imgui,
        "get_content_region_avail",
        lambda: imgui.ImVec2(800, 600),
    )
    monkeypatch.setattr(
        frame_load_panel.imgui,
        "get_cursor_screen_pos",
        lambda: imgui.ImVec2(10, 20),
    )
    monkeypatch.setattr(
        frame_load_panel.imgui,
        "invisible_button",
        lambda label, size: canvas_size.append(size),
    )
    monkeypatch.setattr(
        frame_load_panel.imgui,
        "get_item_rect_max",
        lambda: imgui.ImVec2(750, 320),
    )
    monkeypatch.setattr(
        frame_load_panel.imgui, "get_window_draw_list", lambda: draw_list
    )
    monkeypatch.setattr(frame_load_panel.imgui, "get_color_u32", lambda color: 1)
    monkeypatch.setattr(
        frame_load_panel.imgui, "text_colored", lambda color, text: None
    )
    monkeypatch.setattr(frame_load_panel.imgui, "same_line", lambda *args: None)

    panel = frame_load_panel.FrameLoadPanel()
    panel.active_set.segments = [LoadSegment(0.0, 1.0, 1.0, 3.0)]
    monkeypatch.setattr(panel, "_handle_canvas_input", lambda *args: None)

    panel._draw_canvas()

    assert canvas_size == [imgui.ImVec2(790, panel.CANVAS_HEIGHT)]
    assert draw_list.calls > 20
