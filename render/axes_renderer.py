# render/local_axes_renderer.py
"""
LocalAxesRenderer
-----------------
Element'lerin lokal koordinat sistemlerini (1-2-3 eksenleri) düz çizgi olarak çizer.

Renk konvansiyonu:
    1-ekseni → kırmızı  (1.00, 0.15, 0.15)
    2-ekseni → yeşil    (0.20, 1.00, 0.30)
    3-ekseni → cyan     (0.00, 0.90, 1.00)

Geometri:
    Birim uzayda 3 eksen × 2 nokta = 6 vertex.
    Origin (0,0,0) → (1,0,0), (0,1,0), (0,0,1).
    Her vertex position(3f) + color(3f) = 6 float, 24 byte.

Kullanım:
    renderer = LocalAxesRenderer(shader)
    renderer.init_gl()
    ...
    renderer.draw(mvp_matrix)      # çağrı başına bir model matrisi
    ...
    renderer.cleanup()
"""
from __future__ import annotations

import ctypes

import glm
import numpy as np
from OpenGL.GL import (
    GL_ARRAY_BUFFER,
    GL_FALSE,
    GL_FLOAT,
    GL_LINES,
    GL_STATIC_DRAW,
    glBindBuffer,
    glBindVertexArray,
    glBufferData,
    glDeleteBuffers,
    glDeleteVertexArrays,
    glDrawArrays,
    glEnableVertexAttribArray,
    glGenBuffers,
    glGenVertexArrays,
    glVertexAttribPointer,
)

from logging_config import CadLogger

logger = CadLogger.get(__name__)


# ---------------------------------------------------------------------------
# Renk paleti (tek yerden değiştirilebilir)
# ---------------------------------------------------------------------------
AXIS_COLORS = {
    1: (1.00, 0.15, 0.15),   # kırmızı
    2: (0.20, 1.00, 0.30),   # yeşil
    3: (0.00, 0.90, 1.00),   # cyan
}


class LocalAxesRenderer:
    """
    Element lokal eksenlerini çizen hafif GPU renderer'ı.

    Notlar:
        - Derinlik testi KAPALI olarak kullanılmalı (overlay).
        - Pick pass'e kaydedilmemeli (tıklama hedefi değil).
        - Tek VAO/VBO ile tüm elementler için aynı birim ok geometrisi kullanılır;
          her element için yalnızca model matrisi (MVP) değişir.
    """

    _VERTEX_COUNT = 6
    _VERTEX_FLOATS = 6   # pos(3) + color(3)
    _STRIDE = _VERTEX_FLOATS * 4  # byte

    def __init__(self, shader):
        """
        Parameters
        ----------
        shader : ShaderProgram
            Uniform'u `u_mvp` (mat4) olan, location=0 pos, location=1 color
            alan shader. Vertex/fragment programları önceden derlenmiş olmalı.
        """
        self.shader = shader
        self.vao = 0
        self.vbo = 0
        self._initialized = False
        self._u_mvp_loc = -1
        self._line_width = 2.0

    # ------------------------------------------------------------------ setup
    def init_gl(self) -> bool:
        """VAO/VBO ve shader uniform lokasyonunu hazırlar."""
        if self._initialized:
            return True

        if self.shader is None:
            logger.error("[LocalAxes] Shader None — init iptal")
            return False

        try:
            data = self._build_unit_axes()
            self._upload_geometry(data)

            # Uniform lokasyonunu önbelleğe al
            loc = self.shader.get_loc("u_mvp")
            self._u_mvp_loc = loc if loc is not None else -1
            if self._u_mvp_loc == -1:
                logger.warning("[LocalAxes] shader'da 'u_mvp' uniform'u bulunamadı")

            self._initialized = True
            logger.info(f"[LocalAxes] Hazır — {self._VERTEX_COUNT} vertex, "
                        f"u_mvp_loc={self._u_mvp_loc}")
            return True

        except Exception:
            logger.exception("[LocalAxes] init_gl hatası")
            self._safe_cleanup()
            return False

    def _build_unit_axes(self) -> np.ndarray:
        """Birim uzayda 3 eksen × 2 nokta verisini üretir."""
        r = AXIS_COLORS[1]
        g = AXIS_COLORS[2]
        c = AXIS_COLORS[3]

        # (x, y, z, r, g, b) × 6 vertex
        verts = (
            # 1-ekseni: origin → +X
            0.0, 0.0, 0.0,   *r,
            1.0, 0.0, 0.0,   *r,
            # 2-ekseni: origin → +Y
            0.0, 0.0, 0.0,   *g,
            0.0, 1.0, 0.0,   *g,
            # 3-ekseni: origin → +Z
            0.0, 0.0, 0.0,   *c,
            0.0, 0.0, 1.0,   *c,
        )
        return np.array(verts, dtype=np.float32)

    def _upload_geometry(self, data: np.ndarray) -> None:
        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)

        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_STATIC_DRAW)

        # location = 0 → position (vec3)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, self._STRIDE,
                              ctypes.c_void_p(0))
        glEnableVertexAttribArray(0)

        # location = 1 → color (vec3)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, self._STRIDE,
                              ctypes.c_void_p(12))
        glEnableVertexAttribArray(1)

        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

    # ------------------------------------------------------------------- draw
    def draw(self, mvp: glm.mat4) -> None:
        """
        Tek bir element için eksen üçlüsünü çizer.

        Parameters
        ----------
        mvp : glm.mat4
            Projeksiyon · View · Model matrisi. Model matrisi
            T(origin) · R(3x3 local→global) · S(scale) olmalı.
        """
        if not self._initialized or self._u_mvp_loc == -1:
            return

        from OpenGL.GL import glUniformMatrix4fv
        glUniformMatrix4fv(self._u_mvp_loc, 1, GL_FALSE, glm.value_ptr(mvp))

        glBindVertexArray(self.vao)
        glDrawArrays(GL_LINES, 0, self._VERTEX_COUNT)
        glBindVertexArray(0)

    def draw_many(self, mvps) -> None:
        """
        Birden fazla element için aynı draw call bloğunda çizer.
        Sadece u_mvp güncellenir — VAO binding'i dışarıda kalmış olsun.

        Parameters
        ----------
        mvps : Iterable[glm.mat4]
        """
        if not self._initialized or self._u_mvp_loc == -1:
            return

        from OpenGL.GL import glUniformMatrix4fv
        glBindVertexArray(self.vao)
        for mvp in mvps:
            glUniformMatrix4fv(self._u_mvp_loc, 1, GL_FALSE, glm.value_ptr(mvp))
            glDrawArrays(GL_LINES, 0, self._VERTEX_COUNT)
        glBindVertexArray(0)

    # ----------------------------------------------------------------- helpers
    def set_line_width(self, width: float) -> None:
        """
        NOT: Core profile'da 1.0 üstü driver'a bağlı. Çoğu masaüstü GPU
        en fazla 10'a kadar destekler; aşırı değerler GL_INVALID_VALUE
        üretebilir. Sessizce kabul edilebilir aralığa sıkıştırılır.
        """
        self._line_width = max(1.0, min(float(width), 10.0))

    def line_width(self) -> float:
        return self._line_width

    # ----------------------------------------------------------------- cleanup
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
        """init sırasında yarı tamamlanmış kaynakları temizler."""
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