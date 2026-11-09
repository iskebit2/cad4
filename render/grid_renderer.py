# render/grid_renderer.py
from __future__ import annotations

import ctypes
import math

import numpy as np
from OpenGL.GL import *

from render.gl_utils import mat4_data


class _GLBuffer:
    STRIDE = 24

    def __init__(self):
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, self.STRIDE, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, self.STRIDE, ctypes.c_void_p(12))
        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

    def upload(self, verts: list[float]) -> int:
        data = np.asarray(verts, dtype=np.float32)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_DYNAMIC_DRAW)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        return data.size // 6

    def draw(self, mode, count, offset=0):
        if count <= 0:
            return
        glBindVertexArray(self.vao)
        glDrawArrays(mode, offset, count)
        glBindVertexArray(0)

    def cleanup(self):
        glDeleteVertexArrays(1, [self.vao])
        glDeleteBuffers(1, [self.vbo])


def _line(out, a, b, color):
    out += [a[0], a[1], a[2], *color, b[0], b[1], b[2], *color]


def _dash_dot(out, a, b, color):
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    v = b - a
    L = float(np.linalg.norm(v))
    if L < 1e-6:
        _line(out, a, b, color)
        return
    u = v / L
    step = 300.0 + 80.0 + 40.0 + 80.0
    t = 0.0
    while t < L:
        for seg, off in ((300.0, 0.0), (40.0, 380.0)):
            s = t + off
            e = min(L, s + seg)
            if e > s:
                _line(out, a + u * s, a + u * e, color)
        t += step


class GridRenderer:
    ALPHA = 0.6

    def __init__(self, shader):
        self.shader = shader
        self.grid = None
        self._custom_axes = None  # Dışarıdan gelen filtrelenmiş akslar için
        self._buf = None
        self._count = 0
        self._dirty = True

    def set_grid(self, grid):
        self.grid = grid
        self._custom_axes = None
        self._dirty = True

    def set_axes(self, axes):
        """Proje seviyesinden gelen filtrelenmiş aksları doğrudan set eder."""
        self._custom_axes = axes
        self._dirty = True

    def mark_dirty(self):
        self._dirty = True

    def _get_axes(self):
        if self._custom_axes is not None:
            return self._custom_axes
        if self.grid is not None:
            return list(self.grid.visible_axes())
        return []

    def draw(self, mvp):
        if self._dirty:
            self._rebuild()
        if not self._count:
            return
        self._bind(mvp)
        self._buf.draw(GL_LINES, self._count)

    def _bind(self, mvp):
        self.shader.use()
        loc = self.shader.get_loc("mvp")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, mat4_data(mvp))
        loc = self.shader.get_loc("alpha")
        if loc != -1:
            glUniform1f(loc, self.ALPHA)

    def _rebuild(self):
        self._dirty = False
        axes = self._get_axes()
        if not axes:
            self._count = 0
            return
        verts: list[float] = []
        for axis in axes:
            d = axis.normalized_direction()
            o = np.asarray(axis.origin, float)
            h = axis.length
            p0, p1 = o - d * h, o + d * h
            _dash_dot(verts, p0, p1, axis.color)
            if axis.parallel_spacing > 0 and axis.parallel_count > 0:
                perp = self._perp(d)
                for i in range(-axis.parallel_count, axis.parallel_count + 1):
                    if i:
                        off = perp * (i * axis.parallel_spacing)
                        _dash_dot(verts, p0 + off, p1 + off, axis.color)
        if not verts:
            self._count = 0
            return
        if self._buf is None:
            self._buf = _GLBuffer()
        self._count = self._buf.upload(verts)

    @staticmethod
    def _perp(d):
        ref = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        p = np.cross(d, ref)
        n = np.linalg.norm(p)
        return p / n if n > 1e-9 else np.array([1.0, 0.0, 0.0])

    def get_label_anchors(self):
        out = []
        for a in self._get_axes():
            if a.skip_bubble:
                continue
            d = a.normalized_direction()
            anchor = np.asarray(a.origin, float) + d * a.length
            leader, normal = self._leader(a, d)
            out.append({
                        "anchor": tuple(anchor),
                        "direction_world": tuple(leader),
                        "plane_normal": tuple(normal),
                        "text": a.label,
                        "text_world_width": len(a.label) * 260.0,
                        "color": a.color,
                        "kind": a.kind,
                    })
        return out

    def _leader(self, a, d):
        if a.kind == "ortho_x":
            return np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0])
        if a.kind == "ortho_y":
            return np.array([1.0, 0.0, 0.0]), np.array([0.0, 0.0, 1.0])
        if a.kind == "boundary":
            perp = np.array([-d[1], d[0], 0.0])
            if self.grid and self.grid.boundary_coords:
                c = np.mean(self.grid.boundary_coords, axis=0)
                if np.dot(perp[:2], np.asarray(a.origin)[:2] - c[:2]) < 0:
                    perp = -perp
            return perp, np.array([0.0, 0.0, 1.0])
        return d, np.array([0.0, 0.0, 1.0])

    def cleanup(self):
        if self._buf:
            self._buf.cleanup()
            self._buf = None
        self._count = 0


class BubbleRenderer:
    ARC_SEG = 12
    RADIUS = 250.0
    PAD = 100.0
    LEADER = 800.0

    def __init__(self, shader):
        self.shader = shader
        self.scale = 0.8
        self._buf = None
        self._bubbles: list[dict] = []
        self._leaders: list[dict] = []

    def begin(self):
        self._bubbles.clear()
        self._leaders.clear()

    def add(self, anchor, direction, normal, text_width, color,
            leader_len=None):
        r = self.RADIUS * self.scale
        p = self.PAD * self.scale
        ld = self.LEADER if leader_len is None else leader_len
        rgb = tuple(color[:3])

        d = self._norm(direction, [0.0, 1.0, 0.0])
        n = self._norm(normal, [0.0, 0.0, 1.0])
        a = np.asarray(anchor, float)
        end = a + d * ld

        perp = np.cross(d, n)
        if np.linalg.norm(perp) < 1e-6:
            ref = np.array([1.0, 0.0, 0.0]) if abs(d[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
            perp = np.cross(d, ref)
        perp /= np.linalg.norm(perp)

        center = end + d * (p + r)
        self._bubbles.append({
            "center": center, "u": perp, "v": d, "hl": text_width / 2.0 + p,
            "r": r, "color": rgb,
        })
        self._leaders.append({"from": a, "to": end, "color": rgb})
        return {
                "center": center,
                "u_axis": perp,
                "v_axis": d,
                "normal": n,
            }

    @staticmethod
    def _norm(v, fallback):
        a = np.asarray(v, float)
        L = np.linalg.norm(a)
        return a / L if L > 1e-9 else np.asarray(fallback, float)

    def _outline(self, b):
        pts = []
        n = self.ARC_SEG
        for cx, start in ((b["center"] + b["u"] * b["hl"], -math.pi / 2),
                          (b["center"] - b["u"] * b["hl"], math.pi / 2)):
            for i in range(n + 1):
                t = start + math.pi * i / n
                pts.append(cx + b["u"] * (b["r"] * math.cos(t))
                              + b["v"] * (b["r"] * math.sin(t)))
        return pts

    def flush(self, mvp):
        if not self._bubbles:
            return
        verts: list[float] = []
        counts: list[int] = []
        for b in self._bubbles:
            pts = self._outline(b)
            counts.append(len(pts))
            for q in pts:
                verts += [q[0], q[1], q[2], *b["color"]]
        for ldr in self._leaders:
            verts += [*ldr["from"], *ldr["color"], *ldr["to"], *ldr["color"]]

        if self._buf is None:
            self._buf = _GLBuffer()
        self._buf.upload(verts)

        self.shader.use()
        loc = self.shader.get_loc("mvp")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, mat4_data(mvp))
        loc = self.shader.get_loc("alpha")
        if loc != -1:
            glUniform1f(loc, 1.0)

        depth = glIsEnabled(GL_DEPTH_TEST)
        glDisable(GL_DEPTH_TEST)
        off = 0
        for c in counts:
            self._buf.draw(GL_LINE_LOOP, c, off)
            off += c
        self._buf.draw(GL_LINES, len(self._leaders) * 2, off)
        if depth:
            glEnable(GL_DEPTH_TEST)

    def cleanup(self):
        if self._buf:
            self._buf.cleanup()
            self._buf = None