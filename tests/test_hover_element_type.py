from types import SimpleNamespace

from core.gl_engine import Engine
from domain.element import Node


def test_node_element_type_is_normalized_for_hover():
    assert Engine._element_type(Node(1, 2, 3)) == "node"


def test_node_hover_is_recorded_as_lowercase_and_updates_world_position():
    node = Node(1, 2, 3)
    engine = Engine.__new__(Engine)
    engine.hover_id = 0
    engine.renderer = SimpleNamespace(
        get_element_from_id=lambda pick_id: node
    )
    engine.input = SimpleNamespace(mouse_world_pos=None, mouse_world_valid=False)
    engine.on_hover_changed_callback = None

    engine._update_hover(node.pick_id)

    assert engine.hover_element_type == "node"
    assert tuple(engine.input.mouse_world_pos) == (1, 2, 3)
    assert engine.input.mouse_world_valid
