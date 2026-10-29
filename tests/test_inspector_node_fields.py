# tests/test_inspector_node_fields.py
from domain.element import Node
from ui.adapters import node_to_values, values_to_node


def test_node_to_values_includes_mass_and_constraint():
    n = Node(0, 0, 0, label="N1")
    n.added_mass_1 = 10.0
    n.added_mass_2 = 20.0
    n.added_mass_3 = 30.0
    n.added_mmi_3 = 5000.0
    n.constraint_name = "D1"

    v = node_to_values(n)
    assert v["added_mass_1"] == 10.0
    assert v["added_mass_2"] == 20.0
    assert v["added_mass_3"] == 30.0
    assert v["added_mmi_3"] == 5000.0
    assert v["constraint_name"] == "D1"


def test_values_to_node_roundtrip():
    n = Node(0, 0, 0)
    v = {
        "added_mass_1": 1.0,
        "added_mmi_1": 100.0,
        "constraint_name": "C1",
        "mass_1": 5.0,
    }
    values_to_node(n, v)
    assert n.added_mass_1 == 1.0
    assert n.added_mmi_1 == 100.0
    assert n.constraint_name == "C1"
    assert n.mass_1 == 5.0