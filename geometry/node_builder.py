# geometry/node_builder.py
"""Node geometri üretici.

Node için iki ayrı iş:
  - build()              → shaded mesh (free node: küp; restraint: sembol)
  - build_simple_points() → simple mod için 1 nokta

Vertex layout her ikisinde de 9 float:
    pos3 (local) + normal3 + center3 (global)

`standard.vert` `isConstantSize=1` iken aCenter + aPos*factor hesaplar;
`isConstantSize=0` iken mvp * aPos (global) hesaplar. NodeRenderer
`isConstantSize=1` kullandığı için aPos local kalabilir.
"""
from __future__ import annotations

import math

import numpy as np

from domain.element import Node
from logging_config import CadLogger

logger = CadLogger.get(__name__)

# 9-float vertex: pos3 + normal3 + center3
_STRIDE = 9


class NodeBuilder:
    """Node mesh'i (küp veya restraint sembolleri) üretir."""

    SEGMENTS = 16   # daire sembolü için segment sayısı
    SHADED_SCALE = 10.0
    SIMPLE_SCALE = 500.0

    def __init__(self):
        self.size: float = 1.0
        self.simple_restraint_size: float = self.SIMPLE_SCALE
        self.shaded_restraint_size: float = self.SHADED_SCALE
        self.shapes: dict[str, np.ndarray] = {}
        self._rot_cache: dict[tuple[float, float, float], np.ndarray] = {}
        self._rebuild_shapes()

    # ==================================================================
    # PUBLIC
    # ==================================================================
    def set_size(self, size: float) -> bool:
        size = float(size)
        if size <= 0 or abs(self.size - size) < 1e-6:
            return False
        self.size = size
        self._rebuild_shapes()
        return True

    def set_restraint_size(self, size: float) -> bool:
        size = float(size)
        if size <= 0 or abs(self.shaded_restraint_size - size) < 1e-6 or abs(self.simple_restraint_size - size) < 1e-6:
            return False
        self.simple_restraint_size = self.SIMPLE_SCALE * size
        self.shaded_restraint_size = self.SHADED_SCALE * size
        self._rebuild_shapes()
        return True

    def build(self, node: Node) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        center = np.array([node.x, node.y, node.z], dtype=np.float32)

        vlist: list = []
        ilist: list = []

        if node.restraint is None or node.restraint.is_free():
            self._add_cube(center, vlist, ilist)
        else:
            self._add_restraint_symbols(node.restraint, center, vlist, ilist)

        if not vlist:
            empty_f = np.array([], dtype=np.float32)
            empty_u = np.array([], dtype=np.uint32)
            return empty_f, empty_f, empty_u

        vc = len(vlist) // _STRIDE
        # Base renk — gerçek renk NodeRenderer.update_colors ile uygulanır
        color = np.array([0.2, 0.2, 0.2], dtype=np.float32)
        colors = np.tile(color, (vc, 1))

        return (
            np.asarray(vlist, dtype=np.float32),
            colors,
            np.asarray(ilist, dtype=np.uint32),
        )

    def build_simple_points(self, node: Node) -> np.ndarray:
        """Simple modda node → 1 nokta (9 float)."""
        return np.array([
            node.x, node.y, node.z,
            0.0, 0.0, 1.0,
            node.x, node.y, node.z,
        ], dtype=np.float32)

    # ==================================================================
    # SHAPES
    # ==================================================================
    def _rebuild_shapes(self):
        self.shapes = self._build_shapes_for(self.size)
        self.shapes_restraint = self._build_shapes_for(self.shaded_restraint_size)

    def _build_shapes_for(self, size):
        radius = size / 2.0
        
        return {
            "triangle": np.array([
                [0.0,      radius,  0.0],
                [radius,  -radius,  0.0],
                [-radius, -radius,  0.0],
            ], dtype=np.float32),
            "square": np.array([
                [-radius,  radius, 0.0],
                [ radius,  radius, 0.0],
                [ radius, -radius, 0.0],
                [-radius, -radius, 0.0],
            ], dtype=np.float32),
            "circle": self._create_circle(radius),
        }

    def _create_circle(self, radius: float) -> np.ndarray:
        pts = [[0.0, 0.0, 0.0]]
        for i in range(self.SEGMENTS):
            a = 2.0 * math.pi * i / self.SEGMENTS
            pts.append([radius * math.cos(a), radius * math.sin(a), 0.0])
        return np.asarray(pts, dtype=np.float32)

    # ==================================================================
    # RESTRAINT SEMBOLLERI
    # ==================================================================
    def build_simple_restraint_lines(self, node: Node) -> np.ndarray:
        if node.restraint is None or node.restraint.is_free():
            return np.array([], dtype=np.float32)

        # restraint_size değerini doğrudan baz alalım (fazla küçük kalmaması için ölçekleyelim)
        s = self.simple_restraint_size * 0.5
        s_z = self.simple_restraint_size * 0.25
        cx, cy, cz = node.x, node.y, node.z

        lines: list = []   # her eleman 6 float (2 vertex × 3)

        def add_seg(a, b):
            lines.extend([
                a[0], a[1], a[2], 0.0, 0.0, 0.0,
                b[0], b[1], b[2], 0.0, 0.0, 0.0,
            ])

        r = node.restraint

        # Z ekseninde sembol
        if r.uz:
            if r.rx and r.ry and r.rz:
                # FIXED: Ters T
                add_seg((cx - s, cy, cz - s_z), (cx + s, cy, cz - s_z))
                add_seg((cx, cy, cz - s_z), (cx, cy, cz))
                add_seg((cx - s * 0.3, cy, cz - s_z * 0.5), (cx + s * 0.3, cy, cz - s_z * 0.5))
            elif not r.rx and not r.ry and not r.rz:
                # PINNED: Üçgen
                add_seg((cx - s, cy, cz - s_z), (cx + s, cy, cz - s_z))
                add_seg((cx - s, cy, cz - s_z), (cx, cy, cz))
                add_seg((cx + s, cy, cz - s_z), (cx, cy, cz))
            else:
                # ROLLER: Daire
                add_seg((cx - s, cy, cz - s_z), (cx + s, cy, cz - s_z))
                n = 16
                prev = None
                for i in range(n + 1):
                    a = 2.0 * math.pi * i / n
                    p = (cx + s * math.cos(a), cy, cz - s_z + s_z * math.sin(a))
                    if prev is not None:
                        add_seg(prev, p)
                    prev = p

        return np.array(lines, dtype=np.float32)
    
    def _add_restraint_symbols(self, restraint, center, vlist, ilist):
        symbols = self.determine_support_symbols(restraint)
        r_xy = self.shaded_restraint_size * 0.5
        r_z = self.shaded_restraint_size * 0.25
        if symbols["x"]:
            m = self._rot(90, 0, 0)
            self._add_symbol(symbols["x"], m, [0, 0, -r_z], center, vlist, ilist)
        if symbols["y"]:
            m = self._rot(90, 0, 90)
            self._add_symbol(symbols["y"], m, [0, 0, -r_z], center, vlist, ilist)
        if symbols["z"]:
            m = self._rot(0, 0, 0)
            self._add_symbol(symbols["z"], m, [0, 0, -r_z * 2], center, vlist, ilist)

    def determine_support_symbols(self, restraint) -> dict[str, str | None]:
        """Restraint → her eksende kullanılacak şekil."""
        if restraint is None:
            return {"x": None, "y": None, "z": None}

        return {
            "x": (
                "circle" if not restraint.ux
                else ("triangle" if not restraint.ry else "square")
            ),
            "y": (
                "circle" if not restraint.uy
                else ("triangle" if not restraint.rx else "square")
            ),
            "z": (
                None if not restraint.uz
                else ("square" if restraint.rz else "circle")
            ),
        }

    def _add_symbol(self, shape_name, rot, offset, center, vlist, ilist):
        shape = self.shapes_restraint[shape_name]
        rotated = shape @ rot.T
        offset_np = np.asarray(offset, dtype=np.float32)
        local = rotated + offset_np

        base = len(vlist) // _STRIDE
        n = len(local)
        if shape_name == "circle":
            normal = rot @ np.array([0.0, 0.0, 1.0], dtype=np.float32)
        else:
            normal = np.cross(rotated[1] - rotated[0], rotated[2] - rotated[0])
            normal_length = np.linalg.norm(normal)
            if normal_length > 1e-10:
                normal /= normal_length

        for p in local:
            vlist.extend((
                float(p[0]), float(p[1]), float(p[2]),
                float(normal[0]), float(normal[1]), float(normal[2]),
                float(center[0]), float(center[1]), float(center[2]),
            ))

        if shape_name == "triangle":
            ilist.extend([base, base + 1, base + 2])
        elif shape_name == "square":
            ilist.extend([base, base + 1, base + 2, base, base + 2, base + 3])
        elif shape_name == "circle":
            for i in range(1, n):
                nxt = i + 1 if i < n - 1 else 1
                ilist.extend([base, base + i, base + nxt])

    # ==================================================================
    # FREE NODE KÜPÜ
    # ==================================================================
    def _add_cube(self, center, vlist, ilist):
        half = self.size * 0.4 / 2.0

        corners = np.array([
            [-1, -1, -1], [ 1, -1, -1], [ 1,  1, -1], [-1,  1, -1],
            [-1, -1,  1], [ 1, -1,  1], [ 1,  1,  1], [-1,  1,  1],
        ], dtype=np.float32) * half

        faces = (
            (0, 1, 2, 3, (0, 0, -1)),
            (4, 5, 6, 7, (0, 0,  1)),
            (0, 4, 7, 3, (-1, 0, 0)),
            (1, 5, 6, 2, ( 1, 0, 0)),
            (0, 1, 5, 4, (0, -1, 0)),
            (3, 2, 6, 7, (0,  1, 0)),
        )

        cx, cy, cz = float(center[0]), float(center[1]), float(center[2])

        for a, b, c, d, normal in faces:
            base = len(vlist) // _STRIDE
            for idx in (a, b, c, d):
                p = corners[idx]
                vlist.extend((
                    float(p[0]), float(p[1]), float(p[2]),
                    float(normal[0]), float(normal[1]), float(normal[2]),
                    cx, cy, cz,
                ))
            ilist.extend([base, base + 1, base + 2, base, base + 2, base + 3])

    # ==================================================================
    # ROTASYON CACHE
    # ==================================================================
    def _rot(self, x_deg: float, y_deg: float, z_deg: float) -> np.ndarray:
        key = (float(x_deg), float(y_deg), float(z_deg))
        cached = self._rot_cache.get(key)
        if cached is not None:
            return cached

        rx = math.radians(x_deg)
        ry = math.radians(y_deg)
        rz = math.radians(z_deg)

        Rx = np.array([
            [1, 0, 0],
            [0, math.cos(rx), -math.sin(rx)],
            [0, math.sin(rx),  math.cos(rx)],
        ], dtype=np.float32)
        Ry = np.array([
            [ math.cos(ry), 0, math.sin(ry)],
            [ 0,            1, 0],
            [-math.sin(ry), 0, math.cos(ry)],
        ], dtype=np.float32)
        Rz = np.array([
            [math.cos(rz), -math.sin(rz), 0],
            [math.sin(rz),  math.cos(rz), 0],
            [0, 0, 1],
        ], dtype=np.float32)

        result = (Rz @ Ry @ Rx).astype(np.float32)
        self._rot_cache[key] = result
        return result
