# render/area_load_renderer.py
"""Alan yükü görselleştirme — polygon/area merkezinde label + yön oku."""
from __future__ import annotations

import numpy as np
from OpenGL.GL import *
from pyglm import glm

from logging_config import CadLogger

logger = CadLogger.get(__name__)


class AreaLoadRenderer:
    """Polygon/Area üstündeki alan yükleri için label + küçük ok."""

    PATTERN_COLORS = [
        (1.00, 0.30, 0.30),
        (0.30, 0.60, 1.00),
        (0.30, 0.85, 0.45),
        (1.00, 0.75, 0.20),
        (0.85, 0.40, 0.85),
    ]

    def __init__(self):
        self._pattern_color_cache: dict = {}
        self.enabled = False
        self.active_pattern: str | None = None   # None = hepsi
        self._unit_system: str | None = None
        self.arrow_scale = 1.0      # kullanıcı slider'ı
        self.show_labels = True
        self.show_arrows = True

        # Line VAO (ok için)
        self.vao_line = None
        self.vbo_line = None
        self.line_count = 0
        self.shader = None
        self._initialized = False


    # ------------------------------------------------------------------
    def _pattern_color(self, name: str):
        if name in self._pattern_color_cache:
            return self._pattern_color_cache[name]
        h = sum(ord(c) * (i + 1) for i, c in enumerate(str(name))) % len(self.PATTERN_COLORS)
        color = self.PATTERN_COLORS[h]
        self._pattern_color_cache[name] = color
        return color

    # ------------------------------------------------------------------
    # INIT (LoadRenderer'daki shader aynı — kopyala)
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # UPDATE — vertex üret
    # ------------------------------------------------------------------
    def update(self, math_model, camera_scale=1.0, scene_size=1.0, unit_system=None):
        if not self._initialized:
            self.init_gl()

        self._label_items: list[dict] = []
        self.line_count = 0
        self._unit_system = unit_system
        if not self.enabled or math_model is None:
            return

        lines = []
        arrow_len = max(scene_size, 1.0) * 0.04 * self.arrow_scale

        # ★ Pattern filtresi aktifse, sadece o pattern'daki yükleri göster
        for polygon in math_model.polygons.values():
            if not getattr(polygon, "is_visible", True):
                continue
            
            # ★ 1) Atanmış yükler (assigned_loads)
            analysis = math_model.polygon_analysis.get(polygon.unique_id)
            if analysis and analysis.assigned_loads:
                self._emit_polygon_loads(polygon, analysis, lines, arrow_len)
            
            # ★ 2) Rüzgar zone yükleri (zone_children_by_direction)
            if getattr(self, "show_wind_zones", True):
                self._emit_wind_zones(polygon, lines, arrow_len)


        for area in math_model.areas.values():
            if not getattr(area, "is_visible", True):
                continue
            analysis = math_model.polygon_analysis.get(area.unique_id)
            if analysis is None or not analysis.assigned_loads:
                continue
            self._emit_area_loads(area, analysis, lines, arrow_len)

        if lines:
            data = np.asarray(lines, dtype=np.float32)
            self.line_count = len(data) // 6
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo_line)
            glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_DYNAMIC_DRAW)
        else:
            self.line_count = 0

        glBindBuffer(GL_ARRAY_BUFFER, 0)

    def _emit_wind_zones(self, polygon, lines, arrow_len):
        """Her zone için centroid'de label + ok."""
        zone_dict = polygon.zone_children_by_direction or {}
        direction = polygon.show_zones_direction
        if direction is None or direction not in zone_dict:
            return
        
        # Basınç: wind_results'tan q_p
        wind_results = getattr(self, "_wind_results", None) or {}
        result = wind_results.get(direction)
        if result is None:
            return
        q_p = float(getattr(result, "q_p", 0.0))
        wind_dir = np.asarray(
            getattr(result, "direction", (0.0, 0.0, -1.0)), dtype=float
        )
        if np.linalg.norm(wind_dir) < 1e-9:
            wind_dir = np.array([0.0, 0.0, -1.0])
        wind_dir = wind_dir / np.linalg.norm(wind_dir)
        
        for zi, z_dict in enumerate(zone_dict.get(direction, [])):
            coords = z_dict.get("coords") or []
            if len(coords) < 3:
                continue
            
            # Centroid
            pts = np.asarray(coords, dtype=float)
            centroid = pts.mean(axis=0)
            
            # Cpe10 veya cpe1 (override varsa ondan)
            cpe10 = z_dict.get("cpe10_override") or z_dict.get("cpe10", (0.0, 0.0))
            cpe1 = z_dict.get("cpe1_override") or z_dict.get("cpe1", (0.0, 0.0))
            cpe = cpe10[0] if isinstance(cpe10, (list, tuple)) else cpe10
            cpe2 = cpe10[1] if isinstance(cpe10, (list, tuple)) and len(cpe10) > 1 else cpe
            
            # Basınç değeri (Cpe * q_p) — kaba tahmin
            # sign: yüzey normali wind_dir ile ters mi
            try:
                from domain.polygon import Polygon
                zone_nodes = [type("N", (), {"x": c[0], "y": c[1], "z": c[2]})() for c in coords]
                normal = Polygon.calculate_normal(zone_nodes)
                n_arr = np.array([normal.x, normal.y, normal.z], dtype=float)
                sign = -1.0 if float(np.dot(n_arr, wind_dir)) > 0 else 1.0
            except Exception:
                sign = 1.0
            
            pressure = sign * q_p * cpe
            label = z_dict.get("label", f"Z{zi}")
            
            # ★ Label: zone label + pressure
            if abs(pressure) < 1e-3 or abs(pressure) >= 1e5:
                pressure_txt = f"{pressure:+.2e}"
            else:
                pressure_txt = f"{pressure:+.3f}"
            
            unit = ""
            if self._unit_system is not None:
                unit = f"{self._unit_system.force_unit}/{self._unit_system.length_unit}^2"
            
            text = f"WZ {label}: {pressure_txt} {unit}"
            
            color = self._pattern_color(f"WIND_{direction}")
            self._label_items.append({
                "position": tuple(centroid),
                "text": text,
                "color": color,
                "priority": 2,
            })
            
            # ★ Küçük ok (yön)
            if self.show_arrows:
                start = centroid - wind_dir * (arrow_len * 0.5)
                end = centroid + wind_dir * (arrow_len * 0.5)
                self._push_line(lines, start, end, color)
                
    def _emit_polygon_loads(self, polygon, analysis, lines, arrow_len):
        # Centroid
        cx, cy, cz = polygon.centroid()
        center = np.array([cx, cy, cz], dtype=float)
        for load in analysis.assigned_loads:
            self._emit_single_load(center, load, polygon, lines, arrow_len)

    def _emit_area_loads(self, area, analysis, lines, arrow_len):
        nodes = area.nodes
        if not nodes:
            return
        xs = [n.x for n in nodes]
        ys = [n.y for n in nodes]
        zs = [n.z for n in nodes]
        center = np.array([
            sum(xs) / len(xs),
            sum(ys) / len(ys),
            sum(zs) / len(zs),
        ])
        for load in analysis.assigned_loads:
            self._emit_single_load(center, load, area, lines, arrow_len)

    def _emit_single_load(self, center, load, element, lines, arrow_len):
        if self.active_pattern and load.pattern_name != self.active_pattern:
            return
        # Yön vektörü
        direction = self._resolve_direction(load, element)
        if direction is None:
            return

        color = self._pattern_color(load.pattern_name)

        # ★ Bilimsel gösterim — küçük değerler için
        val = float(load.value)
        if abs(val) < 1e-3 or abs(val) >= 1e5:
            text = f"{load.pattern_name}: {val:+.2e}"   # -5.00e-03 gibi
        else:
            text = f"{load.pattern_name}: {val:+.3f}"   # -5.000 gibi
        
        # Birim
        if self._unit_system is None:
            unit = ""
        else:
            unit = f"{self._unit_system.force_unit}/{self._unit_system.length_unit}^2"
    
        full_text = f"{text} {unit}"

        self._label_items.append({
            "position": tuple(center + direction * (arrow_len * 0.2)),
            "text": full_text,
            "color": color,
            "priority": 1,
        })


        # ★ Yön oku (kısa)
        if self.show_arrows:
            start = center - direction * (arrow_len * 0.5)
            end = center + direction * (arrow_len * 0.5)
            self._push_line(lines, start, end, color)
            # Ok başı (2 çizgi)
            perp = self._perp_vector(direction)
            side = np.cross(direction, perp)
            slen = np.linalg.norm(side)
            if slen > 1e-9:
                side = side / slen
                head = arrow_len * 0.3
                left = end - direction * head + side * head * 0.5
                right = end - direction * head - side * head * 0.5
                self._push_line(lines, end, left, color)
                self._push_line(lines, end, right, color)

    def _resolve_direction(self, load, element):
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
        # Local → element normal
        try:
            from domain.polygon import Polygon
            nodes = getattr(element, "nodes", None) or []
            if len(nodes) >= 3:
                n = Polygon.calculate_normal(nodes)
                return np.array([n.x, n.y, n.z], dtype=float)
        except Exception:
            pass
        return np.array([0.0, 0.0, -1.0])

    @staticmethod
    def _perp_vector(d):
        a = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([0.0, 1.0, 0.0])
        p = np.cross(d, a)
        n = np.linalg.norm(p)
        return p / n if n > 1e-9 else np.array([1.0, 0.0, 0.0])

    @staticmethod
    def _push_line(out, a, b, color):
        r, g, bl = color
        out.extend([a[0], a[1], a[2], r, g, bl])
        out.extend([b[0], b[1], b[2], r, g, bl])

    # ------------------------------------------------------------------
    # RENDER — sadece ok çizgileri
    # ------------------------------------------------------------------
    def render(self, mvp):
        if not self._initialized or not self.enabled:
            return
        if self.line_count == 0:
            return

        glUseProgram(self.shader)
        loc = glGetUniformLocation(self.shader, "uMVP")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))
        loc_a = glGetUniformLocation(self.shader, "uAlpha")
        if loc_a != -1:
            glUniform1f(loc_a, 1.0)

        glBindVertexArray(self.vao_line)
        glDrawArrays(GL_LINES, 0, self.line_count)
        glBindVertexArray(0)
        glUseProgram(0)

    def get_labels(self) -> list[dict]:
        return getattr(self, "_label_items", [])

    def cleanup(self):
        for buf in (self.vbo_line,):
            if buf:
                glDeleteBuffers(1, [buf])
        for vao in (self.vao_line,):
            if vao:
                glDeleteVertexArrays(1, [vao])
        if self.shader:
            glDeleteProgram(self.shader)
        self.vbo_line = self.vao_line = None
        self.shader = None
        self._initialized = False