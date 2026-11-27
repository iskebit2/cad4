# render/interactionrenderer.py
from __future__ import annotations

import numpy as np
from OpenGL.GL import *
from pyglm import glm

from domain.element import Area, Frame, Node
from domain.polygon import Polygon
from plane.plane import Plane
from render.snapsquare import SnapSquareRenderer


class InteractionRenderer:

    _SNAP_STYLES = {
        "default":  {"color": (0.75, 0.92, 0.35, 0.95), "scale": 0.80, "shape": "square"},
        "grid":     {"color": (1.00, 0.86, 0.15, 1.00), "scale": 1.00, "shape": "cross"},
        "node":     {"color": (0.20, 0.72, 1.00, 1.00), "scale": 1.00, "shape": "square_dot"},
        "vertex":   {"color": (0.20, 0.72, 1.00, 1.00), "scale": 1.00, "shape": "square_dot"},
        "frame":    {"color": (0.22, 0.92, 0.48, 1.00), "scale": 1.15, "shape": "triangle"},
        "link":     {"color": (0.45, 0.95, 0.55, 1.00), "scale": 1.15, "shape": "triangle"},
        "midpoint": {"color": (0.22, 0.92, 0.48, 1.00), "scale": 1.15, "shape": "triangle"},
        "area":     {"color": (1.00, 0.55, 0.12, 1.00), "scale": 1.10, "shape": "diamond"},
        "polygon":  {"color": (0.95, 0.35, 0.90, 1.00), "scale": 1.10, "shape": "diamond"},
        "line":     {"color": (0.95, 0.95, 0.95, 1.00), "scale": 1.00, "shape": "square"},
    }

    def __init__(self, overlay_shader):
        self.overlay_shader = overlay_shader
        self._overlay_mvp_loc = overlay_shader.get_loc("mvp") if overlay_shader else -1
        self._overlay_color_loc = overlay_shader.get_loc("color") if overlay_shader else -1

        self._dyn_vao = None
        self._dyn_vbo = None
        self.preview_plane = None

    def render(self, engine, w, h, camera=None, viewport_name=None,
               mouse_pos=None, plane=None, visible_ids=None):
        if not engine:
            return
        show = getattr(engine, "show", None) or {}
        if not show.get("interaction", False):
            return

        camera = camera or engine.cam
        if mouse_pos is None and viewport_name is None and engine.input:
            mouse_pos = (
                engine.input.state.mouse_pos.x,
                engine.input.state.mouse_pos.y,
            )

        if show.get("snap", False) and engine.snap and getattr(engine, "hover_visual_enabled", True):
            self._draw_snap(engine, w, h, camera, mouse_pos, visible_ids=visible_ids)

        if show.get("tool_preview", False) and engine.draw_mgr and engine.draw_mgr.is_active:
            mvp = camera.get_projection_matrix() @ camera.get_view_matrix()
            engine.draw_mgr.render_preview(mvp, engine.preview_s)

        tool = getattr(engine, "plane_draw_mgr", None)
        if show.get("tool_preview", False) and tool is not None and tool.is_active:
            mvp = camera.get_projection_matrix() @ camera.get_view_matrix()
            tool.render(mvp)

        if show.get("plane_preview", False) and self.preview_plane is not None and camera is not None:
            mvp = camera.get_projection_matrix() @ camera.get_view_matrix()
            self._draw_plane_preview(self.preview_plane, mvp)

        pfe = getattr(engine, "_plane_from_element", None)
        if show.get("plane_preview", False) and pfe is not None and pfe.active and pfe.hover_element is not None:
            el = pfe.hover_element
            self._draw_element_outline(el, camera, color=(0.3, 0.9, 0.3, 1.0))
            cand_plane = Plane.from_element(el, frame_local_12=pfe.frame_axis_12)
            mvp = camera.get_projection_matrix() @ camera.get_view_matrix()
            self._draw_plane_preview(cand_plane, mvp)

    def _draw_snap(self, engine, w, h, camera, mouse_pos, visible_ids=None):
        if not getattr(engine, "hover_visual_enabled", True):
            return
        if self._draw_tool_snap(engine, w, h, camera):
            return
        self._draw_hover_snap(engine, w, h, camera, mouse_pos, visible_ids=visible_ids)

    def _draw_tool_snap(self, engine, w, h, camera) -> bool:
        for tool in (getattr(engine, "plane_draw_mgr", None),
                     getattr(engine, "draw_mgr", None)):
            if tool is None or not tool.is_active or tool.hover_node is None:
                continue
            node = tool.hover_node
            screen = self._project(camera, node.x, node.y, node.z, w, h)
            if screen is None:
                continue
            snap_type = getattr(tool, "hover_snap_type", None) or getattr(tool, "hover_type", "node")
            self._draw_snap_marker(screen[0], screen[1], w, h, snap_type)
            return True
        return False

    def _draw_hover_snap(self, engine, w, h, camera, mouse_pos, visible_ids=None) -> bool:
        if engine.hover_id <= 0 or mouse_pos is None:
            return False

        element = engine._find_element(engine.hover_id)
        if element is None:
            return False

        if visible_ids is not None and getattr(element, "unique_id", None) not in visible_ids:
            return False

        mx, my = mouse_pos
        if isinstance(element, Node):
            screen = self._project(camera, element.x, element.y, element.z, w, h)
            if screen is not None:
                self._draw_snap_marker(screen[0], screen[1], w, h, "node")
                return True

        kind = type(element).__name__.lower()
        self._draw_snap_marker(mx, my, w, h, kind)
        return True

    def _draw_snap_marker(self, px: float, py: float, w: int, h: int, snap_type: str) -> None:
        if self.overlay_shader is None or w <= 0 or h <= 0:
            return
        self._ensure_dynamic_buffers()

        style = self._SNAP_STYLES.get(snap_type, self._SNAP_STYLES["default"])
        r = SnapSquareRenderer.SNAP_RADIUS_PX * style["scale"]
        shape = style["shape"]

        if shape == "triangle":
            pts = [
                px, py - r * 1.15, px - r, py + r * 0.85,
                px - r, py + r * 0.85, px + r, py + r * 0.85,
                px + r, py + r * 0.85, px, py - r * 1.15,
            ]
        elif shape == "diamond":
            pts = [
                px, py - r * 1.15, px + r * 1.15, py,
                px + r * 1.15, py, px, py + r * 1.15,
                px, py + r * 1.15, px - r * 1.15, py,
                px - r * 1.15, py, px, py - r * 1.15,
            ]
        elif shape == "cross":
            c = r * 0.85
            pts = [
                px - c, py - c, px + c, py + c,
                px - c, py + c, px + c, py - c,
            ]
        else:
            pts = [
                px - r, py - r, px + r, py - r,
                px + r, py - r, px + r, py + r,
                px + r, py + r, px - r, py + r,
                px - r, py + r, px - r, py - r,
            ]
            if shape == "square_dot":
                d = r * 0.25
                pts.extend([px - d, py, px + d, py, px, py - d, px, py + d])

        verts = np.zeros((len(pts) // 2, 3), dtype=np.float32)
        verts[:, 0] = pts[0::2]
        verts[:, 1] = pts[1::2]

        self.overlay_shader.use()
        proj = glm.ortho(0.0, float(w), float(h), 0.0, -1.0, 1.0)
        if self._overlay_mvp_loc != -1:
            glUniformMatrix4fv(self._overlay_mvp_loc, 1, GL_FALSE, glm.value_ptr(proj))
        if self._overlay_color_loc == -1:
            return

        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glLineWidth(3.5)
        self._upload_and_draw(
            self._dyn_vao, self._dyn_vbo, verts.reshape(-1),
            GL_LINES, len(verts), (0.04, 0.05, 0.08, 0.85), self._overlay_color_loc,
        )
        glLineWidth(1.8)
        self._upload_and_draw(
            self._dyn_vao, self._dyn_vbo, verts.reshape(-1),
            GL_LINES, len(verts), style["color"], self._overlay_color_loc,
        )

        glLineWidth(1.0)
        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glEnable(GL_DEPTH_TEST)

    def _draw_element_outline(self, element, camera, color=(1, 1, 0, 1)):
        if self.overlay_shader is None:
            return
        self._ensure_dynamic_buffers()

        verts = []
        if isinstance(element, Frame):
            ni, nj = element.node_i, element.node_j
            if ni and nj:
                verts.extend([ni.x, ni.y, ni.z, nj.x, nj.y, nj.z])
        elif isinstance(element, (Area, Polygon)):
            nodes = element.nodes
            for i, n in enumerate(nodes):
                m = nodes[(i + 1) % len(nodes)]
                verts.extend([n.x, n.y, n.z, m.x, m.y, m.z])
        if not verts:
            return

        self.overlay_shader.use()
        mvp = camera.get_projection_matrix() @ camera.get_view_matrix()
        if self._overlay_mvp_loc != -1:
            glUniformMatrix4fv(self._overlay_mvp_loc, 1, GL_FALSE, glm.value_ptr(mvp))
        if self._overlay_color_loc == -1:
            return

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_DEPTH_TEST)
        glLineWidth(3.0)
        self._upload_and_draw(
            self._dyn_vao, self._dyn_vbo,
            np.array(verts, dtype=np.float32),
            GL_LINES, len(verts) // 3, color, self._overlay_color_loc,
        )
        glLineWidth(1.0)
        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glEnable(GL_DEPTH_TEST)

    @staticmethod
    def _project(camera, x, y, z, w, h):
        mvp = camera.get_projection_matrix() @ camera.get_view_matrix()
        clip = mvp * glm.vec4(x, y, z, 1.0)
        if clip.w <= 0:
            return None
        ndc = glm.vec3(clip) / clip.w
        return (ndc.x + 1.0) * w / 2.0, (1.0 - ndc.y) * h / 2.0

    def _ensure_dynamic_buffers(self):
        if self._dyn_vao is None:
            self._dyn_vao = glGenVertexArrays(1)
            self._dyn_vbo = glGenBuffers(1)

    def _draw_plane_preview(self, plane, mvp):
        if self.overlay_shader is None:
            return
        self._ensure_dynamic_buffers()
        self.overlay_shader.use()
        if self._overlay_mvp_loc != -1:
            glUniformMatrix4fv(self._overlay_mvp_loc, 1, GL_FALSE, glm.value_ptr(mvp))
        if self._overlay_color_loc == -1:
            return

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_DEPTH_TEST)
        glDepthMask(GL_FALSE)

        corners = plane.corners_3d()
        if len(corners) < 4:
            center = plane.origin
            normal_tip = center + plane.normal * 500.0
            arrow = np.array([*center, *normal_tip], dtype=np.float32)
            glLineWidth(3.0)
            self._upload_and_draw(
                self._dyn_vao, self._dyn_vbo, arrow,
                GL_LINES, 2, (1.0, 0.6, 0.2, 1.0), self._overlay_color_loc,
            )
            glLineWidth(1.0)
            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glDepthMask(GL_TRUE)
            return

        c0, c1, c2, c3 = corners[0], corners[1], corners[2], corners[3]
        tris = np.array([*c0, *c1, *c2, *c0, *c2, *c3], dtype=np.float32)
        self._upload_and_draw(
            self._dyn_vao, self._dyn_vbo, tris,
            GL_TRIANGLES, 6, (0.4, 0.7, 1.0, 0.18), self._overlay_color_loc,
        )

        edges = np.array([*c0, *c1, *c1, *c2, *c2, *c3, *c3, *c0], dtype=np.float32)
        glLineWidth(2.0)
        self._upload_and_draw(
            self._dyn_vao, self._dyn_vbo, edges,
            GL_LINES, 8, (0.5, 0.85, 1.0, 1.0), self._overlay_color_loc,
        )

        center = plane.origin
        normal_tip = center + plane.normal * max(plane.depth_plus, 500.0)
        arrow = np.array([*center, *normal_tip], dtype=np.float32)
        self._upload_and_draw(
            self._dyn_vao, self._dyn_vbo, arrow,
            GL_LINES, 2, (1.0, 0.6, 0.2, 1.0), self._overlay_color_loc,
        )
        glLineWidth(1.0)

        depth_minus = center - plane.normal * plane.depth_minus
        depth_plus = center + plane.normal * plane.depth_plus
        depth_line = np.array([*depth_minus, *depth_plus], dtype=np.float32)
        self._upload_and_draw(
            self._dyn_vao, self._dyn_vbo, depth_line,
            GL_LINES, 2, (0.9, 0.4, 0.9, 0.7), self._overlay_color_loc,
        )

        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glDepthMask(GL_TRUE)

    def _upload_and_draw(self, vao, vbo, verts, mode, count, color, loc_color):
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STREAM_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, None)
        glUniform4f(loc_color, *color)
        glDrawArrays(mode, 0, count)

    def cleanup(self):
        if self._dyn_vao:
            glDeleteVertexArrays(1, [self._dyn_vao])
            self._dyn_vao = None
        if self._dyn_vbo:
            glDeleteBuffers(1, [self._dyn_vbo])
            self._dyn_vbo = None