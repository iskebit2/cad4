# ui/snapsquare.py
"""
Basit snap göstergesi.

Sadece draw mode aktifken kullanılır.
Node'a yakınken sarı kare gösterir.
Fare normal ok kalır.
"""
from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader

import numpy as np
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class SnapSquareRenderer:
    """Draw mode için basit snap göstergesi (sarı kare)."""

    def __init__(self):
        self.shader = None
        self.u_color_loc = -1
        self.vao = None
        self.vbo = None

        self._init_shader()

        # Kare boyutu (NDC uzayında)
        self.size = 0.025

        # Renk — sarı
        self.color = (1.0, 0.9, 0.0, 1.0)

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
            compileShader(frag_src, GL_FRAGMENT_SHADER)
        )
        glUseProgram(self.shader)
        self.u_color_loc = glGetUniformLocation(self.shader, "uColor")
        glUseProgram(0)

    def draw_snap(self, mouse_x, mouse_y, w, h, active=True):
        """
        Snap göstergesi çiz.

        Parameters
        ----------
        mouse_x, mouse_y : float
            Fare pozisyonu (Kivy koordinatı)
        w, h : int
            Pencere boyutu
        active : bool
            True ise sarı kare çizilir, False ise hiçbir şey çizilmez.
        """
        if not active:
            return

        if not self.shader:
            return

        # Lazy init
        if self.vao is None:
            self.vao = glGenVertexArrays(1)
            self.vbo = glGenBuffers(1)

        # Fare NDC koordinatı
        nx = (mouse_x / w) * 2.0 - 1.0
        ny = 1.0 - (mouse_y / h) * 2.0

        # Aspect ratio (kare yatayda uzamasın)
        asp = w / h

        # Kare boyutu
        s = self.size

        vertices = np.array([
            nx - s / asp, ny - s,   # sol-alt
            nx + s / asp, ny - s,   # sağ-alt
            nx + s / asp, ny + s,   # sağ-üst
            nx - s / asp, ny + s,   # sol-üst
        ], dtype=np.float32)

        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glUseProgram(self.shader)
        glUniform4f(self.u_color_loc, *self.color)

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

    def cleanup(self):
        """GPU kaynaklarını serbest bırak."""
        if self.shader and glIsProgram(self.shader):
            glDeleteProgram(self.shader)
            self.shader = None

        if self.vao and glIsVertexArray(self.vao):
            glDeleteVertexArrays(1, [self.vao])
            self.vao = None

        if self.vbo and glIsBuffer(self.vbo):
            glDeleteBuffers(1, [self.vbo])
            self.vbo = None