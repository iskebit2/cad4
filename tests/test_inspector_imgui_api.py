from types import SimpleNamespace

from imgui_bundle import imgui

import inspector.window as inspector_window
from inspector.schema_bridge import MIXED
from inspector.widgets.base import DrawContext
from inspector.widgets.mixed_widget import MixedWidget
from inspector.widgets.string_widget import StringWidget
from inspector.widgets.base import Widget


def test_mixed_text_widget_passes_input_flags_in_correct_position(monkeypatch):
    calls = []
    monkeypatch.setattr(
        imgui, "input_text",
        lambda *args: (calls.append(args) or (True, "updated")),
    )
    monkeypatch.setattr(Widget, "mixed_marker", staticmethod(lambda: None))

    ctx = DrawContext(values={"name": MIXED}, mixed_buffer={"name": ""})
    field = SimpleNamespace(kind="string", key="name", label="Name")
    changed = MixedWidget()._draw_editor(field, ctx)

    assert changed
    assert calls == [
        ("##m_name", "", imgui.InputTextFlags_.enter_returns_true)
    ]
    assert ctx.values["name"] == "updated"


def test_string_widget_does_not_pass_legacy_buffer_length(monkeypatch):
    calls = []
    monkeypatch.setattr(imgui, "align_text_to_frame_padding", lambda: None)
    monkeypatch.setattr(imgui, "text", lambda *args: None)
    monkeypatch.setattr(imgui, "same_line", lambda *args: None)
    monkeypatch.setattr(imgui, "set_next_item_width", lambda *args: None)
    monkeypatch.setattr(
        imgui, "input_text",
        lambda *args: (calls.append(args) or (True, "updated")),
    )

    ctx = DrawContext(values={"name": "before"})
    field = SimpleNamespace(kind="string", key="name", label="Name")
    changed = StringWidget().draw(field, ctx)

    assert changed
    assert calls == [("##name", "before")]
    assert ctx.values["name"] == "updated"


def test_inspector_context_menu_supplies_required_menu_item_arguments(monkeypatch):
    menu_calls = []
    element = SimpleNamespace(unique_id=1, label="Node")
    window = inspector_window.InspectorWindow.__new__(
        inspector_window.InspectorWindow
    )
    window.controller = SimpleNamespace(
        selection=SimpleNamespace(elements=[])
    )
    window.scene = object()
    window._scroll_to_id = None

    monkeypatch.setattr(
        inspector_window, "_scene_groups",
        lambda scene: [("Node", [element])],
    )
    monkeypatch.setattr(
        inspector_window, "_matches",
        lambda *args: True,
    )
    monkeypatch.setattr(
        inspector_window, "_element_label",
        lambda item: item.label,
    )
    monkeypatch.setattr(imgui, "collapsing_header", lambda *args: True)
    monkeypatch.setattr(imgui, "indent", lambda *args: None)
    monkeypatch.setattr(imgui, "unindent", lambda *args: None)
    monkeypatch.setattr(imgui, "selectable", lambda *args: (False, False))
    monkeypatch.setattr(
        imgui, "begin_popup_context_item", lambda *args: True
    )
    monkeypatch.setattr(
        imgui, "menu_item",
        lambda *args: (menu_calls.append(args) or (False, False)),
    )
    monkeypatch.setattr(imgui, "separator", lambda: None)
    monkeypatch.setattr(imgui, "end_popup", lambda: None)

    window._draw_filtered_groups("", force_open=False)

    assert menu_calls == [
        ("Sahneye odakla", "", False),
        ("ID kopyala", "", False),
        ("Sadece bunu seç", "", False),
    ]
