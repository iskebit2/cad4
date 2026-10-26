# render/load_renderer.py
"""
Frame yayılı yük görselleştirme.
- Ayrı line ve triangle buffer'ları (karışma yok)
- Pattern seçim filtresi
- Alpha ile şeffaf dolgu
"""
import ctypes
import numpy as np
import glm
from OpenGL.GL import *

from logging_config import CadLogger

logger = CadLogger.get(__name__)


class LoadRenderer:

    PROFILE_HEIGHT_RATIO = 0.10
    ARROW_MIN = 3
    ARROW_MAX = 12
    ARROW_LENGTH_RATIO = 0.35
    MIN_PROFILE_H = 5.0

    PATTERN_COLORS = [
        (1.00, 0.30, 0.30),
        (0.30, 0.60, 1.00),
        (0.30, 0.85, 0.45),
        (1.00, 0.75, 0.20),
        (0.85, 0.40, 0.85),
        (0.30, 0.85, 0.85),
        (1.00, 0.55, 0.20),
        (0.60, 0.60, 0.60),
    ]

    def __init__(self):
        self.vao_line = None
        self.vbo_line = None
        self.line_count = 0

        self.vao_tri = None
        self.vbo_tri = None
        self.tri_count = 0

        self.shader = None
        self._initialized = False
        self._pattern_color_cache: dict = {}
        self.enabled = True

        # --- Pattern filtreleme ---
        # None → hepsi gösterilir
        # str  → sadece o pattern gösterilir
        
        # Alternatif: bir liste
        self.available_patterns: list[str] = []

        self.enabled = True
        self.active_pattern: str | None = None

        # Görsel ayarlar
        self.profile_scale = 1.0
        self.line_width = 2.0
        self.fill_alpha = 0.28
        self.show_arrows = True
        self.show_fill = True
        self._point_force_scale = 50.0   # mm/kN — her update'te güncellenir

        self.show_frame_loads = True
        self.show_point_loads = True

    # ==================================================================
    # INIT
    # ==================================================================
    def init_gl(self):
        if self._initialized:
            return

        vs = """
        #version 330 core
        layout (location = 0) in vec3 aPos;
        layout (location = 1) in vec3 aColor;
        uniform mat4 uMVP;
        out vec3 vColor;
        void main() {
            gl_Position = uMVP * vec4(aPos, 1.0);
            vColor = aColor;
        }
        """

        fs = """
        #version 330 core
        in vec3 vColor;
        out vec4 FragColor;
        uniform float uAlpha;
        void main() {
            FragColor = vec4(vColor, uAlpha);
        }
        """

        self.shader = self._compile(vs, fs)

        # Line VAO
        self.vao_line = glGenVertexArrays(1)
        self.vbo_line = glGenBuffers(1)
        glBindVertexArray(self.vao_line)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo_line)
        stride = 6 * 4
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(3 * 4))
        glBindVertexArray(0)

        # Tri VAO
        self.vao_tri = glGenVertexArrays(1)
        self.vbo_tri = glGenBuffers(1)
        glBindVertexArray(self.vao_tri)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo_tri)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(3 * 4))
        glBindVertexArray(0)

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        self._initialized = True

    def _compile(self, vs_src, fs_src):
        vs = glCreateShader(GL_VERTEX_SHADER)
        glShaderSource(vs, vs_src)
        glCompileShader(vs)
        if not glGetShaderiv(vs, GL_COMPILE_STATUS):
            raise RuntimeError(f"VS: {glGetShaderInfoLog(vs).decode()}")

        fs = glCreateShader(GL_FRAGMENT_SHADER)
        glShaderSource(fs, fs_src)
        glCompileShader(fs)
        if not glGetShaderiv(fs, GL_COMPILE_STATUS):
            raise RuntimeError(f"FS: {glGetShaderInfoLog(fs).decode()}")

        p = glCreateProgram()
        glAttachShader(p, vs)
        glAttachShader(p, fs)
        glLinkProgram(p)
        if not glGetProgramiv(p, GL_LINK_STATUS):
            raise RuntimeError(f"Link: {glGetProgramInfoLog(p).decode()}")

        glDeleteShader(vs)
        glDeleteShader(fs)
        return p

    # ==================================================================
    # PATTERN RENK
    # ==================================================================
    def _pattern_color(self, name: str):
        if name in self._pattern_color_cache:
            return self._pattern_color_cache[name]
        h = sum(ord(c) * (i + 1) for i, c in enumerate(str(name))) % len(self.PATTERN_COLORS)
        color = self.PATTERN_COLORS[h]
        self._pattern_color_cache[name] = color
        return color

    # ==================================================================
    # UPDATE — vertex üretimi
    # ==================================================================
    def update(self, scene, camera_scale: float = 1.0, scene_size: float = 1.0):
        if not self._initialized:
            self.init_gl()

        if not self.enabled or not scene:
            self.line_count = 0
            self.tri_count = 0
            return

        self.available_patterns = self._scan_patterns(scene)

        lines = []
        tris = []

        # --- Frame yayılı yükleri (değişmez) ---
        if self.show_frame_loads:
            for frame in scene.frames.values():
                ...

        # --- Point loads: ÖLÇEĞİ ÖNCE HESAPLA ---
        if self.show_point_loads:
            # Maksimum yük büyüklüğü (filtre uygulanmış)
            point_load_max = 1.0
            for node in scene.nodes.values():
                if not getattr(node, "is_visible", True):
                    continue
                for pl in getattr(node, "loads", None) or []:
                    pat = getattr(pl, "pattern_name", "?")
                    if self.active_pattern and pat != self.active_pattern:
                        continue
                    mag = abs(pl.fx) + abs(pl.fy) + abs(pl.fz)
                    if mag > point_load_max:
                        point_load_max = mag

            # Ok boyu: sahnenin %5'i (max yük için)
            target_arrow_len = max(scene_size, 1.0) * 0.05
            self._point_force_scale = target_arrow_len / point_load_max

            # Şimdi her yükü çiz
            for node in scene.nodes.values():
                if not getattr(node, "is_visible", True):
                    continue
                for pl in getattr(node, "loads", None) or []:
                    pat = getattr(pl, "pattern_name", "?")
                    if self.active_pattern and pat != self.active_pattern:
                        continue
                    self._emit_point_load(node, pl, lines, tris, camera_scale)
        

        # Line buffer
        if lines:
            data = np.asarray(lines, dtype=np.float32)
            self.line_count = len(data) // 6
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo_line)
            glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_DYNAMIC_DRAW)
        else:
            self.line_count = 0

        # Tri buffer
        if tris:
            data = np.asarray(tris, dtype=np.float32)
            self.tri_count = len(data) // 6
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo_tri)
            glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_DYNAMIC_DRAW)
        else:
            self.tri_count = 0

        glBindBuffer(GL_ARRAY_BUFFER, 0)

    def _scan_patterns(self, scene) -> list[str]:
        """Sahnedeki tüm pattern isimlerini topla."""
        pats = set()
        for frame in scene.frames.values():
            load_sets = getattr(frame, "dist_load_sets", None)
            if load_sets:
                pats.update(load_sets.keys())
            for dl in getattr(frame, "dist_loads", []) or []:
                p = getattr(dl, "pattern_name", None)
                if p:
                    pats.add(p)

        for node in scene.nodes.values():              # ← YENİ
            for pl in getattr(node, "loads", None) or []:
                p = getattr(pl, "pattern_name", None)
                if p:
                    pats.add(p)
        return sorted(pats)

    # ==================================================================
    # EMIT
    # ==================================================================
    def _emit_load_set(self, frame, ls, lines, tris, cam_scale):
        segments = getattr(ls, "segments", None) or []
        if not segments:
            return

        # Segment'leri pts listesine çevir
        pts = []
        for seg in segments:
            x1 = self._attr(seg, "x1")
            x2 = self._attr(seg, "x2")
            q1 = self._attr(seg, "q1")
            q2 = self._attr(seg, "q2")
            if None in (x1, x2, q1, q2):
                continue
            if not pts:
                pts.append((float(x1), float(q1)))
            pts.append((float(x2), float(q2)))

        if len(pts) < 2:
            return

        color = self._pattern_color(getattr(ls, "pattern_name", "?"))
        # ls'in kendisini load olarak geçir (coord_sys, load_dir oradan gelir)
        self._emit_profile(frame, pts, color, lines, tris, cam_scale, load=ls)

    def _emit_legacy(self, frame, dl, lines, tris, cam_scale):
        pts_raw = getattr(dl, "points", None) or []
        pts = [(float(a), float(b)) for a, b in pts_raw if a is not None and b is not None]
        if len(pts) < 2:
            return
        color = self._pattern_color(getattr(dl, "pattern_name", "?"))
        self._emit_profile(frame, pts, color, lines, tris, cam_scale)

    @staticmethod
    def _attr(obj, key):
        if hasattr(obj, key):
            return getattr(obj, key)
        if isinstance(obj, dict):
            return obj.get(key)
        return None

    # ==================================================================
    # PROFİL — frame'e yerleştir
    # ==================================================================
    def _emit_profile(self, frame, pts, color, lines, tris, cam_scale, load=None):
        """
        Frame üzerindeki yayılı yük profilini çiz.

        pts: [(xr, q), ...] — relative konum, yük değeri
        load: FrameDistributedLoad (yön bilgisi için)
        """
        ni = getattr(frame, "node_i", None)
        nj = getattr(frame, "node_j", None)
        if not ni or not nj:
            return

        p0 = np.array([ni.x, ni.y, ni.z], dtype=float)
        p1 = np.array([nj.x, nj.y, nj.z], dtype=float)
        L = float(np.linalg.norm(p1 - p0))
        if L < 1e-9:
            return

        axis = (p1 - p0) / L

        # --- Frame yerel eksenleri ---
        e1, e2, e3 = self._frame_local_axes(p0, p1, getattr(frame, "rotation_deg", 0.0))

        # --- Yük yönü (3D dünya vektörü) ---
        if load is not None:
            load_dir_vec = self._resolve_load_direction(load, e1, e2, e3)
        else:
            # Varsayılan: Local 2 (kirişe dik, dünya Z'ye yakın)
            load_dir_vec = e2

        # --- Profil ekseni: yük yönü ---
        # +q yükü load_dir_vec yönünde, -q ters yönde
        up = load_dir_vec  # yük profili bu yönde uzayacak

        max_q = max(abs(q) for _, q in pts) or 1.0
        profile_h = max(L * self.PROFILE_HEIGHT_RATIO * cam_scale * self.profile_scale,
                self.MIN_PROFILE_H)

        # İşaretli q → profil q yönünde, ters ise diğer yönde
        def to_3d(xr, q):
            base = p0 + axis * (xr * L)
            return base + up * (q / max_q * profile_h)  # q işaretli, up birim

        # --- Üst çizgi ---
        for i in range(len(pts) - 1):
            a = to_3d(*pts[i])
            b = to_3d(*pts[i + 1])
            self._push_line(lines, a, b, color)

        # --- Dikey kenarlar (profilin frame eksenine bağlandığı yerler) ---
        for xr, q in (pts[0], pts[-1]):
            base = p0 + axis * (xr * L)
            tip = to_3d(xr, q)
            if np.linalg.norm(tip - base) > 1e-6:
                self._push_line(lines, base, tip, color)

        # --- Dolgu (üçgen şerit) ---
        for i in range(len(pts) - 1):
            xa, qa = pts[i]
            xb, qb = pts[i + 1]
            ta = to_3d(xa, qa)
            tb = to_3d(xb, qb)
            ba = p0 + axis * (xa * L)
            bb = p0 + axis * (xb * L)
            self._push_tri(tris, ta, ba, bb, color)
            self._push_tri(tris, ta, bb, tb, color)

        # --- Oklar: yük yönünde ---
        if self.show_arrows:
            n = max(self.ARROW_MIN, min(self.ARROW_MAX, int(L / 400.0) + 2))
            for i in range(n):
                xr = (i + 0.5) / n
                q = self._interp(pts, xr)
                if abs(q) < 1e-9:
                    continue

                base = p0 + axis * (xr * L)
                # Ok her zaman frame ekseninden BAŞLAR, yükün yönüne gider
                tip = base + up * (q / max_q * profile_h)

                # Gövde
                self._push_line(lines, base, tip, color)

                # Ok başı — uç kısmında
                d = tip - base
                dlen = np.linalg.norm(d)
                if dlen < 1e-6:
                    continue
                d = d / dlen

                # Ok başı için bir "yan" vektör: axis ve up'a dik
                side = np.cross(d, axis)
                slen = np.linalg.norm(side)
                if slen < 1e-6:
                    side = np.cross(d, np.array([0.0, 0.0, 1.0]))
                    slen = np.linalg.norm(side)
                    if slen < 1e-6:
                        continue
                side = side / slen

                head_len = min(dlen * self.ARROW_LENGTH_RATIO, profile_h * 0.25)
                head_w = head_len * 0.5
                hb = tip - d * head_len
                left = hb + side * head_w
                right = hb - side * head_w

                self._push_tri(tris, tip, left, right, color)

    @staticmethod
    def _interp(pts, xr):
        if xr <= pts[0][0]:
            return pts[0][1]
        if xr >= pts[-1][0]:
            return pts[-1][1]
        for i in range(len(pts) - 1):
            xa, qa = pts[i]
            xb, qb = pts[i + 1]
            if xa <= xr <= xb:
                t = (xr - xa) / (xb - xa) if xb > xa else 0.0
                return qa + (qb - qa) * t
        return 0.0

    # ==================================================================
    # VERTEX PUSH — line ve tri AYRI
    # ==================================================================
    @staticmethod
    def _push_line(out, a, b, color):
        r, g, bl = color
        out.extend([a[0], a[1], a[2], r, g, bl])
        out.extend([b[0], b[1], b[2], r, g, bl])

    @staticmethod
    def _push_tri(out, a, b, c, color):
        r, g, bl = color
        out.extend([a[0], a[1], a[2], r, g, bl])
        out.extend([b[0], b[1], b[2], r, g, bl])
        out.extend([c[0], c[1], c[2], r, g, bl])

    # ==================================================================
    # RENDER — iki pass (tri + line)
    # ==================================================================
    def render(self, mvp):
        if not self._initialized or not self.enabled:
            return

        glUseProgram(self.shader)
        loc = glGetUniformLocation(self.shader, "uMVP")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))

        loc_a = glGetUniformLocation(self.shader, "uAlpha")

        # --- Dolgu ---
        if self.show_fill and self.tri_count > 0:
            if loc_a != -1:
                glUniform1f(loc_a, float(self.fill_alpha))
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glBindVertexArray(self.vao_tri)
            glDrawArrays(GL_TRIANGLES, 0, self.tri_count)
            glBindVertexArray(0)

        # --- Çizgiler ---
        if self.line_count > 0:
            if loc_a != -1:
                glUniform1f(loc_a, 1.0)
            glLineWidth(float(self.line_width))
            glBindVertexArray(self.vao_line)
            glDrawArrays(GL_LINES, 0, self.line_count)
            glBindVertexArray(0)

        glUseProgram(0)

    # ==================================================================
    # CLEANUP
    # ==================================================================
    def cleanup(self):
        for buf in (self.vbo_line, self.vbo_tri):
            if buf:
                glDeleteBuffers(1, [buf])
        for vao in (self.vao_line, self.vao_tri):
            if vao:
                glDeleteVertexArrays(1, [vao])
        if self.shader:
            glDeleteProgram(self.shader)
        self.vbo_line = self.vbo_tri = None
        self.vao_line = self.vao_tri = None
        self.shader = None
        self._initialized = False

    # Yardımcı Metotlar

    def _frame_local_axes(self, p0, p1, rotation_deg=0.0):
        """Frame'in 3 yerel ekseni (1, 2, 3) — birim vektörler."""
        e1 = p1 - p0
        L = np.linalg.norm(e1)
        if L < 1e-9:
            return np.array([1, 0, 0]), np.array([0, 1, 0]), np.array([0, 0, 1])
        e1 = e1 / L

        world_z = np.array([0.0, 0.0, 1.0])
        e2 = world_z - e1 * np.dot(world_z, e1)
        norm = np.linalg.norm(e2)

        if norm < 1e-6:
            # Düşey çubuk → dünya X
            for ref in (np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])):
                e2 = ref - e1 * np.dot(ref, e1)
                norm = np.linalg.norm(e2)
                if norm > 1e-6:
                    break
        if norm < 1e-6:
            e2 = np.array([0.0, 1.0, 0.0])
        else:
            e2 = e2 / norm

        e3 = np.cross(e1, e2)

        # Rotasyon (Local 1 etrafında)
        if abs(rotation_deg) > 1e-9:
            theta = np.radians(rotation_deg)
            c, s = np.cos(theta), np.sin(theta)
            e2_new = c * e2 + s * e3
            e3_new = -s * e2 + c * e3
            e2, e3 = e2_new, e3_new

        return e1, e2, e3

    def _resolve_load_direction(self, load, e1, e2, e3):
        """Yükün 3D dünya yönü."""
        dir_raw = str(getattr(load, "load_dir", "2")).strip()
        csys = str(getattr(load, "coord_sys", "Local")).strip().lower()

        # Global / Gravity / Projected
        if csys in ("global", "g") or dir_raw in ("4", "5", "6", "7", "8", "9", "10"):
            global_map = {
                "4": np.array([1.0, 0.0, 0.0]),
                "5": np.array([0.0, 1.0, 0.0]),
                "6": np.array([0.0, 0.0, 1.0]),
                "7": np.array([0.0, 0.0, -1.0]),   # Gravity
                "8": np.array([1.0, 0.0, 0.0]),
                "9": np.array([0.0, 1.0, 0.0]),
                "10": np.array([0.0, 0.0, 1.0]),
            }
            return global_map.get(dir_raw, np.array([0.0, 0.0, -1.0]))

        # Local
        if dir_raw == "1":
            return e1
        if dir_raw == "3":
            return e3
        return e2  # varsayılan Local 2

    def _emit_point_load(self, node, pl, lines, tris, cam_scale):
        """
        PointLoad görselleştir:
        - Fx, Fy, Fz → dünya ekseni yönünde ok
        - Mx, My, Mz → şimdilik atla (torus dilimi karmaşık)
        Ok boyu: |F| * scale (kamera bağımsız dünya birimi)
        """
        origin = np.array([node.x, node.y, node.z], dtype=float)
        color = self._pattern_color(getattr(pl, "pattern_name", "?"))

        

        components = [
            (pl.fx, np.array([1.0, 0.0, 0.0])),
            (pl.fy, np.array([0.0, 1.0, 0.0])),
            (pl.fz, np.array([0.0, 0.0, 1.0])),
        ]
        for val, axis in components:
            if abs(val) < 1e-9:
                continue
            length = float(val) * self._point_force_scale * self.profile_scale
            self._emit_arrow_3d(origin, axis, length, color, lines, tris)

        # Moment — opsiyonel, atla. İstersen eksen etrafında yay çiz.

    def _emit_arrow_3d(self, origin, direction, length, color, lines, tris):
        """
        origin'den `direction` yönünde `length` boyunda 3D ok.
        Negatif length → ters yön.
        Gövde: line. Ok başı: üçgen (tri).
        """
        d = np.array(direction, dtype=float)
        n = np.linalg.norm(d)
        if n < 1e-9:
            return
        d = d / n

        L = float(length)
        if abs(L) < 1e-9:
            return

        o = np.array(origin, dtype=float)
        tip = o + d * L
        hb = o + d * (L * 0.85)   # ok başı tabanı

        # Gövde
        self._push_line(lines, o, hb, color)

        # Ok başı için dik vektörler
        perp = self._perp_vector(d)
        side = np.cross(d, perp)
        slen = np.linalg.norm(side)
        if slen < 1e-9:
            return
        side = side / slen

        head_w = abs(L) * 0.10
        left  = hb + side * head_w
        right = hb - side * head_w

        self._push_tri(tris, tip, left, right, color)

    @staticmethod
    def _perp_vector(d):
        """d'ye dik herhangi bir birim vektör."""
        a = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([0.0, 1.0, 0.0])
        p = np.cross(d, a)
        n = np.linalg.norm(p)
        return p / n if n > 1e-9 else np.array([1.0, 0.0, 0.0])