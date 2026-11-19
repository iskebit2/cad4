# tools/draw_manager.py
from __future__ import annotations

import time

import glfw
import numpy as np
from OpenGL.GL import *
from pyglm import glm

from domain.vertex import Vertex
from domain.line import Line
from domain.polygon import Polygon
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class DrawManager:
    SNAP_RADIUS_PX = 15
    MOVE_THROTTLE = 0.033

    def __init__(self, engine):
        self.engine = engine
        self.mode = "sequential"
        self.is_active = False
        self.points: list[Vertex] = []
        self.hover_node: Vertex | None = None
        self.hover_is_snap = False
        self.mouse_world_pos = None
        self.preview_vao = None
        self.preview_vbo = None
        self._last_move = 0.0

    # ------------------------------------------------------------------
    def start(self, mode: str = "sequential"):
        self.is_active = True
        self.mode = mode
        self.points.clear()
        self.hover_node = None
        self.hover_is_snap = False
        self.mouse_world_pos = None

    def cancel(self):
        self.is_active = False
        self.points.clear()
        self.hover_node = None
        self.hover_is_snap = False
        self.mouse_world_pos = None

    def close(self):
        if self.mode == "line":
            self._close_line()
            return
        if self.mode == "rectangle":
            self._close_rectangle()
            return
        if self.mode == "single_point":
            self.cancel()
            return
        if len(self.points) < 3:
            self.cancel()
            return
        self._finalize_polygon(Polygon(nodes=list(self.points), label=""))

    # ------------------------------------------------------------------
    def _active_vp(self):
        vm = getattr(self.engine, "viewport_manager", None)
        return vm.active if vm is not None else None

    def _point_on_active_plane(self, x: float, y: float, vp=None) -> Vertex | None:
        target_vp = vp or self._active_vp()
        world = self.engine.screen_to_world(x, y, vp=target_vp)
        if world is None:
            return None
        plane = getattr(target_vp, "plane", None) if target_vp is not None else None
        if plane is not None:
            on_p = plane.project((world.x, world.y, world.z))
            return Vertex(float(on_p[0]), float(on_p[1]), float(on_p[2]))
        return Vertex(float(world.x), float(world.y), float(world.z))

    def on_mouse_move(self, x, y):
        if not self.is_active:
            return
        now = time.time()
        if now - self._last_move < self.MOVE_THROTTLE:
            return
        self._last_move = now

        eng = self.engine
        active_vp = self._active_vp()
        cam = active_vp.camera if active_vp else eng.cam
        size = (active_vp.width, active_vp.height) if active_vp else (eng.w, eng.h)
        plane = getattr(active_vp, "plane", None) if active_vp else None
        visible_ids = getattr(active_vp, "visible_ids", None) if active_vp else None

        target, is_snap, snap_type = eng.snap.find_snap(
            eng, x, y,
            magnetic=True,
            cam=cam,
            viewport_size=size,
            plane=plane,
            visible_ids=visible_ids,
        )
        self.hover_node = target
        self.hover_is_snap = is_snap
        self.hover_snap_type = snap_type
        self.mouse_world_pos = self._point_on_active_plane(x, y, vp=active_vp)
        eng.update_world_pos(x, y, vp=active_vp)

    def on_mouse_click(self, x, y) -> bool:
        if not self.is_active:
            return False

        eng = self.engine
        active_vp = self._active_vp()
        cam = active_vp.camera if active_vp else eng.cam
        size = (active_vp.width, active_vp.height) if active_vp else (eng.w, eng.h)
        plane = getattr(active_vp, "plane", None) if active_vp else None
        visible_ids = getattr(active_vp, "visible_ids", None) if active_vp else None

        target, _, _ = eng.snap.find_snap(
            eng, x, y,
            magnetic=True,
            cam=cam,
            viewport_size=size,
            plane=plane,
            visible_ids=visible_ids,
        )
        if target is None:
            target = self._point_on_active_plane(x, y, vp=active_vp)
        if target is None:
            return True

        if self.mode == "line":
            return self._click_line(target)

        if self.mode == "rectangle":
            self.points.append(target)
            if len(self.points) == 2:
                self._close_rectangle()
            return True

        if self.mode == "single_point":
            self._polygon_from_inside(target)
            return True

        if len(self.points) >= 3 and self._same(target, self.points[0]):
            self.close()
            return True
        if self.points and self._same(target, self.points[-1]):
            return True
        self.points.append(target)
        return True

    def on_key_press(self, key) -> bool:
        if not self.is_active:
            return False
        if key in (glfw.KEY_C, glfw.KEY_ENTER):
            self.close()
            return True
        if key == glfw.KEY_ESCAPE:
            self.cancel()
            return True
        if key == glfw.KEY_BACKSPACE and self.points:
            self.points.pop()
            return True
        return False

    # ------------------------------------------------------------------
    def _click_line(self, target):
        if not self.points:
            self.points.append(target)
            return True
        if self._same(target, self.points[0]):
            return True
        self.points.append(target)
        self._close_line()
        return True


    # ------------------------------------------------------------------
    def _close_rectangle(self):
        if len(self.points) < 2:
            self.cancel()
            return
        corners_xyz = self._ucs_rectangle_corners(self.points[0], self.points[1])
        corners = [Vertex(x, y, z) for x, y, z in corners_xyz]
        self._finalize_polygon(Polygon(nodes=corners, label=""))

    def _polygon_from_inside(self, start):
        math_model = self.engine.math_model
        if not math_model:
            self.cancel()
            return
        candidates = sorted(
            (nd.distance_to(start), nd)
            for nd in math_model.nodes.values()
            if nd is not start
        )
        near = [start] + [nd for _, nd in candidates[:3]]
        if len(near) < 3:
            self.cancel()
            return
        vertices = [
            Vertex(nd.x, nd.y, nd.z, label=getattr(nd, "label", ""),
                   source_node_id=getattr(nd, "unique_id", None))
            for nd in near
        ]
        self._finalize_polygon(Polygon(nodes=vertices, label=""))

    def _close_line(self):
        if len(self.points) < 2:
            self.cancel()
            return
        v1, v2 = self.points[0], self.points[1]
        line = Line(v1=v1, v2=v2)
        self._emit_drawn(line)
        self.cancel()

    def _finalize_polygon(self, polygon: Polygon):
        self._emit_drawn(polygon)
        self.cancel()

    def _emit_drawn(self, element) -> None:
        cq = getattr(self.engine, "command_queue", None)
        if cq is not None:
            from app.commands import project_commands as PC
            cq.put(PC.CommitDrawnElement(element=element))
            return

        # Fallback (test ortamlarında command_queue yoksa)
        project = self._project()
        if project is not None:
            if isinstance(element, Line):
                project.add_line(element)
            elif isinstance(element, Polygon):
                project.add_polygon(element)
            self.engine.update_geo(project)

    def _project(self):
        return self.engine.project

    def _refresh_pr(self):
        pr = getattr(self.engine, "presentation_renderer", None)
        if pr is None:
            return
        project = self._project()
        if project is not None:
            pr.update_polygons(list(project.polygons.values()))

    # ------------------------------------------------------------------
    def _find_target(self, x, y):
        node = self._find_node(x, y)
        if node is not None:
            return self._vertex_from_node(node), False
        snap = self._find_snap(x, y)
        if snap is not None:
            return snap, True
        return None, False

    def _find_node(self, x, y):
        scene = self.engine.math_model
        cam = self.engine.cam
        if not scene or not cam:
            return None
        mvp = cam.get_projection_matrix() @ cam.get_view_matrix()
        best, best_d2 = None, self.SNAP_RADIUS_PX ** 2
        for node in scene.nodes.values():
            if not node.is_visible:
                continue
            p = self._project_pt(mvp, node.x, node.y, node.z)
            if p is None:
                continue
            d2 = (p[0] - x) ** 2 + (p[1] - y) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = node
        return best

    def _find_snap(self, x, y):
        project = self._project()
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

        mvp = self.engine.cam.get_projection_matrix() @ self.engine.cam.get_view_matrix()
        best, best_d2 = None, self.SNAP_RADIUS_PX ** 2
        for c in candidates:
            p = self._project_pt(mvp, c[0], c[1], c[2])
            if p is None:
                continue
            d2 = (p[0] - x) ** 2 + (p[1] - y) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = c
        if best is None:
            return None
        return Vertex(best[0], best[1], best[2])

    def _project_pt(self, mvp, x, y, z):
        w, h = self.engine.w, self.engine.h
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

    @staticmethod
    def _same(a, b) -> bool:
        return (abs(a.x - b.x) < 1e-3
                and abs(a.y - b.y) < 1e-3
                and abs(a.z - b.z) < 1e-3)

    # ------------------------------------------------------------------
    def _ensure_buffer(self):
        if self.preview_vao is not None:
            return
        self.preview_vao = glGenVertexArrays(1)
        self.preview_vbo = glGenBuffers(1)

    def render_preview(self, mvp, shader):
        if not self.is_active or not self.points or shader is None:
            return
        self._ensure_buffer()

        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        try:
            shader.use()
            mvp_loc = shader.get_loc("mvp")
            if mvp_loc != -1:
                glUniformMatrix4fv(mvp_loc, 1, GL_FALSE, glm.value_ptr(mvp))
            color_loc = shader.get_loc("uColor")
            if color_loc == -1:
                return

            glBindVertexArray(self.preview_vao)
            glBindBuffer(GL_ARRAY_BUFFER, self.preview_vbo)
            glEnableVertexAttribArray(0)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 12, None)

            if self.mode == "line":
                self._render_line_preview(color_loc)
            else:
                self._render_polygon_preview(color_loc)

            if self.hover_is_snap and self.hover_node is not None:
                hn = self.hover_node
                verts = self._crosshair_verts((hn.x, hn.y, hn.z), 80.0)
                self._upload_draw(color_loc, verts, GL_LINES, 4, (0.2, 1.0, 0.2, 1.0))

            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)
        finally:
            glEnable(GL_DEPTH_TEST)

    def _preview_endpoint(self) -> Vertex | None:
        """Aktif preview uç noktası: hover_node varsa onu, yoksa mouse_world_pos."""
        if self.hover_node is not None:
            if isinstance(self.hover_node, Vertex):
                return self.hover_node
            # Node objesi (x,y,z)
            return Vertex(self.hover_node.x, self.hover_node.y, self.hover_node.z)
        return self.mouse_world_pos

    def _render_line_preview(self, color_loc):
        n = len(self.points)
        if n == 0:
            return
        last = self.points[-1]
        endpoint = self._preview_endpoint()
        if endpoint is not None:
            verts = np.array(
                [last.x, last.y, last.z, endpoint.x, endpoint.y, endpoint.z],
                np.float32,
            )
            self._upload_draw(color_loc, verts, GL_LINES, 2, (1.0, 1.0, 0.0, 0.9))
        if n >= 1:
            p = self.points[0]
            verts = self._crosshair_verts((p.x, p.y, p.z), 40.0)
            self._upload_draw(color_loc, verts, GL_LINES, 4, (0.5, 1.0, 0.5, 1.0))

    def _render_polygon_preview(self, color_loc):
        n = len(self.points)
        if n >= 3:
            self._draw_points(color_loc, self.points, GL_TRIANGLE_FAN, (0.8, 0.3, 0.8, 0.35))
        if n >= 2:
            self._draw_points(color_loc, self.points, GL_LINE_STRIP, (1.0, 1.0, 0.0, 1.0))

        endpoint = self._preview_endpoint()
        if endpoint is not None and n >= 1:
            last = self.points[-1]
            verts = np.array(
                [last.x, last.y, last.z, endpoint.x, endpoint.y, endpoint.z],
                np.float32,
            )
            self._upload_draw(color_loc, verts, GL_LINES, 2, (1.0, 1.0, 1.0, 0.85))

        if n >= 3:
            first = self.points[0]
            verts = np.array(
                [self.points[-1].x, self.points[-1].y, self.points[-1].z,
                first.x, first.y, first.z],
                np.float32,
            )
            self._upload_draw(color_loc, verts, GL_LINES, 2, (0.5, 1.0, 0.5, 0.7))

        if self.mode == "rectangle" and n == 1 and endpoint is not None:
            self._draw_rectangle_preview(color_loc)

    def _draw_points(self, color_loc, points, mode, color):
        verts = np.array(
            [(p.x, p.y, p.z) for p in points], np.float32,
        ).reshape(-1)
        self._upload_draw(color_loc, verts, mode, len(points), color)

    def _ucs_rectangle_corners(self, p1: Vertex, p2: Vertex) -> list[tuple[float, float, float]]:
        vp = self._active_vp()
        plane = getattr(vp, "plane", None) if vp is not None else None
        if plane is None:
            return [
                (p1.x, p1.y, p1.z),
                (p2.x, p1.y, p1.z),
                (p2.x, p2.y, p2.z),
                (p1.x, p2.y, p2.z),
            ]
        l1 = plane.world_to_local((p1.x, p1.y, p1.z))
        l2 = plane.world_to_local((p2.x, p2.y, p2.z))
        w_mid = 0.5 * (float(l1[2]) + float(l2[2]))
        c0 = plane.local_to_world((float(l1[0]), float(l1[1]), w_mid))
        c1 = plane.local_to_world((float(l2[0]), float(l1[1]), w_mid))
        c2 = plane.local_to_world((float(l2[0]), float(l2[1]), w_mid))
        c3 = plane.local_to_world((float(l1[0]), float(l2[1]), w_mid))
        return [
            (float(c0[0]), float(c0[1]), float(c0[2])),
            (float(c1[0]), float(c1[1]), float(c1[2])),
            (float(c2[0]), float(c2[1]), float(c2[2])),
            (float(c3[0]), float(c3[1]), float(c3[2])),
        ]
    
    def _draw_rectangle_preview(self, color_loc):
        p1 = self.points[0]
        p2 = self._preview_endpoint()
        if p2 is None:
            return
        c0, c1, c2, c3 = self._ucs_rectangle_corners(p1, p2)
        fill = np.array([*c0, *c1, *c2, *c0, *c2, *c3], np.float32)
        self._upload_draw(color_loc, fill, GL_TRIANGLES, 6, (0.8, 0.5, 0.9, 0.25))
        edges = np.array([*c0, *c1, *c1, *c2, *c2, *c3, *c3, *c0], np.float32)
        self._upload_draw(color_loc, edges, GL_LINES, 8, (1.0, 0.9, 0.4, 0.9))

    def _crosshair_verts(self, center_xyz: tuple[float, float, float], size: float) -> np.ndarray:
        vp = self._active_vp()
        plane = getattr(vp, "plane", None) if vp is not None else None
        cx, cy, cz = center_xyz
        if plane is None:
            return np.array([
                cx - size, cy, cz, cx + size, cy, cz,
                cx, cy - size, cz, cx, cy + size, cz,
            ], np.float32)
        c = np.array([cx, cy, cz], dtype=float)
        u_a = c - plane.u * size
        u_b = c + plane.u * size
        v_a = c - plane.v * size
        v_b = c + plane.v * size
        return np.array([*u_a, *u_b, *v_a, *v_b], np.float32)
    
    def _upload_draw(self, color_loc, verts, mode, count, color):
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STREAM_DRAW)
        glUniform4f(color_loc, *color)
        glDrawArrays(mode, 0, count)

    def handle_click(self, x, y, button) -> bool:
        if button != 0:
            return False
        self.on_mouse_click(x, y)
        return True

    def handle_release(self, x, y, button) -> bool:
        return False

    def handle_move(self, x, y, dx, dy) -> bool:
        if not self.is_active:
            return False
        eng = self.engine
        # ★ MIDDLE basılıysa CameraController'a bırak (pan)
        if eng.input.state.buttons.get(2):
            return False
        # ★ Shift+LEFT orbit
        if eng.input.state.buttons.get(0) and eng.input.is_shift():
            return False
        # ★ RIGHT basılıysa (eğer varsa kamera kontrolü) — bırak
        if eng.input.state.buttons.get(1):
            return False
        self.on_mouse_move(x, y)
        return True

    def handle_key(self, key, mods) -> bool:
        return self.on_key_press(key)

    def handle_scroll(self, delta) -> bool:
        return False
        
    # ------------------------------------------------------------------
    def cleanup(self):
        if self.preview_vbo:
            glDeleteBuffers(1, [int(self.preview_vbo)])
            self.preview_vbo = None
        if self.preview_vao:
            glDeleteVertexArrays(1, [int(self.preview_vao)])
            self.preview_vao = None