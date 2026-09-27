# render/light_ubo.py
from OpenGL.GL import *
import numpy as np
import logging

logger = logging.getLogger(__name__)


class LightUBO:
    MAX_LIGHTS    = 8
    BINDING_POINT = 0
    BUFFER_SIZE   = 320    # byte (std140 aligned)

    # Float indexleri
    IDX_POS    = 4     # lightPositions[0] başlangıcı
    IDX_COL    = 36    # lightColors[0] başlangıcı
    IDX_VIEW   = 68    # viewPos
    IDX_PARAMS = 72    # ambient, diffuse, ...

    def __init__(self):
        self.ubo = glGenBuffers(1)

        glBindBuffer(GL_UNIFORM_BUFFER, self.ubo)
        glBufferData(GL_UNIFORM_BUFFER, self.BUFFER_SIZE, None, GL_DYNAMIC_DRAW)
        glBindBufferBase(GL_UNIFORM_BUFFER, self.BINDING_POINT, self.ubo)
        glBindBuffer(GL_UNIFORM_BUFFER, 0)

        # CPU buffer — int32 view + float32 view (aynı bellek)
        self._buf_i = np.zeros(self.BUFFER_SIZE // 4, dtype=np.int32)
        self._buf_f = self._buf_i.view(np.float32)

        logger.debug(f"[LightUBO] oluşturuldu ({self.BUFFER_SIZE} byte)")

    def update(self, lighting, camera_pos):
        fi = self._buf_f
        ii = self._buf_i

        # Sıfırla
        fi[:] = 0.0

        n = min(len(lighting.pos), self.MAX_LIGHTS)

        

        # ---- lightCount (int) ----
        ii[0] = n

        # ---- Işıklar ----
        for i in range(n):
            p    = lighting.pos[i]
            c    = lighting.colors[i]
            inten = lighting.intensities[i]

            fi[self.IDX_POS + i * 4 : self.IDX_POS + i * 4 + 3] = p
            fi[self.IDX_COL + i * 4 : self.IDX_COL + i * 4 + 3] = (
                c[0] * inten,
                c[1] * inten,
                c[2] * inten,
            )

        # ---- Kamera pozisyonu (vec4) ----
        fi[self.IDX_VIEW : self.IDX_VIEW + 3] = camera_pos
        fi[self.IDX_VIEW + 3] = 1.0

        # ---- Parametreler (ardışık float) ----
        fi[self.IDX_PARAMS + 0] = lighting.ambient
        fi[self.IDX_PARAMS + 1] = lighting.diffuse
        fi[self.IDX_PARAMS + 2] = lighting.specular
        fi[self.IDX_PARAMS + 3] = lighting.shininess
        fi[self.IDX_PARAMS + 4] = lighting.brightness

        # ---- GPU'ya gönder ----
        glBindBuffer(GL_UNIFORM_BUFFER, self.ubo)
        glBufferSubData(GL_UNIFORM_BUFFER, 0, fi.nbytes, fi)
        glBindBuffer(GL_UNIFORM_BUFFER, 0)

    def cleanup(self):
        if self.ubo:
            glDeleteBuffers(1, [int(self.ubo)])
            self.ubo = None