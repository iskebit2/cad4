# tests/test_area_winding.py
import pytest
from domain.element import Node
from tools.s2k.scene_builder import _order_polygon_nodes


def test_rectangular_butterfly_fixed():
    n0 = Node(0, 0, 0)
    n1 = Node(1, 0, 0)
    n2 = Node(0, 1, 0)
    n3 = Node(1, 1, 0)
    ordered = _order_polygon_nodes([n0, n1, n2, n3])

    coords = [(n.x, n.y) for n in ordered]
    for i in range(4):
        a = coords[i]
        b = coords[(i + 1) % 4]
        assert abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9


def test_triangle_unchanged():
    n0 = Node(0, 0, 0)
    n1 = Node(1, 0, 0)
    n2 = Node(0, 1, 0)
    ordered = _order_polygon_nodes([n0, n1, n2])
    assert ordered == [n0, n1, n2]


def test_correct_order_preserved():
    n0 = Node(0, 0, 0)
    n1 = Node(1, 0, 0)
    n2 = Node(1, 1, 0)
    n3 = Node(0, 1, 0)
    ordered = _order_polygon_nodes([n0, n1, n2, n3])
    # Açısal sıra korunur (başlangıç noktası değişebilir)
    assert len(ordered) == 4
    # Ardışık kenarlar eksenel
    coords = [(n.x, n.y) for n in ordered]
    for i in range(4):
        a = coords[i]
        b = coords[(i + 1) % 4]
        assert abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9

def test_butterfly_area_positive():
    """Sıralı dörtgen pozitif alan verir (kelebek sıfır/negatif)."""
    import numpy as np
    n0 = Node(0, 0, 0)
    n1 = Node(1, 0, 0)
    n2 = Node(0, 1, 0)
    n3 = Node(1, 1, 0)
    ordered = _order_polygon_nodes([n0, n1, n2, n3])

    pts = np.array([[n.x, n.y] for n in ordered])
    # Shoelace
    area = 0.5 * abs(sum(
        pts[i, 0] * pts[(i + 1) % 4, 1] - pts[(i + 1) % 4, 0] * pts[i, 1]
        for i in range(4)
    ))
    assert area == pytest.approx(1.0)  # dikdörtgen alanı 1