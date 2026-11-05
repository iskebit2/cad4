# tests/test_plane.py
import numpy as np
import pytest

from domain.plane import (
    Plane, ChangeOp, PendingChange,
    ASSOC_KINDS, ON_PLANE, INTERSECTING, WITHIN_DEPTH, OUTSIDE,
)


# ===========================================================================
# Constructor
# ===========================================================================

def test_origin_normal_axis_aligned():
    p = Plane((0, 0, 0), (0, 0, 1))
    assert np.allclose(p.origin, (0, 0, 0))
    assert np.allclose(p.normal, (0, 0, 1))
    assert abs(np.linalg.norm(p.u) - 1.0) < 1e-9
    assert abs(np.linalg.norm(p.v) - 1.0) < 1e-9
    assert abs(np.dot(p.u, p.normal)) < 1e-9
    assert abs(np.dot(p.v, p.normal)) < 1e-9
    assert abs(np.dot(p.u, p.v)) < 1e-9


def test_zero_normal_raises():
    with pytest.raises(ValueError):
        Plane((0, 0, 0), (0, 0, 0))


def test_parallel_u_raises():
    with pytest.raises(ValueError):
        Plane((0, 0, 0), (0, 0, 1), u=(0, 0, 1))


def test_bounds_recenter():
    p = Plane((0, 0, 0), (0, 0, 1), u_min=0, u_max=10, v_min=0, v_max=20)
    assert np.allclose(p.origin, (5, 10, 0))


# ===========================================================================
# Constructors
# ===========================================================================

def test_from_3_points():
    p = Plane.from_3_points((0, 0, 0), (1, 0, 0), (0, 1, 0))
    assert np.allclose(np.abs(p.normal), (0, 0, 1))


def test_from_3_points_collinear_raises():
    with pytest.raises(ValueError):
        Plane.from_3_points((0, 0, 0), (1, 0, 0), (2, 0, 0))


def test_from_2_points_z_up():
    p = Plane.from_2_points_z_up((0, 0, 0), (1, 0, 0))
    assert np.allclose(p.u, (1, 0, 0))
    assert np.allclose(p.v, (0, 0, 1))


def test_from_2_points_xy():
    p = Plane.from_2_points((0, 0, 5), (1, 0, 5), "XY")
    assert np.allclose(p.normal, (0, 0, 1))


def test_from_2_points_wrong_orientation():
    with pytest.raises(ValueError):
        Plane.from_2_points((0, 0, 0), (0, 0, 5), "XY")


def test_from_axis_offset_z():
    p = Plane.from_axis_offset("z", 5.0)
    assert np.allclose(p.origin, (0, 0, 5))
    assert np.allclose(p.normal, (0, 0, 1))
    assert np.allclose(p.u, (1, 0, 0))
    assert np.allclose(p.v, (0, 1, 0))


def test_from_axis_offset_invalid():
    with pytest.raises(ValueError):
        Plane.from_axis_offset("w", 0)


# ===========================================================================
# Geometry
# ===========================================================================

def test_distance_signed():
    p = Plane((0, 0, 0), (0, 0, 1))
    assert abs(p.distance((0, 0, 5)) - 5) < 1e-9
    assert abs(p.distance((0, 0, -3)) + 3) < 1e-9
    assert abs(p.distance_abs((0, 0, -3)) - 3) < 1e-9


def test_project_point():
    p = Plane((0, 0, 0), (0, 0, 1))
    assert np.allclose(p.project((2, 3, 7)), (2, 3, 0))


def test_to_2d_3d_roundtrip():
    p = Plane((1, 2, 3), (0, 0, 1))
    pt = (5, 7, 3)
    u, v = p.to_2d(pt)
    assert np.allclose(p.to_3d((u, v)), pt)


def test_world_to_local_roundtrip():
    p = Plane((1, 2, 3), (0, 0, 1))
    pt = (5, 7, 8)
    local = p.world_to_local(pt)
    assert np.allclose(p.local_to_world(local), pt)


def test_intersect_ray_hit():
    p = Plane((0, 0, 0), (0, 0, 1))
    hit = p.intersect_ray((0, 0, 5), (0, 0, -1))
    assert np.allclose(hit, (0, 0, 0))


def test_intersect_ray_parallel():
    p = Plane((0, 0, 0), (0, 0, 1))
    assert p.intersect_ray((0, 0, 5), (1, 0, 0)) is None


def test_intersect_ray_behind():
    p = Plane((0, 0, 0), (0, 0, 1))
    assert p.intersect_ray((0, 0, 5), (0, 0, 1)) is None


def test_bounds_contains_uv():
    p = Plane((0, 0, 0), (0, 0, 1), u_min=0, u_max=10, v_min=0, v_max=10)
    p.set_bounds(0, 10, 0, 10, recenter=False)
    assert p.bounds_contains_uv(5, 5)
    assert not p.bounds_contains_uv(15, 5)
    assert not p.bounds_contains_uv(5, -1)
    assert not p.bounds_contains_uv(-1, 5)


def test_band_contains_pt():
    p = Plane((0, 0, 0), (0, 0, 1), depth_minus=2, depth_plus=3)
    assert p.band_contains_pt((0, 0, 2))
    assert p.band_contains_pt((0, 0, -1))
    assert not p.band_contains_pt((0, 0, 4))
    assert not p.band_contains_pt((0, 0, -3))


def test_contains_pt_bounds_and_band():
    p = Plane((0, 0, 0), (0, 0, 1), u_min=0, u_max=10, v_min=0, v_max=10,
              depth_minus=1, depth_plus=1)
    assert p.contains_pt((5, 5, 0))
    assert p.contains_pt((5, 5, 1))
    assert not p.contains_pt((5, 5, 2))
    assert not p.contains_pt((15, 5, 0))

def test_corners_3d():
    p = Plane((0, 0, 0), (0, 0, 1), u_min=0, u_max=10, v_min=0, v_max=10)
    assert len(p.corners_3d()) == 4


def test_corners_3d_unbounded_empty():
    p = Plane((0, 0, 0), (0, 0, 1))
    assert p.corners_3d() == []


# ===========================================================================
# Association — add/remove
# ===========================================================================

def test_add_assoc_revision_bumps():
    p = Plane((0, 0, 0), (0, 0, 1))
    r0 = p.association_revision
    p.add_assoc("node", 1)
    assert p.association_revision == r0 + 1
    assert 1 in p.all_assoc_ids("node")


def test_add_assoc_removes_from_excluded():
    p = Plane((0, 0, 0), (0, 0, 1))
    p.remove_assoc("node", 5)
    assert p.is_excluded("node", 5)
    p.add_assoc("node", 5)
    assert not p.is_excluded("node", 5)


def test_remove_assoc_permanent():
    p = Plane((0, 0, 0), (0, 0, 1))
    p.add_assoc("node", 1)
    p.remove_assoc("node", 1)
    assert p.is_excluded("node", 1)
    assert 1 not in p.all_assoc_ids("node")


def test_remove_assoc_non_permanent():
    p = Plane((0, 0, 0), (0, 0, 1))
    p.add_assoc("node", 1)
    p.remove_assoc("node", 1, permanent=False)
    assert not p.is_excluded("node", 1)


def test_association_of_defaults_outside():
    p = Plane((0, 0, 0), (0, 0, 1))
    assert p.association_of("node", 999) == OUTSIDE


def test_association_counts():
    p = Plane((0, 0, 0), (0, 0, 1))
    p.association_status["node"][1] = ON_PLANE
    p.association_status["node"][2] = OUTSIDE
    counts = p.association_counts("node")
    assert counts[ON_PLANE] == 1
    assert counts[OUTSIDE] == 1


# ===========================================================================
# Classification
# ===========================================================================

class _FakeNode:
    def __init__(self, x, y, z):
        self._x, self._y, self._z = x, y, z
        self.unique_id = id(self)
        self.connected = []

    @property
    def x(self): return self._x

    @property
    def y(self): return self._y

    @property
    def z(self): return self._z

    @property
    def coords(self): return (self._x, self._y, self._z)


class _FakeFrame:
    def __init__(self, ni, nj):
        self.node_i = ni
        self.node_j = nj
        self.unique_id = id(self)


class _FakePoly:
    def __init__(self, nodes):
        self.nodes = nodes
        self.unique_id = id(self)


def _xy_plane_centered():
    return Plane((0, 0, 0), (0, 0, 1),
                 u_min=-10, u_max=10, v_min=-10, v_max=10,
                 depth_minus=1, depth_plus=1)


def test_classify_node_on_plane():
    p = _xy_plane_centered()
    n = _FakeNode(0, 0, 0)
    assert p.classify_element(n, "node") == ON_PLANE


def test_classify_node_within_depth():
    p = _xy_plane_centered()
    n = _FakeNode(0, 0, 0.5)
    assert p.classify_element(n, "node") == WITHIN_DEPTH


def test_classify_node_outside_depth():
    p = _xy_plane_centered()
    n = _FakeNode(0, 0, 5)
    assert p.classify_element(n, "node") == OUTSIDE


def test_classify_node_outside_bounds():
    p = _xy_plane_centered()
    n = _FakeNode(20, 0, 0)
    assert p.classify_element(n, "node") == OUTSIDE


def test_classify_frame_on_plane():
    p = _xy_plane_centered()
    f = _FakeFrame(_FakeNode(-5, 0, 0), _FakeNode(5, 0, 0))
    assert p.classify_element(f, "frame") == ON_PLANE


def test_classify_frame_intersecting():
    p = _xy_plane_centered()
    f = _FakeFrame(_FakeNode(-5, 0, -5), _FakeNode(5, 0, 5))
    assert p.classify_element(f, "frame") == INTERSECTING


def test_classify_frame_within_depth():
    p = _xy_plane_centered()
    f = _FakeFrame(_FakeNode(-5, 0, 0.5), _FakeNode(5, 0, 0.5))
    assert p.classify_element(f, "frame") == WITHIN_DEPTH


def test_classify_frame_outside():
    p = _xy_plane_centered()
    f = _FakeFrame(_FakeNode(-5, 0, 5), _FakeNode(5, 0, 5))
    assert p.classify_element(f, "frame") == OUTSIDE


def test_classify_polygon_on_plane():
    p = _xy_plane_centered()
    poly = _FakePoly([_FakeNode(-5, -5, 0), _FakeNode(5, -5, 0),
                      _FakeNode(5, 5, 0), _FakeNode(-5, 5, 0)])
    assert p.classify_element(poly, "poly") == ON_PLANE


def test_classify_polygon_outside():
    p = _xy_plane_centered()
    poly = _FakePoly([_FakeNode(100, 100, 5), _FakeNode(110, 100, 5),
                      _FakeNode(110, 110, 5), _FakeNode(100, 110, 5)])
    assert p.classify_element(poly, "poly") == OUTSIDE


def test_classify_unknown_kind_raises():
    p = _xy_plane_centered()
    with pytest.raises(ValueError):
        p.classify_element(_FakeNode(0, 0, 0), "unknown")


# ===========================================================================
# refresh_assoc
# ===========================================================================

class _FakeScene:
    def __init__(self):
        self.nodes = {}
        self.frames = {}
        self.areas = {}
        self.links = {}
        self.polygons = {}


def test_refresh_assoc_populates():
    scene = _FakeScene()
    n_in = _FakeNode(0, 0, 0)
    n_out = _FakeNode(100, 0, 0)
    scene.nodes = {n_in.unique_id: n_in, n_out.unique_id: n_out}

    p = _xy_plane_centered()
    p.refresh_assoc(scene)

    assert n_in.unique_id in p.all_assoc_ids("node")
    assert n_out.unique_id not in p.all_assoc_ids("node")
    assert p.association_of("node", n_in.unique_id) == ON_PLANE


def test_refresh_assoc_respects_excluded():
    scene = _FakeScene()
    n = _FakeNode(0, 0, 0)
    scene.nodes = {n.unique_id: n}

    p = _xy_plane_centered()
    p.remove_assoc("node", n.unique_id)
    p.refresh_assoc(scene)

    assert n.unique_id not in p.all_assoc_ids("node")


def test_refresh_assoc_skipped_when_disabled():
    scene = _FakeScene()
    n = _FakeNode(0, 0, 0)
    scene.nodes = {n.unique_id: n}

    p = _xy_plane_centered()
    p.auto_assoc = False
    p.refresh_assoc(scene)
    assert p.all_assoc_ids("node") == set()


# ===========================================================================
# Pending
# ===========================================================================

def test_add_pending_simple():
    p = Plane((0, 0, 0), (0, 0, 1))
    p.add_pending(ChangeOp.ADD, "node", 1, {"x": 0})
    assert p.is_pending("node", 1)
    assert p.pending_of("node", 1).op == ChangeOp.ADD


def test_add_pending_invalid_op():
    p = Plane((0, 0, 0), (0, 0, 1))
    with pytest.raises(ValueError):
        p.add_pending("bogus", "node", 1)


def test_add_then_modify_merges():
    p = Plane((0, 0, 0), (0, 0, 1))
    p.add_pending(ChangeOp.ADD, "node", 1, {"x": 1})
    p.add_pending(ChangeOp.MODIFY, "node", 1, {"after": {"x": 2}})
    assert p.pending_of("node", 1).data["x"] == 2


def test_add_then_delete_removes():
    p = Plane((0, 0, 0), (0, 0, 1))
    p.add_pending(ChangeOp.ADD, "node", 1, {"x": 1})
    p.add_pending(ChangeOp.DELETE, "node", 1)
    assert not p.is_pending("node", 1)


def test_modify_then_delete_becomes_delete():
    p = Plane((0, 0, 0), (0, 0, 1))
    p.add_pending(ChangeOp.MODIFY, "node", 1, {"after": {"x": 2}})
    p.add_pending(ChangeOp.DELETE, "node", 1)
    assert p.pending_of("node", 1).op == ChangeOp.DELETE


def test_modify_then_modify_keeps_before():
    p = Plane((0, 0, 0), (0, 0, 1))
    p.add_pending(ChangeOp.MODIFY, "node", 1, {"before": {"x": 0}, "after": {"x": 1}})
    p.add_pending(ChangeOp.MODIFY, "node", 1, {"before": {"x": 0}, "after": {"x": 2}})
    data = p.pending_of("node", 1).data
    assert data["before"] == {"x": 0}
    assert data["after"] == {"x": 2}


def test_delete_then_add_becomes_modify():
    p = Plane((0, 0, 0), (0, 0, 1))
    p.add_pending(ChangeOp.DELETE, "node", 1)
    p.add_pending(ChangeOp.ADD, "node", 1, {"x": 5})
    assert p.pending_of("node", 1).op == ChangeOp.MODIFY


def test_clear_pending():
    p = Plane((0, 0, 0), (0, 0, 1))
    p.add_pending(ChangeOp.ADD, "node", 1, {})
    p.clear_pending()
    assert not p.pending


# ===========================================================================
# set_bounds
# ===========================================================================

def test_set_bounds_recenter():
    p = Plane((0, 0, 0), (0, 0, 1))
    p.set_bounds(0, 10, 0, 20)
    assert np.allclose(p.origin, (5, 10, 0))
    assert p.u_min == -5 and p.u_max == 5
    assert p.v_min == -10 and p.v_max == 10


def test_set_bounds_swap():
    p = Plane((0, 0, 0), (0, 0, 1))
    p.set_bounds(10, 0, 20, 0)
    assert p.u_min < p.u_max
    assert p.v_min < p.v_max


def test_set_bounds_no_recenter():
    p = Plane((0, 0, 0), (0, 0, 1))
    p.set_bounds(0, 10, 0, 10, recenter=False)
    assert np.allclose(p.origin, (0, 0, 0))
    assert p.u_min == 0 and p.u_max == 10


# ===========================================================================
# uv_basis
# ===========================================================================

def test_uv_basis_orthonormal():
    p = Plane((1, 2, 3), (0.3, 0.4, 0.5))
    u, v, n = p.uv_basis()
    assert abs(np.dot(u, n)) < 1e-9
    assert abs(np.dot(v, n)) < 1e-9
    assert abs(np.dot(u, v)) < 1e-9
    assert abs(np.linalg.norm(n) - 1.0) < 1e-9

def test_scene_plane_assoc_no_mgr():
    from domain.scene import Scene
    from domain.project import Project
    from domain.element import Node
    from domain.plane import ON_PLANE

    proj = Project()
    proj.scene.nodes = {}
    n = Node(0, 0, 0)
    proj.scene.add_node(n)

    z0_planes = [p for p in proj.all_planes().values() if p.name.startswith("XY_Z0")]
    assert z0_planes
    plane = z0_planes[0]
    plane.refresh_assoc(proj.scene)
    assert n.unique_id in plane.all_assoc_ids("node")