# render/offscreen_fbo.py
"""ImGui pencerelerinde gösterilebilir bağımsız render target."""
from __future__ import annotations

import numpy as np
from OpenGL.GL import *


class OffscreenFBO:
    """Renk (+ opsiyonel ID) + depth render target. Texture olarak okunabilir."""

    def __init__(self, width: int = 640, height: int = 480,
                 with_id: bool = False):
        self.w = max(1, int(width))
        self.h = max(1, int(height))
        self.with_id = bool(with_id)
        self.fbo = 0
        self.color = 0
        self.id_tex = 0
        self.depth = 0
        self._create()

    # ------------------------------------------------------------------
    def _create(self):
        self.fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)

        # Color attachment 0
        self.color = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.color)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self.w, self.h, 0,
                     GL_RGB, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                               GL_TEXTURE_2D, self.color, 0)

        # Optional ID attachment 1
        if self.with_id:
            self.id_tex = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.id_tex)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_R32UI, self.w, self.h, 0,
                         GL_RED_INTEGER, GL_UNSIGNED_INT, None)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT1,
                                   GL_TEXTURE_2D, self.id_tex, 0)
            glDrawBuffers(2, [GL_COLOR_ATTACHMENT0, GL_COLOR_ATTACHMENT1])

        # Depth
        self.depth = glGenRenderbuffers(1)
        glBindRenderbuffer(GL_RENDERBUFFER, self.depth)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, self.w, self.h)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
                                  GL_RENDERBUFFER, self.depth)

        if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError("OffscreenFBO tamamlanamadı")
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    # ------------------------------------------------------------------
    def bind(self):
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
        glViewport(0, 0, self.w, self.h)
        if self.with_id:
            glDrawBuffers(2, [GL_COLOR_ATTACHMENT0, GL_COLOR_ATTACHMENT1])
        else:
            glDrawBuffer(GL_COLOR_ATTACHMENT0)

    @staticmethod
    def unbind():
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def clear(self, color=(0.10, 0.10, 0.12, 1.0)):
        self.bind()
        glClearColor(*color)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if self.with_id:
            zero = np.array([0, 0, 0, 0], dtype=np.uint32)
            glClearBufferuiv(GL_COLOR, 1, zero)

    def resize(self, w: int, h: int):
        w, h = max(1, int(w)), max(1, int(h))
        if (w, h) == (self.w, self.h):
            return
        self.w, self.h = w, h
        # Texture'ları yeniden boyutlandır
        glBindTexture(GL_TEXTURE_2D, self.color)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self.w, self.h, 0,
                     GL_RGB, GL_UNSIGNED_BYTE, None)
        glBindTexture(GL_TEXTURE_2D, 0)
        if self.with_id and self.id_tex:
            glBindTexture(GL_TEXTURE_2D, self.id_tex)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_R32UI, self.w, self.h, 0,
                         GL_RED_INTEGER, GL_UNSIGNED_INT, None)
            glBindTexture(GL_TEXTURE_2D, 0)
        glBindRenderbuffer(GL_RENDERBUFFER, self.depth)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, self.w, self.h)
        glBindRenderbuffer(GL_RENDERBUFFER, 0)

    def texture_id(self) -> int:
        return self.color

    def cleanup(self):
        if self.color:
            glDeleteTextures(1, [self.color]); self.color = 0
        if self.id_tex:
            glDeleteTextures(1, [self.id_tex]); self.id_tex = 0
        if self.depth:
            glDeleteRenderbuffers(1, [self.depth]); self.depth = 0
        if self.fbo:
            glDeleteFramebuffers(1, [self.fbo]); self.fbo = 0