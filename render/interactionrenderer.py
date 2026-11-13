# render/interactionrenderer.py
from __future__ import annotations

import numpy as np
from pyglm import glm
from OpenGL.GL import *
from domain.element import Node, Frame, Area, Link
from domain.polygon import Polygon
from logging_config import CadLogger

logger = CadLogger.get(__name__)

class InteractionRenderer:
    """
    Kullanıcı etkileşiminin anlık görselleri (Interaction Layer):
    - Seçim Kutusu (Marquee)
    - Yakalama İşaretçileri (SnapMarker)
    - Çizim Önizlemeleri (DrawingPreview)
    """
    def __init__(self, overlay_shader):
        self.overlay_shader = overlay_shader
        self._overlay_mvp_loc = overlay_shader.get_loc("mvp") if overlay_shader else -1
        self._overlay_color_loc = overlay_shader.get_loc("color") if overlay_shader else -1

        # Marquee (seçim dikdörtgeni) için buffer'lar
        self._marquee_ov_vao = None
        self._marquee_ov_vbo = None

        self._dyn_vao = None
        self._dyn_vbo = None
        self.preview_plane = None

    def render(self, engine, w, h, camera=None, viewport_name=None,
               mouse_pos=None):
        """Tüm etkileşim ve anlık preview görsellerini çizer."""
        if not engine:
            return
        camera = camera or engine.cam
        if mouse_pos is None and viewport_name is None and engine.input:
            mouse_pos = (
                engine.input.state.mouse_pos.x,
                engine.input.state.mouse_pos.y,
            )

        # 2. Snap (Yakalama) Göstergesi
        if engine.snap and getattr(engine, "hover_visual_enabled", True):
            self._draw_snap(engine, w, h, camera, mouse_pos)

        # 3. Çizim Önizlemesi (DrawingPreview)
        if engine.draw_mgr and engine.draw_mgr.is_active:
            mvp = camera.get_projection_matrix() @ camera.get_view_matrix()
            engine.draw_mgr.render_preview(mvp, engine.preview_s)
            
        # 4. plane cre
        tool = getattr(engine, "plane_draw_mgr", None)
        if tool is not None and tool.is_active:
            mvp = camera.get_projection_matrix() @ camera.get_view_matrix()
            tool.render(mvp)

        # 5
        if self.preview_plane is not None and camera is not None:
            mvp = camera.get_projection_matrix() @ camera.get_view_matrix()
            self._draw_plane_preview(self.preview_plane, mvp)

        # 6. Plane from element preview
        pfe = getattr(engine, "_plane_from_element", None)
        if pfe is not None and pfe.active and pfe.hover_element is not None:
            el = pfe.hover_element
            # Element'i vurgula (kenar kalınlığı, glow)
            self._draw_element_outline(el, camera, w, h, color=(0.3, 0.9, 0.3, 1.0))
            # Aday plane'i yarı saydam çiz
            try:
                from plane.plane import Plane
                plane = Plane.from_element(el, frame_local_12=pfe.frame_axis_12)
                mvp = camera.get_projection_matrix() @ camera.get_view_matrix()
                self._draw_plane_preview(plane, mvp)   # mevcut metodu kullan
            except Exception:
                pass

    def _draw_element_outline(self, element, camera, w, h, color=(1, 1, 0, 1)):
        """Element'in kenar/vertex noktalarını vurgula."""
        from domain.element import Node, Frame, Area, Link
        from domain.polygon import Polygon
        if not self._dyn_vao:
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
        loc_mvp = self.overlay_shader.get_loc("mvp")
        if loc_mvp != -1:
            glUniformMatrix4fv(loc_mvp, 1, GL_FALSE, glm.value_ptr(mvp))
        loc_color = self.overlay_shader.get_loc("color")
        if loc_color == -1:
            return
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_DEPTH_TEST)
        glLineWidth(3.0)
        self._upload_and_draw(self._dyn_vao, self._dyn_vbo,
                            np.array(verts, dtype=np.float32),
                            GL_LINES, len(verts) // 3, color, loc_color)
        glLineWidth(1.0)
        glEnable(GL_DEPTH_TEST)
        glDisable(GL_BLEND)
        
    def _draw_marquee(self, marquee, w, h):
        coords = marquee.get_box_coords()
        if not coords:
            return
        x1, y1, x2, y2 = coords
        if abs(x2 - x1) < 2 and abs(y2 - y1) < 2:
            return

        cross = x2 < x1

        if self._marquee_ov_vao is None:
            self._marquee_ov_vao = glGenVertexArrays(1)
            self._marquee_ov_vbo = glGenBuffers(1)
            glBindVertexArray(self._marquee_ov_vao)
            glBindBuffer(GL_ARRAY_BUFFER, self._marquee_ov_vbo)
            glEnableVertexAttribArray(0)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, None)
            glBindVertexArray(0)

        depth_was_on = glIsEnabled(GL_DEPTH_TEST) != 0
        blend_was_on = glIsEnabled(GL_BLEND) != 0
        lw_prev = glGetFloatv(GL_LINE_WIDTH)

        try:
            glDisable(GL_DEPTH_TEST)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

            self.overlay_shader.use()
            proj = glm.ortho(0.0, float(w), float(h), 0.0, -1.0, 1.0)
            if self._overlay_mvp_loc != -1:
                glUniformMatrix4fv(self._overlay_mvp_loc, 1, GL_FALSE, glm.value_ptr(proj))
            if self._overlay_color_loc == -1:
                return

            mn_x, mx_x = min(x1, x2), max(x1, x2)
            mn_y, mx_y = min(y1, y2), max(y1, y2)
            verts = np.array([mn_x, mn_y, 0, mx_x, mn_y, 0,
                              mx_x, mx_y, 0, mn_x, mx_y, 0], dtype=np.float32)

            glBindVertexArray(self._marquee_ov_vao)
            glBindBuffer(GL_ARRAY_BUFFER, self._marquee_ov_vbo)
            glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STREAM_DRAW)

            if cross:
                fill, border = (0.2, 0.8, 0.2, 0.3), (0.2, 1.0, 0.2, 0.9)
            else:
                fill, border = (0.2, 0.5, 0.9, 0.3), (0.4, 0.7, 1.0, 0.9)

            glUniform4f(self._overlay_color_loc, *fill)
            glDrawArrays(GL_TRIANGLE_FAN, 0, 4)

            glLineWidth(1.5)
            glUniform4f(self._overlay_color_loc, *border)
            glDrawArrays(GL_LINE_LOOP, 0, 4)
        finally:
            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glLineWidth(float(lw_prev))
            if not blend_was_on:
                glDisable(GL_BLEND)
            if depth_was_on:
                glEnable(GL_DEPTH_TEST)

    def _draw_snap(self, engine, w, h, camera, mouse_pos):
        snap = engine.snap
        if snap is None or not getattr(engine, "hover_visual_enabled", True):
            return

        if self._draw_tool_snap(engine, snap, w, h, camera):
            return
        if self._draw_hover_snap(engine, snap, w, h, camera, mouse_pos):
            return

    def _draw_tool_snap(self, engine, snap, w, h, camera) -> bool:
        for tool in (getattr(engine, "plane_draw_mgr", None),
                    getattr(engine, "draw_mgr", None)):
            if tool is None or not tool.is_active or tool.hover_node is None:
                continue
            
            node = tool.hover_node
            screen = self._project(camera, node.x, node.y, node.z, w, h)
            if screen is None:
                continue
            snap_type = getattr(tool, "hover_snap_type", None) or getattr(tool, "hover_type", "node")
            
            snap.draw_snap(screen[0], screen[1], w, h, active=True, snap_type=snap_type)
            return True
        return False

    def _draw_hover_snap(self, engine, snap, w, h, camera, mouse_pos) -> bool:
        if engine.hover_id <= 0 or mouse_pos is None:
            return False
        element = engine._find_element(engine.hover_id)
        if element is None:
            return False

        mx, my = mouse_pos

        if isinstance(element, Node):
            screen = self._project(camera, element.x, element.y, element.z, w, h)
            if screen is not None:
                snap.draw_snap(screen[0], screen[1], w, h, active=True, snap_type="node")
                return True

        snap.draw_snap(mx, my, w, h, active=True, snap_type="default")
        return True

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
        corners = plane.corners_3d()
        if len(corners) < 4:
            # fallback: merkez + normal göster
            center = plane.origin
            normal_tip = center + plane.normal * 500.0
            arrow = np.array([*center, *normal_tip], dtype=np.float32)
            self._ensure_dynamic_buffers()
            self.overlay_shader.use()
            loc_mvp = self.overlay_shader.get_loc("mvp")
            if loc_mvp != -1:
                glUniformMatrix4fv(loc_mvp, 1, GL_FALSE, glm.value_ptr(mvp))
            loc_color = self.overlay_shader.get_loc("color")
            if loc_color == -1:
                return
            glEnable(GL_BLEND)
            glEnable(GL_DEPTH_TEST)
            glDepthMask(GL_FALSE)
            glLineWidth(3.0)
            self._upload_and_draw(self._dyn_vao, self._dyn_vbo, arrow,
                                GL_LINES, 2,
                                (1.0, 0.6, 0.2, 1.0), loc_color)
            glLineWidth(1.0)
            glBindVertexArray(0)
            glDepthMask(GL_TRUE)
            glDisable(GL_BLEND)
            return
        self._ensure_dynamic_buffers()
        self.overlay_shader.use()
        loc_mvp = self.overlay_shader.get_loc("mvp")
        if loc_mvp != -1:
            glUniformMatrix4fv(loc_mvp, 1, GL_FALSE, glm.value_ptr(mvp))
        loc_color = self.overlay_shader.get_loc("color")
        if loc_color == -1:
            return

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_DEPTH_TEST)
        glDepthMask(GL_FALSE)

        # Yarı saydam dolgu
        c0, c1, c2, c3 = corners[0], corners[1], corners[2], corners[3]
        tris = np.array([
            *c0, *c1, *c2,
            *c0, *c2, *c3,
        ], dtype=np.float32)
        self._upload_and_draw(self._dyn_vao, self._dyn_vbo, tris,
                              GL_TRIANGLES, 6,
                              (0.4, 0.7, 1.0, 0.18), loc_color)

        # Kenar çizgileri
        edges = np.array([
            *c0, *c1, *c1, *c2,
            *c2, *c3, *c3, *c0,
        ], dtype=np.float32)
        glLineWidth(2.0)
        self._upload_and_draw(self._dyn_vao, self._dyn_vbo, edges,
                              GL_LINES, 8,
                              (0.5, 0.85, 1.0, 1.0), loc_color)
        glLineWidth(1.0)

        # Normal yönü (merkezden dışa ok)
        center = plane.origin
        normal_tip = center + plane.normal * max(plane.depth_plus, 500.0)
        arrow = np.array([*center, *normal_tip], dtype=np.float32)
        glLineWidth(2.0)
        self._upload_and_draw(self._dyn_vao, self._dyn_vbo, arrow,
                              GL_LINES, 2,
                              (1.0, 0.6, 0.2, 1.0), loc_color)
        glLineWidth(1.0)

        # Depth silindiri (uç noktalar -n ve +n)
        depth_minus = center - plane.normal * plane.depth_minus
        depth_plus = center + plane.normal * plane.depth_plus
        depth_line = np.array([*depth_minus, *depth_plus], dtype=np.float32)
        self._upload_and_draw(self._dyn_vao, self._dyn_vbo, depth_line,
                              GL_LINES, 2,
                              (0.9, 0.4, 0.9, 0.7), loc_color)

        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glDepthMask(GL_TRUE)
        glDisable(GL_BLEND)

    def _upload_and_draw(self, vao, vbo, verts, mode, count, color, loc_color):
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STREAM_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, None)
        glUniform4f(loc_color, *color)
        glDrawArrays(mode, 0, count)

    def cleanup(self):
        if self._marquee_ov_vao and glIsVertexArray(self._marquee_ov_vao):
            glDeleteVertexArrays(1, [self._marquee_ov_vao])
        if self._marquee_ov_vbo and glIsBuffer(self._marquee_ov_vbo):
            glDeleteBuffers(1, [self._marquee_ov_vbo])

        if self._dyn_vao:
            glDeleteVertexArrays(1, [self._dyn_vao])
            self._dyn_vao = None
        if self._dyn_vbo:
            glDeleteBuffers(1, [self._dyn_vbo])
            self._dyn_vbo = None