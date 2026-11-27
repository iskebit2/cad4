# render/load_renderer.py
from __future__ import annotations

import ctypes
from pyglm import glm
import numpy as np
from OpenGL.GL import *

from logging_config import CadLogger

logger = CadLogger.get(__name__)


class LoadRenderer:

    PROFILE_HEIGHT_RATIO = 0.10
    ARROW_MIN = 3
    ARROW_MAX = 12
    ARROW_LENGTH_RATIO = 0.35

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
        self._pattern_color_cache: dict[str, tuple[float, float, float]] = {}

        self.available_patterns: list[str] = []
        self.enabled = False
        self.active_pattern: str | None = None

        self.profile_scale = 1.0
        self.line_width = 2.0
        self.fill_alpha = 0.8
        self.show_arrows = True
        self.show_fill = True
        self._point_force_scale = 50.0

        self.show_frame_loads = True
        self.show_point_loads = True
        self.show_area_loads = True
        self.show_wind_zones = True
        self._wind_results: dict = {}

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

        stride = 6 * 4
        self.vao_line = glGenVertexArrays(1)
        self.vbo_line = glGenBuffers(1)
        glBindVertexArray(self.vao_line)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo_line)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(3 * 4))
        glBindVertexArray(0)

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

        fs = glCreateShader(GL_FRAGMENT_SHADER)
        glShaderSource(fs, fs_src)
        glCompileShader(fs)

        p = glCreateProgram()
        glAttachShader(p, vs)
        glAttachShader(p, fs)
        glLinkProgram(p)

        glDeleteShader(vs)
        glDeleteShader(fs)
        return p

    def _pattern_color(self, name: str) -> tuple[float, float, float]:
        if name in self._pattern_color_cache:
            return self._pattern_color_cache[name]
        h = sum(ord(c) * (i + 1) for i, c in enumerate(str(name))) % len(self.PATTERN_COLORS)
        color = self.PATTERN_COLORS[h]
        self._pattern_color_cache[name] = color
        return color

    def update(self, scene, camera_scale: float = 1.0, scene_size: float = 1.0):
        if not self._initialized:
            self.init_gl()

        if not self.enabled or not scene:
            self.line_count = 0
            self.tri_count = 0
            return

        self.available_patterns = self._scan_patterns(scene)

        lines: list[float] = []
        tris: list[float] = []

        if self.show_frame_loads and hasattr(scene, "frames"):
            for frame in scene.frames.values():
                if not getattr(frame, "is_visible", True):
                    continue
                load_sets = getattr(frame, "dist_load_sets", None)
                if not load_sets:
                    continue
                for key, ls in load_sets.items():
                    # key = (pattern, load_dir, coord_sys, force_or_moment)
                    pattern = key[0] if isinstance(key, tuple) else key
                    if self.active_pattern and pattern != self.active_pattern:
                        continue
                    self._emit_load_set(frame, ls, lines, tris, camera_scale)

        if self.show_point_loads and hasattr(scene, "nodes"):
            point_load_max = 1.0
            for node in scene.nodes.values():
                if not getattr(node, "is_visible", True):
                    continue
                for pl in getattr(node, "loads", None) or []:
                    pat = getattr(pl, "pattern_name", "?")
                    if self.active_pattern and pat != self.active_pattern:
                        continue
                    mag = abs(pl.fx) + abs(pl.fy) + abs(pl.fz)
                    point_load_max = max(point_load_max, mag)

            target_arrow_len = max(scene_size, 1.0) * 0.05
            self._point_force_scale = target_arrow_len / point_load_max

            for node in scene.nodes.values():
                if not getattr(node, "is_visible", True):
                    continue
                for pl in getattr(node, "loads", None) or []:
                    pat = getattr(pl, "pattern_name", "?")
                    if self.active_pattern and pat != self.active_pattern:
                        continue
                    self._emit_point_load(node, pl, lines, tris)

        if self.show_area_loads and hasattr(scene, "polygons") and hasattr(scene, "polygon_analysis"):
            arrow_len = max(scene_size, 1.0) * 0.04 * self.profile_scale
            for polygon in scene.polygons.values():
                if not getattr(polygon, "is_visible", True):
                    continue
                analysis = scene.polygon_analysis.get(polygon.unique_id)
                if analysis and analysis.assigned_loads:
                    for load in analysis.assigned_loads:
                        if self.active_pattern and load.pattern_name != self.active_pattern:
                            continue
                        self._emit_polygon_load(polygon, load, lines, tris, arrow_len)
                if self.show_wind_zones:
                    self._emit_wind_zones(polygon, lines, tris, arrow_len)

        if self.show_area_loads and hasattr(scene, "areas") and hasattr(scene, "polygon_analysis"):
            arrow_len = max(scene_size, 1.0) * 0.04 * self.profile_scale
            for area in scene.areas.values():
                if not getattr(area, "is_visible", True):
                    continue
                analysis = scene.polygon_analysis.get(area.unique_id)
                if analysis and analysis.assigned_loads:
                    for load in analysis.assigned_loads:
                        if self.active_pattern and load.pattern_name != self.active_pattern:
                            continue
                        self._emit_area_load(area, load, lines, tris, arrow_len)

        if lines:
            data_line = np.asarray(lines, dtype=np.float32)
            self.line_count = len(data_line) // 6
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo_line)
            glBufferData(GL_ARRAY_BUFFER, data_line.nbytes, data_line, GL_DYNAMIC_DRAW)
        else:
            self.line_count = 0

        if tris:
            data_tri = np.asarray(tris, dtype=np.float32)
            self.tri_count = len(data_tri) // 6
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo_tri)
            glBufferData(GL_ARRAY_BUFFER, data_tri.nbytes, data_tri, GL_DYNAMIC_DRAW)
        else:
            self.tri_count = 0

        glBindBuffer(GL_ARRAY_BUFFER, 0)

    def _scan_patterns(self, scene) -> list[str]:
        pats = set()
        if hasattr(scene, "frames"):
            for frame in scene.frames.values():
                load_sets = getattr(frame, "dist_load_sets", None)
                if load_sets:
                    for k in load_sets.keys():
                        pat = k[0] if isinstance(k, tuple) else k
                        if pat:
                            pats.add(pat)
                for dl in getattr(frame, "dist_loads", []) or []:
                    p = getattr(dl, "pattern_name", None)
                    if p:
                        pats.add(p)

        if hasattr(scene, "nodes"):
            for node in scene.nodes.values():
                for pl in getattr(node, "loads", None) or []:
                    p = getattr(pl, "pattern_name", None)
                    if p:
                        pats.add(p)

        if hasattr(scene, "polygons") and hasattr(scene, "polygon_analysis"):
            for polygon in scene.polygons.values():
                analysis = scene.polygon_analysis.get(polygon.unique_id)
                if analysis and analysis.assigned_loads:
                    for load in analysis.assigned_loads:
                        p = getattr(load, "pattern_name", None)
                        if p:
                            pats.add(p)

        if hasattr(scene, "areas") and hasattr(scene, "polygon_analysis"):
            for area in scene.areas.values():
                analysis = scene.polygon_analysis.get(area.unique_id)
                if analysis and analysis.assigned_loads:
                    for load in analysis.assigned_loads:
                        p = getattr(load, "pattern_name", None)
                        if p:
                            pats.add(p)

        return sorted(pats)

    def _emit_load_set(self, frame, ls, lines, tris, cam_scale):
        segments = getattr(ls, "segments", None) or []
        if not segments:
            return

        pattern = getattr(ls, "pattern_name", "?")
        load_dir = getattr(ls, "load_dir", "2")

        # load_dir'i renge dahil et ki farklı yönler ayırt edilebilsin
        color = self._pattern_color(f"{pattern}_{load_dir}")

        # Süreksiz aralıkları ayrı profiller olarak çiz
        if hasattr(ls, "to_contiguous_runs"):
            runs = ls.to_contiguous_runs()
        else:
            # geriye dönük uyumluluk: tek run
            runs = [list(segments)]
        group_max_q = ls.max_abs_q() if hasattr(ls, "max_abs_q") else None
        for run in runs:
            pts: list[tuple[float, float]] = []
            for seg in run:
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
                continue

            self._emit_profile(
                            frame, pts, color, lines, tris, cam_scale,
                            load=ls, max_q_override=group_max_q,
                        )

    @staticmethod
    def _attr(obj, key):
        if hasattr(obj, key):
            return getattr(obj, key)
        if isinstance(obj, dict):
            return obj.get(key)
        return None

    def _emit_profile(self, frame, pts, color, lines, tris, cam_scale,
                  load=None, max_q_override=None):
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
        e1, e2, e3 = self._frame_local_axes(p0, p1, getattr(frame, "rotation_deg", 0.0))

        load_dir_vec = self._resolve_load_direction(load, e1, e2, e3) if load is not None else e2
        up = -load_dir_vec

        if max_q_override is not None and max_q_override > 1e-12:
            max_q = float(max_q_override)
        else:
            max_q = max(abs(q) for _, q in pts) or 1.0
        profile_h = max(
            L * self.PROFILE_HEIGHT_RATIO * self.profile_scale,
            L * 0.02,
        )

        def to_3d(xr, q):
            base = p0 + axis * (xr * L)
            return base + up * (q / max_q * profile_h)

        for i in range(len(pts) - 1):
            a = to_3d(*pts[i])
            b = to_3d(*pts[i + 1])
            self._push_line(lines, a, b, color)

        for xr, q in (pts[0], pts[-1]):
            base = p0 + axis * (xr * L)
            tip = to_3d(xr, q)
            if np.linalg.norm(tip - base) > 1e-6:
                self._push_line(lines, base, tip, color)

        for i in range(len(pts) - 1):
            xa, qa = pts[i]
            xb, qb = pts[i + 1]
            ta = to_3d(xa, qa)
            tb = to_3d(xb, qb)
            ba = p0 + axis * (xa * L)
            bb = p0 + axis * (xb * L)
            self._push_tri(tris, ta, ba, bb, color)
            self._push_tri(tris, ta, bb, tb, color)

        if self.show_arrows:
            n = max(self.ARROW_MIN, min(self.ARROW_MAX, int(L / 400.0) + 2))
            for i in range(n):
                xr = (i + 0.5) / n
                q = self._interp(pts, xr)
                if abs(q) < 1e-9:
                    continue

                base = p0 + axis * (xr * L)
                tip = base + up * (q / max_q * profile_h)
                self._push_line(lines, base, tip, color)

                d = tip - base
                dlen = np.linalg.norm(d)
                if dlen < 1e-6:
                    continue
                d = d / dlen

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

    def render(self, mvp):
        if not self._initialized or not self.enabled:
            return

        glUseProgram(self.shader)
        loc = glGetUniformLocation(self.shader, "uMVP")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))

        loc_a = glGetUniformLocation(self.shader, "uAlpha")

        if self.show_fill and self.tri_count > 0:
            if loc_a != -1:
                glUniform1f(loc_a, float(self.fill_alpha))
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glBindVertexArray(self.vao_tri)
            glDrawArrays(GL_TRIANGLES, 0, self.tri_count)
            glBindVertexArray(0)

        if self.line_count > 0:
            if loc_a != -1:
                glUniform1f(loc_a, 1.0)
            glLineWidth(float(self.line_width))
            glBindVertexArray(self.vao_line)
            glDrawArrays(GL_LINES, 0, self.line_count)
            glBindVertexArray(0)

        glUseProgram(0)

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

    @staticmethod
    def _frame_local_axes(p0, p1, rotation_deg=0.0):
        e1 = p1 - p0
        L = np.linalg.norm(e1)
        if L < 1e-9:
            return np.array([1, 0, 0]), np.array([0, 1, 0]), np.array([0, 0, 1])
        e1 = e1 / L

        world_z = np.array([0.0, 0.0, 1.0])
        e2 = world_z - e1 * np.dot(world_z, e1)
        norm = np.linalg.norm(e2)

        if norm < 1e-6:
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

        if abs(rotation_deg) > 1e-9:
            theta = np.radians(rotation_deg)
            c, s = np.cos(theta), np.sin(theta)
            e2_new = c * e2 + s * e3
            e3_new = -s * e2 + c * e3
            e2, e3 = e2_new, e3_new

        return e1, e2, e3

    @staticmethod
    def _resolve_load_direction(load, e1, e2, e3):
        dir_raw = str(getattr(load, "load_dir", "2")).strip()
        csys = str(getattr(load, "coord_sys", "Local")).strip().lower()

        if csys in ("global", "g") or dir_raw in ("4", "5", "6", "7", "8", "9", "10"):
            global_map = {
                "4": np.array([1.0, 0.0, 0.0]),
                "5": np.array([0.0, 1.0, 0.0]),
                "6": np.array([0.0, 0.0, 1.0]),
                "7": np.array([0.0, 0.0, -1.0]),
                "8": np.array([1.0, 0.0, 0.0]),
                "9": np.array([0.0, 1.0, 0.0]),
                "10": np.array([0.0, 0.0, 1.0]),
            }
            return global_map.get(dir_raw, np.array([0.0, 0.0, -1.0]))

        if dir_raw == "1":
            return e1
        if dir_raw == "3":
            return e3
        return e2

    def _emit_point_load(self, node, pl, lines, tris):
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

    def _emit_polygon_load(self, polygon, load, lines, tris, arrow_len):
        nodes = getattr(polygon, "nodes", None) or []
        if not nodes:
            return
        direction = self._resolve_area_direction(load, polygon)
        if direction is None:
            return
        color = self._pattern_color(load.pattern_name)
        self._emit_distributed_patch(nodes, direction, arrow_len * 0.7, color, lines, tris)

    def _emit_area_load(self, area, load, lines, tris, arrow_len):
        nodes = getattr(area, "nodes", None) or []
        if not nodes:
            return
        direction = self._resolve_area_direction(load, area)
        if direction is None:
            return
        color = self._pattern_color(load.pattern_name)
        self._emit_distributed_patch(nodes, direction, arrow_len * 0.7, color, lines, tris)

    def _emit_wind_zones(self, polygon, lines, tris, arrow_len):
        zone_dict = polygon.zone_children_by_direction or {}
        direction = polygon.show_zones_direction
        if direction is None or direction not in zone_dict:
            return
        wind_results = getattr(self, "_wind_results", None) or {}
        result = wind_results.get(direction)
        if result is None:
            return
        wind_dir = np.asarray(getattr(result, "direction", (0.0, 0.0, -1.0)), dtype=float)
        if np.linalg.norm(wind_dir) < 1e-9:
            wind_dir = np.array([0.0, 0.0, -1.0])
        wind_dir = wind_dir / np.linalg.norm(wind_dir)

        for zi, z_dict in enumerate(zone_dict.get(direction, [])):
            coords = z_dict.get("coords") or []
            if len(coords) < 3:
                continue
            zone_nodes = [type("N", (), {"x": c[0], "y": c[1], "z": c[2]})() for c in coords]
            color = self._pattern_color(f"WIND_{direction}")
            self._emit_distributed_patch(zone_nodes, wind_dir, arrow_len * 0.7, color, lines, tris)

    def _emit_distributed_patch(self, nodes, direction, length, color, lines, tris):
        pts = np.array([[n.x, n.y, n.z] for n in nodes], dtype=float)
        center = pts.mean(axis=0)

        d = np.array(direction, dtype=float)
        dn = np.linalg.norm(d)
        if dn < 1e-9:
            return
        d = d / dn

        perp = self._perp_vector(d)
        u = np.cross(d, perp)
        un = np.linalg.norm(u)
        u = u / un if un > 1e-9 else np.array([1.0, 0.0, 0.0])
        v = np.cross(d, u)
        vn = np.linalg.norm(v)
        v = v / vn if vn > 1e-9 else np.array([0.0, 1.0, 0.0])

        min_coords = pts.min(axis=0)
        max_coords = pts.max(axis=0)
        extent = max_coords - min_coords
        span = max(extent[0], extent[1], extent[2]) * 0.35

        offsets = [
            center,
            center + u * span,
            center - u * span,
            center + v * span,
            center - v * span,
        ]

        for pos in offsets:
            self._emit_arrow_3d(pos, d, length, color, lines, tris)

    def _resolve_area_direction(self, load, element):
        direction_map = {
            "GRAV": np.array([0.0, 0.0, -1.0]),
            "GX": np.array([1.0, 0.0, 0.0]),
            "GY": np.array([0.0, 1.0, 0.0]),
            "GZ": np.array([0.0, 0.0, 1.0]),
        }
        if load.direction is None:
            return np.array([0.0, 0.0, -1.0])
        val = load.direction.value if hasattr(load.direction, "value") else str(load.direction)
        if val in direction_map:
            return direction_map[val]
        nodes = getattr(element, "nodes", None) or []
        if len(nodes) >= 3:
            return self._calculate_normal(nodes)
        return np.array([0.0, 0.0, -1.0])

    @staticmethod
    def _calculate_normal(nodes):
        if len(nodes) < 3:
            return np.array([0.0, 0.0, 1.0])
        p0 = np.array([nodes[0].x, nodes[0].y, nodes[0].z], dtype=float)
        p1 = np.array([nodes[1].x, nodes[1].y, nodes[1].z], dtype=float)
        p2 = np.array([nodes[2].x, nodes[2].y, nodes[2].z], dtype=float)
        v1 = p1 - p0
        v2 = p2 - p0
        n = np.cross(v1, v2)
        norm = np.linalg.norm(n)
        if norm < 1e-9:
            return np.array([0.0, 0.0, 1.0])
        return n / norm

    def _emit_arrow_3d(self, origin, direction, length, color, lines, tris):
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
        hb = o + d * (L * 0.85)

        self._push_line(lines, o, hb, color)

        perp = self._perp_vector(d)
        side = np.cross(d, perp)
        slen = np.linalg.norm(side)
        if slen < 1e-9:
            return
        side = side / slen

        head_w = abs(L) * 0.10
        left = hb + side * head_w
        right = hb - side * head_w

        self._push_tri(tris, tip, left, right, color)

    @staticmethod
    def _perp_vector(d):
        a = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([0.0, 1.0, 0.0])
        p = np.cross(d, a)
        n = np.linalg.norm(p)
        return p / n if n > 1e-9 else np.array([1.0, 0.0, 0.0])