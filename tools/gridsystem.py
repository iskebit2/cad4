# tools/gridsystem.py
"""
Dinamik grid sistemi.

- Model bounds'larına göre otomatik ölçeklenir.
- Major / minor çizgi ayrımı.
- Vertex rengi grid'den gelir, alpha shader'dan gelir.
- Kendi shader'ını kullanır (grid.vert / grid.frag).
"""

import glm
import numpy as np
import ctypes
import logging

from OpenGL.GL import (
    glGenVertexArrays, glGenBuffers, glBindVertexArray, glBindBuffer,
    glBufferData, glIsBuffer, glIsVertexArray, glVertexAttribPointer, glEnableVertexAttribArray,
    glDrawArrays, glDeleteVertexArrays, glDeleteBuffers,
    glUniformMatrix4fv, glUniform1f,
    GL_ARRAY_BUFFER, GL_STATIC_DRAW, GL_FLOAT, GL_FALSE,
    GL_LINES,
)

logger = logging.getLogger(__name__)


# ============================================================
# RENK PALETİ
# ============================================================

COLOR_MAJOR  = (0.55, 0.55, 0.60)   # Ana çizgiler
COLOR_MINOR  = (0.25, 0.27, 0.32)   # İnce çizgiler
COLOR_X_AXIS = (0.70, 0.25, 0.25)   # X ekseni (kırmızımsı)
COLOR_Y_AXIS = (0.25, 0.70, 0.25)   # Y ekseni (yeşilimsi)


# ============================================================
# GRID SYSTEM
# ============================================================

class GridSystem:
    """
    Model boyutuna göre otomatik ölçeklenen grid.

    Kullanım:
        grid = GridSystem(shader)
        grid.update(glm.vec3(cx, cy, 0), size=5000)
        grid.draw(mvp)
    """

    # Grid çizim parametreleri
    GRID_ALPHA = 0.55          # Tüm grid için global saydamlık
    VERTEX_FLOATS = 6          # pos3 + color3
    VERTEX_STRIDE = VERTEX_FLOATS * 4   # 24 byte

    def __init__(self, shader_program):
        self.shader = shader_program

        self.vao = None
        self.vbo = None
        self.vertex_count = 0

        # Grid durumu
        self.center = glm.vec3(0.0, 0.0, 0.0)
        self.size = 50.0
        self.divisions = 20

        # İlk grid'i oluştur
        self._create_grid(self.size, self.divisions)

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------

    def update(self, center: glm.vec3, size: float):
        """Merkez ve boyuta göre grid'i yeniden üret."""
        self.center = center
        self.size = size
        self.divisions = self._optimal_divisions(size)
        self._create_grid(size, self.divisions)

    def draw(self, mvp_matrix):
        """Grid'i çiz."""
        if not self.vao or self.vertex_count == 0 or not self.shader:
            return

        self.shader.use()

        # MVP
        mvp_loc = self.shader.get_loc("mvp")
        if mvp_loc != -1:
            glUniformMatrix4fv(mvp_loc, 1, GL_FALSE, glm.value_ptr(mvp_matrix))

        # Alpha
        alpha_loc = self.shader.get_loc("alpha")
        if alpha_loc != -1:
            glUniform1f(alpha_loc, self.GRID_ALPHA)

        glBindVertexArray(self.vao)
        glDrawArrays(GL_LINES, 0, self.vertex_count)
        glBindVertexArray(0)

    def cleanup(self):
        """GPU kaynaklarını serbest bırak."""
        try:
            if self.vao is not None and glIsVertexArray(self.vao):
                glDeleteVertexArrays(1, [int(self.vao)])
        except Exception:
            pass
        try:
            if self.vbo is not None and glIsBuffer(self.vbo):
                glDeleteBuffers(1, [int(self.vbo)])
        except Exception:
            pass

        self.vao = None
        self.vbo = None
        self.vertex_count = 0
        self.shader = None

    # ---------------------------------------------------------
    # OPTİMAL DEĞERLER
    # ---------------------------------------------------------

    @staticmethod
    def _optimal_divisions(size: float) -> int:
        """Grid boyutuna göre optimal bölünme sayısı."""
        if size < 10:    return 10
        if size < 50:    return 20
        if size < 200:   return 30
        if size < 1000:  return 40
        return 50

    @staticmethod
    def _major_spacing(size: float) -> float:
        """Grid boyutuna göre ana çizgi aralığı."""
        if size < 5:      return 0.5
        if size < 10:     return 1.0
        if size < 20:     return 2.0
        if size < 50:     return 5.0
        if size < 100:    return 10.0
        if size < 200:    return 20.0
        if size < 500:    return 50.0
        if size < 1000:   return 100.0
        if size < 2000:   return 200.0
        if size < 5000:   return 500.0
        if size < 10000:  return 1000.0
        if size < 20000:  return 2000.0
        if size < 50000:  return 5000.0
        return 10000.0

    # ---------------------------------------------------------
    # GRID ÜRETİMİ
    # ---------------------------------------------------------

    def _create_grid(self, size: float, divisions: int):
        """Grid vertex'lerini oluştur ve GPU'ya yükle."""
        half = size / 2
        step = size / divisions
        major_spacing = self._major_spacing(size)

        sx = self.center.x - half
        sy = self.center.y - half
        ex = self.center.x + half
        ey = self.center.y + half
        z = self.center.z

        vertices = []   # [x, y, z, r, g, b] × N

        # ---- Dikey çizgiler (X sabit) ----
        for i in range(divisions + 1):
            x = sx + i * step
            color = self._line_color(x, step, major_spacing)
            vertices.extend([x, sy, z, *color])
            vertices.extend([x, ey, z, *color])

        # ---- Yatay çizgiler (Y sabit) ----
        for i in range(divisions + 1):
            y = sy + i * step
            color = self._line_color(y, step, major_spacing)
            vertices.extend([sx, y, z, *color])
            vertices.extend([ex, y, z, *color])

        # ---- Merkez eksenleri ----
        vertices.extend([sx, 0, z, *COLOR_X_AXIS])
        vertices.extend([ex, 0, z, *COLOR_X_AXIS])
        vertices.extend([0, sy, z, *COLOR_Y_AXIS])
        vertices.extend([0, ey, z, *COLOR_Y_AXIS])

        # ---- GPU'ya yükle ----
        self._upload(vertices)

        logger.debug(f"size={size:.1f}, divisions={divisions}, vertices={self.vertex_count}")

    @staticmethod
    def _line_color(coord: float, step: float, major_spacing: float) -> tuple:
        """Koordinata göre major/minor çizgi rengi."""
        # Major çizgi kontrolü (toleranslı)
        remainder = abs(coord) % major_spacing
        is_major = remainder < step / 2 or (major_spacing - remainder) < step / 2
        return COLOR_MAJOR if is_major else COLOR_MINOR

    def _upload(self, vertices: list):
        """Vertex listesini GPU'ya yükle."""
        # Önceki kaynakları temizle
        self._delete_buffers()

        self.vertex_count = len(vertices) // self.VERTEX_FLOATS
        if self.vertex_count == 0:
            return

        data = np.asarray(vertices, dtype=np.float32)

        self.vao = glGenVertexArrays(1)
        self.vbo = glGenBuffers(1)

        glBindVertexArray(self.vao)

        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_STATIC_DRAW)

        stride = self.VERTEX_STRIDE

        # location 0: pozisyon
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))

        # location 1: renk (RGB)
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

    def _delete_buffers(self):
        """VAO/VBO'yu sil (yeni grid için)."""
        try:
            if self.vao is not None and glIsVertexArray(self.vao):
                glDeleteVertexArrays(1, [int(self.vao)])
        except Exception:
            pass
        try:
            if self.vbo is not None and glIsBuffer(self.vbo):
                glDeleteBuffers(1, [int(self.vbo)])
        except Exception:
            pass

        self.vao = None
        self.vbo = None
        self.vertex_count = 0