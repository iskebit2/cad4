# tests/test_zone_children.py
"""Parent polygon + yön bazlı child zone'lar — izole test."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


# ============================================================================
# Minimal imgui shim (CAD4 açmadan)
# ============================================================================
@dataclass
class MockVec2:
    x: float
    y: float


@dataclass
class DrawPrimitive:
    kind: str
    points: list[tuple[float, float]]
    color: int
    thickness: float = 1.0
    text: str = ""


@dataclass
class MockDrawList:
    prims: list[DrawPrimitive] = field(default_factory=list)

    def add_line(self, p0, p1, col, thickness=1.0):
        self.prims.append(
            DrawPrimitive("line",
                          [(p0.x, p0.y), (p1.x, p1.y)],
                          int(col), thickness)
        )

    def add_quad_filled(self, p0, p1, p2, p3, col):
        self.prims.append(
            DrawPrimitive("quad",
                          [(p0.x, p0.y), (p1.x, p1.y),
                           (p2.x, p2.y), (p3.x, p3.y)],
                          int(col))
        )

    def add_convex_poly_filled(self, points, col):
        self.prims.append(
            DrawPrimitive("poly",
                          [(p.x, p.y) for p in points],
                          int(col))
        )

    def add_polyline(self, points, col, flags, thickness):
        self.prims.append(
            DrawPrimitive("polyline",
                          [(p.x, p.y) for p in points],
                          int(col), thickness)
        )

    def add_text(self, pos, col, text):
        self.prims.append(
            DrawPrimitive("text", [(pos.x, pos.y)], int(col), text=text)
        )


# ============================================================================
# Test sahnesi — parent + child zones (mock)
# ============================================================================
def build_test_polygon():
    """4x6 dikdörtgen parent + 3 zone (01) + 3 zone (02)."""
    from domain.element import Node, Polygon
    from data.enums import PolygonType

    # Parent — 4 köşe (z=0)
    n1 = Node(0,    0,    0, label="n1")
    n2 = Node(4000, 0,    0, label="n2")
    n3 = Node(4000, 6000, 0, label="n3")
    n4 = Node(0,    6000, 0, label="n4")

    poly = Polygon(
        [n1, n2, n3, n4],
        label="Cati_Sahanlik",
        poly_type=PolygonType.LOAD_AREA,
    )

    # Yön 01 zone'ları — dikey şeritler (X+ yönü)
    def znode(x, y, label=""):
        return Node(x, y, 0, label=label)

    # Zone F — sol üst
    z_F = [
        znode(0,    0, "F_a"),
        znode(1000, 0, "F_b"),
        znode(1000, 2000, "F_c"),
        znode(0,    2000, "F_d"),
    ]
    # Zone G — sol alt
    z_G = [
        znode(0,    2000, "G_a"),
        znode(1000, 2000, "G_b"),
        znode(1000, 6000, "G_c"),
        znode(0,    6000, "G_d"),
    ]
    # Zone H — sağ (kalan)
    z_H = [
        znode(1000, 0, "H_a"),
        znode(4000, 0, "H_b"),
        znode(4000, 6000, "H_c"),
        znode(1000, 6000, "H_d"),
    ]

    def zone_dict(nodes, label, cpe10, cpe1, kind, relation):
        return {
            "label": label,
            "kind": kind,
            "coords": [(n.x, n.y, n.z) for n in nodes],
            "cpe10": cpe10,
            "cpe1": cpe1,
            "pitch": 0.0,
            "table_type": "WALL",
            "wind_relation": relation,
            "skip_transfer": False,
            "label_override": None,
            "cpe10_override": None,
            "cpe1_override": None,
        }

    poly.zone_children_by_direction["01"] = [
        zone_dict(z_F, "F", (-1.2, -0.8), (-1.4, -0.9),
                  "TURBULENCE_CORNER_HIGH", "WINDWARD"),
        zone_dict(z_G, "G", (-0.9, -0.5), (-1.0, -0.6),
                  "TURBULENCE_REMAIN", "WINDWARD"),
        zone_dict(z_H, "H", (0.6, 0.3), (0.7, 0.4),
                  "ORDINARY", "LEEWARD"),
    ]

    # Yön 02 zone'ları — yatay şeritler (Y+ yönü)
    z_A = [
        znode(0,    0, "A_a"),
        znode(4000, 0, "A_b"),
        znode(4000, 2000, "A_c"),
        znode(0,    2000, "A_d"),
    ]
    z_B = [
        znode(0,    2000, "B_a"),
        znode(4000, 2000, "B_b"),
        znode(4000, 6000, "B_c"),
        znode(0,    6000, "B_d"),
    ]

    poly.zone_children_by_direction["02"] = [
        zone_dict(z_A, "A", (-1.5, -1.0), (-1.6, -1.1),
                  "TURBULENCE", "PARALLEL"),
        zone_dict(z_B, "B", (0.8, 0.5), (0.9, 0.6),
                  "ORDINARY", "WINDWARD"),
    ]

    return poly


# ============================================================================
# Render — parent + zone (yön seçili)
# ============================================================================
def draw_polygon_with_zones(dl, polygon, direction_key, to_screen):
    """Parent polygon + seçili yönün zone'larını çiz."""
    # Parent
    parent_screen = [to_screen(n.x, n.y) for n in polygon.nodes]
    imgui_points = [MockVec2(*p) for p in parent_screen]

    # Parent fill
    dl.add_convex_poly_filled(imgui_points, 0x508080C0)
    # Parent outline
    n = len(imgui_points)
    for i in range(n):
        a = imgui_points[i]
        b = imgui_points[(i + 1) % n]
        dl.add_line(a, b, 0xFFA0A0C0, 2.0)

    # Parent label
    cx = sum(p[0] for p in parent_screen) / len(parent_screen)
    cy = sum(p[1] for p in parent_screen) / len(parent_screen)
    dl.add_text(MockVec2(cx, cy - 30), 0xFFFFFFFF,
                f"{polygon.label}")

    # Zone'lar — seçili yön
    zones = polygon.zone_children_by_direction.get(direction_key, [])
    for z in zones:
        coords = z["coords"]
        zone_screen = [to_screen(x, y) for x, y, _ in coords]
        imgui_points = [MockVec2(*p) for p in zone_screen]

        # CPE işareti → renk
        cpe_min = z["cpe10"][0]
        if cpe_min >= 0:
            fill = 0x70E05050   # kırmızımsı (basınç)
            edge = 0xFFE07070
        else:
            fill = 0x7050A0E0   # mavi (emme)
            edge = 0xFF70A0E0

        dl.add_convex_poly_filled(imgui_points, fill)

        # Kenar — kesikli görünüm (kısa segmentler)
        n = len(imgui_points)
        for i in range(n):
            a = imgui_points[i]
            b = imgui_points[(i + 1) % n]
            dl.add_line(a, b, edge, 1.0)

        # Zone etiketi
        zcx = sum(p.x for p in imgui_points) / len(imgui_points)
        zcy = sum(p.y for p in imgui_points) / len(imgui_points)
        label = z.get("label_override") or z["label"]
        cpe_txt = f"{z['cpe10'][0]:.2f}/{z['cpe10'][1]:.2f}"
        dl.add_text(MockVec2(zcx - 10, zcy - 8), 0xFFFFFFFF,
                    f"{label}")
        dl.add_text(MockVec2(zcx - 20, zcy + 8), 0xFFE0E0E0,
                    cpe_txt)


def make_to_screen(canvas_w=800, canvas_h=600, zoom=0.06):
    """Plane uv → ekran."""
    cx, cy = canvas_w * 0.5, canvas_h * 0.5

    def to_screen(x, y):
        sx = cx + (x - 2000) * zoom
        sy = cy - (y - 3000) * zoom
        return sx, sy
    return to_screen


# ============================================================================
# Ana test
# ============================================================================
def run_test():
    poly = build_test_polygon()

    print("\n=== Parent Polygon ===")
    print(f"  label={poly.label}  nodes={len(poly.nodes)}  "
          f"poly_type={poly.poly_type.name}")
    print(f"  Yönler: {list(poly.zone_children_by_direction.keys())}")
    for d, zones in poly.zone_children_by_direction.items():
        print(f"    Yön {d}: {len(zones)} zone  "
              f"({[z['label'] for z in zones]})")

    to_screen = make_to_screen()

    # --- Yön 01 ---
    print("\n=== Render Yön 01 ===")
    dl1 = MockDrawList()
    draw_polygon_with_zones(dl1, poly, "01", to_screen)
    print(f"  Primitives: {len(dl1.prims)}")
    counts = {}
    for p in dl1.prims:
        counts[p.kind] = counts.get(p.kind, 0) + 1
    print(f"  {counts}")
    # İlk zone F etiketi var mı?
    texts = [p.text for p in dl1.prims if p.kind == "text"]
    print(f"  Labels: {texts[:6]}")

    # --- Yön 02 ---
    print("\n=== Render Yön 02 ===")
    dl2 = MockDrawList()
    draw_polygon_with_zones(dl2, poly, "02", to_screen)
    print(f"  Primitives: {len(dl2.prims)}")
    texts2 = [p.text for p in dl2.prims if p.kind == "text"]
    print(f"  Labels: {texts2[:6]}")

    # --- PNG ---
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import os

        out_dir = os.path.join(os.path.dirname(__file__), "out")
        os.makedirs(out_dir, exist_ok=True)

        for dir_key, dl in (("01", dl1), ("02", dl2)):
            fig, ax = plt.subplots(figsize=(10, 7.5))
            ax.set_xlim(0, 800)
            ax.set_ylim(600, 0)
            ax.set_aspect("equal")
            ax.grid(True, alpha=0.2)

            for p in dl.prims:
                if p.kind == "line":
                    (x0, y0), (x1, y1) = p.points
                    ax.plot([x0, x1], [y0, y1],
                            color="#A0A0C0", lw=p.thickness)
                elif p.kind == "poly":
                    pts = p.points + [p.points[0]]
                    xs = [q[0] for q in pts]
                    ys = [q[1] for q in pts]
                    alpha = ((p.color >> 24) & 0xFF) / 255.0
                    r = ((p.color >> 0) & 0xFF) / 255.0
                    g = ((p.color >> 8) & 0xFF) / 255.0
                    b = ((p.color >> 16) & 0xFF) / 255.0
                    ax.fill(xs, ys, alpha=alpha, color=(r, g, b))
                    ax.plot(xs, ys, color=(r, g, b), lw=0.8)
                elif p.kind == "text":
                    (x, y), = p.points
                    ax.text(x, y, p.text, fontsize=8,
                            color="#E0E0E0")

            path = os.path.join(out_dir, f"zone_children_{dir_key}.png")
            fig.savefig(path, dpi=100, facecolor="#1A1A1A")
            plt.close(fig)
            print(f"  → {path}")
    except ImportError:
        print("  matplotlib yok → PNG atlandı")

    print("\n=== Test tamam ===")


if __name__ == "__main__":
    run_test()