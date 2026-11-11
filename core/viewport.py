# core/viewport.py
from __future__ import annotations

import numpy as np
from OpenGL.GL import (
    GL_FRAMEBUFFER, GL_READ_FRAMEBUFFER, GL_DRAW_FRAMEBUFFER,
    GL_COLOR_ATTACHMENT1, glBindFramebuffer, glReadBuffer, glReadPixels,
    GL_RED_INTEGER, GL_UNSIGNED_INT,
)

from core.camera import Camera
from render.offscreen_fbo import OffscreenFBO

from logging_config import CadLogger
logger = CadLogger.get(__name__)

class Viewport:
    """Bağımsız kamera + FBO. Renderer'lar ortaktır (VAO paylaşımı)."""

    def __init__(self, name: str, width: int = 640, height: int = 480,
                 camera: Camera | None = None):
        self.name = name
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self.camera = camera if camera is not None else Camera()
        self.camera.set_aspect(self.width, self.height)
        self.fbo = OffscreenFBO(self.width, self.height, with_id=True)
        self.visible = True
        self.plane = None

    # ------------------------------------------------------------------
    def resize(self, w: int, h: int):
        w, h = max(1, int(w)), max(1, int(h))
        if (w, h) == (self.width, self.height):
            return
        self.width, self.height = w, h
        self.camera.set_aspect(w, h)
        self.fbo.resize(w, h)

    def bind(self):
        self.fbo.bind()

    def unbind(self):
        self.fbo.unbind()

    def texture_id(self) -> int:
        return self.fbo.texture_id()

    # ------------------------------------------------------------------
    def pick_at(self, pick_pass, x_px: int, y_px: int):
        """FBO'nun ID attachment'ından piksel oku → element döndür."""
        if pick_pass is None or self.fbo.id_tex is None:
            return None
        x = int(x_px)
        y = self.height - 1 - int(y_px)
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return None
        fbo = self.fbo
        glBindFramebuffer(GL_READ_FRAMEBUFFER, fbo.fbo)
        glReadBuffer(GL_COLOR_ATTACHMENT1)
        buf = np.zeros((1, 1), dtype=np.uint32)
        glReadPixels(x, y, 1, 1, GL_RED_INTEGER, GL_UNSIGNED_INT, buf)
        glBindFramebuffer(GL_READ_FRAMEBUFFER, 0)
        pid = int(buf[0, 0])
        
        
        
        if pid <= 0:
            return None
        logger.debug(f"[VP_PICK_AT] fbo={self.fbo.fbo} pid={pid}")
        return pick_pass.get_element(pid)

    def pick_rect(self, pick_pass, x0, y0, x1, y1) -> list:
        """Kutu içindeki elementleri döndürür (filter'a tabi)."""
        if pick_pass is None or self.fbo.id_tex is None:
            return []
        ids = pick_pass.pick_rect(
            x0, y0, x1, y1, self.fbo.fbo, (self.width, self.height),
        )
        result = []
        for pid in ids:
            el = pick_pass.get_element(pid)
            if el is not None:
                result.append(el)
        return result

    # ------------------------------------------------------------------
    def cleanup(self):
        if self.fbo is not None:
            self.fbo.cleanup()
            self.fbo = None