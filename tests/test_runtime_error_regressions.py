from types import SimpleNamespace

from imgui_bundle import imgui

from core.selection_manager import SelectionManager
from ui.adapters import element_to_values
from ui.plane_manager_panel import PlaneManagerPanel


def test_select_notifies_callback_once():
    element = SimpleNamespace(unique_id=1, is_selected=False)
    scene = SimpleNamespace(all_elements={1: element})
    renderer = SimpleNamespace(
        scene=scene,
        update_element_color=lambda _element: None,
    )
    manager = SelectionManager(renderer)
    calls = []
    manager.on_selection_changed = lambda selected: calls.append(selected)

    manager.select(element)

    assert len(calls) == 1
    assert calls[0] == [element]


def test_plane_detail_returns_when_new_form_has_no_selected_plane(monkeypatch):
    panel = PlaneManagerPanel.__new__(PlaneManagerPanel)
    panel._form_open = True
    panel._selected_plane = lambda: None
    panel._draw_new_plane_form = lambda: None
    messages = []

    monkeypatch.setattr(imgui, "separator", lambda: None)
    monkeypatch.setattr(imgui, "spacing", lambda: None)
    monkeypatch.setattr(imgui, "text_colored", lambda _color, text: messages.append(text))

    panel._draw_detail()

    assert messages == ["Bir plane seç veya '+ Yeni'."]


def test_inspector_accepts_link_without_color():
    link = SimpleNamespace(
        element_type="Link",
        label="Link",
        is_visible=True,
        color=None,
        propname="",
    )

    assert element_to_values(link)["color"] is None


def test_inspector_accepts_polygon_without_color():
    polygon = SimpleNamespace(
        element_type="Polygon",
        label="Polygon",
        is_visible=True,
        is_temporary=False,
        color=None,
        poly_type=None,
        uniform_to_frame_loads=[],
        windplane={},
        associated_frame_ids=[],
    )

    assert element_to_values(polygon)["color"] is None
