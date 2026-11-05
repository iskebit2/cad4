# render/global_axis_renderer.py
"""
GlobalAxisRenderer — Tekla tarzı tıklanabilir global eksen.

Özellikler:
    - Sol alt köşede 3D eksen üçlüsü (X=kırmızı, Y=yeşil, Z=mavi)
    - Kameraya duyarlı (view rotation ile döner)
    - Tıklanabilir: X/Y/Z eksenine tıklayınca kamera o yönden bakar
    - Hover vurgusu: fare üstündeyken eksen parlar
    - Ayarlanabilir: renk, uzunluk, görünürlük, konum, etiket
    - 2D/3D projection desteği (2D'de ekrana dik eksen gizlenir)

Kullanım:
    axis = GlobalAxisRenderer(shader=axes_shader)
    axis.init_gl()

    # her frame:
    axis.begin_frame(camera, viewport_w, viewport_h, projection="3d")
    axis.render()   # çizer + hover güncelle

    # tıklama:
    hit = axis.pick(mouse_x, mouse_y)
    if hit:
        axis.apply_view(hit, camera)   # X/Y/Z → view preset
"""

from __future__ import annotations

import ctypes
import math
from dataclasses import dataclass, field

from pyglm import glm
import numpy as np
from OpenGL.GL import *

from logging_config import CadLogger

logger = CadLogger.get(__name__)


# ---------------------------------------------------------------------------
# Ayarlar
# ---------------------------------------------------------------------------
@dataclass
class GlobalAxisSettings:
    """Global eksen görsel ayarları."""
    visible: bool = True
    show_labels: bool = True

    # Görsel
    length: float = 1.0                 # NDC uzayında eksen uzunluğu (HUD boyutu)
    line_width: float = 2.0
    gizmo_size: int = 100               # viewport piksel cinsinden kutu boyutu
    margin: int = 12                    # kenardan boşluk
    position: str = "bottom_right"      # "bottom_right" | "bottom_left" | "top_right" | "top_left"

    # Renkler (RGB)
    color_x: tuple = (1.00, 0.20, 0.20)
    color_y: tuple = (0.20, 1.00, 0.30)
    color_z: tuple = (0.20, 0.55, 1.00)
    color_hover: tuple = (1.00, 1.00, 0.40)     # hover vurgu rengi
    color_shadow: tuple = (0.0, 0.0, 0.0)       # hafif gölge (okunabilirlik)

    # Etkileşim
    pick_radius_px: float = 12.0        # tıklama toleransı
    hover_alpha: float = 1.0
    normal_alpha: float = 0.85

    # Görünürlük
    hide_axis_when_perpendicular: bool = True   # 2D'de ekrana dik ekseni gizle


# ---------------------------------------------------------------------------
# Eksen tanımı
# ---------------------------------------------------------------------------
AXIS_X = "X"
AXIS_Y = "Y"
AXIS_Z = "Z"
AXES = (AXIS_X, AXIS_Y, AXIS_Z)


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------
class GlobalAxisRenderer:
    """
    Tekla tarzı global eksen HUD'u.

    - Sol alt köşede sabit konumda küçük bir viewport açar
    - İçine kameranın rotasyonuyla dönen eksen üçlüsü çizer
    - Ekran uzayında tıklama testi yapar (pick_radius_px toleransı)
    """

    _VERTEX_FLOATS = 6   # pos3 + color3
    _STRIDE = _VERTEX_FLOATS * 4

    def __init__(self, shader, settings: GlobalAxisSettings | None = None):
        self.shader = shader
        self.settings = settings or GlobalAxisSettings()

        self.vao = 0
        self.vbo = 0
        self._initialized = False
        self._u_mvp_loc = -1
        self._u_alpha_loc = -1

        # Frame state
        self._camera = None
        self._viewport_w = 1
        self._viewport_h = 1
        self._projection = "3d"

        # Hover state
        self._hover_axis: str | None = None

        # Screen-space hit boxes (her frame güncellenir)
        self._hit_boxes: dict[str, tuple[float, float, float, float]] = {}

    # ==================================================================
    # INIT
    # ==================================================================
    def init_gl(self) -> bool:
        if self._initialized:
            return True
        if self.shader is None:
            logger.error("[GlobalAxis] shader None — init iptal")
            return False

        try:
            data = self._build_unit_axes()
            self._upload_geometry(data)

            self._u_mvp_loc = self.shader.get_loc("u_mvp")
            if self._u_mvp_loc == -1:
                self._u_mvp_loc = self.shader.get_loc("mvp")
            self._u_alpha_loc = self.shader.get_loc("alpha")

            self._initialized = True
            logger.info("[GlobalAxis] Hazır (vao=%d, u_mvp=%d)",
                        self.vao, self._u_mvp_loc)
            return True
        except Exception:
            logger.exception("[GlobalAxis] init hatası")
            self._safe_cleanup()
            return False

    def _build_unit_axes(self) -> np.ndarray:
        """
        Origin'den +X, +Y, +Z yönlerine 3 eksen.
        Her eksen 2 vertex (başlangıç + bitiş).
        Toplam 6 vertex × 6 float (pos + color).
        """
        cx = self.settings.color_x
        cy = self.settings.color_y
        cz = self.settings.color_z

        verts = (
            # X — kırmızı
            0.0, 0.0, 0.0,  *cx,
            1.0, 0.0, 0.0,  *cx,
            # Y — yeşil
            0.0, 0.0, 0.0,  *cy,
            0.0, 1.0, 0.0,  *cy,
            # Z — mavi
            0.0, 0.0, 0.0,  *cz,
            0.0, 0.0, 1.0,  *cz,
        )
        return np.array(verts, dtype=np.float32)

    def _upload_geometry(self, data: np.ndarray) -> None:
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_STATIC_DRAW)

        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, self._STRIDE,
                              ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, self._STRIDE,
                              ctypes.c_void_p(12))

        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

    # ==================================================================
    # FRAME API
    # ==================================================================
    def begin_frame(self, camera, viewport_w: int, viewport_h: int,
                    projection: str = "3d") -> None:
        """Her frame başında çağrılır — hover ve hit box'ları temizler."""
        self._camera = camera
        self._viewport_w = max(1, viewport_w)
        self._viewport_h = max(1, viewport_h)
        self._projection = projection
        self._hover_axis = None
        self._hit_boxes.clear()

    def update_hover(self, mouse_x: float, mouse_y: float) -> str | None:
        """Fare üzerinde hangi eksen var? Hit box'lar zaten güncel."""
        if not self._hit_boxes:
            return None
        best_axis = None
        best_dist = self.settings.pick_radius_px
        for axis, (x0, y0, x1, y1) in self._hit_boxes.items():
            # Nokta-doğru parçası mesafesi (ekran uzayı)
            d = self._point_segment_dist(mouse_x, mouse_y, x0, y0, x1, y1)
            if d < best_dist:
                best_dist = d
                best_axis = axis
        self._hover_axis = best_axis
        return best_axis

    def render(self) -> None:
        """
        Eksenleri çizer.

        Adımlar:
            1. Gizmo viewport'unu ayır (sol alt köşe)
            2. Ortografik projeksiyon + kameranın view rotasyonu
            3. Eksenleri çiz (hover vurgusu ile)
            4. Viewport'u geri yükle
            5. Ekran uzayında hit box'ları güncelle (tıklama için)
        """
        if not self._initialized or not self.settings.visible:
            return
        if self._camera is None:
            return

        # ---- 1. Gizmo viewport ----
        old_viewport = glGetIntegerv(GL_VIEWPORT)
        gx, gy = self._gizmo_origin_px()
        gs = self.settings.gizmo_size
        glViewport(gx, gy, gs, gs)

        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glLineWidth(self.settings.line_width)

        try:
            # ---- 2. MVP ----
            proj = glm.ortho(-1.5, 1.5, -1.5, 1.5, -10.0, 10.0)
            view_mat = self._camera.get_view_matrix()
            # Sadece rotasyon (translation sıfırla)
            view_rot = glm.mat4(glm.mat3(view_mat))
            model = glm.scale(glm.mat4(1.0), glm.vec3(self.settings.length * 0.85))
            mvp = proj * view_rot * model

            self.shader.use()
            if self._u_mvp_loc != -1:
                glUniformMatrix4fv(self._u_mvp_loc, 1, GL_FALSE,
                                   glm.value_ptr(mvp))

            glBindVertexArray(self.vao)

            # ---- 3. Eksenleri çiz ----
            # Her eksen 2 vertex = 6 float per vertex
            # X: vertex 0-1, Y: 2-3, Z: 4-5
            axis_ranges = (
                (AXIS_X, 0, 2),
                (AXIS_Y, 2, 4),
                (AXIS_Z, 4, 6),
            )
            for axis_name, start, end in axis_ranges:
                if self._should_hide_axis(axis_name):
                    continue
                alpha = self._alpha_for(axis_name)
                if self._u_alpha_loc != -1:
                    glUniform1f(self._u_alpha_loc, alpha)
                # Hover rengini ayrı çiz (opsiyonel — şimdilik aynı renk, sadece alpha)
                glDrawArrays(GL_LINES, start, end - start)

            glBindVertexArray(0)

        finally:
            glEnable(GL_DEPTH_TEST)
            glDisable(GL_BLEND)
            glViewport(*old_viewport)

        # ---- 5. Hit box'ları güncelle (ekran uzayı) ----
        self._update_hit_boxes()

    # ==================================================================
    # PICK / VIEW
    # ==================================================================
    def pick(self, mouse_x: float, mouse_y: float) -> str | None:
        """
        Fare pozisyonuna göre eksen seç.
        Hit box'lar `render()` sonrası hazır olmalı.
        """
        if not self._hit_boxes:
            return None
        best_axis = None
        best_dist = self.settings.pick_radius_px
        for axis, (x0, y0, x1, y1) in self._hit_boxes.items():
            d = self._point_segment_dist(mouse_x, mouse_y, x0, y0, x1, y1)
            if d < best_dist:
                best_dist = d
                best_axis = axis
        return best_axis

    def apply_view(self, axis: str, camera) -> bool:
        """
        X/Y/Z eksenine göre kamerayı hizala.
        Tekla'da eksen tıklaması = o yönden bak.
        """
        presets = {
            AXIS_X: "right",   # +X yönünden bak → sağ görünüm
            AXIS_Y: "front",   # +Y yönünden bak → ön görünüm
            AXIS_Z: "top",     # +Z yönünden bak → üst görünüm
        }
        preset = presets.get(axis)
        if preset is None:
            return False
        try:
            camera.set_view_preset(preset)
            logger.info("[GlobalAxis] View preset: %s", preset)
            return True
        except Exception:
            logger.exception("[GlobalAxis] apply_view hatası: %s", axis)
            return False

    def hover_axis(self) -> str | None:
        return self._hover_axis

    # ==================================================================
    # AYARLAR
    # ==================================================================
    def set_visible(self, visible: bool) -> None:
        self.settings.visible = bool(visible)

    def set_length(self, length: float) -> None:
        self.settings.length = max(0.1, min(float(length), 3.0))

    def set_colors(self, x=None, y=None, z=None) -> None:
        if x is not None:
            self.settings.color_x = tuple(x)
        if y is not None:
            self.settings.color_y = tuple(y)
        if z is not None:
            self.settings.color_z = tuple(z)
        # Renk değişti → VBO yeniden üret
        if self._initialized:
            data = self._build_unit_axes()
            glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
            glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_STATIC_DRAW)
            glBindBuffer(GL_ARRAY_BUFFER, 0)

    def set_position(self, position: str) -> None:
        if position in ("bottom_right", "bottom_left", "top_right", "top_left"):
            self.settings.position = position

    # ==================================================================
    # YARDIMCILAR
    # ==================================================================
    def _gizmo_origin_px(self) -> tuple[int, int]:
        """Gizmo viewport'unun sol-alt köşesi (OpenGL piksel)."""
        m = self.settings.margin
        gs = self.settings.gizmo_size
        w, h = self._viewport_w, self._viewport_h
        pos = self.settings.position
        if pos == "bottom_right":
            return (w - gs - m, m)
        if pos == "bottom_left":
            return (m, m)
        if pos == "top_right":
            return (w - gs - m, h - gs - m)
        if pos == "top_left":
            return (m, h - gs - m)
        return (m, m)

    def _should_hide_axis(self, axis: str) -> bool:
        """2D'de ekrana dik ekseni gizle."""
        if not self.settings.hide_axis_when_perpendicular:
            return False
        if self._projection == "3d":
            return False
        # 2D top view: Z ekseni ekrana dik → gizle
        # (İleride diğer preset'ler için genişlet)
        return axis == AXIS_Z

    def _alpha_for(self, axis: str) -> float:
        if self._hover_axis == axis:
            return self.settings.hover_alpha
        return self.settings.normal_alpha

    def _update_hit_boxes(self) -> None:
        """
        Dünya uzayındaki eksen uçlarını ekran uzayına projekte et.
        Her eksen için (x0, y0, x1, y1) piksel hit box.
        """
        if self._camera is None:
            return

        # Gizmo'nun MVP'sini tekrar hesapla (render ile aynı)
        proj = glm.ortho(-1.5, 1.5, -1.5, 1.5, -10.0, 10.0)
        view_mat = self._camera.get_view_matrix()
        view_rot = glm.mat4(glm.mat3(view_mat))
        model = glm.scale(glm.mat4(1.0), glm.vec3(self.settings.length * 0.85))
        mvp = proj * view_rot * model

        gx, gy = self._gizmo_origin_px()
        gs = self.settings.gizmo_size

        def to_screen(world_pt: glm.vec3) -> tuple[float, float]:
            clip = mvp * glm.vec4(world_pt.x, world_pt.y, world_pt.z, 1.0)
            if abs(clip.w) < 1e-9:
                return (0.0, 0.0)
            ndc = glm.vec3(clip) / clip.w
            # Gizmo viewport içi → tam ekran piksel
            px_in_gizmo = (ndc.x + 1.0) * 0.5 * gs
            py_in_gizmo = (1.0 - ndc.y) * 0.5 * gs
            return (gx + px_in_gizmo, gy + py_in_gizmo)

        origin = to_screen(glm.vec3(0.0, 0.0, 0.0))
        endpoints = {
            AXIS_X: to_screen(glm.vec3(1.0, 0.0, 0.0)),
            AXIS_Y: to_screen(glm.vec3(0.0, 1.0, 0.0)),
            AXIS_Z: to_screen(glm.vec3(0.0, 0.0, 1.0)),
        }

        for axis, end in endpoints.items():
            if self._should_hide_axis(axis):
                continue
            # Ekran Y'si OpenGL ile ters — mouse Y ile eşleşsin diye ters çevir
            # (CadApp mouse koordinatı Kivy/GLFW: y=0 üst, y=h alt)
            x0, y0 = origin[0], self._viewport_h - origin[1]
            x1, y1 = end[0], self._viewport_h - end[1]
            self._hit_boxes[axis] = (x0, y0, x1, y1)

    @staticmethod
    def _point_segment_dist(px: float, py: float,
                            x0: float, y0: float,
                            x1: float, y1: float) -> float:
        """Noktadan doğru parçasına mesafe (ekran uzayı)."""
        dx = x1 - x0
        dy = y1 - y0
        L2 = dx * dx + dy * dy
        if L2 < 1e-9:
            return math.hypot(px - x0, py - y0)
        t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
        cx = x0 + t * dx
        cy = y0 + t * dy
        return math.hypot(px - cx, py - cy)

    # ==================================================================
    # CLEANUP
    # ==================================================================
    def cleanup(self) -> None:
        if self.vao:
            try:
                glDeleteVertexArrays(1, [self.vao])
            except Exception:
                pass
            self.vao = 0
        if self.vbo:
            try:
                glDeleteBuffers(1, [self.vbo])
            except Exception:
                pass
            self.vbo = 0
        self._initialized = False

    def _safe_cleanup(self) -> None:
        if self.vao and not self._initialized:
            try:
                glDeleteVertexArrays(1, [self.vao])
            except Exception:
                pass
            self.vao = 0
        if self.vbo and not self._initialized:
            try:
                glDeleteBuffers(1, [self.vbo])
            except Exception:
                pass
            self.vbo = 0