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
        glDrawBuffer(GL_COLOR_ATTACHMENT0)
        glClearColor(0.15, 0.15, 0.15, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glDrawBuffer(GL_COLOR_ATTACHMENT1)
        zero = np.array([0, 0, 0, 0], dtype=np.uint32)
        glClearBufferuiv(GL_COLOR, 0, zero)
        glDrawBuffer(GL_COLOR_ATTACHMENT0)

    def blit_to(
        self, target_fbo, target_w=None, target_h=None, copy_id=False,
        source_w=None, source_h=None,
    ):
        tw = int(target_w) if target_w else self.w
        th = int(target_h) if target_h else self.h
        sw = int(source_w) if source_w else self.w
        sh = int(source_h) if source_h else self.h
        glBindFramebuffer(GL_READ_FRAMEBUFFER, self.fbo)
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, target_fbo)

        # Color
        glReadBuffer(GL_COLOR_ATTACHMENT0)
        glDrawBuffer(GL_COLOR_ATTACHMENT0)
        glBlitFramebuffer(0, 0, sw, sh,
                          0, 0, tw, th,
                          GL_COLOR_BUFFER_BIT, GL_NEAREST)

        # ID (opsiyonel)
        if copy_id:
            
            glReadBuffer(GL_COLOR_ATTACHMENT1)
            glDrawBuffer(GL_COLOR_ATTACHMENT1)
            glBlitFramebuffer(0, 0, sw, sh,
                              0, 0, tw, th,
                              GL_COLOR_BUFFER_BIT, GL_NEAREST)
            glDrawBuffer(GL_COLOR_ATTACHMENT0)

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