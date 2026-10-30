import pytest

from domain.plane import Plane
from domain.project import Project


def _plane(name: str, plane_id: str | None = None) -> Plane:
    return Plane(
        origin=(0.0, 0.0, 0.0),
        normal=(0.0, 0.0, 1.0),
        name=name,
        plane_id=plane_id,
    )


def test_project_plane_manager_wrappers_share_active_plane_state():
    project = Project()
    plane = project.add_plane(_plane("Work"))

    assert project.plane_mgr.activate(plane.plane_id) is plane
    assert project.plane_mgr.active_plane is plane
    assert project.plane_mgr.active_plane_id == plane.plane_id


def test_plane_manager_activates_by_name_and_deactivates():
    project = Project()
    plane = project.add_plane(_plane("Work"))

    assert project.plane_mgr.activate("Work") is plane
    assert project.plane_mgr.active_plane is plane
    assert project.plane_mgr.deactivate() is plane
    assert project.plane_mgr.active_plane is None


def test_plane_manager_rejects_unknown_plane_and_duplicate_ids():
    project = Project()
    project.add_plane(_plane("Work", "plane-id"))

    with pytest.raises(KeyError, match="bulunamadı"):
        project.plane_mgr.activate("missing")
    with pytest.raises(ValueError, match="ID zaten kayıtlı"):
        project.add_plane(_plane("Other", "plane-id"))


def test_replacing_or_removing_active_plane_clears_active_state():
    project = Project()
    original = project.add_plane(_plane("Work"))
    project.plane_mgr.activate(original)

    replacement = project.add_plane(_plane("Work"))

    assert project.plane_mgr.active_plane is None
    project.plane_mgr.activate(replacement)
    assert project.remove_plane("Work")
    assert project.plane_mgr.active_plane_id is None


def test_plane_manager_preserves_same_name_replacement_behavior():
    project = Project()
    original = project.add_plane(_plane("Work"))
    replacement = project.add_plane(_plane("Work"))

    assert replacement is not original
    assert project.plane_mgr.count() == 1
    assert project.get_plane("Work") is replacement
