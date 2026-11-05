# render/presentationrenderer.py
from __future__ import annotations

import math

import numpy as np
from OpenGL.GL import *
from pyglm import glm

from render.axes_renderer import LocalAxesRenderer
from render.global_axis_renderer import GlobalAxisRenderer
from render.grid_renderer import GridRenderer, BubbleRenderer
from render.label_batch import LabelBatch
from render.line_renderer import LineRenderer
from render.load_renderer import LoadRenderer
from render.polygonrenderer import PolygonRenderer
from tools.font_atlas import FontAtlas


class PresentationRenderer:

    def __init__(self, standard_shader, axes_shader, overlay_shader,
                 simple_shader, grid_shader):
        self.standard_shader = standard_shader
        self.axes_shader = axes_shader
        self.overlay_shader = overlay_shader
        self.simple_shader = simple_shader
        self._projection = "3d"

        self.global_axis = GlobalAxisRenderer(axes_shader)
        self.global_axis.init_gl()

        self.grid = GridRenderer(grid_shader)
        self.bubble = BubbleRenderer(grid_shader)

        self.polygon = PolygonRenderer(simple_shader or standard_shader)
        self.lines = LineRenderer(simple_shader or standard_shader)
        self.loads = LoadRenderer()
        self.axes = LocalAxesRenderer(axes_shader)
        self.axes.init_gl()

        self.font = FontAtlas(None, size=32, supersample=2)
        self.labels = LabelBatch(self.font)
        self.labels.init_gl()

        self.zone_vao = None
        self.zone_vbo = None
        self.zone_vcount = 0
        
        self.show = {
            "polygon": True,
            "lines": True,
            "zones": True,
            "loads": True,
            "local_axes": False,
            "grid_labels": True,
            "selected_labels": True,
        }

    # ------------------------------------------------------------------
    def update_polygons(self, polygons):
        self.polygon.update(polygons)
        parts = []
        for pg in polygons:
            if getattr(pg, "is_visible", True):
                v = self.polygon.builder.build_lines(pg)
                if len(v):
                    parts.append(v)
        if parts:
            self.polygon._upload_outline(np.concatenate(parts).astype(np.float32))
        else:
            self.polygon._cleanup_outline()
        self._update_zones(polygons)

    def _update_zones(self, polygons):
        verts = []
        for pg in polygons:
            if not getattr(pg, "is_visible", True):
                continue
            direction = getattr(pg, "show_zones_direction", None)
            if direction is None:
                continue
            zones = (pg.zone_children_by_direction or {}).get(direction, [])
            for zone in zones:
                coords = zone.get("coords") or []
                if len(coords) < 3:
                    continue
                color = self._zone_color(zone)
                # Triangle fan
                for i in range(1, len(coords) - 1):
                    for c in (coords[0], coords[i], coords[i + 1]):
                        verts += [c[0], c[1], c[2], *color[:3]]
        if verts:
            self._upload_zone_verts(np.array(verts, np.float32))
        else:
            self._cleanup_zone_verts()

    def _zone_color(self, zone) -> tuple[float, float, float]:
        cpe = zone.get("cpe10", (0, 0))
        v = abs(cpe[0]) if cpe else 0
        return (min(1.0, 0.3 + v * 0.75), 0.3, 0.5)   # basit renk skalası

    def update_loads(self, scene, camera_scale=1.0, scene_size=1.0):
        if self.loads.enabled:
            self.loads.update(scene, camera_scale=camera_scale, scene_size=scene_size)

    def set_projection(self, projection):
        self._projection = projection

    # ------------------------------------------------------------------
    def render(self, cam, model, scene, w, h):
        self._bind_grid(scene)
        mvp = cam.get_projection_matrix() * cam.get_view_matrix() * model

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        if self.grid.grid:
            glDepthMask(GL_FALSE)
            self.grid.draw(mvp)
            glDepthMask(GL_TRUE)

        self._draw_polygons(mvp)
        self._draw_lines(mvp)
        self._draw_zones(mvp)
        self._draw_loads(mvp)
        self._draw_local_axes(cam, scene)
        self._draw_labels(cam, scene, h)
        self._draw_global_axis(cam, w, h)

    def render_pick(self, cam, model, pick_shader):
        if not self.show["polygon"]:
            return
        mvp = cam.get_projection_matrix() * cam.get_view_matrix() * model
        self.polygon.render_pick(mvp, pick_shader)

    def _bind_grid(self, scene):
        project = getattr(scene, "project", None)
        g = getattr(project, "grid", None)
        if self.grid.grid is not g:
            self.grid.set_grid(g)

    # ------------------------------------------------------------------
    def _draw_lines(self, mvp):
        if not self.show.get("lines", True):
            return
        self.lines.draw(mvp)
        
    def _draw_polygons(self, mvp):
        if not self.show["polygon"]:
            return
        sh = self.simple_shader or self.standard_shader
        glDepthMask(GL_FALSE)
        self.polygon.render_simple(mvp, sh, alpha=0.50)
        self.polygon.render_lines_white(mvp, sh)
        glDepthMask(GL_TRUE)

    def _draw_loads(self, mvp):
        if not (self.show["loads"] and self.loads.enabled):
            return
        glDisable(GL_DEPTH_TEST)
        self.loads.render(mvp)
        glEnable(GL_DEPTH_TEST)

    def _draw_global_axis(self, cam, w, h):
        self.global_axis.begin_frame(cam, w, h, projection=self._projection)
        self.global_axis.render()

    def _draw_local_axes(self, cam, scene):
        if not getattr(scene, "show_local_axes", False):
            return
        base = cam.get_projection_matrix() * cam.get_view_matrix()
        scale = 0.025 * getattr(scene, "show_local_axes_scale", 1.0)
        only_sel = getattr(scene, "show_local_axes_for_selected", True)

        glDisable(GL_DEPTH_TEST)
        self.axes_shader.use()
        loc = self.axes_shader.get_loc("u_mvp")

        for f in scene.frames.values():
            if not f.is_visible or (only_sel and not f.is_selected):
                continue
            if f.show_axes_override is False:
                continue
            R = f.get_local_axes()
            R3 = np.array([[R[0][0], R[1][0], R[2][0]],
                           [R[0][1], R[1][1], R[2][1]],
                           [R[0][2], R[1][2], R[2][2]]], dtype=np.float32)
            M = (glm.translate(glm.mat4(1.0), glm.vec3(*f.get_midpoint()))
                 * glm.mat4(glm.mat3(*[glm.vec3(*R3[:, i]) for i in range(3)])))
            mvp = base * glm.scale(M, glm.vec3(scale))
            if loc != -1:
                glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))
            glBindVertexArray(self.axes.vao)
            glDrawArrays(GL_LINES, 0, 6)
            glDrawArrays(GL_TRIANGLES, 6, 12)

        glBindVertexArray(0)
        glEnable(GL_DEPTH_TEST)

    # ------------------------------------------------------------------
    def _draw_labels(self, cam, scene, screen_h):
        if self.show["grid_labels"]:
            self._grid_labels(cam)
        if self.show["selected_labels"]:
            self._frame_labels(cam, scene, screen_h)

    def _grid_labels(self, cam):
        dg = self.grid.grid
        if not dg or not dg.show_labels:
            return
        anchors = [a for a in self.grid.get_label_anchors() if a["text"]]
        if not anchors:
            return

        mvp = cam.get_projection_matrix() * cam.get_view_matrix()
        overflow = dg.label_overflow

        self.bubble.begin()
        info = []
        for a in anchors:
            info.append(self.bubble.add(
                anchor=a["anchor"],
                direction=a["direction_world"],
                normal=a["plane_normal"],
                text_width=a["text_world_width"],
                color=(*a["color"][:3], 1.0),
                leader_len=overflow,
            ))
        self.bubble.flush(mvp)

        self.labels.begin(mode="world", mvp=mvp)
        for a, i in zip(anchors, info):
            encoded = a["text"].encode("latin-1", "replace")
            advances = self.labels.lut["advance"][np.frombuffer(encoded, dtype=np.uint8)]
            size_world = (
                a["text_world_width"] * self.font.size / float(advances.sum())
            )
            self.labels.add(
                world_pos=i["center"],
                text=a["text"],
                color=(*a["color"][:3], 1.0),
                size_world=size_world,
                anchor="center",
                u_axis=i["u_axis"],
                v_axis=i["v_axis"],
            )
        self.labels.flush(disable_depth=True)

    def _frame_labels(self, cam, scene, screen_h):
        frames = [f for f in scene.frames.values() if f.is_selected]
        if not frames:
            return
        n = len(frames)
        pos = np.empty((n, 3), dtype=np.float32)
        off = np.tile(np.array([20.0, 20.0, 20.0], dtype=np.float32), (n, 1))
        texts = [""] * n
        for i, f in enumerate(frames):
            pos[i] = ((f.node_i.x + f.node_j.x) * 0.5,
                      (f.node_i.y + f.node_j.y) * 0.5,
                      (f.node_i.z + f.node_j.z) * 0.5)
            texts[i] = f"F{f.unique_id}"

        self.labels.begin(
            view=cam.get_view_matrix(),
            proj=cam.get_projection_matrix(),
            cam_pos=(cam.position.x, cam.position.y, cam.position.z),
            screen_h=screen_h,
            fov_y_rad=math.radians(getattr(cam, "fov", 45.0)),
            mode="billboard",
        )
        self.labels.add_many(
            positions=pos, texts=texts,
            colors=np.array([1.0, 1.0, 0.3, 1.0], dtype=np.float32),
            pixel_sizes=13.0, anchors="bottom-center", world_offsets=off,
        )
        self.labels.flush()

    def _upload_zone_verts(self, verts):
        if self.zone_vao is None:
            self.zone_vao = glGenVertexArrays(1)
            self.zone_vbo = glGenBuffers(1)
        glBindVertexArray(self.zone_vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.zone_vbo)
        glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_DYNAMIC_DRAW)
        stride = 6 * 4
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))
        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        self.zone_vcount = len(verts) // 6

    def _cleanup_zone_verts(self):
        if self.zone_vbo:
            glDeleteBuffers(1, [self.zone_vbo])
            self.zone_vbo = None
        if self.zone_vao:
            glDeleteVertexArrays(1, [self.zone_vao])
            self.zone_vao = None
        self.zone_vcount = 0

    def _draw_zones(self, mvp):
        if not (self.show.get("zones") and self.zone_vao and self.zone_vcount):
            return
        sh = self.simple_shader or self.standard_shader
        sh.use()
        loc = sh.get_loc("mvp")
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(mvp))
        vc = sh.get_loc("useVertexColor")
        if vc != -1:
            glUniform1i(vc, 1)
        a = sh.get_loc("alpha")
        if a != -1:
            glUniform1f(a, 0.45)
        glBindVertexArray(self.zone_vao)
        glDrawArrays(GL_TRIANGLES, 0, self.zone_vcount)
        glBindVertexArray(0)

    def update_lines(self, lines):
        self.lines.update(lines)

    def draw(self, mvp):
        if not self.vcount or self.shader is None:
            return

    
    # ------------------------------------------------------------------
    def cleanup(self):
        for r in (self.polygon, self.lines, self.loads, self.axes, self.bubble, self.labels):
            r.cleanup()
