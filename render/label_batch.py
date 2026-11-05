# render/label_batch.py
from __future__ import annotations

import ctypes
import math

import numpy as np
from OpenGL.GL import *
from pyglm import glm

from render.gl_utils import mat4_data


_VS = """
#version 330 core
layout (location=0) in vec3 a_pos;
layout (location=1) in vec2 a_uv;
layout (location=2) in vec4 a_color;
uniform mat4 u_view;
uniform mat4 u_proj;
out vec2 v_uv;
out vec4 v_color;
void main() {
    gl_Position = u_proj * u_view * vec4(a_pos, 1.0);
    v_uv = a_uv;
    v_color = a_color;
}
"""

_FS = """
#version 330 core
in vec2 v_uv;
in vec4 v_color;
out vec4 frag;
uniform sampler2D u_atlas;
void main() {
    float a = texture(u_atlas, v_uv).r;
    if (a < 0.02) discard;
    frag = vec4(v_color.rgb, v_color.a * a);
}
"""


class LabelBatch:

    FLOATS_PER_VERTEX = 9
    FLOATS_PER_QUAD = 6 * FLOATS_PER_VERTEX
    INITIAL_QUADS = 4096

    ANCHORS = {
        "bottom-left":   (0.0,  0.0),
        "bottom-center": (-0.5, 0.0),
        "bottom-right":  (-1.0, 0.0),
        "top-left":      (0.0, -1.0),
        "top-center":    (-0.5, -1.0),
        "top-right":     (-1.0, -1.0),
        "center":        (-0.5, -0.5),
    }

    def __init__(self, atlas):
        self.atlas = atlas
        self.shader = 0
        self.vao = 0
        self.vbo = 0
        self.capacity_quads = 0
        self.write_offset = 0
        self.buf: np.ndarray | None = None

        self.loc_view = self.loc_proj = self.loc_atlas = -1

        self._mode = "billboard"
        self._view = glm.mat4(1.0)
        self._proj = glm.mat4(1.0)
        self._mvp = None
        self._cam = glm.vec3(0.0)
        self._screen_h = 1080
        self._fov = math.radians(45.0)

    # ------------------------------------------------------------------
    def init_gl(self):
        self._shader()
        self._buffers(self.INITIAL_QUADS)
        self.atlas.upload()
        self._lut()

    def _shader(self):
        def stage(kind, src):
            s = glCreateShader(kind)
            glShaderSource(s, src)
            glCompileShader(s)
            if not glGetShaderiv(s, GL_COMPILE_STATUS):
                raise RuntimeError(glGetShaderInfoLog(s).decode())
            return s
        vs, fs = stage(GL_VERTEX_SHADER, _VS), stage(GL_FRAGMENT_SHADER, _FS)
        p = glCreateProgram()
        glAttachShader(p, vs)
        glAttachShader(p, fs)
        glLinkProgram(p)
        glDeleteShader(vs)
        glDeleteShader(fs)
        self.shader = p
        self.loc_view = glGetUniformLocation(p, "u_view")
        self.loc_proj = glGetUniformLocation(p, "u_proj")
        self.loc_atlas = glGetUniformLocation(p, "u_atlas")

    def _buffers(self, quads: int):
        self.capacity_quads = quads
        self.buf = np.zeros(quads * self.FLOATS_PER_QUAD, dtype=np.float32)
        if not self.vao:
            self.vao = glGenVertexArrays(1)
        if not self.vbo:
            self.vbo = glGenBuffers(1)
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, self.buf.nbytes, None, GL_STREAM_DRAW)
        s = self.FLOATS_PER_VERTEX * 4
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, s, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, s, ctypes.c_void_p(12))
        glEnableVertexAttribArray(2)
        glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, s, ctypes.c_void_p(20))
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

    def _lut(self):
        glyphs = self.atlas.glyphs
        n = max((ord(c) for c in glyphs), default=127) + 1
        keys = ("advance", "bearing_x", "bearing_y", "width", "height",
                "u0", "u1", "v0", "v1")
        self.lut = {k: np.zeros(n, dtype=np.float32) for k in keys}
        for ch, g in glyphs.items():
            o = ord(ch)
            if o < n:
                for k in keys:
                    self.lut[k][o] = getattr(g, k)

    def _grow(self, need_quads: int):
        cap = self.capacity_quads
        while cap < need_quads:
            cap *= 2
        new = np.zeros(cap * self.FLOATS_PER_QUAD, dtype=np.float32)
        used = self.write_offset * self.FLOATS_PER_VERTEX
        new[:used] = self.buf[:used]
        self.buf = new
        self._buffers(cap)

    # ------------------------------------------------------------------
    def begin(self, view=None, proj=None, cam_pos=None, screen_h=None,
              fov_y_rad=None, mode="billboard", mvp=None):
        self._mode = mode
        self._view = view if view is not None else glm.mat4(1.0)
        self._proj = proj if proj is not None else glm.mat4(1.0)
        self._mvp = mvp
        self._cam = glm.vec3(*cam_pos) if cam_pos else glm.vec3(0.0)
        self._screen_h = max(1, screen_h or 1080)
        self._fov = fov_y_rad if fov_y_rad is not None else math.radians(45.0)
        self.write_offset = 0

    def add(self, world_pos, text, color=(1, 1, 1, 1), pixel_size=14.0,
            anchor="center", u_axis=None, v_axis=None, size_world=None,
            world_offset=None):
        self.add_many(
            positions=[world_pos], texts=[text], colors=[color],
            pixel_sizes=[pixel_size], anchors=anchor,
            u_axis=u_axis, v_axis=v_axis, size_world=size_world,
            world_offsets=[world_offset] if world_offset is not None else None,
        )

    def add_many(self, positions, texts, colors, pixel_sizes, anchors="center",
                 max_distances=None, world_offsets=None,
                 u_axis=None, v_axis=None, size_world=None):
        pos = np.asarray(positions, dtype=np.float32)
        if pos.ndim != 2 or pos.shape[1] != 3:
            raise ValueError("positions (N,3)")
        N = pos.shape[0]
        if N == 0:
            return

        col = np.asarray(colors, dtype=np.float32)
        col = np.tile(col, (N, 1)) if col.ndim == 1 else (
              np.full((N, 4), float(col), np.float32) if col.ndim == 0 else col)

        ps = np.asarray(pixel_sizes, dtype=np.float32)
        ps = np.full(N, float(ps), np.float32) if ps.ndim == 0 else ps

        wo = np.asarray(world_offsets, np.float32) if world_offsets is not None \
             else np.zeros((N, 3), np.float32)

        anchors_list = [anchors] * N if isinstance(anchors, str) else anchors

        lengths = np.fromiter((len(t) for t in texts), np.int32, N)
        joined = "".join(texts)
        if not joined:
            return
        ords = np.frombuffer(joined.encode("latin-1", "replace"),
                             np.uint8).astype(np.int32)
        total = ords.size
        label_of = np.repeat(np.arange(N, dtype=np.int32), lengths)

        world = pos + wo
        fs_per_label, wp_per_px, cr, cu = self._basis(world, ps, size_world,
                                                     u_axis, v_axis, N)
        per_char = self.lut["advance"][ords] * fs_per_label[label_of]

        starts = np.zeros(N, np.int64)
        if N > 1:
            np.cumsum(lengths[:-1], out=starts[1:])
        nz = lengths > 0
        text_w = np.zeros(N, np.float32)
        idx = np.nonzero(nz)[0]
        if idx.size:
            text_w[idx] = np.add.reduceat(per_char, starts[idx]).astype(np.float32)

        text_h = self.atlas.line_height * fs_per_label
        kx, ky = self._anchor_k(anchors_list, N)
        ax = text_w * kx
        ay = text_h * ky

        if self.write_offset + total * 6 > self.capacity_quads * 6:
            self._grow(self.write_offset // 6 + total + 1024)

        fs_g = fs_per_label[label_of]
        wp_g = world[label_of]
        ax_g = ax[label_of]
        ay_g = ay[label_of]
        wpp_g = wp_per_px[label_of]

        starts_label = np.zeros(N, np.int64)
        if N > 1:
            np.cumsum(lengths[:-1], out=starts_label[1:])
        gl_starts = starts_label[label_of]
        cumsum = np.cumsum(per_char)
        before = np.zeros(total, np.float32)
        nz2 = gl_starts > 0
        before[nz2] = cumsum[gl_starts[nz2] - 1]
        cursor = cumsum - per_char - before

        bx = self.lut["bearing_x"][ords]
        by = self.lut["bearing_y"][ords]
        gw = self.lut["width"][ords]
        gh = self.lut["height"][ords]

        gx = ax_g + cursor + bx * fs_g
        gy = ay_g + by * fs_g
        x1 = gx + gw * fs_g
        y1 = gy + gh * fs_g

        if self._mode == "world":
            px0, py0, px1, py1 = gx, gy, x1, y1
        else:
            px0 = gx * wpp_g
            py0 = gy * wpp_g
            px1 = x1 * wpp_g
            py1 = y1 * wpp_g

        crx, cry, crz = cr
        cux, cuy, cuz = cu
        wx, wy, wz = wp_g[:, 0], wp_g[:, 1], wp_g[:, 2]

        def corner(xs, ys):
            return (wx + crx * xs + cux * ys,
                    wy + cry * xs + cuy * ys,
                    wz + crz * xs + cuz * ys)
        p0 = corner(px0, py0)
        p1 = corner(px1, py0)
        p2 = corner(px1, py1)
        p3 = corner(px0, py1)

        u0 = self.lut["u0"][ords]; u1 = self.lut["u1"][ords]
        v0 = self.lut["v0"][ords]; v1 = self.lut["v1"][ords]
        r = col[label_of, 0]; g = col[label_of, 1]
        b = col[label_of, 2]; a = col[label_of, 3]

        n6 = total * 6
        out = np.empty((n6, self.FLOATS_PER_VERTEX), dtype=np.float32)
        pos_block = out[:, :3]
        uv_block = out[:, 3:5]
        col_block = out[:, 5:9]

        corners = [(p0, u0, v1), (p1, u1, v1), (p2, u1, v0),
                   (p0, u0, v1), (p2, u1, v0), (p3, u0, v0)]
        for k, (pt, uu, vv) in enumerate(corners):
            sl = slice(k, n6, 6)
            pos_block[sl, 0] = pt[0]
            pos_block[sl, 1] = pt[1]
            pos_block[sl, 2] = pt[2]
            uv_block[sl, 0] = uu
            uv_block[sl, 1] = vv
            col_block[sl, 0] = r
            col_block[sl, 1] = g
            col_block[sl, 2] = b
            col_block[sl, 3] = a

        base = self.write_offset * self.FLOATS_PER_VERTEX
        self.buf[base:base + n6 * self.FLOATS_PER_VERTEX] = out.reshape(-1)
        self.write_offset += n6

        if total > 0 and getattr(self, '_debug_count', 0) < 3:
            self._debug_count = getattr(self, '_debug_count', 0) + 1
            #print(f"[LB #{self._debug_count}] mode={self._mode} total={total}")
            #print(f"  fs_g[0]={fs_g[0]:.4f} wpp_g[0]={wpp_g[0]:.4f}")
            #print(f"  gx[0]={gx[0]:.4f} gy[0]={gy[0]:.4f} gw[0]={gw[0]:.4f} gh[0]={gh[0]:.4f}")
            #print(f"  p0[0]={p0[0]} p1[0]={p1[0]} p2[0]={p2[0]} p3[0]={p3[0]}")
            #print(f"  wx[0]={wx[0]:.4f} wy[0]={wy[0]:.4f} wz[0]={wz[0]:.4f}")

    def _basis(self, world, ps, size_world, u_axis, v_axis, N):
        if self._mode == "world":
            sw = size_world if size_world is not None else 200.0
            sw = np.asarray(sw, np.float32)
            if sw.ndim == 0:
                sw = np.full(N, float(sw), np.float32)
            fs = sw / float(self.atlas.size)
            ua = self._unit(u_axis if u_axis is not None else (1, 0, 0))
            va = self._unit(v_axis if v_axis is not None else (0, 1, 0))
            return fs, np.ones(N, np.float32), tuple(ua), tuple(va)

        d = np.linalg.norm(world - np.array([self._cam.x, self._cam.y, self._cam.z],
                                            np.float32), axis=1)
        wpp = (2.0 * np.maximum(d, 1e-3) * math.tan(self._fov * 0.5)) / self._screen_h
        fs = ps / float(self.atlas.size)
        cr = (self._view[0][0], self._view[1][0], self._view[2][0])
        cu = (self._view[0][1], self._view[1][1], self._view[2][1])
        return fs, wpp, cr, cu

    @staticmethod
    def _unit(v):
        a = np.asarray(v, np.float32)
        n = np.linalg.norm(a)
        return a / n if n > 1e-9 else np.array([1.0, 0.0, 0.0], np.float32)

    def _anchor_k(self, anchors, N):
        kx = np.empty(N, np.float32)
        ky = np.empty(N, np.float32)
        for i, a in enumerate(anchors):
            kx[i], ky[i] = self.ANCHORS.get(a, (0.0, 0.0))
        return kx, ky

    # ------------------------------------------------------------------
    def flush(self, disable_depth=False):
        if self.write_offset == 0:
            return

        glUseProgram(self.shader)
        if self._mode == "world" and self._mvp is not None:
            glUniformMatrix4fv(self.loc_view, 1, GL_FALSE,
                               mat4_data(glm.mat4(1.0)))
            glUniformMatrix4fv(self.loc_proj, 1, GL_FALSE,
                               mat4_data(self._mvp))
        else:
            glUniformMatrix4fv(self.loc_view, 1, GL_FALSE,
                               mat4_data(self._view))
            glUniformMatrix4fv(self.loc_proj, 1, GL_FALSE,
                               mat4_data(self._proj))

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.atlas.texture_id)
        glUniform1i(self.loc_atlas, 0)

        if disable_depth:
            glDisable(GL_DEPTH_TEST)
        glDepthMask(GL_FALSE)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_CULL_FACE)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        n = self.write_offset * self.FLOATS_PER_VERTEX
        glBufferSubData(GL_ARRAY_BUFFER, 0, n * 4, self.buf[:n].tobytes())
        glDrawArrays(GL_TRIANGLES, 0, self.write_offset)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

        glDepthMask(GL_TRUE)
        if disable_depth:
            glEnable(GL_DEPTH_TEST)
        glUseProgram(0)

    def stats(self):
        return {"quads": self.write_offset // 6,
                "capacity": self.capacity_quads}

    def cleanup(self):
        if self.vbo:
            glDeleteBuffers(1, [self.vbo])
            self.vbo = 0
        if self.vao:
            glDeleteVertexArrays(1, [self.vao])
            self.vao = 0
        if self.shader:
            glDeleteProgram(self.shader)
            self.shader = 0
        self.buf = None
        self.capacity_quads = 0
        self.write_offset = 0