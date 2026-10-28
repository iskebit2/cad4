# tests/test_units_schema.py
from core.units import UnitSystem, convert_project_units
from data.enums import SectionType
from domain.definition import (
    LoadSegment,
    Material,
    Section,
)
from domain.element import Node


def test_section_roundtrip():
    class P:
        unit_system = UnitSystem.N_MM
        ui_dirty = False
        materials = {"S235": Material(name="S235", E1=210000, G12=80769, density=7.85e-6)}
        sections = {"HE220B": Section(
            name="HE220B", profile_type=SectionType.I,
            profile_params={"Area": 9100.0, "I33": 8.09e7, "I22": 2.84e7,
                            "J": 7.7e5, "h": 220.0, "b": 220.0},
        )}

    p = P()
    orig_Area = p.sections["HE220B"].profile_params["Area"]
    orig_h = p.sections["HE220B"].profile_params["h"]

    convert_project_units(p, UnitSystem.TONF_M)
    convert_project_units(p, UnitSystem.N_MM)

    assert abs(p.sections["HE220B"].profile_params["Area"] - orig_Area) / orig_Area < 1e-9
    assert abs(p.sections["HE220B"].profile_params["h"] - orig_h) / orig_h < 1e-9
    print("✅ test_section_roundtrip")


def test_node_roundtrip():
    from domain.project import Project
    p = Project()
    p.unit_system = UnitSystem.N_MM
    n = Node(6000, 0, 3000)
    p.scene.add_node(n)

    orig_x = n.x
    convert_project_units(p, UnitSystem.KN_M)
    assert abs(n.x - 6.0) < 1e-9
    convert_project_units(p, UnitSystem.N_MM)
    assert abs(n.x - orig_x) < 1e-9
    print("✅ test_node_roundtrip")


def test_load_segment():
    class P:
        unit_system = UnitSystem.N_MM
        ui_dirty = False
        segs = []   # ← ekle

    p = P()
    seg = LoadSegment(q1=10.0, q2=10.0)   # N/mm
    p.segs.append(seg)   # ← p'ye bağla
    orig = seg.q1

    convert_project_units(p, UnitSystem.KN_M)
    # 10 N/mm = 10 kN/m
    assert abs(seg.q1 - 10.0) < 1e-9, seg.q1

    convert_project_units(p, UnitSystem.N_MM)
    assert abs(seg.q1 - orig) < 1e-9
    print("✅ test_load_segment")


if __name__ == "__main__":
    test_section_roundtrip()
    test_node_roundtrip()
    test_load_segment()
    print("✅ Aşama 2 schema testleri geçti")