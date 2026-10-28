from core.units import UnitSystem
from data.enums import SectionType
from domain.project import Project
from geometry.project_builder import ProjectBuilder


def test_basic_project():
    p = Project()
    b = ProjectBuilder(p, UnitSystem.N_MM)

    mat = b.add_material("S235", E1=210000, G12=80769, density=7.85e-6)
    sec = b.add_section("HE220B", profile_type=SectionType.I,
                        profile_params={"Area": 9100, "I33": 8.09e7, "I22": 2.84e7,
                                        "J": 7.7e5, "h": 220, "b": 220},
                        material=mat)
    n1 = b.create_node(0, 0, 0, label="1")
    n2 = b.create_node(0, 0, 3000, label="2")
    f = b.create_frame(n1, n2, "HE220B", label="1")

    b.finalize()

    assert p.unit_system == UnitSystem.N_MM
    assert len(p.materials) == 1
    assert len(p.sections) == 1
    assert len(p.scene.nodes) == 2
    assert len(p.scene.frames) == 1
    print("✅ test_basic_project")


def test_convert_to_tonf_m():
    p = Project()
    b = ProjectBuilder(p, UnitSystem.N_MM)
    b.add_material("S235", E1=210000, G12=80769, density=7.85e-6)
    b.finalize()

    from core.units import convert_project_units
    convert_project_units(p, UnitSystem.TONF_M)

    mat = p.materials["S235"]
    # 210000 N/mm² → 210000000 kN/m²? HAYIR → tonf/m²
    # 210000 N/mm² = 210000 * (1 tonf/9806.65 N) * (1000 mm/m)²
    #              = 210000 / 9806.65 * 1e6 = 2.14e7 tonf/m²
    print(f"E1 TONF_M = {mat.E1}")
    print("✅ test_convert_to_tonf_m")


if __name__ == "__main__":
    test_basic_project()
    test_convert_to_tonf_m()
    print("✅ ProjectBuilder testleri geçti")