# render/label_batch.py
"""
LabelBatch — binlerce 3D billboard text'i TEK draw call'da çizer.

Kullanım:
    batch = LabelBatch(font_atlas)
    batch.init_gl()

    # her frame:
    batch.begin(view_matrix, proj_matrix, cam_pos, screen_h, fov_y_rad)
    batch.add(world_pos=(x,y,z), text="X1", color=(1,1,1,1), pixel_size=14)
    ...
    batch.flush()   # tek draw call
"""
from __future__ import annotations

import ctypes
import math

from pyglm import glm
import numpy as np
from OpenGL.GL import *

from logging_config import CadLogger

logger = CadLogger.get(__name__)


# ---------------------------------------------------------------------------
# Shader
# ---------------------------------------------------------------------------
_VS = """
#version 330 core
layout (location = 0) in vec3 a_world_pos;   // dünya uzayında quad köşesi (offset dahil)
layout (location = 1) in vec2 a_uv;
layout (location = 2) in vec4 a_color;

uniform mat4 u_view;
uniform mat4 u_proj;

out vec2 v_uv;
out vec4 v_color;

void main() {
    gl_Position = u_proj * u_view * vec4(a_world_pos, 1.0);
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
    // Atlas R8 → kırmızı kanal alpha olarak kullanılıyor
    float a = texture(u_atlas, v_uv).r;
    if (a < 0.02) discard;
    frag = vec4(v_color.rgb, v_color.a * a);
}
"""


# ---------------------------------------------------------------------------
# LabelBatch
# ---------------------------------------------------------------------------
class LabelBatch:
    """
    Binlerce label'ı tek VBO + tek draw call ile çizer.
    Dinamik VBO (GL_STREAM_DRAW) kullanır — her frame yeniden yüklenir.
    """

    VERTEX_FLOATS = 9   # 3 (pos) + 2 (uv) + 4 (color)
    FLOATS_PER_QUAD = 6 * VERTEX_FLOATS  # 6 vertex × 9 float = 54

    # Başlangıç kapasitesi (label × max_karakter × 6 vertex)
    INITIAL_QUADS = 4096

    _ANCHOR_LUT = {
        "bottom-left":   (0.0,  0.0),
        "bottom-center": (-0.5, 0.0),
        "bottom-right":  (-1.0, 0.0),
        "top-left":      (0.0, -1.0),
        "top-center":    (-0.5, -1.0),
        "top-right":     (-1.0, -1.0),
        "center":        (-0.5, -0.5),
    }

    def __init__(self, font_atlas):
        self.atlas = font_atlas
        self.shader = 0
        self.vao = 0
        self.vbo = 0
        self.capacity_quads = 0
        self.vertex_count = 0
        self.cpu_buffer: np.ndarray | None = None
        self.write_offset = 0   # kaç vertex yazıldı

        # Uniform location cache
        self.loc_view = -1
        self.loc_proj = -1
        self.loc_atlas = -1

        # Frame state
        self._view = glm.mat4(1.0)
        self._proj = glm.mat4(1.0)
        self._cam_pos = glm.vec3(0.0)
        self._screen_h = 1080
        self._fov_y_rad = math.radians(45.0)
        self._enabled = True
        self._last_flush_calls = 0
        self._last_flush_labels = 0
        self._build_lut()
    # ------------------------------------------------------------------
    def _build_lut(self):
        glyphs = self.atlas.glyphs
        max_ord = max((ord(c) for c in glyphs), default=127) + 1
        self._adv_lut = np.zeros(max_ord, dtype=np.float32)
        self._bx_lut  = np.zeros(max_ord, dtype=np.float32)
        self._by_lut  = np.zeros(max_ord, dtype=np.float32)
        self._gw_lut  = np.zeros(max_ord, dtype=np.float32)
        self._gh_lut  = np.zeros(max_ord, dtype=np.float32)
        self._u0_lut  = np.zeros(max_ord, dtype=np.float32)
        self._u1_lut  = np.zeros(max_ord, dtype=np.float32)
        self._v0_lut  = np.zeros(max_ord, dtype=np.float32)
        self._v1_lut  = np.zeros(max_ord, dtype=np.float32)
        for ch, g in glyphs.items():
            o = ord(ch)
            if o >= max_ord:
                continue
            self._adv_lut[o] = g.advance
            self._bx_lut[o]  = g.bearing_x
            self._by_lut[o]  = g.bearing_y
            self._gw_lut[o]  = g.width
            self._gh_lut[o]  = g.height
            self._u0_lut[o]  = g.u0
            self._u1_lut[o]  = g.u1
            self._v0_lut[o]  = g.v0
            self._v1_lut[o]  = g.v1

    # ------------------------------------------------------------------
    # GL init
    # ------------------------------------------------------------------
    def init_gl(self):
        self._create_shader()
        self._create_buffers(self.INITIAL_QUADS)
        self.atlas.upload()

    def _create_shader(self):
        def compile_stage(stype, src):
            sid = glCreateShader(stype)
            glShaderSource(sid, src)
            glCompileShader(sid)
            if not glGetShaderiv(sid, GL_COMPILE_STATUS):
                raise RuntimeError(glGetShaderInfoLog(sid).decode())
            return sid

        vs = compile_stage(GL_VERTEX_SHADER, _VS)
        fs = compile_stage(GL_FRAGMENT_SHADER, _FS)
        prog = glCreateProgram()
        glAttachShader(prog, vs)
        glAttachShader(prog, fs)
        glLinkProgram(prog)
        if not glGetProgramiv(prog, GL_LINK_STATUS):
            raise RuntimeError(glGetProgramInfoLog(prog).decode())
        glDeleteShader(vs)
        glDeleteShader(fs)
        self.shader = prog

        self.loc_view = glGetUniformLocation(prog, "u_view")
        self.loc_proj = glGetUniformLocation(prog, "u_proj")
        self.loc_atlas = glGetUniformLocation(prog, "u_atlas")

    def _create_buffers(self, quads: int):
        quads = max(quads, 1)
        self.capacity_quads = quads
        total_floats = quads * self.FLOATS_PER_QUAD

        # CPU tarafı buffer
        self.cpu_buffer = np.zeros(total_floats, dtype=np.float32)

        if self.vao == 0:
            self.vao = glGenVertexArrays(1)
        if self.vbo == 0:
            self.vbo = glGenBuffers(1)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, self.cpu_buffer.nbytes, None, GL_STREAM_DRAW)

        stride = self.VERTEX_FLOATS * 4
        # position
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        # uv
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))
        # color
        glEnableVertexAttribArray(2)
        glVertexAttribPointer(2, 4, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(20))

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

    def _grow(self, needed_quads: int):
        """Kapasiteyi 2× büyüt (yeterli olana kadar)."""
        new_cap = self.capacity_quads
        while new_cap < needed_quads:
            new_cap *= 2
        # CPU buffer büyüt (yazılan veri korunur)
        new_buf = np.zeros(new_cap * self.FLOATS_PER_QUAD, dtype=np.float32)
        new_buf[:self.write_offset * self.VERTEX_FLOATS] = \
            self.cpu_buffer[:self.write_offset * self.VERTEX_FLOATS]
        self.cpu_buffer = new_buf
        self._create_buffers(new_cap)

    # ------------------------------------------------------------------
    # Frame API
    # ------------------------------------------------------------------
    def begin(self, view: glm.mat4, proj: glm.mat4, cam_pos,
              screen_h: int, fov_y_rad: float):
        self._view = view
        self._proj = proj
        self._cam_pos = glm.vec3(*cam_pos) if not isinstance(cam_pos, glm.vec3) else cam_pos
        self._screen_h = max(1, screen_h)
        self._fov_y_rad = fov_y_rad
        self.write_offset = 0

    
    # ------------------------------------------------------------------
    def _write_vertex(self, p, u, v, r, g, b, a):
        if self.write_offset + 1 > self.capacity_quads * 6:
            # Kapasite aşımı — büyüt
            needed = (self.write_offset + 6) // 6 + 64
            self._grow(needed)
        buf = self.cpu_buffer
        i = self.write_offset * self.VERTEX_FLOATS
        buf[i + 0] = p.x
        buf[i + 1] = p.y
        buf[i + 2] = p.z
        buf[i + 3] = u
        buf[i + 4] = v
        buf[i + 5] = r
        buf[i + 6] = g
        buf[i + 7] = b
        buf[i + 8] = a
        self.write_offset += 1

    # ------------------------------------------------------------------
    def flush(self):
        """Birikmiş tüm label'ları tek draw call'da çizer."""
        if self.write_offset == 0:
            return

        self.vertex_count = self.write_offset

        glUseProgram(self.shader)
        glUniformMatrix4fv(self.loc_view, 1, GL_FALSE, glm.value_ptr(self._view))
        glUniformMatrix4fv(self.loc_proj, 1, GL_FALSE, glm.value_ptr(self._proj))

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.atlas.texture_id)
        glUniform1i(self.loc_atlas, 0)

        # Depth: test açık, write kapalı (transparan obje gibi)
        glEnable(GL_DEPTH_TEST)
        glDepthMask(GL_FALSE)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_CULL_FACE)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        # Sadece yazılan kısmı yükle
        byte_count = self.write_offset * self.VERTEX_FLOATS * 4
        glBufferSubData(
            GL_ARRAY_BUFFER, 0, byte_count,
            self.cpu_buffer[:self.write_offset * self.VERTEX_FLOATS].tobytes(),
        )
        glDrawArrays(GL_TRIANGLES, 0, self.vertex_count)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

        glDepthMask(GL_TRUE)
        glUseProgram(0)

        self._last_flush_calls = 1
        self._last_flush_labels = self.write_offset // 6

    # ------------------------------------------------------------------
    def stats(self):
        return {
            "labels": self._last_flush_labels,
            "vertices": self.vertex_count,
            "capacity_quads": self.capacity_quads,
        }

    # ------------------------------------------------------------------
    def cleanup(self):
        if self.vbo:
            try: glDeleteBuffers(1, [self.vbo])
            except Exception: pass
            self.vbo = 0
        if self.vao:
            try: glDeleteVertexArrays(1, [self.vao])
            except Exception: pass
            self.vao = 0
        if self.shader:
            try: glDeleteProgram(self.shader)
            except Exception: pass
            self.shader = 0
        self.cpu_buffer = None
        self.capacity_quads = 0
        self.write_offset = 0

    def add_many(self, positions, texts, colors, pixel_sizes,
                 anchors="center", max_distances=None, world_offsets=None):
        pos = np.asarray(positions, dtype=np.float32)
        if pos.ndim != 2 or pos.shape[1] != 3:
            raise ValueError("positions (N, 3) olmalı")
        N = pos.shape[0]
        if N == 0:
            return

        col = np.asarray(colors, dtype=np.float32)
        if col.ndim == 1:
            col = np.tile(col, (N, 1))
        elif col.ndim == 0:
            col = np.full((N, 4), float(col), dtype=np.float32)

        ps = np.asarray(pixel_sizes, dtype=np.float32)
        if ps.ndim == 0:
            ps = np.full(N, float(ps), dtype=np.float32)

        if world_offsets is not None:
            wo = np.asarray(world_offsets, dtype=np.float32)
        else:
            wo = np.zeros((N, 3), dtype=np.float32)

        if isinstance(anchors, str):
            anchors_list = [anchors] * N
        else:
            anchors_list = anchors

        if max_distances is not None:
            md = np.asarray(max_distances, dtype=np.float32)
            if md.ndim == 0:
                md = np.full(N, float(md), dtype=np.float32)
        else:
            md = None

        # --- 1. Karakter ordinalleri ---
        text_lengths = np.fromiter((len(t) for t in texts),
                                   dtype=np.int32, count=N)
        all_text = "".join(texts)
        if not all_text:
            return
        all_ords = np.frombuffer(
            all_text.encode("latin-1", errors="replace"),
            dtype=np.uint8,
        ).astype(np.int32)

        total_chars = all_ords.size
        label_of_char = np.repeat(np.arange(N, dtype=np.int32), text_lengths)

        # --- 2. Dünya pozisyonu ve kamera ---
        world_pos = pos + wo
        cam = self._cam_pos
        d = np.sqrt(((world_pos - np.array([cam.x, cam.y, cam.z],
                                            dtype=np.float32)) ** 2).sum(axis=1))
        d_safe = np.maximum(d, 1e-3)
        world_per_px = (2.0 * d_safe *
                        math.tan(self._fov_y_rad * 0.5)) / self._screen_h
        font_scale = ps / float(self.atlas.size)

        # --- 3. text_w_px / anchor ---
        adv_per_char = self._adv_lut[all_ords] * font_scale[label_of_char]

        # daha hızlı: lookup array
        adv_per_char = self._adv_lut[all_ords] * font_scale[label_of_char]

                # text_w_px — vektörize
        offsets = np.zeros(N, dtype=np.int64)
        if N > 1:
            np.cumsum(text_lengths[:-1], out=offsets[1:])
        nz = text_lengths > 0
        if np.all(nz):
            text_w_px = np.add.reduceat(adv_per_char, offsets).astype(np.float32)
        else:
            # boş text'ler varsa — nadir durum
            text_w_px = np.zeros(N, dtype=np.float32)
            idx = np.nonzero(nz)[0]
            text_w_px[idx] = np.add.reduceat(adv_per_char, offsets[idx]).astype(np.float32)

        line_h = self.atlas.line_height
        text_h_px = line_h * font_scale

        # Anchor — vektörize (LUT)
        if isinstance(anchors, str):
            kx, ky = self._ANCHOR_LUT.get(anchors, (0.0, 0.0))
            ax = text_w_px * kx
            ay = text_h_px * ky
        else:
            kx = np.empty(N, dtype=np.float32)
            ky = np.empty(N, dtype=np.float32)
            lut = self._ANCHOR_LUT
            for i, a in enumerate(anchors_list):
                kxi, kyi = lut.get(a, (0.0, 0.0))
                kx[i] = kxi
                ky[i] = kyi
            ax = text_w_px * kx
            ay = text_h_px * ky


        # pass(f"[DBG anchors] anchors={anchors!r} ax={ax[:2]} ay={ay[:2]} text_w_px={text_w_px[:2]} text_h_px={text_h_px[:2]}")

        
        # --- 4. Kamera eksenleri ---
        cr = (self._view[0][0], self._view[1][0], self._view[2][0])
        cu = (self._view[0][1], self._view[1][1], self._view[2][1])

        # --- 5. Kapasite ---
        total_quads = total_chars
        if self.write_offset + total_quads * 6 > self.capacity_quads * 6:
            self._grow(self.write_offset // 6 + total_quads + 1024)

        # --- 6. Per-char verileri ---
        wpp_g  = world_per_px[label_of_char]
        fs_g   = font_scale[label_of_char]
        wp_g   = world_pos[label_of_char]
        ax_g   = ax[label_of_char]
        ay_g   = ay[label_of_char]
        r_g    = col[label_of_char, 0]
        g_g    = col[label_of_char, 1]
        b_g    = col[label_of_char, 2]
        a_g    = col[label_of_char, 3]

        # --- 7. cursor_x_px (label-içi prefix sum) ---
        # Label başlangıç index'leri
        starts_per_label = np.zeros(N, dtype=np.int64)
        if N > 1:
            np.cumsum(text_lengths[:-1], out=starts_per_label[1:])
        gl_starts = starts_per_label[label_of_char]
        global_cumsum = np.cumsum(adv_per_char)
        before_label = np.zeros(total_chars, dtype=np.float32)
        nz = gl_starts > 0
        before_label[nz] = global_cumsum[gl_starts[nz] - 1]
        cursor_x_px = global_cumsum - adv_per_char - before_label

        
        # --- 8. Glyph metrikleri ---
        bx_g  = self._bx_lut[all_ords]
        by_g  = self._by_lut[all_ords]
        gw_g  = self._gw_lut[all_ords]
        gh_g  = self._gh_lut[all_ords]
        u0_g  = self._u0_lut[all_ords]
        u1_g  = self._u1_lut[all_ords]
        v0_g  = self._v0_lut[all_ords]   # flip YOK
        v1_g  = self._v1_lut[all_ords]   # flip YOK

        # --- 9. Glyph pozisyonları (px) ---
        gx = ax_g + cursor_x_px + bx_g * fs_g
        gy = ay_g - (by_g + gh_g) * fs_g
        gw = gw_g * fs_g
        gh = gh_g * fs_g

        # pass(f"[DBG gx] ax_g={ax_g[:2]} cursor_x_px={cursor_x_px[:2]} gx={gx[:2]} gy={gy[:2]}")
        
        x0 = gx * wpp_g
        y0 = gy * wpp_g
        x1 = (gx + gw) * wpp_g
        y1 = (gy + gh) * wpp_g

        crx, cry, crz = cr
        cux, cuy, cuz = cu

        # --- 10. Vertex'leri yaz ---
        # her glyph için 6 vertex, sıra: p0, p1, p2, p0, p2, p3
        # p0 = wp + cr*x0 + cu*y0
        # p1 = wp + cr*x1 + cu*y0
        # p2 = wp + cr*x1 + cu*y1
        # p3 = wp + cr*x0 + cu*y1
        wpx = wp_g[:, 0]; wpy = wp_g[:, 1]; wpz = wp_g[:, 2]

        p0x = wpx + crx*x0 + cux*y0; p0y = wpy + cry*x0 + cuy*y0; p0z = wpz + crz*x0 + cuz*y0
        p1x = wpx + crx*x1 + cux*y0; p1y = wpy + cry*x1 + cuy*y0; p1z = wpz + crz*x1 + cuz*y0
        p2x = wpx + crx*x1 + cux*y1; p2y = wpy + cry*x1 + cuy*y1; p2z = wpz + crz*x1 + cuz*y1
        p3x = wpx + crx*x0 + cux*y1; p3y = wpy + cry*x0 + cuy*y1; p3z = wpz + crz*x0 + cuz*y1

        buf = self.cpu_buffer
        V = self.VERTEX_FLOATS
        base = self.write_offset

        # 6 vertex'i vektörize yaz — her glyph için 6 satır
        n = total_chars
        # index array'leri
        idx0 = base + np.arange(n) * 6 + 0
        idx1 = base + np.arange(n) * 6 + 1
        idx2 = base + np.arange(n) * 6 + 2
        idx3 = base + np.arange(n) * 6 + 3
        idx4 = base + np.arange(n) * 6 + 4
        idx5 = base + np.arange(n) * 6 + 5

        buf = self.cpu_buffer
        V = self.VERTEX_FLOATS
        base = self.write_offset
        n = total_chars

        # Her glyph için 6 vertex indexi: base + i*6 + {0..5}
        # Yani 6 ardışık vertex bloğu
        # Slice: buf.reshape(-1, 9) kullan
        view = buf[: (base + n * 6) * 9].reshape(-1, 9)
        base_v = base  # vertex indexi

        # Vertex indexleri (her glyph için)
        rows = base_v + np.arange(n)[:, None] * 6 + np.arange(6)[None, :]
        # rows shape (n, 6) — düzleştir
        rows_flat = rows.reshape(-1)

        # Pozisyonlar (n, 6, 3)
        pos_all = np.empty((n, 6, 3), dtype=np.float32)
        pos_all[:, 0, 0] = p0x; pos_all[:, 0, 1] = p0y; pos_all[:, 0, 2] = p0z
        pos_all[:, 1, 0] = p1x; pos_all[:, 1, 1] = p1y; pos_all[:, 1, 2] = p1z
        pos_all[:, 2, 0] = p2x; pos_all[:, 2, 1] = p2y; pos_all[:, 2, 2] = p2z
        pos_all[:, 3, 0] = p0x; pos_all[:, 3, 1] = p0y; pos_all[:, 3, 2] = p0z
        pos_all[:, 4, 0] = p2x; pos_all[:, 4, 1] = p2y; pos_all[:, 4, 2] = p2z
        pos_all[:, 5, 0] = p3x; pos_all[:, 5, 1] = p3y; pos_all[:, 5, 2] = p3z

        # UV (n, 6, 2)
        uv_all = np.empty((n, 6, 2), dtype=np.float32)
        uv_all[:, 0, 0] = u0_g; uv_all[:, 0, 1] = v1_g
        uv_all[:, 1, 0] = u1_g; uv_all[:, 1, 1] = v1_g
        uv_all[:, 2, 0] = u1_g; uv_all[:, 2, 1] = v0_g
        uv_all[:, 3, 0] = u0_g; uv_all[:, 3, 1] = v1_g
        uv_all[:, 4, 0] = u1_g; uv_all[:, 4, 1] = v0_g
        uv_all[:, 5, 0] = u0_g; uv_all[:, 5, 1] = v0_g

        # Renk (n, 6, 4)
        col_all = np.empty((n, 6, 4), dtype=np.float32)
        col_all[..., 0] = r_g[:, None]
        col_all[..., 1] = g_g[:, None]
        col_all[..., 2] = b_g[:, None]
        col_all[..., 3] = a_g[:, None]

        # Buffer view'a yaz
        base_flat = base_v * V
        end_flat = (base_v + n * 6) * V
        combined = np.concatenate(
            [pos_all.reshape(n*6, 3),
             uv_all.reshape(n*6, 2),
             col_all.reshape(n*6, 4)],
            axis=1,
        )  # (n*6, 9)
        buf[base_flat:end_flat] = combined.reshape(-1)

        self.write_offset += n * 6

    