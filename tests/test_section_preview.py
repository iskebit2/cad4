from types import SimpleNamespace

import pytest
from imgui_bundle import imgui

from data.enums import SectionType
from tools import section_preview


class StrictDrawList:
    def __init__(self):
        self.call_count = 0

    def _check_points(self, *points):
        assert all(isinstance(point, imgui.ImVec2) for point in points)
        self.call_count += 1

    def add_rect_filled(self, p_min, p_max, color, rounding=0.0, flags=0):
        self._check_points(p_min, p_max)

    def add_rect(
        self, p_min, p_max, color, rounding=0.0, flags=0, thickness=1.0
    ):
        self._check_points(p_min, p_max)

    def add_circle_filled(self, center, radius, color, num_segments=0):
        self._check_points(center)

    def add_circle(self, center, radius, color, num_segments=0, thickness=1.0):
        self._check_points(center)


@pytest.mark.parametrize("profile_type", list(SectionType))
def test_draw_section_preview_uses_imgui_bundle_draw_api(monkeypatch, profile_type):
    draw_list = StrictDrawList()
    dummy_sizes = []
    section = SimpleNamespace(
        profile_type=profile_type,
        color=(0.5, 0.6, 0.7),
        profile_params={
            "h": 400.0,
            "b": 200.0,
            "d": 400.0,
            "t": 15.0,
            "tw": 10.0,
            "tf": 12.0,
        },
    )
    monkeypatch.setattr(
        section_preview.imgui, "get_window_draw_list", lambda: draw_list
    )
    monkeypatch.setattr(
        section_preview.imgui,
        "get_cursor_screen_pos",
        lambda: imgui.ImVec2(10.0, 20.0),
    )
    monkeypatch.setattr(
        section_preview.imgui, "dummy", lambda size: dummy_sizes.append(size)
    )

    section_preview.draw_section_preview(section)

    assert section_preview.imgui is imgui
    assert draw_list.call_count >= 3
    assert len(dummy_sizes) == 1
    assert isinstance(dummy_sizes[0], imgui.ImVec2)
