# tests/test_project.py
import tempfile
from pathlib import Path

import numpy as np
import pytest

from domain.definition import Material, Restraint, Section
from domain.element import Frame, Node
from domain.grid import Grid, ObliqueAxis
from domain.plane import Plane
from domain.project import Project


# ===========================================================================
# Başlangıç
# ===========================================================================

def test_new_project_has_default_grid():
    p = Project()
    assert p.grid.x_coords == [0.0, 4000.0, 8000.0]
    assert p.grid.y_coords == [0.0, 5000.0, 10000.0]
    assert p.grid.z_coords == [0.0, 4000.0]


def test_scene_does_not_own_grid():
    p = Project()
    assert not hasattr(p.scene, "grid")


def test_scene_project_is_linked():
    p = Project()
    assert p.scene.project is p


# ===========================================================================
# Grid plane üretimi
# ===========================================================================

def test_grid_planes_count():
    p = Project()
    planes = p.grid_planes()
    n_x, n_y, n_z = len(p.grid.x_coords), len(p.grid.y_coords), len(p.grid.z_coords)
    assert len(planes) == n_x + n_y + n_z


def test_grid_planes_names():
    p = Project()
    names = {pl.name for pl in p.grid_planes()}
    assert "XY_Z0" in names
    assert "XZ_Y0" in names
    assert "YZ_X0" in names


def test_grid_planes_cached():
    p = Project()
    a = p.grid_planes()
    b = p.grid_planes()
    assert a[0] is b[0]


def test_invalidate_grid_planes():
    p = Project()
    a = p.grid_planes()
    p.invalidate_grid_planes()
    b = p.grid_planes()
    assert a[0] is not b[0]


# ===========================================================================
# Grid mutasyonu — invalidate sonrası yeni plane
# ===========================================================================

def test_grid_change_after_invalidate():
    p = Project()
    before = {pl.name for pl in p.grid_planes()}
    p.grid.z_coords = [0.0, 2000.0]
    p.invalidate_grid_planes()
    after = {pl.name for pl in p.grid_planes()}
    assert "XY_Z2000" in after
    assert "XY_Z4000" not in after


def test_sync_from_s2k_invalidates():
    p = Project()
    p.grid_planes()
    p.sync_grid_from_s2k_lines([
        {"axis_dir": "X", "ordinate": 0},
        {"axis_dir": "X", "ordinate": 1000},
        {"axis_dir": "Y", "ordinate": 0},
        {"axis_dir": "Z", "ordinate": 0},
    ])
    assert 1000.0 in p.grid.x_coords
    assert not hasattr(p.scene, "grid")


# ===========================================================================
# Custom planes
# ===========================================================================

def test_custom_plane_add_get():
    p = Project()
    pl = Plane((0, 0, 500), (0, 0, 1), name="CUSTOM_500")
    p.add_plane(pl)
    assert p.get_plane("CUSTOM_500") is pl


def test_all_planes_includes_grid_and_custom():
    p = Project()
    pl = Plane((0, 0, 9999), (0, 0, 1), name="EXTRA")
    p.add_plane(pl)
    allp = p.all_planes()
    assert "EXTRA" in allp
    assert any(name.startswith("XY_Z") for name in allp)


def test_remove_custom_plane():
    p = Project()
    pl = Plane((0, 0, 1), (0, 0, 1), name="X")
    p.add_plane(pl)
    assert p.remove_plane("X")
    assert p.get_plane("X") is None


def test_remove_plane_nonexistent():
    p = Project()
    assert not p.remove_plane("NOPE")


# ===========================================================================
# Active plane
# ===========================================================================

def test_activate_plane_by_name():
    p = Project()
    pl = Plane((0, 0, 1), (0, 0, 1), name="P1")
    p.add_plane(pl)
    active = p.activate_plane("P1")
    assert p.active_plane is active
    assert p.active_plane_id == pl.plane_id


def test_activate_missing_raises():
    p = Project()
    with pytest.raises(KeyError):
        p.activate_plane("YOK")


def test_deactivate_plane():
    p = Project()
    pl = Plane((0, 0, 1), (0, 0, 1), name="P1")
    p.add_plane(pl)
    p.activate_plane(pl)
    old = p.deactivate_plane()
    assert old is pl
    assert p.active_plane is None


# ===========================================================================
# Element ve polygon ekleme
# ===========================================================================

def test_scene_add_node():
    p = Project()
    n = Node(100, 200, 0)
    p.scene.add_node(n)
    assert p.scene.nodes[n.unique_id] is n


def test_scene_add_frame_connects_nodes():
    p = Project()
    n1, n2 = Node(0, 0, 0), Node(1000, 0, 0)
    p.scene.add_node(n1)
    p.scene.add_node(n2)
    sec = Section(name="S1", material=Material())
    p.sections["S1"] = sec
    f = Frame(n1, n2, sec)
    p.scene.add_frame(f)
    assert p.scene.frames[f.unique_id] is f
    assert any(t == "Frame" or eid == f.unique_id for t, eid in n1.connected)


# ===========================================================================
# Scene bounds
# ===========================================================================

def test_scene_bounds_empty():
    p = Project()
    assert p.scene.bounds is None


def test_scene_bounds_two_nodes():
    p = Project()
    p.scene.add_node(Node(0, 0, 0))
    p.scene.add_node(Node(1000, 2000, 3000))
    b = p.scene.bounds
    assert np.allclose(b.min, (0, 0, 0))
    assert np.allclose(b.max, (1000, 2000, 3000))


# ===========================================================================
# Plane association
# ===========================================================================

def test_scene_refresh_plane_assoc():
    p = Project()
    n = Node(0, 0, 0)
    p.scene.add_node(n)
    assert p.scene.refresh_plane_associations(force=True)
    z0 = next(pl for pl in p.grid_planes() if pl.name == "XY_Z0")
    assert n.unique_id in z0.all_assoc_ids("node")


def test_scene_assoc_skipped_when_clean():
    p = Project()
    p.scene.mark_plane_associations_current()
    assert not p.scene.refresh_plane_associations()


# ===========================================================================
# save / load roundtrip
# ===========================================================================

def test_save_load_empty():
    p = Project()
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "test.cd4"
        p.save(str(path))
        assert path.exists()
        loaded = Project.load(str(path))
        assert loaded.grid.x_coords == p.grid.x_coords


def test_save_load_grid():
    p = Project()
    p.grid = Grid(x_coords=[0, 1000, 2000], y_coords=[0, 500], z_coords=[0])
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "test.cd4"
        p.save(str(path))
        loaded = Project.load(str(path))
        assert loaded.grid.x_coords == [0, 1000, 2000]
        assert loaded.grid.y_coords == [0, 500]


def test_save_load_nodes_and_frames():
    p = Project()
    n1, n2 = Node(0, 0, 0), Node(1000, 0, 0)
    p.scene.add_node(n1)
    p.scene.add_node(n2)
    p.sections["S1"] = Section(name="S1", material=Material())
    p.scene.add_frame(Frame(n1, n2, p.sections["S1"]))

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "test.cd4"
        p.save(str(path))
        loaded = Project.load(str(path))

    assert len(loaded.scene.nodes) == 2
    assert len(loaded.scene.frames) == 1
    f = next(iter(loaded.scene.frames.values()))
    assert f.node_i is not None
    assert f.node_j is not None
    assert f.node_i.unique_id in loaded.scene.nodes


def test_save_load_custom_plane():
    p = Project()
    pl = Plane((10, 20, 30), (0, 0, 1), name="P_CUSTOM")
    p.add_plane(pl)

    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "test.cd4"
        p.save(str(path))
        loaded = Project.load(str(path))

    assert "P_CUSTOM" in loaded.custom_planes
    lp = loaded.custom_planes["P_CUSTOM"]
    assert np.allclose(lp.origin, (10, 20, 30))


def test_load_nonexistent_returns_new():
    with tempfile.TemporaryDirectory() as td:
        p = Project.load(str(Path(td) / "yok.cd4"))
        assert p.grid.x_coords  # default grid


def test_save_appends_extension():
    p = Project()
    with tempfile.TemporaryDirectory() as td:
        base = Path(td) / "proje"
        p.save(str(base))
        assert (Path(td) / "proje.cd4").exists()


# ===========================================================================
# Grid bağlama sonrası renderer uyumu
# ===========================================================================

def test_project_grid_survives_load():
    p = Project()
    p.grid = Grid(x_coords=[0, 1000], y_coords=[0, 500], z_coords=[0])
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "test.cd4"
        p.save(str(path))
        loaded = Project.load(str(path))
    assert loaded.scene.project is loaded
    assert not hasattr(loaded.scene, "grid")
    assert loaded.grid.x_coords == [0, 1000]


# ===========================================================================
# Oblique grid
# ===========================================================================

def test_grid_oblique_axes():
    p = Project()
    p.grid.oblique_axes.append(ObliqueAxis(name="E1", p1=(0, 0), p2=(5000, 5000)))
    axes = p.grid.axes
    assert any(a.kind == "oblique" and a.label == "E1" for a in axes)