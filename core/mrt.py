# core/mrt.py
import numpy as np
from OpenGL.GL import *


class MRTFramebuffer:

    def __init__(self, w, h):
        self.w = max(1, int(w))
        self.h = max(1, int(h))
        self.fbo = None
        self.color_tex = None
        self.id_tex = None
        self.depth_rbo = None
        self._create()

    def _create(self):
        self.fbo = glGenFramebuffers(1)
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)

        self.color_tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.color_tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, self.w, self.h, 0,
                     GL_RGB, GL_UNSIGNED_BYTE, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                               GL_TEXTURE_2D, self.color_tex, 0)

        self.id_tex = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.id_tex)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_R32UI, self.w, self.h, 0,
                     GL_RED_INTEGER, GL_UNSIGNED_INT, None)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT1,
                               GL_TEXTURE_2D, self.id_tex, 0)

        self.depth_rbo = glGenRenderbuffers(1)
        glBindRenderbuffer(GL_RENDERBUFFER, self.depth_rbo)
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, self.w, self.h)
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
                                  GL_RENDERBUFFER, self.depth_rbo)

        glDrawBuffers(2, [GL_COLOR_ATTACHMENT0, GL_COLOR_ATTACHMENT1])

        if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError("MRT FBO tamamlanamadı")
        glBindFramebuffer(GL_FRAMEBUFFER, 0)

    def bind(self):
        glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)

    def clear(self):
        self.bind()
        glClearColor(0.15, 0.15, 0.15, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        zero = np.array([0], dtype=np.uint32)
        glClearBufferuiv(GL_COLOR, 1, zero)

    def blit_to(self, target_fbo):
        glBindFramebuffer(GL_READ_FRAMEBUFFER, self.fbo)
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, target_fbo)
        glReadBuffer(GL_COLOR_ATTACHMENT0)
        glBlitFramebuffer(0, 0, self.w, self.h,
                          0, 0, self.w, self.h,
                          GL_COLOR_BUFFER_BIT, GL_NEAREST)
        glBindFramebuffer(GL_FRAMEBUFFER, target_fbo)

    def resize(self, w, h):
        self.cleanup()
        self.w = max(1, int(w))
        self.h = max(1, int(h))
        self._create()

    def cleanup(self):
        for buf, kind in (
            (self.fbo, "fbo"), (self.color_tex, "tex"),
            (self.id_tex, "tex"), (self.depth_rbo, "rbo"),
        ):
            if buf:
                if kind == "fbo":
                    glDeleteFramebuffers(1, [buf])
                elif kind == "tex":
                    glDeleteTextures(1, [buf])
                else:
                    glDeleteRenderbuffers(1, [buf])
        self.fbo = self.color_tex = self.id_tex = self.depth_rbo = None