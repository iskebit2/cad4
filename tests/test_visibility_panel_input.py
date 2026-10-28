import pytest
from imgui_bundle import imgui

from ui.base_panel import BasePanel
from ui.visibility_panel import VisibilityPanel


def test_visibility_filter_uses_imgui_bundle_input_text_signature(monkeypatch):
    calls = []

    def input_text(*args):
        calls.append(args)
        return False, args[1]

    monkeypatch.setattr(imgui, "input_text", input_text)
    monkeypatch.setattr(imgui, "push_item_width", lambda width: None)
    monkeypatch.setattr(imgui, "pop_item_width", lambda: None)
    monkeypatch.setattr(imgui, "separator", lambda: None)
    monkeypatch.setattr(
        imgui, "get_content_region_avail", lambda: imgui.ImVec2(300, 400)
    )
    monkeypatch.setattr(imgui, "button", lambda *args: False)
    monkeypatch.setattr(imgui, "same_line", lambda *args: None)
    monkeypatch.setattr(imgui, "get_frame_height_with_spacing", lambda: 24)
    monkeypatch.setattr(imgui, "begin_child", lambda *args: True)
    monkeypatch.setattr(imgui, "end_child", lambda: None)
    monkeypatch.setattr(imgui, "text_colored", lambda *args: None)
    monkeypatch.setattr(imgui, "push_style_color", lambda *args: None)
    monkeypatch.setattr(imgui, "pop_style_color", lambda *args: None)

    panel = VisibilityPanel()
    panel.draw_content()

    assert calls == [
        ("##filter", "", imgui.InputTextFlags_.enter_returns_true)
    ]


def test_base_panel_ends_imgui_window_when_panel_content_raises(monkeypatch):
    calls = []
    monkeypatch.setattr(imgui, "set_next_window_size", lambda *args: None)
    monkeypatch.setattr(imgui, "set_next_window_pos", lambda *args: None)
    monkeypatch.setattr(imgui, "begin", lambda *args: (True, True))
    monkeypatch.setattr(imgui, "end", lambda: calls.append("end"))

    class BrokenPanel(BasePanel):
        def draw_content(self):
            raise RuntimeError("panel failure")

    panel = BrokenPanel()
    panel.visible = True

    with pytest.raises(RuntimeError, match="panel failure"):
        panel.draw()

    assert calls == ["end"]
