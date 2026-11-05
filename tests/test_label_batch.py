# tests/test_label_batch.py
import numpy as np
import pytest
from pyglm import glm

from render.label_batch import LabelBatch
from render.gl_utils import mat4_data


def test_mat4_data_copies_pyglm_matrix_values():
    matrix = glm.translate(glm.mat4(1.0), glm.vec3(3.0, 4.0, 5.0))
    data = mat4_data(matrix)
    assert data.dtype == np.float32
    assert np.allclose(data[12:15], (3.0, 4.0, 5.0))


class _FakeGlyph:
    def __init__(self, advance=10.0, bearing_x=1.0, bearing_y=2.0,
                 width=8.0, height=12.0, u0=0.0, u1=0.1, v0=0.0, v1=0.1):
        self.advance = advance
        self.bearing_x = bearing_x
        self.bearing_y = bearing_y
        self.width = width
        self.height = height
        self.u0, self.u1 = u0, u1
        self.v0, self.v1 = v0, v1


class _FakeAtlas:
    def __init__(self):
        self.glyphs = {c: _FakeGlyph() for c in "ABC "}
        self.size = 32
        self.line_height = 40
        self.texture_id = 0
    def upload(self): pass


def _batch():
    b = LabelBatch(_FakeAtlas())
    b.init_gl_patches = None  # init_gl çağrılmaz
    # LUT manuel kur (init_gl GL ister, _lut değil)
    b._lut()
    # Buffer manuel oluştur
    b.capacity_quads = b.INITIAL_QUADS
    b.buf = np.zeros(b.capacity_quads * b.FLOATS_PER_QUAD, dtype=np.float32)
    return b


def test_lut_fills_glyph_metrics():
    b = _batch()
    o = ord("A")
    assert b.lut["advance"][o] == 10.0
    assert b.lut["width"][o] == 8.0


def test_unit_normalizes():
    v = LabelBatch._unit((3, 4, 0))
    assert np.allclose(v, (0.6, 0.8, 0))


def test_unit_fallback_zero():
    v = LabelBatch._unit((0, 0, 0))
    assert np.allclose(v, (1, 0, 0))


def test_anchor_k_center():
    b = _batch()
    kx, ky = b._anchor_k(["center", "bottom-left"], 2)
    assert kx[0] == -0.5 and ky[0] == -0.5
    assert kx[1] == 0.0 and ky[1] == 0.0


def test_add_many_billboard_writes_vertices():
    b = _batch()
    b.begin(mode="billboard", cam_pos=(0, 0, 1000), screen_h=1080,
            fov_y_rad=np.deg2rad(45))
    b.add_many(
        positions=[(0, 0, 0)],
        texts=["A"],
        colors=[(1, 1, 1, 1)],
        pixel_sizes=[14.0],
    )
    assert b.write_offset == 6  # 1 char × 6 vertex


def test_add_many_world_writes_vertices():
    b = _batch()
    b.begin(mode="world", mvp=None)
    b.add_many(
        positions=[(0, 0, 0)],
        texts=["ABC"],
        colors=[(1, 0, 0, 1)],
        pixel_sizes=[14.0],
        size_world=200.0,
        u_axis=(1, 0, 0),
        v_axis=(0, 1, 0),
    )
    assert b.write_offset == 18  # 3 char × 6 vertex


def test_add_many_world_scalar_size_broadcast():
    # 0-d array bug regresyon testi
    b = _batch()
    b.begin(mode="world", mvp=None)
    b.add_many(
        positions=[(0, 0, 0)],
        texts=["AB"],
        colors=[(1, 1, 1, 1)],
        pixel_sizes=[14.0],
        size_world=250.0,   # skalar
    )
    assert b.write_offset == 12


def test_add_many_multiple_labels_positions():
    b = _batch()
    b.begin(mode="world", mvp=None)
    b.add_many(
        positions=[(0, 0, 0), (100, 0, 0)],
        texts=["A", "BB"],
        colors=[(1, 1, 1, 1), (0, 1, 0, 1)],
        pixel_sizes=[14.0, 14.0],
        size_world=200.0,
    )
    assert b.write_offset == 18  # 1 + 2 = 3 char


def test_add_many_empty_texts_noop():
    b = _batch()
    b.begin(mode="world", mvp=None)
    b.add_many(
        positions=[(0, 0, 0)],
        texts=[""],
        colors=[(1, 1, 1, 1)],
        pixel_sizes=[14.0],
        size_world=200.0,
    )
    assert b.write_offset == 0


def test_begin_resets_offset():
    b = _batch()
    b.begin(mode="world")
    b.add_many(
        positions=[(0, 0, 0)], texts=["A"],
        colors=[(1, 1, 1, 1)], pixel_sizes=[14.0],
        size_world=200.0,
    )
    assert b.write_offset > 0
    b.begin(mode="world")
    assert b.write_offset == 0


def test_grow_expands_buffer():
    b = _batch()
    b._buffers = lambda cap: setattr(b, "capacity_quads", cap)
    old_cap = b.capacity_quads
    b._grow(old_cap * 2)
    assert b.capacity_quads >= old_cap * 2
    assert b.buf.shape[0] == b.capacity_quads * b.FLOATS_PER_QUAD


def test_add_wrapper_forwards_args():
    b = _batch()
    b.begin(mode="world")
    b.add(world_pos=(0, 0, 0), text="A",
          color=(1, 1, 1, 1), pixel_size=14.0,
          size_world=200.0, u_axis=(1, 0, 0), v_axis=(0, 1, 0))
    assert b.write_offset == 6


def test_anchor_array_path():
    b = _batch()
    b.begin(mode="world")
    b.add_many(
        positions=[(0, 0, 0), (1, 0, 0)],
        texts=["A", "B"],
        colors=[(1, 1, 1, 1)] * 2,
        pixel_sizes=[14.0] * 2,
        anchors=["center", "bottom-left"],
        size_world=200.0,
    )
    assert b.write_offset == 12