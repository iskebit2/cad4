# plane/plane_creation_tool.py
from __future__ import annotations

import glfw
import numpy as np
from pyglm import glm
from OpenGL.GL import (
    GL_ARRAY_BUFFER, GL_BLEND, GL_DEPTH_TEST, GL_FALSE, GL_FLOAT,
    GL_LINES, GL_ONE_MINUS_SRC_ALPHA, GL_SRC_ALPHA, GL_STREAM_DRAW,
    GL_TRIANGLES, GL_TRUE,
    glBindBuffer, glBindVertexArray, glBlendFunc, glBufferData,
    glDeleteBuffers, glDeleteVertexArrays, glDepthMask, glDisable,
    glDrawArrays, glEnable, glEnableVertexAttribArray, glGenBuffers,
    glGenVertexArrays, glLineWidth, glUniform4f, glUniformMatrix4fv,
    glVertexAttribPointer,
)
from domain.element import Node
from plane.plane import Plane
from domain.vertex import Vertex
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class PlaneCreationTool:

    STAGE_P0 = 0
    STAGE_P1 = 1
    STAGE_P2 = 2
    STAGE_DEPTH_PLUS = 3
    STAGE_DEPTH_MINUS = 4

    SNAP_RADIUS_PX = 15.0
    DEFAULT_DEPTH = 500.0
    MIN_U_LENGTH = 10.0
    MIN_V_LENGTH = 10.0
    DEPTH_K_FACTOR = 1.0 / 500.0

    MODE_3PT = "3pt"
    MODE_2PT_Z = "2pt_z"

    def __init__(self, engine):
        self.engine = engine
        self.is_active = False
        self.mode = self.MODE_3PT
        self.stage = self.STAGE_P0
        self.p0: Vertex | None = None
        self.p1: Vertex | None = None
        self.p2: Vertex | None = None
        self.hover_node: Node | None = None
        self.depth_plus = self.DEFAULT_DEPTH
        self.depth_minus = self.DEFAULT_DEPTH
        self._last_mouse_y = None
        self._mouse_pos: tuple[float, float] | None = None
        self.completed_plane: Plane | None = None

    def start_3pt(self):
        self._start(self.MODE_3PT)

    def start_2pt_z(self):
        self._start(self.MODE_2PT_Z)

    def _start(self, mode):
        print("plane başla", mode)
        self.is_active = True
        self.mode = mode
        self.stage = self.STAGE_P0
        self.p0 = self.p1 = self.p2 = None
        self.hover_node = None
        self.depth_plus = self.depth_minus = self.DEFAULT_DEPTH
        self._last_mouse_y = None
        self._mouse_pos = None
        self.completed_plane = None

    def cancel(self):
        self.is_active = False
        self.p0 = self.p1 = self.p2 = None
        self.hover_node = None
        self._last_mouse_y = None
        self._mouse_pos = None

    def _step_back(self):
        if self.stage == self.STAGE_DEPTH_PLUS:
            self.stage = self.STAGE_P2
            self.p2 = None
            self.depth_plus = self.depth_minus = self.DEFAULT_DEPTH
        elif self.stage == self.STAGE_DEPTH_MINUS:
            self.stage = self.STAGE_DEPTH_PLUS
            self.depth_minus = self.DEFAULT_DEPTH
        elif self.stage == self.STAGE_P2:
            self.stage = self.STAGE_P1
            self.p1 = None
        elif self.stage == self.STAGE_P1:
            self.stage = self.STAGE_P0
            self.p0 = None
        elif self.stage == self.STAGE_P0:
            self.cancel()
            return
        self._last_mouse_y = None

    def _u_vec(self):
        if self.p0 is None or self.p1 is None:
            return None
        return np.array([self.p1.x - self.p0.x,
                         self.p1.y - self.p0.y,
                         self.p1.z - self.p0.z], dtype=float)

    def _v_perp(self):
        if self.p0 is None or self.p2 is None:
            return None
        u = self._u_vec()
        if u is None:
            return None
        raw = np.array([self.p2.x - self.p0.x,
                        self.p2.y - self.p0.y,
                        self.p2.z - self.p0.z], dtype=float)
        u_len = float(np.linalg.norm(u))
        if u_len < 1e-9:
            return None
        u_hat = u / u_len
        return raw - u_hat * float(np.dot(raw, u_hat))

    def _normal(self):
        u = self._u_vec()
        v = self._v_perp()
        if u is None or v is None:
            return None
        n = np.cross(u, v)
        n_len = float(np.linalg.norm(n))
        if n_len < 1e-9:
            return None
        return n / n_len

    def _dims(self):
        u = self._u_vec()
        v = self._v_perp()
        if u is None or v is None:
            return None
        return float(np.linalg.norm(u)), float(np.linalg.norm(v))

    def on_mouse_move(self, x, y):
        if not self.is_active:
            return
        self._mouse_pos = (x, y)
        if self.stage in (self.STAGE_P0, self.STAGE_P1, self.STAGE_P2):
            active_vp = self.engine.viewport_manager.active
            cam = active_vp.camera if active_vp else self.engine.cam
            size = (active_vp.width, active_vp.height) if active_vp else (self.engine.w, self.engine.h)
            target, _, snap_type = self.engine.snap.find_snap(
                self.engine, x, y, magnetic=True, cam=cam, viewport_size=size,
            )
            self.hover_node = target
            self.hover_snap_type = snap_type
        else:
            self.hover_node = None
        if self.stage in (self.STAGE_DEPTH_PLUS, self.STAGE_DEPTH_MINUS):
            if self._last_mouse_y is not None:
                dy = self._last_mouse_y - y
                k = self._depth_sensitivity()
                if self.stage == self.STAGE_DEPTH_PLUS:
                    self.depth_plus = max(0.0, self.depth_plus + dy * k)
                else:
                    self.depth_minus = max(0.0, self.depth_minus - dy * k)
            self._last_mouse_y = y

    def on_mouse_click(self, x, y) -> bool:
        active_vp = self.engine.viewport_manager.active # veya ilgili viewport
        cam = active_vp.camera if active_vp else self.engine.cam
        w, h = active_vp.width if active_vp else self.engine.w, active_vp.height if active_vp else self.engine.h
        size = (active_vp.width, active_vp.height) if active_vp else (self.engine.w, self.engine.h)
        if not self.is_active:
            return False
        self._mouse_pos = (x, y)

        if self.stage in (self.STAGE_P0, self.STAGE_P1, self.STAGE_P2):
            
            target, _, snap_type = self.engine.snap.find_snap(
                            self.engine, x, y, magnetic=True, cam=cam, viewport_size=size
                        )

            if target is None:
                return False

            if self.stage == self.STAGE_P0:
                self.p0 = target
                self.stage = self.STAGE_P1
                return True

            if self.stage == self.STAGE_P1:
                if self._same(target, self.p0):
                    return True
                u_len = float(np.linalg.norm(np.array(
                    [target.x - self.p0.x,
                    target.y - self.p0.y,
                    target.z - self.p0.z]
                )))
                if u_len < self.MIN_U_LENGTH:
                    return True
                self.p1 = target
                if self.mode == self.MODE_2PT_Z:
                    self.stage = self.STAGE_DEPTH_PLUS
                    self.depth_plus = self.depth_minus = self.DEFAULT_DEPTH
                    self._last_mouse_y = y
                else:
                    self.stage = self.STAGE_P2
                return True

            if self.stage == self.STAGE_P2:
                if self._same(target, self.p0) or self._same(target, self.p1):
                    return True
                self.p2 = target
                v = self._v_perp()
                v_len = float(np.linalg.norm(v)) if v is not None else 0.0
                if v is None or v_len < self.MIN_V_LENGTH:
                    self.p2 = None
                    return True
                self.stage = self.STAGE_DEPTH_PLUS
                self.depth_plus = self.depth_minus = self.DEFAULT_DEPTH
                self._last_mouse_y = y
                return True

        if self.stage == self.STAGE_DEPTH_PLUS:
            self.stage = self.STAGE_DEPTH_MINUS
            self._last_mouse_y = y
            return True

        if self.stage == self.STAGE_DEPTH_MINUS:
            self._confirm()
            return True

        return False

    def on_key_press(self, key) -> bool:
        if not self.is_active:
            return False
        if key == glfw.KEY_ESCAPE:
            self._step_back()
            return True
        if key == glfw.KEY_SPACE:
            if self.stage in (self.STAGE_DEPTH_PLUS, self.STAGE_DEPTH_MINUS):
                self.depth_plus = self.depth_minus = self.DEFAULT_DEPTH
                return True
        if key == glfw.KEY_ENTER:
            if self.stage in (self.STAGE_DEPTH_PLUS, self.STAGE_DEPTH_MINUS):
                self._confirm()
                return True
        return False

    def _model_v_length(self):
        math_model = self.engine.math_model
        if math_model is None or not math_model.nodes:
            return self.DEFAULT_DEPTH * 2
        zs = [nd.z for nd in math_model.nodes.values()]
        z_range = max(zs) - min(zs)
        if z_range < self.MIN_V_LENGTH:
            bounds = math_model.bounds
            if bounds is not None:
                return float(bounds.size) * 0.5
            return self.DEFAULT_DEPTH * 2
        return z_range

    def _confirm(self):
        if self.p0 is None or self.p1 is None:
            self.cancel()
            return

        u = self._u_vec()
        u_len = float(np.linalg.norm(u)) if u is not None else 0.0

        if self.mode == self.MODE_2PT_Z:
            z = np.array([0.0, 0.0, 1.0])
            if u is None or u_len < self.MIN_U_LENGTH:
                self.cancel()
                return
            u_hat = u / u_len
            n = np.cross(u_hat, z)
            n_len = float(np.linalg.norm(n))
            if n_len < 1e-9:
                self.cancel()
                return
            n = n / n_len
            v_hat = np.cross(n, u_hat)
            v_len = self._model_v_length()
        else:
            if self.p2 is None:
                self.cancel()
                return
            v = self._v_perp()
            n = self._normal()
            if v is None or n is None:
                self.cancel()
                return
            v_len = float(np.linalg.norm(v))
            if u_len < self.MIN_U_LENGTH or v_len < self.MIN_V_LENGTH:
                self.cancel()
                return
            u_hat = u / u_len
            v_hat = v / v_len

        p0 = np.array([self.p0.x, self.p0.y, self.p0.z])
        origin = p0 + u_hat * (u_len * 0.5) + v_hat * (v_len * 0.5)

        project = self.engine.project
        if project is None:
            self.cancel()
            return

        index = 1
        while f"Plane_{index}" in project.custom_planes:
            index += 1

        plane = Plane(
            origin=origin, normal=n, u=u_hat, v=v_hat,
            name=f"Plane_{index}",
            u_min=-u_len * 0.5, u_max=u_len * 0.5,
            v_min=-v_len * 0.5, v_max=v_len * 0.5,
            depth_minus=self.depth_minus, depth_plus=self.depth_plus,
        )
        plane.fit_to_math_model(self.engine.math_model)
        project.add_plane(plane)
        self.completed_plane = plane
        self.is_active = False
        self.p0 = self.p1 = self.p2 = None
        self.hover_node = None
        self._last_mouse_y = None
        

    def _depth_sensitivity(self):
        bounds = self.engine._combined_bounds()
        if bounds is None:
            return 10.0
        return max(1.0, float(bounds.size) * self.DEPTH_K_FACTOR)

    def _preview_point(self):
        if self.hover_node is not None:
            return np.array([self.hover_node.x, self.hover_node.y,
                            self.hover_node.z], dtype=float)
        if self._mouse_pos is None or self.p0 is None:
            return None
            
        # Aktif viewport kamerasını ve boyutlarını güvenli şekilde alalım
        vm = getattr(self.engine, "viewport_manager", None)
        active_vp = vm.get(vm.active_name) if vm and hasattr(vm, "active_name") else None
        cam = active_vp.camera if active_vp else self.engine.cam
        w = active_vp.width if active_vp else self.engine.w
        h = active_vp.height if active_vp else self.engine.h

        x, y = self._mouse_pos
        ndc_x = 2.0 * x / w - 1.0
        ndc_y = 1.0 - 2.0 * y / h
        inv = glm.inverse(cam.get_projection_matrix() @ cam.get_view_matrix())
        near = inv * glm.vec4(ndc_x, ndc_y, -1.0, 1.0)
        far = inv * glm.vec4(ndc_x, ndc_y, 1.0, 1.0)
        near = np.asarray(glm.vec3(near) / near.w, dtype=float)
        far = np.asarray(glm.vec3(far) / far.w, dtype=float)
        ray = far - near
        ray /= np.linalg.norm(ray)
        fwd = np.asarray(cam.target - cam.position, dtype=float)
        fwd /= np.linalg.norm(fwd)
        denom = float(np.dot(ray, fwd))
        if abs(denom) < 1e-9:
            return None
        origin = np.array([self.p0.x, self.p0.y, self.p0.z], dtype=float)
        t = float(np.dot(origin - near, fwd) / denom)
        if t < 0:
            return None
        return near + ray * t

    def _preview_v_perp(self, point):
        if self.p0 is None or point is None:
            return None
        u = self._u_vec()
        if u is None:
            return None
        u_len = float(np.linalg.norm(u))
        if u_len < 1e-9:
            return None
        p0 = np.array([self.p0.x, self.p0.y, self.p0.z], dtype=float)
        raw = point - p0
        u_hat = u / u_len
        return raw - u_hat * float(np.dot(raw, u_hat))

    # ------------------------------------------------------------------
    # Render — InteractionRenderer üzerinden çağrılır
    # ------------------------------------------------------------------
    def render(self, mvp):
        if not self.is_active:
            return
        ir = self.engine.interaction_renderer
        if ir is None or ir.overlay_shader is None:
            return

        sh = ir.overlay_shader
        sh.use()
        loc_mvp = sh.get_loc("mvp")
        if loc_mvp != -1:
            glUniformMatrix4fv(loc_mvp, 1, GL_FALSE, glm.value_ptr(mvp))
        loc_color = sh.get_loc("color")
        if loc_color == -1:
            return

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # ★ Test için depth test'i tamamen kapatıp çizmeyi deneyin
        glDisable(GL_DEPTH_TEST) 
        glDepthMask(GL_FALSE)

        ir._ensure_dynamic_buffers()
        vao = ir._dyn_vao
        vbo = ir._dyn_vbo

        if self.p0 is not None:
            self._draw_u_v_lines(vao, vbo, loc_color)
            if self.stage == self.STAGE_P2:
                self._draw_quad_preview(vao, vbo, loc_color)
            elif self.p2 is not None:
                self._draw_quad(vao, vbo, loc_color)
            if self.stage in (self.STAGE_DEPTH_PLUS, self.STAGE_DEPTH_MINUS):
                self._draw_box(vao, vbo, loc_color)

        if self.hover_node is not None:
            self._draw_hover(vao, vbo, loc_color)

        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glDepthMask(GL_TRUE)
        glEnable(GL_DEPTH_TEST)
        glDisable(GL_BLEND)

    def _upload(self, vao, vbo, verts, mode, color, loc_color, width=1.0):
        arr = np.asarray(verts, dtype=np.float32)
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, arr.nbytes, arr, GL_STREAM_DRAW)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, None)
        glUniform4f(loc_color, *color)
        glLineWidth(width)
        glDrawArrays(mode, 0, len(arr) // 3)

    def _draw_u_v_lines(self, vao, vbo, loc_color):
        p0 = np.array([self.p0.x, self.p0.y, self.p0.z])
        lines = []
        if self.p1 is not None:
            p1 = np.array([self.p1.x, self.p1.y, self.p1.z])
            lines.extend([*p0, *p1])
        elif self.stage == self.STAGE_P1:
            preview = self._preview_point()
            if preview is not None:
                lines.extend([*p0, *preview])
        if self.p1 is not None and self.p2 is not None:
            p2 = np.array([self.p2.x, self.p2.y, self.p2.z])
            v = self._v_perp()
            if v is not None:
                lines.extend([*p1, *(p0 + v)])
        if lines:
            self._upload(vao, vbo, lines, GL_LINES,
                         (1.0, 0.85, 0.2, 1.0), loc_color, 2.0)

    def _draw_quad_preview(self, vao, vbo, loc_color):
        point = self._preview_point()
        
        if point is None:
            return
        v = self._preview_v_perp(point)
        v_norm = np.linalg.norm(v) if v is not None else "N/A"
        
        if v is None or v_norm < 1e-9:
            return
        self._draw_quad_geometry(vao, vbo, v, loc_color, alpha=0.15)

    def _draw_quad(self, vao, vbo, loc_color):
        v = self._v_perp()
        if v is None:
            return
        self._draw_quad_geometry(vao, vbo, v, loc_color, alpha=0.20)

    def _draw_quad_geometry(self, vao, vbo, v, loc_color, alpha):
        u = self._u_vec()
        p0 = np.array([self.p0.x, self.p0.y, self.p0.z])
        c0, c1 = p0, p0 + u
        c2, c3 = p0 + u + v, p0 + v
        tris = [*c0, *c1, *c2, *c0, *c2, *c3]
        self._upload(vao, vbo, tris, GL_TRIANGLES,
                     (0.3, 0.6, 0.9, alpha), loc_color)
        edges = [*c0, *c1, *c1, *c2, *c2, *c3, *c3, *c0]
        self._upload(vao, vbo, edges, GL_LINES,
                     (0.5, 0.8, 1.0, 0.9), loc_color, 1.5)

    def _draw_box(self, vao, vbo, loc_color):
        u = self._u_vec()
        if self.mode == self.MODE_2PT_Z:
            u_hat = u / np.linalg.norm(u)
            n = np.cross(u_hat, np.array([0.0, 0.0, 1.0]))
            n /= np.linalg.norm(n)
            v = np.cross(n, u_hat) * (np.linalg.norm(u) * 0.5)
        else:
            v = self._v_perp()
            n = self._normal()
        if u is None or v is None or n is None:
            return
        p0 = np.array([self.p0.x, self.p0.y, self.p0.z])
        top = [p0 + n * self.depth_plus, p0 + u + n * self.depth_plus,
               p0 + u + v + n * self.depth_plus, p0 + v + n * self.depth_plus]
        bot = [p0 - n * self.depth_minus, p0 + u - n * self.depth_minus,
               p0 + u + v - n * self.depth_minus, p0 + v - n * self.depth_minus]
        tris = [*top[0], *top[1], *top[2], *top[0], *top[2], *top[3],
                *bot[0], *bot[2], *bot[1], *bot[0], *bot[3], *bot[2]]
        for i in range(4):
            j = (i + 1) % 4
            tris.extend([*bot[i], *bot[j], *top[j],
                         *bot[i], *top[j], *top[i]])
        self._upload(vao, vbo, tris, GL_TRIANGLES,
                     (0.2, 0.8, 0.85, 0.18), loc_color)
        edges = []
        for i in range(4):
            j = (i + 1) % 4
            edges.extend([*top[i], *top[j], *bot[i], *bot[j]])
        for i in range(4):
            edges.extend([*bot[i], *top[i]])
        self._upload(vao, vbo, edges, GL_LINES,
                     (1.0, 1.0, 1.0, 0.85), loc_color, 1.2)

    def _draw_hover(self, vao, vbo, loc_color):
        n = self.hover_node
        s = 20.0
        p = np.array([n.x, n.y, n.z])
        lines = [p[0]-s, p[1], p[2], p[0]+s, p[1], p[2],
                 p[0], p[1]-s, p[2], p[0], p[1]+s, p[2],
                 p[0], p[1], p[2]-s, p[0], p[1], p[2]+s]
        self._upload(vao, vbo, lines, GL_LINES,
                     (0.2, 1.0, 0.3, 1.0), loc_color, 2.0)

    def handle_click(self, x, y, button) -> bool:
        if button != 0:
            return False
        return self.on_mouse_click(x, y)

    def handle_release(self, x, y, button) -> bool:
        return False

    def handle_move(self, x, y, dx, dy) -> bool:
        if not self.is_active:
            return False
        eng = self.engine
        if eng.input.state.buttons.get(2):
            return False
        if eng.input.state.buttons.get(0) and eng.input.is_shift():
            return False
        self.on_mouse_move(x, y)
        return True

    def handle_key(self, key, mods) -> bool:
        return self.on_key_press(key)

    def handle_scroll(self, delta) -> bool:
        return False

    def cleanup(self):
        pass

    @staticmethod
    def _same(a, b) -> bool:
        return (abs(a.x - b.x) < 1e-3
                and abs(a.y - b.y) < 1e-3
                and abs(a.z - b.z) < 1e-3)

class PlaneFromElementInputHandler:
    def __init__(self, state):
        self.state = state
        self.engine = state.engine
    
    def handle_click(self, x, y, button):
        if not self.state.active:
            return False
        if button != 0:
            return False
        # Hover'daki elementi seç
        return self.state.try_confirm()
    
    def handle_key(self, key, mods):
        if not self.state.active:
            return False
        import glfw
        if key == glfw.KEY_ESCAPE:
            self.state.cancel()
            return True
        if key == glfw.KEY_SPACE:
            # 1-2 / 1-3 toggle
            self.state.frame_axis_12 = not self.state.frame_axis_12
            return True
        return False
    
class PlaneFromElementState:
    """Element seçimi state'i."""
    def __init__(self):
        self.active = False
        self.hover_element = None
        self.frame_axis_12 = False   # False → 1-3, True → 1-2
    
    def start(self):
        self.active = True
        self.hover_element = None
    
    def cancel(self):
        self.active = False
        self.hover_element = None
    
    def set_hover(self, element):
        """Seçim hover'ında çağrılır."""
        from domain.element import Frame, Area
        from domain.polygon import Polygon
        if not isinstance(element, (Frame, Area, Polygon)):
            self.hover_element = None
            return
        self.hover_element = element
    
    def try_confirm(self) -> bool:
        """Seçili elemandan plane oluştur."""
        el = self.hover_element
        if el is None:
            return False
        from plane.plane import Plane
        try:
            plane = Plane.from_element(
                el, frame_local_12=self.frame_axis_12,
                name=f"Plane_{el.element_type}_{el.unique_id}",
            )
        except Exception as e:
            logger.warning("[PlaneFromElement] Plane oluşturulamadı: %s", e)
            return False
        eng = getattr(self, "engine", None)
        if eng is not None:
            proj = eng.project
            if proj is not None:
                plane.fit_to_math_model(eng.math_model)
                proj.add_plane(plane)
                eng.update_geo(proj)
                # plane manager'da seç
                pm = eng._app.panels.get("plane_manager", {}).get("instance") if eng._app else None
                if pm is not None:
                    pm._selected_name = plane.name
                    pm.visible = True
                    pm._load_edit(plane, force=True)
        self.active = False
        self.hover_element = None
        return True