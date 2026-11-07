# render/snapsquare.py
from __future__ import annotations

import numpy as np
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader
from pyglm import glm

from domain.vertex import Vertex
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class SnapSquareRenderer:

    SNAP_RADIUS_PX = 10

    def __init__(self):
        self.shader = None
        self.u_color_loc = -1
        self.vao = None
        self.vbo = None
        self._init_shader()

        self.size = 0.012
        self.styles = {
            "default":  {"color": (0.50, 0.90, 0.00, 1.0), "scale": 0.80},  # sarı
            "grid":     {"color": (1.00, 0.90, 0.00, 1.0), "scale": 1.00},  # sarı
            "node":     {"color": (0.20, 0.55, 1.00, 1.0), "scale": 1.25},  # mavi
            "vertex":   {"color": (0.20, 0.55, 1.00, 1.0), "scale": 1.25},  # mavi
            "frame":    {"color": (0.20, 0.85, 0.40, 1.0), "scale": 1.15},  # yeşil
            "link":     {"color": (0.50, 0.85, 0.50, 1.0), "scale": 1.15},  # açık yeşil
            "area":     {"color": (1.00, 0.50, 0.00, 1.0), "scale": 1.15},  # turuncu
            "polygon":  {"color": (0.90, 0.30, 0.90, 1.0), "scale": 1.15},  # magenta
            "line":     {"color": (1.00, 1.00, 1.00, 1.0), "scale": 1.15},  # beyaz
        }

    def _init_shader(self):
        vertex_src = """
        #version 330 core
        layout(location = 0) in vec2 aPos;
        void main() {
            gl_Position = vec4(aPos, 0.0, 1.0);
        }
        """
        frag_src = """
        #version 330 core
        uniform vec4 uColor;
        out vec4 fCol;
        void main() {
            fCol = uColor;
        }
        """
        self.shader = compileProgram(
            compileShader(vertex_src, GL_VERTEX_SHADER),
            compileShader(frag_src, GL_FRAGMENT_SHADER),
        )
        glUseProgram(self.shader)
        self.u_color_loc = glGetUniformLocation(self.shader, "uColor")
        glUseProgram(0)

    # ------------------------------------------------------------------
    def find_snap(self, engine, x, y, magnetic=False):
        if magnetic:
            finders = (
                (self._find_node, "node"),
                (self._find_grid_snap, "grid"),
            )
        else:
            finders = (
                (self._find_node, "node"),
                (self._find_grid_snap, "grid"),
                (self._find_frame, "frame"),
                (self._find_link, "link"),
                (self._find_area, "area"),
                (self._find_polygon, "polygon"),
                (self._find_line, "line"),
            )

        for finder, kind in finders:
            result = finder(engine, x, y)
            if result is not None:
                is_snap = (kind in ("node", "grid"))
                return result, is_snap, kind
        return None, False, "default"

    def _find_node(self, engine, x, y):
        scene = engine.math_model
        cam = engine.cam
        if not scene or not cam:
            return None
        mvp = cam.get_projection_matrix() @ cam.get_view_matrix()
        best, best_d2 = None, self.SNAP_RADIUS_PX ** 2
        for node in scene.nodes.values():
            if not node.is_visible:
                continue
            p = self._project_pt(engine, mvp, node.x, node.y, node.z)
            if p is None:
                continue
            d2 = (p[0] - x) ** 2 + (p[1] - y) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = node
        return best

    def _find_frame(self, engine, x, y):
        math_model = engine.math_model
        cam = engine.cam
        if not math_model or not cam:
            return None
        mvp = cam.get_projection_matrix() @ cam.get_view_matrix()
        best, best_d2 = None, self.SNAP_RADIUS_PX ** 2
        for frame in math_model.frames.values():
            if not frame.is_visible:
                continue
            n0, n1 = frame.node_i, frame.node_j
            p0 = self._project_pt(engine, mvp, n0.x, n0.y, n0.z)
            p1 = self._project_pt(engine, mvp, n1.x, n1.y, n1.z)
            if p0 is None or p1 is None:
                continue
            d2, mid = self._dist_to_segment((x, y), p0, p1)
            if d2 < best_d2:
                best_d2 = d2
                # Orta nokta dünya koordinatı
                mx = (n0.x + n1.x) * 0.5
                my = (n0.y + n1.y) * 0.5
                mz = (n0.z + n1.z) * 0.5
                best = Vertex(mx, my, mz, label=getattr(frame, "label", ""))
        return best

    def _find_grid_snap(self, engine, x, y):
        scene = engine.scene
        project = engine.project if scene else None
        if not project:
            return None

        plane = project.active_plane
        if plane is not None:
            axis = ("x", "y", "z")[int(np.argmax(np.abs(plane.normal)))]
            level = float(np.dot(plane.normal, plane.origin))
            candidates = project.grid.snap_points_on_plane(axis, level)
        else:
            candidates = project.grid.snap_points()

        if not candidates:
            return None

        cam = engine.cam
        mvp = cam.get_projection_matrix() @ cam.get_view_matrix()
        best, best_d2 = None, self.SNAP_RADIUS_PX ** 2
        for c in candidates:
            p = self._project_pt(engine, mvp, c[0], c[1], c[2])
            if p is None:
                continue
            d2 = (p[0] - x) ** 2 + (p[1] - y) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = c
        if best is None:
            return None
        return Vertex(best[0], best[1], best[2])

    def _project_pt(self, engine, mvp, x, y, z):
        w, h = engine.w, engine.h
        clip = mvp * glm.vec4(x, y, z, 1.0)
        if clip.w <= 1e-9:
            return None
        ndc = glm.vec3(clip) / clip.w
        return (ndc.x + 1.0) * w * 0.5, (1.0 - ndc.y) * h * 0.5

    @staticmethod
    def _vertex_from_node(node) -> Vertex:
        return Vertex(
            node.x, node.y, node.z,
            label=getattr(node, "label", ""),
            source_node_id=getattr(node, "unique_id", None),
        )

    # ------------------------------------------------------------------
    # Görsel
    # ------------------------------------------------------------------
    def draw_snap(self, mouse_x, mouse_y, w, h, active=True, snap_type="default"):
        if not active or not self.shader:
            return

        if self.vao is None:
            self.vao = glGenVertexArrays(1)
            self.vbo = glGenBuffers(1)

        nx = (mouse_x / w) * 2.0 - 1.0
        ny = 1.0 - (mouse_y / h) * 2.0
        asp = w / h

        style = self.styles.get(snap_type, self.styles["default"])
        s = self.size * style["scale"]

        vertices = np.array([
            nx - s / asp, ny - s,
            nx + s / asp, ny - s,
            nx + s / asp, ny + s,
            nx - s / asp, ny + s,
        ], dtype=np.float32)

        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glUseProgram(self.shader)
        glUniform4f(self.u_color_loc, *style["color"])
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STREAM_DRAW)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(0)
        glDrawArrays(GL_LINE_LOOP, 0, 4)
        glBindVertexArray(0)
        glUseProgram(0)
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)

    def _find_polygon(self, engine, x, y):
        scene = engine.scene
        cam = engine.cam
        if not scene or not cam:
            return None
        mvp = cam.get_projection_matrix() @ cam.get_view_matrix()
        best, best_d2 = None, self.SNAP_RADIUS_PX ** 2
        for poly in scene.polygons.values():
            if not getattr(poly, "is_visible", True):
                continue
            cx, cy, cz = poly.centroid()
            p = self._project_pt(engine, mvp, cx, cy, cz)
            if p is None:
                continue
            d2 = (p[0] - x) ** 2 + (p[1] - y) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = Vertex(cx, cy, cz)
        return best

    @staticmethod
    def _dist_to_segment(p, a, b):
        px, py = p
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        if abs(dx) < 1e-9 and abs(dy) < 1e-9:
            return (px - ax)**2 + (py - ay)**2, (ax, ay)
        t = ((px - ax) * dx + (py - ay) * dy) / (dx*dx + dy*dy)
        t = max(0.0, min(1.0, t))
        cx, cy = ax + t*dx, ay + t*dy
        return (px - cx)**2 + (py - cy)**2, (cx, cy)

    def cleanup(self):
        if self.shader and glIsProgram(self.shader):
            glDeleteProgram(self.shader)
            self.shader = None
        if self.vao and glIsVertexArray(self.vao):
            glDeleteVertexArrays(1, [self.vao])
            self.vao = None
        if self.vbo and glIsBuffer(self.vbo):
            glDeleteBuffers(1, [self.vbo])
            self.vbo = None

    def draw_at_world_pos(self, engine, x, y, z, w, h, snap_type="default", active=True):
        if not active or not self.shader:
            return

        if self.vao is None:
            self.vao = glGenVertexArrays(1)
            self.vbo = glGenBuffers(1)

        cam = engine.cam
        if not cam:
            return
        mvp = cam.get_projection_matrix() @ cam.get_view_matrix()
        
        # 3D dünya koordinatını ekran koordinatına (pixel) projekte et
        p = self._project_pt(engine, mvp, x, y, z)
        if p is None:
            return

        mouse_x, mouse_y = p[0], p[1]
        nx = (mouse_x / w) * 2.0 - 1.0
        ny = 1.0 - (mouse_y / h) * 2.0
        asp = w / h

        style = self.styles.get(snap_type, self.styles["default"])
        s = self.size * style["scale"]

        vertices = np.array([
            nx - s / asp, ny - s,
            nx + s / asp, ny - s,
            nx + s / asp, ny + s,
            nx - s / asp, ny + s,
        ], dtype=np.float32)

        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glUseProgram(self.shader)
        glUniform4f(self.u_color_loc, *style["color"])
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STREAM_DRAW)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(0)
        glDrawArrays(GL_LINE_LOOP, 0, 4)
        glBindVertexArray(0)
        glUseProgram(0)
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)