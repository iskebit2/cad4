# tests/test_grid.py
import math
from types import SimpleNamespace

import numpy as np
import pytest

from domain.grid import Grid, Axis, ObliqueAxis
from render.grid_renderer import GridRenderer, BubbleRenderer, _line, _dash_dot
from render.presentationrenderer import PresentationRenderer


# ===========================================================================
# Domain (mevcut 25 test)
# ===========================================================================

def test_default_grid():
    g = Grid()
    assert g.x_coords == [0.0, 4000.0, 8000.0]
    assert g.x_labels == ["X1", "X2", "X3"]


def test_empty_grid_does_not_crash():
    g = Grid(x_coords=[], y_coords=[], z_coords=[])
    assert g.axes


def test_presentation_renderer_binds_grid_from_project():
    grid = Grid()

    class GridRendererStub:
        grid = None

        def set_grid(self, value):
            self.grid = value

    renderer = PresentationRenderer.__new__(PresentationRenderer)
    renderer.grid = GridRendererStub()
    scene = SimpleNamespace(project=SimpleNamespace(grid=grid))
    renderer._bind_grid(scene)
    assert renderer.grid.grid is grid


def test_ortho_axes_counts():
    g = Grid(x_coords=[0, 4000, 8000], y_coords=[0, 5000], z_coords=[0])
    assert len([a for a in g.axes if a.kind == "ortho_x"]) == 3
    assert len([a for a in g.axes if a.kind == "ortho_y"]) == 2


def test_ortho_axis_geometry():
    g = Grid(x_coords=[0, 8000], y_coords=[0, 10000], z_coords=[0])
    a = next(a for a in g.axes if a.kind == "ortho_x" and a.origin[0] == 0.0)
    assert a.direction == (0.0, 1.0, 0.0)
    assert a.length == 5000.0


def test_axis_labels_fallback():
    g = Grid(x_coords=[0, 4000], y_coords=[0, 5000], z_coords=[0])
    xs = [a for a in g.axes if a.kind == "ortho_x" and a.label]
    assert xs[0].label == "X1" and xs[1].label == "X2"


def test_axis_labels_custom():
    g = Grid(x_coords=[0, 4000], y_coords=[0, 5000], z_coords=[0],
             x_labels=["A", "B"])
    xs = sorted([a for a in g.axes if a.kind == "ortho_x"], key=lambda a: a.origin[0])
    assert xs[0].label == "A" and xs[1].label == "B"


def test_label_only_on_first_z():
    g = Grid(x_coords=[0, 4000], y_coords=[0, 5000], z_coords=[0, 3000])
    labeled = [a for a in g.axes if a.kind == "ortho_x" and a.label]
    assert len(labeled) == 2
    assert all(a.origin[2] == 0.0 for a in labeled)


def test_z_axes_skip_bubble():
    g = Grid(x_coords=[0, 4000], y_coords=[0, 5000], z_coords=[0, 3000])
    zs = [a for a in g.axes if a.kind == "ortho_z"]
    assert len(zs) == 4 and all(a.skip_bubble for a in zs)


def _square():
    return [(0, 0), (10000, 0), (10000, 10000), (0, 10000)]


def test_boundary_contains():
    g = Grid(boundary_coords=_square())
    assert g._in_boundary(5000, 5000)
    assert not g._in_boundary(15000, 5000)


def test_boundary_edge_is_inside():
    g = Grid(boundary_coords=_square())
    assert g._in_boundary(0, 5000)
    assert g._in_boundary(5000, 0)
    assert g._in_boundary(0, 0)


def test_boundary_clips_ortho_x():
    g = Grid(x_coords=[0, 5000, 10000], y_coords=[0, 5000, 10000],
             z_coords=[0], boundary_coords=_square())
    assert all(a.length == 5000.0 for a in g.axes if a.kind == "ortho_x")


def test_boundary_skips_outside_x():
    g = Grid(x_coords=[0, 9000], y_coords=[0, 5000], z_coords=[0],
             boundary_coords=[(0, 0), (10000, 0), (0, 10000)])
    ax = [a for a in g.axes if a.kind == "ortho_x" and a.origin[0] == 9000.0]
    assert len(ax) == 1 and ax[0].length < 1000.0


def test_boundary_axes_generated():
    g = Grid(x_coords=[0, 10000], y_coords=[0, 10000], z_coords=[0],
             boundary_coords=_square())
    assert len([a for a in g.axes if a.kind == "boundary" and not a.skip_bubble]) == 4


def test_boundary_vertical_corners_when_multiple_z():
    g = Grid(x_coords=[0, 10000], y_coords=[0, 10000], z_coords=[0, 3000],
             boundary_coords=_square())
    bz = [a for a in g.axes if a.name.startswith("BZ_")]
    assert len(bz) == 4 and all(a.skip_bubble for a in bz)


def test_oblique_basic():
    g = Grid(x_coords=[0, 10000], y_coords=[0, 10000], z_coords=[0])
    g.oblique_axes.append(ObliqueAxis(name="E1", p1=(0, 0), p2=(10000, 10000)))
    a = next(a for a in g.axes if a.kind == "oblique")
    assert a.label == "E1"
    assert abs(a.direction[0] - math.sqrt(0.5)) < 1e-6


def test_oblique_hidden():
    g = Grid(x_coords=[0, 10000], y_coords=[0, 10000], z_coords=[0])
    g.oblique_axes.append(ObliqueAxis(name="E1", p1=(0, 0), p2=(10000, 10000),
                                       visible=False))
    assert not [a for a in g.axes if a.kind == "oblique"]


def test_oblique_clipped_by_boundary():
    g = Grid(x_coords=[0, 10000], y_coords=[0, 10000], z_coords=[0],
             boundary_coords=[(0, 0), (5000, 0), (5000, 5000), (0, 5000)])
    g.oblique_axes.append(ObliqueAxis(name="E1", p1=(0, 0), p2=(10000, 10000)))
    a = next(a for a in g.axes if a.kind == "oblique")
    assert a.length < 4000.0


def test_snap_ortho_intersections():
    g = Grid(x_coords=[0, 4000], y_coords=[0, 5000], z_coords=[0])
    pts = g.snap_points()
    assert len(pts) == 4 and (0, 0, 0) in pts and (4000, 5000, 0) in pts


def test_snap_respects_boundary():
    g = Grid(x_coords=[0, 5000, 10000], y_coords=[0, 5000, 10000],
             z_coords=[0],
             boundary_coords=[(0, 0), (5000, 0), (5000, 5000), (0, 5000)])
    for p in g.snap_points():
        assert g._in_boundary(p[0], p[1])


def test_snap_deduplicates():
    g = Grid(x_coords=[0, 4000], y_coords=[0, 5000], z_coords=[0])
    pts = g.snap_points()
    assert len(pts) == len(set(pts))


def test_snap_with_oblique_crossing():
    g = Grid(x_coords=[0, 10000], y_coords=[0, 10000], z_coords=[0])
    g.oblique_axes.append(ObliqueAxis(name="E1", p1=(0, 5000), p2=(10000, 5000)))
    assert any(abs(p[1] - 5000) < 1e-6 for p in g.snap_points())


def test_snap_single_z():
    g = Grid(x_coords=[0, 4000], y_coords=[0, 5000], z_coords=[0, 3000, 6000])
    assert all(p[2] == 3000 for p in g.snap_points(z_level=3000))


def test_bounds():
    g = Grid(x_coords=[0, 8000], y_coords=[0, 10000], z_coords=[0, 4000])
    center, size = g.get_bounds()
    assert center == (4000.0, 5000.0, 2000.0) and size > 10000


def test_axes_rebuilt_each_access():
    g = Grid()
    a1 = g.axes
    g.x_coords = [0, 1000]
    assert len(a1) != len(g.axes)


# ===========================================================================
# Renderer — saf fonksiyonlar (GL yok)
# ===========================================================================

def test_line_pushes_2_vertices():
    out = []
    _line(out, (0, 0, 0), (100, 0, 0), (1.0, 0.5, 0.2))
    assert len(out) == 12
    assert out[:3] == [0, 0, 0]
    assert out[6:9] == [100, 0, 0]


def test_dash_dot_alternates_dash_and_dot():
    out = []
    _dash_dot(out, (0, 0, 0), (1000, 0, 0), (1, 1, 1))
    segs = len(out) // 12
    assert segs >= 2
    assert segs % 2 == 0


def test_dash_dot_degenerate():
    out = []
    _dash_dot(out, (5, 5, 0), (5, 5, 0), (1, 1, 1))
    assert len(out) == 12


def test_perp_is_unit_and_orthogonal():
    d = np.array([0.0, 1.0, 0.0])
    p = GridRenderer._perp(d)
    assert abs(np.linalg.norm(p) - 1.0) < 1e-6
    assert abs(np.dot(p, d)) < 1e-6


def test_perp_fallback_when_parallel_z():
    p = GridRenderer._perp(np.array([0.0, 0.0, 1.0]))
    assert abs(np.linalg.norm(p) - 1.0) < 1e-6


# ===========================================================================
# Renderer — GridRenderer (GL'siz rebuild)
# ===========================================================================

class _FakeShader:
    def use(self): pass
    def get_loc(self, name): return -1


class _FakeBuffer:
    def __init__(self):
        self.verts = []
    def upload(self, v):
        self.verts = v
        return len(v) // 6
    def cleanup(self): pass
    def draw(self, *a, **k): pass


def _renderer_with(grid):
    r = GridRenderer(_FakeShader())
    r._buf = _FakeBuffer()
    r.set_grid(grid)
    r._rebuild()
    return r


def test_rebuild_emits_lines_for_default():
    r = _renderer_with(Grid(x_coords=[0, 4000], y_coords=[0, 5000], z_coords=[0]))
    assert r._count > 0
    assert r._dirty is False


def test_rebuild_empty_grid():
    r = _renderer_with(None)
    assert r._count == 0


def test_rebuild_skips_hidden_oblique():
    g = Grid(x_coords=[0, 10000], y_coords=[0, 10000], z_coords=[0])
    g.oblique_axes.append(ObliqueAxis(name="E1", p1=(0, 0), p2=(10000, 10000),
                                       visible=False))
    r1 = _renderer_with(g)
    g.oblique_axes[0].visible = True
    r2 = _renderer_with(g)
    assert r2._count > r1._count


def test_rebuild_parallel_offsets_increase_count():
    g = Grid(x_coords=[0, 4000], y_coords=[0, 5000], z_coords=[0])
    r1 = _renderer_with(g)
    for a in g.axes:
        a.parallel_spacing = 200.0
        a.parallel_count = 2
    g2 = Grid(x_coords=[0, 4000], y_coords=[0, 5000], z_coords=[0])
    for a in g2.axes:
        a.parallel_spacing = 200.0
        a.parallel_count = 2
    r2 = _renderer_with(g2)
    assert r2._count >= r1._count


# ===========================================================================
# Renderer — get_label_anchors
# ===========================================================================

def test_label_anchors_skip_z_and_boundary_verticals():
    g = Grid(x_coords=[0, 4000], y_coords=[0, 5000], z_coords=[0, 3000],
             boundary_coords=_square())
    r = GridRenderer(_FakeShader())
    r.set_grid(g)
    anchors = r.get_label_anchors()
    assert anchors
    for a in anchors:
        assert a["text"] or a["kind"] != "ortho_z"


def test_label_anchor_ortho_x_leader_along_y():
    g = Grid(x_coords=[0, 4000], y_coords=[0, 5000], z_coords=[0])
    r = GridRenderer(_FakeShader())
    r.set_grid(g)
    ax = next(a for a in r.get_label_anchors() if a["kind"] == "ortho_x")
    assert ax["direction_world"] == (0.0, 1.0, 0.0)
    assert ax["plane_normal"] == (0.0, 0.0, 1.0)


def test_label_anchor_ortho_y_leader_along_x():
    g = Grid(x_coords=[0, 4000], y_coords=[0, 5000], z_coords=[0])
    r = GridRenderer(_FakeShader())
    r.set_grid(g)
    ax = next(a for a in r.get_label_anchors() if a["kind"] == "ortho_y")
    assert ax["direction_world"] == (1.0, 0.0, 0.0)


def test_label_anchor_position_at_end():
    g = Grid(x_coords=[0, 8000], y_coords=[0, 10000], z_coords=[0])
    r = GridRenderer(_FakeShader())
    r.set_grid(g)
    ax = next(a for a in r.get_label_anchors()
              if a["kind"] == "ortho_x" and a["anchor"][0] == 0.0)
    assert ax["anchor"][1] == 10000.0
    assert ax["anchor"][2] == 0.0


def test_label_anchor_text_width_zero_for_empty():
    g = Grid(x_coords=[0, 4000], y_coords=[0, 5000], z_coords=[0])
    r = GridRenderer(_FakeShader())
    r.set_grid(g)
    for a in r.get_label_anchors():
        if not a["text"]:
            assert a["text_world_width"] == 0.0


def test_label_anchor_oblique_leader_along_direction():
    g = Grid(x_coords=[0, 10000], y_coords=[0, 10000], z_coords=[0])
    g.oblique_axes.append(ObliqueAxis(name="E1", p1=(0, 0), p2=(10000, 10000)))
    r = GridRenderer(_FakeShader())
    r.set_grid(g)
    ax = next(a for a in r.get_label_anchors() if a["kind"] == "oblique")
    assert abs(ax["direction_world"][0] - ax["direction_world"][1]) < 1e-6


def test_label_anchor_boundary_outward():
    g = Grid(x_coords=[0, 10000], y_coords=[0, 10000], z_coords=[0],
             boundary_coords=_square())
    r = GridRenderer(_FakeShader())
    r.set_grid(g)
    cx, cy = 5000.0, 5000.0
    for a in r.get_label_anchors():
        if a["kind"] != "boundary":
            continue
        d = np.asarray(a["direction_world"])
        anchor = np.asarray(a["anchor"])
        outward = anchor[:2] - np.array([cx, cy])
        assert np.dot(d[:2], outward) >= -1e-6


# ===========================================================================
# BubbleRenderer
# ===========================================================================

def test_bubble_add_returns_geometry():
    br = BubbleRenderer(_FakeShader())
    br.begin()
    info = br.add(
        anchor=(0, 0, 0), direction=(0, 1, 0), normal=(0, 0, 1),
        text_width=2000.0, color=(1, 0.5, 0.2),
    )
    assert set(info) == {"center", "u_axis", "v_axis", "normal"}
    assert np.linalg.norm(info["u_axis"]) == pytest.approx(1.0, abs=1e-6)
    assert np.linalg.norm(info["v_axis"]) == pytest.approx(1.0, abs=1e-6)


def test_bubble_center_along_direction():
    br = BubbleRenderer(_FakeShader())
    br.begin()
    info = br.add(
        anchor=(0, 0, 0), direction=(0, 1, 0), normal=(0, 0, 1),
        text_width=0.0, color=(1, 1, 1), leader_len=1000.0,
    )
    assert info["center"][1] > 1000.0
    assert abs(info["center"][0]) < 1e-9


def test_bubble_center_does_not_depend_on_text_width():
    br = BubbleRenderer(_FakeShader())
    narrow = br.add(
        anchor=(0, 0, 0), direction=(0, 1, 0), normal=(0, 0, 1),
        text_width=100.0, color=(1, 1, 1), leader_len=400.0,
    )
    br.begin()
    wide = br.add(
        anchor=(0, 0, 0), direction=(0, 1, 0), normal=(0, 0, 1),
        text_width=2000.0, color=(1, 1, 1), leader_len=400.0,
    )
    assert np.allclose(narrow["center"], wide["center"])


def test_bubble_discards_alpha_for_rgb_vertex_buffer():
    br = BubbleRenderer(_FakeShader())
    br.add(
        anchor=(0, 0, 0), direction=(0, 1, 0), normal=(0, 0, 1),
        text_width=500.0, color=(1, 0.5, 0.2, 1.0),
    )
    assert len(br._bubbles[0]["color"]) == 3
    assert len(br._leaders[0]["color"]) == 3


def test_bubble_leader_recorded():
    br = BubbleRenderer(_FakeShader())
    br.begin()
    br.add(anchor=(10, 20, 0), direction=(1, 0, 0), normal=(0, 0, 1),
           text_width=500.0, color=(1, 1, 1), leader_len=400.0)
    assert len(br._leaders) == 1
    assert tuple(br._leaders[0]["from"]) == (10, 20, 0)


def test_bubble_perpendicular_to_direction():
    br = BubbleRenderer(_FakeShader())
    br.begin()
    info = br.add(anchor=(0, 0, 0), direction=(1, 0, 0), normal=(0, 0, 1),
                  text_width=1000.0, color=(1, 1, 1))
    assert abs(np.dot(info["u_axis"], info["v_axis"])) < 1e-6


def test_bubble_label_axes_match_plane_normal_handedness():
    br = BubbleRenderer(_FakeShader())
    info = br.add(
        anchor=(0, 0, 0), direction=(0, 1, 0), normal=(0, 0, 1),
        text_width=1000.0, color=(1, 1, 1),
    )
    assert np.allclose(info["u_axis"], (1, 0, 0))
    assert np.allclose(np.cross(info["u_axis"], info["v_axis"]), info["normal"])


def test_bubble_outline_closed_loop():
    br = BubbleRenderer(_FakeShader())
    br.begin()
    br.add(anchor=(0, 0, 0), direction=(0, 1, 0), normal=(0, 0, 1),
           text_width=1000.0, color=(1, 1, 1))
    pts = br._outline(br._bubbles[0])
    assert len(pts) == 2 * (BubbleRenderer.ARC_SEG + 1)


def test_bubble_outline_radius_and_half_length():
    br = BubbleRenderer(_FakeShader())
    br.begin()
    br.add(anchor=(0, 0, 0), direction=(0, 1, 0), normal=(0, 0, 1),
           text_width=1000.0, color=(1, 1, 1), leader_len=0.0)
    b = br._bubbles[0]
    pts = br._outline(b)
    us = [np.dot(p - b["center"], b["u"]) for p in pts]
    assert max(us) == pytest.approx(b["hl"] + b["r"], abs=1.0)
    assert min(us) == pytest.approx(-(b["hl"] + b["r"]), abs=1.0)


def test_bubble_norm_fallback():
    assert BubbleRenderer._norm((0, 0, 0), (1, 0, 0)).tolist() == [1.0, 0.0, 0.0]


# ===========================================================================
# GridRenderer — mark_dirty akışı
# ===========================================================================

def test_mark_dirty_triggers_rebuild():
    r = _renderer_with(Grid())
    assert r._dirty is False
    r.mark_dirty()
    assert r._dirty is True


def test_set_grid_triggers_dirty():
    r = GridRenderer(_FakeShader())
    assert r._dirty is True
    r.set_grid(Grid())
    assert r._dirty is True