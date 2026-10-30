# tests/test_plane2d_sections.py
"""
Izole test: CAD4 açmadan Plane2DView + SectionDrawer'ı çalıştır.

Mock DrawList — imgui_bundle çağrılarını yakalar, PNG/ASCII çıktı üretir.
Sahne: z=3000'de plane, altında kirişler (üstten), içinden geçen kolonlar (kesit).

Çalıştır:  python -m tests.test_plane2d_sections
Çıktı:     tests/out/plane2d_test.png  +  tests/out/plane2d_test.txt
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

import numpy as np

# --- CAD4 domain importları (CAD4 app'i başlatmadan) ---
from domain.element import Node, Frame
from domain.definition import Section, SectionType, Restraint
from domain.plane import Plane
from core.units import UnitSystem

# Plane2DView — bunu import edebilmek için imgui_bundle gerekli,
# ama `draw()` çağırmayacağız; sadece element çizim metotlarını
# mock draw list ile besleyeceğiz.


# ============================================================================
# MOCK DRAW LIST — ImGui bağımlılığını izole eder
# ============================================================================
@dataclass
class DrawPrimitive:
    kind: str                       # "line" | "quad" | "tri" | "circle" | "text"
    points: list[tuple[float, float]]
    color_abgr: int
    thickness: float = 1.0
    text: str = ""


@dataclass
class MockDrawList:
    prims: list[DrawPrimitive] = field(default_factory=list)

    def add_line(self, p0, p1, col, thickness=1.0):
        self.prims.append(DrawPrimitive("line", [(p0.x, p0.y), (p1.x, p1.y)],
                                        int(col), thickness))

    def add_quad_filled(self, p0, p1, p2, p3, col):
        self.prims.append(DrawPrimitive("quad",
            [(p0.x, p0.y), (p1.x, p1.y), (p2.x, p2.y), (p3.x, p3.y)],
            int(col)))

    def add_triangle_filled(self, p0, p1, p2, col):
        self.prims.append(DrawPrimitive("tri",
            [(p0.x, p0.y), (p1.x, p1.y), (p2.x, p2.y)], int(col)))

    def add_circle_filled(self, center, r, col):
        self.prims.append(DrawPrimitive("circle", [(center.x, center.y)],
                                        int(col), thickness=r))

    def add_circle(self, center, r, col, thickness=1.0):
        self.prims.append(DrawPrimitive("circle", [(center.x, center.y)],
                                        int(col), thickness=r))

    def add_text(self, pos, col, text):
        self.prims.append(DrawPrimitive("text", [(pos.x, pos.y)],
                                        int(col), text=text))


# ============================================================================
# IMGUI MOCK — ImVec2 benzeri basit vektör
# ============================================================================
@dataclass
class MockVec2:
    x: float
    y: float


class MockImgui:
    """imgui.ImVec2 yerine kullanılacak minimal shim."""
    ImVec2 = MockVec2


# ============================================================================
# SECTION DRAWER — Plane2DView'dan bağımsız test
# (gerçek dosyada ui/widgets/plane_2d_sections.py olacak)
# ============================================================================
class SectionDrawer:
    MIN_PIXEL_SIZE = 2.0

    def __init__(self):
        from geometry.profile_generator import ProfileGenerator, rotate_outline_2d
        self._gen = ProfileGenerator()
        self._rot = rotate_outline_2d

    def draw_frame(self, dl, frame, plane, to_screen, zoom, color):
        # Frame ekseni ile plane normali arasındaki açı
        p_i = np.array([frame.node_i.x, frame.node_i.y, frame.node_i.z], dtype=float)
        p_j = np.array([frame.node_j.x, frame.node_j.y, frame.node_j.z], dtype=float)
        e1 = p_j - p_i
        n_len = np.linalg.norm(e1)
        if n_len < 1e-9:
            return
        e1 /= n_len
        cos_axis_normal = abs(float(np.dot(e1, plane.normal)))

        if cos_axis_normal < 0.87:
            self._draw_beam(dl, frame, plane, to_screen, zoom, color, p_i, p_j, e1)
        else:
            self._draw_column(dl, frame, plane, to_screen, zoom, color, p_i, p_j)

    # ------------------------------------------------------------------
    def _frame_local_23(self, frame):
        axes = frame.get_local_axes()
        e2 = np.array([axes[1][0], axes[1][1], axes[1][2]])
        e3 = np.array([axes[2][0], axes[2][1], axes[2][2]])
        return e2, e3

    def _frame_effective_ends_3d(self, frame, p_i, p_j, e1):
        e2, e3 = self._frame_local_23(frame)
        # End offset along e1
        p_i = p_i + e1 * float(frame.offset_length_i or 0.0)
        p_j = p_j - e1 * float(frame.offset_length_j or 0.0)
        # Insertion offset
        oi = np.array(frame.jt_offset_i or (0.0, 0.0, 0.0), dtype=float)
        oj = np.array(frame.jt_offset_j or (0.0, 0.0, 0.0), dtype=float)
        if frame.insertion_coord_sys == "Global":
            p_i = p_i + oi
            p_j = p_j + oj
        else:
            p_i = p_i + e1 * oi[0] + e2 * oi[1] + e3 * oi[2]
            p_j = p_j + e1 * oj[0] + e2 * oj[1] + e3 * oj[2]
        return p_i, p_j

    def _section_outline_uv(self, frame, plane):
        sec = frame.section
        if sec is None:
            return None
        try:
            outline = self._gen.get_profile(sec.profile_type, sec.profile_params)
            outline = self._rot(outline, frame.rotation_deg)
        except Exception:
            return None
        e2, e3 = self._frame_local_23(frame)
        u, v = plane.u, plane.v
        M = np.array([
            [float(np.dot(e2, u)), float(np.dot(e3, u))],
            [float(np.dot(e2, v)), float(np.dot(e3, v))],
        ])
        return np.array([M @ p for p in outline]), outline

    # ------------------------------------------------------------------
    def _draw_beam(self, dl, frame, plane, to_screen, zoom, color, p_i, p_j, e1):
        off_i = float(frame.offset_length_i or 0.0)
        off_j = float(frame.offset_length_j or 0.0)
        rigid = (off_i > 0 or off_j > 0) and float(frame.rigid_factor or 0.0) >= 0.0
        # NOT: rigid_factor = 0 bile olsa görsel rigid zone çizilir;
        # sadece kullanıcı "gösterme" derse (negatif veya özel flag) atlanır.
        # Şimdilik: offset > 0 ise rigid zone her zaman çizilir.

        p_i_eff = p_i + e1 * off_i
        p_j_eff = p_j - e1 * off_j

        uv_i = plane.to_2d(p_i)
        uv_i_eff = plane.to_2d(p_i_eff)
        uv_j_eff = plane.to_2d(p_j_eff)
        uv_j = plane.to_2d(p_j)

        s_i = to_screen(*uv_i)
        s_i_eff = to_screen(*uv_i_eff)
        s_j_eff = to_screen(*uv_j_eff)
        s_j = to_screen(*uv_j)

        # --- Rigid zone: node → offset başlangıcı (koyu, kalın çizgi) ---
        if off_i > 0:
            dl.add_line(MockVec2(*s_i), MockVec2(*s_i_eff),
                        _alpha(color, 0.85), 3.0)
        if off_j > 0:
            dl.add_line(MockVec2(*s_j_eff), MockVec2(*s_j),
                        _alpha(color, 0.85), 3.0)

        # --- Serbest kiriş: offset'li uçlar arası ---
        uv_outline = self._section_outline_uv(frame, plane)
        if uv_outline is None:
            dl.add_line(MockVec2(*s_i_eff), MockVec2(*s_j_eff), color, 1.5)
            return

        uv_pts, _ = uv_outline
        w_world = max(uv_pts[:, 0].max() - uv_pts[:, 0].min(),
                    uv_pts[:, 1].max() - uv_pts[:, 1].min())
        w_px = w_world * zoom
        if w_px < self.MIN_PIXEL_SIZE:
            dl.add_line(MockVec2(*s_i_eff), MockVec2(*s_j_eff), color, 1.5)
            return

        dx = s_j_eff[0] - s_i_eff[0]
        dy = s_j_eff[1] - s_i_eff[1]
        L = math.hypot(dx, dy)
        if L < 1e-3:
            return
        ux, uy = dx / L, dy / L
        nx, ny = -uy, ux
        hw = w_px * 0.5
        c0 = (s_i_eff[0] + nx * hw, s_i_eff[1] + ny * hw)
        c1 = (s_j_eff[0] + nx * hw, s_j_eff[1] + ny * hw)
        c2 = (s_j_eff[0] - nx * hw, s_j_eff[1] - ny * hw)
        c3 = (s_i_eff[0] - nx * hw, s_i_eff[1] - ny * hw)
        fill = _alpha(color, 0.15)
        dl.add_quad_filled(MockVec2(*c0), MockVec2(*c1),
                        MockVec2(*c2), MockVec2(*c3), fill)
        for a, b in ((c0, c1), (c1, c2), (c2, c3), (c3, c0)):
            dl.add_line(MockVec2(*a), MockVec2(*b), color, 1.0)

    # ------------------------------------------------------------------
    def _draw_column(self, dl, frame, plane, to_screen, zoom, color, p_i, p_j):
        d_i = plane.distance(p_i)
        d_j = plane.distance(p_j)
        if d_i * d_j > 0:
            return
        t = d_i / (d_i - d_j)
        p_x = p_i + t * (p_j - p_i)
        uv = plane.to_2d(p_x)
        s = to_screen(*uv)

        uv_outline = self._section_outline_uv(frame, plane)
        if uv_outline is None:
            return
        uv_pts, _ = uv_outline
        size_px = max(uv_pts[:, 0].max() - uv_pts[:, 0].min(),
                      uv_pts[:, 1].max() - uv_pts[:, 1].min()) * zoom
        if size_px < self.MIN_PIXEL_SIZE:
            dl.add_circle_filled(MockVec2(*s), 3.0, color)
            return

        screen_pts = [(s[0] + p[0] * zoom, s[1] - p[1] * zoom) for p in uv_pts]
        fill = _alpha(color, 0.20)
        p0 = MockVec2(*screen_pts[0])
        for i in range(1, len(screen_pts) - 1):
            dl.add_triangle_filled(
                p0, MockVec2(*screen_pts[i]), MockVec2(*screen_pts[i + 1]), fill,
            )
        for i in range(len(screen_pts)):
            j = (i + 1) % len(screen_pts)
            dl.add_line(MockVec2(*screen_pts[i]), MockVec2(*screen_pts[j]),
                        color, 1.0)


def _alpha(col_abgr, a):
    rgb = col_abgr & 0x00FFFFFF
    alpha = int(((col_abgr >> 24) & 0xFF) * a)
    return (alpha << 24) | rgb


# ============================================================================
# TEST SAHNESİ
# ============================================================================
def build_test_scene():
    """z=3000'de plane, 4 kiriş (üstten), 2 kolon (kesit)."""
    # Kiriş kesiti: 300x500 dikdörtgen
    beam_sec = Section(
        name="B300x500",
        profile_type=SectionType.RECT,
        profile_params={"b": 300.0, "h": 500.0},
    )
    # Kolon kesiti: 400x400 kare
    col_sec = Section(
        name="C400x400",
        profile_type=SectionType.RECT,
        profile_params={"b": 400.0, "h": 400.0},
    )

    # Node'lar
    n1 = Node(0,    0,    3000); n2 = Node(4000, 0,    3000)
    n3 = Node(4000, 4000, 3000); n4 = Node(0,    4000, 3000)
    # Kolon uçları (z=0 → z=6000, plane z=3000'den geçer)
    n5 = Node(0,    0,    0);    n6 = Node(0,    0,    6000)
    n7 = Node(4000, 4000, 0);    n8 = Node(4000, 4000, 6000)

    # Kirişler — plane içinde (üstten görünür)
    beams = [
        Frame(n1, n2, beam_sec, label="B1"),
        Frame(n2, n3, beam_sec, label="B2"),
        Frame(n3, n4, beam_sec, label="B3"),
        Frame(n4, n1, beam_sec, label="B4"),
    ]
    # Kiriş B1'e end offset uygula — kolon yüzünden başlasın
    beams[0].offset_length_i = 200.0
    beams[0].offset_length_j = 200.0

    # Kolonlar — plane'e dik (kesit görünür)
    columns = [
        Frame(n5, n6, col_sec, label="C1"),
        Frame(n7, n8, col_sec, label="C2"),
    ]

    plane = Plane.from_axis_offset("z", 3000.0, name="TestPlane_z3000")
    plane.set_bounds(-3000.0, 3000.0, -3000.0, 3000.0, recenter=False)
    plane.depth_minus = 500.0
    plane.depth_plus = 500.0

    return {
        "plane": plane,
        "beams": beams,
        "columns": columns,
        "nodes": [n1, n2, n3, n4, n5, n6, n7, n8],
    }


# ============================================================================
# MOCK to_screen — plane uv → ekran (basit ölçek)
# ============================================================================
def make_to_screen(canvas_w=800, canvas_h=600, zoom=0.05,
                   center_uv=(0.0, 0.0)):
    """Plane uv → ekran; ekran merkezi center_uv'ye denk gelir."""
    cx, cy = canvas_w * 0.5, canvas_h * 0.5
    uc, vc = center_uv

    def to_screen(u, v):
        sx = cx + (u - uc) * zoom
        sy = cy - (v - vc) * zoom   # ekran Y ters
        return sx, sy
    return to_screen


# ============================================================================
# ÇİZİMİ ÇALIŞTIR + PNG/ASCII KAYDET
# ============================================================================
def run_test():
    scene = build_test_scene()
    plane = scene["plane"]

    dl = MockDrawList()
    drawer = SectionDrawer()
    to_screen = make_to_screen(canvas_w=800, canvas_h=600, zoom=0.05)

    FRAME_COL = 0xFFB0B0B0

    print("\n=== Test sahnesi ===")
    print(f"Plane: {plane.name}, origin={plane.origin}, normal={plane.normal}")
    print(f"  bounds u=[{plane.u_min},{plane.u_max}], "
          f"v=[{plane.v_min},{plane.v_max}], "
          f"depth=[-{plane.depth_minus},+{plane.depth_plus}]")

    # Kirişler
    for f in scene["beams"]:
        drawer.draw_frame(dl, f, plane, to_screen, zoom=0.05, color=FRAME_COL)
        print(f"  Kiriş: {f.label} offset_i={f.offset_length_i} "
              f"offset_j={f.offset_length_j}")

    # Kolonlar
    for f in scene["columns"]:
        drawer.draw_frame(dl, f, plane, to_screen, zoom=0.05, color=FRAME_COL)
        print(f"  Kolon: {f.label}")

    print(f"\nDraw primitives: {len(dl.prims)}")
    counts = {}
    for p in dl.prims:
        counts[p.kind] = counts.get(p.kind, 0) + 1
    print(f"  {counts}")

    # --- PNG (matplotlib varsa) ---
    out_dir = os.path.join(os.path.dirname(__file__), "out")
    os.makedirs(out_dir, exist_ok=True)
    png_path = os.path.join(out_dir, "plane2d_test.png")
    txt_path = os.path.join(out_dir, "plane2d_test.txt")

    # ASCII/JSON özet
    with open(txt_path, "w", encoding="utf-8") as fh:
        fh.write(f"Plane: {plane.name}\n")
        fh.write(f"Prims: {len(dl.prims)}  {counts}\n\n")
        for i, p in enumerate(dl.prims):
            fh.write(f"[{i:03d}] {p.kind:6s} col=0x{p.color_abgr:08X} "
                     f"thick={p.thickness:.2f} {p.text}\n")
            for pt in p.points:
                fh.write(f"       ({pt[0]:.1f}, {pt[1]:.1f})\n")
    print(f"  → {txt_path}")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 7.5))
        ax.set_xlim(0, 800); ax.set_ylim(600, 0)   # Y ters
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.2)

        for p in dl.prims:
            if p.kind == "line":
                (x0, y0), (x1, y1) = p.points
                ax.plot([x0, x1], [y0, y1], color="#B0B0B0",
                        lw=max(p.thickness, 0.5))
            elif p.kind == "quad":
                pts = p.points + [p.points[0]]
                xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
                ax.fill(xs, ys, alpha=0.3, color="#88BBFF")
                ax.plot(xs, ys, color="#B0B0B0", lw=0.8)
            elif p.kind == "tri":
                xs = [q[0] for q in p.points]; ys = [q[1] for q in p.points]
                ax.fill(xs, ys, alpha=0.3, color="#FFBB88")
            elif p.kind == "circle":
                (cx_, cy_), = p.points
                ax.add_patch(plt.Circle((cx_, cy_), p.thickness,
                                        fill=False, color="#B0B0B0"))
            elif p.kind == "text":
                (x, y), = p.points
                ax.text(x, y, p.text, fontsize=8, color="#E0E0E0")

        fig.savefig(png_path, dpi=120, facecolor="#1A1A1A")
        plt.close(fig)
        print(f"  → {png_path}")
    except ImportError:
        print("  matplotlib yok → PNG atlandı")

    return dl


if __name__ == "__main__":
    run_test()