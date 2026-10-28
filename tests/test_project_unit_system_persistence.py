from core.units import UnitSystem
from domain.project import Project


def test_loaded_project_unit_system_is_unit_system_enum(tmp_path):
    project = Project()
    project.unit_system = UnitSystem.KN_M
    project_path = tmp_path / "units.cd4"
    project.save(str(project_path))

    loaded_project = Project.load(str(project_path))

    assert loaded_project.unit_system is UnitSystem.KN_M
    assert loaded_project.unit_system.name == "KN_M"


def test_existing_project_file_unit_system_is_normalized():
    project_path = "tests/model_projesi.cd4"

    project = Project.load(project_path)

    assert isinstance(project.unit_system, UnitSystem)
    assert project.unit_system.name == "N_MM"
