# ui/frame_preview_panel.py
from __future__ import annotations
import math
import numpy as np
from imgui_bundle import imgui
from OpenGL.GL import *
from pyglm import glm

from render.base_renderer import FrameRenderer  # veya render.base_renderer.FrameRenderer
from render.offscreen_fbo import OffscreenFBO
from core.camera import Camera
from ui.base_panel import BasePanel


class FramePreviewPanel(BasePanel):
    """Seçili frame'i bağımsız bir FBO'da shaded çizer."""

    def __init__(self, standard_shader= None):
        super().__init__(title="Frame Preview", width=340, height=380,
                         pos_first_use=(1500, 100))
        self.standard_shader = standard_shader
        self.frame_renderer: FrameRenderer | None = None
        self.fbo: OffscreenFBO | None = None
        self.camera = Camera()
        self.camera.pitch = 25.0
        self.camera.yaw = 45.0
        self.current_frame = None
        self._auto_rotate = False
        self.current_frame = None
        self._pending_resize = (320, 320)

    def set_context(self, ctx):
        super().set_context(ctx)
        project = ctx.get("project")
        engine = ctx.get("engine")
        self.standard_shader = engine.renderer.standard_shader
        if project is None or project.math_model is None:
            return
        sel_mgr = getattr(ctx.get("engine"), "sel_mgr", None)
        frame = None
        if sel_mgr is not None:
            for el in sel_mgr.get_selected():
                if getattr(el, "element_type", "") == "Frame":
                    frame = el
                    break
        if frame is None and self.current_frame is None:
            return
        if frame is not None and frame is not self.current_frame:
            self._load_frame(frame)

    def _load_frame(self, frame):
        self.current_frame = frame

        mid = np.array([
            (frame.node_i.x + frame.node_j.x) * 0.5,
            (frame.node_i.y + frame.node_j.y) * 0.5,
            (frame.node_i.z + frame.node_j.z) * 0.5,
        ], dtype=float)
        L = float(np.linalg.norm([
            frame.node_j.x - frame.node_i.x,
            frame.node_j.y - frame.node_i.y,
            frame.node_j.z - frame.node_i.z,
        ]))

        # Camera'ya frame'i odakla
        self.camera.model_center = mid
        self.camera.model_size = max(L, 1.0)
        self.camera.target = glm.vec3(*mid)
        self.camera.distance = max(L * 3.0, 300.0)
        self.camera._invalidate()

        if self.frame_renderer is None:
            self.frame_renderer = FrameRenderer(self.standard_shader)
        self.frame_renderer.update([frame])
        color_fn = lambda e: (0.7, 0.75, 0.9, 1.0)
        self.frame_renderer.update_colors([frame], color_fn)
        if self.frame_renderer.simple_vao is not None:
            self.frame_renderer.update_simple_colors([frame], color_fn)

    # ------------------------------------------------------------------
    def draw_content(self):
        if self.current_frame is None:
            imgui.text_disabled("Bir frame seçin.")
            return
        if self.frame_renderer is None:
            return

        # Kontroller
        imgui.checkbox("Otomatik döndür##fp_rot", self._auto_rotate)
        imgui.same_line()
        if imgui.button("Sıfırla##fp_reset"):
            self.camera.pitch = 25.0
            self.camera.yaw = 45.0
            self.camera.distance = max(self.camera.model_size * 3.0, 300.0)
            self.camera._invalidate()
        imgui.same_line()
        imgui.text(f"d={self.camera.distance:.0f}  "
                   f"yaw={self.camera.yaw:.0f}  pitch={self.camera.pitch:.0f}")

        # Viewport boyutu
        avail = imgui.get_content_region_avail()
        w = max(200, int(avail.x))
        h = max(240, int(avail.y) - 4)

        if self.fbo is None:
            self.fbo = OffscreenFBO(w, h)
        else:
            self.fbo.resize(w, h)

        self.camera.set_aspect(self.fbo.w, max(self.fbo.h, 1))

        if self._auto_rotate:
            self.camera.yaw = (self.camera.yaw + 0.3) % 360.0
            self.camera._invalidate()

        self._render_scene()

        # ImGui image
        imgui.image(
            imgui.ImTextureRef(self.fbo.texture_id()),
            imgui.ImVec2(float(self.fbo.w), float(self.fbo.h)),
        )

        # ★ Mouse event'leri — sadece görüntü hover'lıysa
        if imgui.is_item_hovered():
            io = imgui.get_io()

            # Zoom (scroll)
            wheel = io.mouse_wheel
            if wheel != 0.0:
                self.camera.zoom(wheel)
                io.mouse_wheel = 0.0            # ana kameraya geçmesin

            # Orbit (sol tık + sürükle)
            if imgui.is_mouse_dragging(0):
                dx, dy = imgui.get_mouse_drag_delta(0)
                if dx or dy:
                    self.camera.orbit(dx, dy)

            # Pan (orta tık + sürükle)
            if imgui.is_mouse_dragging(2):
                dx, dy = imgui.get_mouse_drag_delta(2)
                if dx or dy:
                    self.camera.pan(dx, dy)

    # ------------------------------------------------------------------
    def _render_scene(self):
        fbo = self.fbo
        if fbo is None or self.frame_renderer is None:
            return

        cam = self.camera
        mvp = cam.get_projection_matrix() * cam.get_view_matrix()
        cpos = cam.position

        fbo.bind()
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glClearColor(0.10, 0.10, 0.12, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        self.frame_renderer.render_mode = 1  # shaded
        self.frame_renderer.render(
            mvp, glm.mat4(1.0), cpos,
            cam.get_view_matrix(), cam.get_projection_matrix(),
        )

        fbo.unbind()

    # ------------------------------------------------------------------
    def close(self):
        if self.frame_renderer is not None:
            try: self.frame_renderer.cleanup()
            except Exception: pass
            self.frame_renderer = None
        if self.fbo is not None:
            self.fbo.cleanup()
            self.fbo = None
        super().close()