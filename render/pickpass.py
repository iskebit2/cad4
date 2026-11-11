# render/pickpass.py
import ctypes
import time

import numpy as np
from OpenGL.GL import *

from logging_config import CadLogger

logger = CadLogger.get(__name__)

class PickPass:
    def __init__(self):
        self.fbo = None
        self.texture = None
        self.depth_rbo = None
        
        # PBO'lar (ping-pong)
        self.pbos = [None, None]
        self.current_pbo = 0
        self.read_pbo = 1
        
        # Async pick state
        self.pending_pick = False
        self.pending_x = -1
        self.pending_y = -1
        self.last_pick_id = 0
        
        # Viewport bilgisi
        self.main_fbo = None
        self.viewport_width = 0
        self.viewport_height = 0
        
        # Element map
        self.elements = {}
        self.renderers = {}
        
        self.pick_start_time = 0
        self.pick_timeout = 0.5

        self.pick_size = 3
        self.pick_half = self.pick_size // 2
        self.pick_bytes = self.pick_size * self.pick_size * 4
        
        rows, cols = np.indices((self.pick_size, self.pick_size))
        self._dx = (cols - self.pick_half).flatten()
        self._dy = ((self.pick_size - 1 - rows) - self.pick_half).flatten()
        self._dist2 = self._dx**2 + self._dy**2
        
        self._create_resources()
    
    def _create_resources(self):
        try:
            self.fbo = glGenFramebuffers(1)
            glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)

            self.texture = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.texture)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_R32UI, 1, 1, 0, GL_RED_INTEGER, GL_UNSIGNED_INT, None)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self.texture, 0)

            self.depth_rbo = glGenRenderbuffers(1)
            glBindRenderbuffer(GL_RENDERBUFFER, self.depth_rbo)
            glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, 1, 1)
            glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, self.depth_rbo)

            if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError("FBO tamamlanamadı")

            for i in range(2):
                self.pbos[i] = glGenBuffers(1)
                glBindBuffer(GL_PIXEL_PACK_BUFFER, self.pbos[i])
                glBufferData(GL_PIXEL_PACK_BUFFER, self.pick_bytes, None, GL_STREAM_READ)

            glBindBuffer(GL_PIXEL_PACK_BUFFER, 0)
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
        except Exception as e:
            logger.error(f"PickPass kaynak oluşturma hatası: {e}")
            raise
    
    def set_main_fbo(self, fbo):
        self.main_fbo = fbo
    
    def register(self, pick_id, element, renderer):
        if pick_id > 0:
            self.elements[pick_id] = element
            self.renderers[pick_id] = renderer
    
    def unregister(self, pick_id):
        self.elements.pop(pick_id, None)
        self.renderers.pop(pick_id, None)

    def clear_registry(self):
        self.elements.clear()
        self.renderers.clear()
    
    def get_element(self, pick_id):
        return self.elements.get(pick_id)
    
    def get_renderer(self, pick_id):
        return self.renderers.get(pick_id)
    
    def set_viewport(self, width, height):
        self.viewport_width = width
        self.viewport_height = height

    def pick_async(self, x, y, source_fbo=None, viewport_size=None):
        if self.pending_pick:
            if time.time() - self.pick_start_time > self.pick_timeout:
                self.pending_pick = False
            else:
                return False

        width, height = viewport_size or (
            self.viewport_width, self.viewport_height,
        )
        if x < 0 or x >= width or y < 0 or y >= height:
            self.last_pick_id = 0
            return True

        try:
            read_fbo = source_fbo if source_fbo is not None else self.main_fbo
            if read_fbo:
                glBindFramebuffer(GL_READ_FRAMEBUFFER, read_fbo)
                glReadBuffer(GL_COLOR_ATTACHMENT1)
            else:
                glBindFramebuffer(GL_READ_FRAMEBUFFER, 0)
                glReadBuffer(GL_FRONT)

            size = self.pick_size
            half = self.pick_half

            x0 = int(x) - half
            y0 = int(y) - half

            x0 = max(0, min(x0, width - size))
            y0 = max(0, min(y0, height - size))

            # DÜZELTME: OpenGL Y ekseni dönüşümü (pencere alt-sol orijin uyumu)
            opengl_y = height - y0 - size

            pbo = self.pbos[self.current_pbo]
            glBindBuffer(GL_PIXEL_PACK_BUFFER, pbo)
            glPixelStorei(GL_PACK_ALIGNMENT, 1)

            glReadPixels(x0, opengl_y, size, size, GL_RED_INTEGER, GL_UNSIGNED_INT, 0)

            self.pending_pick = True
            self.pending_x = int(x)
            self.pending_y = int(y)
            self.pick_start_time = time.time()

            self.read_pbo = self.current_pbo
            self.current_pbo = 1 - self.current_pbo

            glBindBuffer(GL_PIXEL_PACK_BUFFER, 0)
            glBindFramebuffer(GL_READ_FRAMEBUFFER, 0)
            return True
        except Exception as e:
            logger.error(f"pick_async hatası: {e}")
            self.pending_pick = False
            return False

    def check_pick(self):
        if not self.pending_pick:
            return None, None, None

        try:
            pbo = self.pbos[self.read_pbo]
            glBindBuffer(GL_PIXEL_PACK_BUFFER, pbo)
            
            ptr = glMapBuffer(GL_PIXEL_PACK_BUFFER, GL_READ_ONLY)
            if not ptr:
                glBindBuffer(GL_PIXEL_PACK_BUFFER, 0)
                self.pending_pick = False
                return 0, self.pending_x, self.pending_y

            count = self.pick_size * self.pick_size
            array_type = ctypes.c_uint32 * count
            data = ctypes.cast(ptr, ctypes.POINTER(array_type)).contents
            
            ids = np.frombuffer(data, dtype=np.uint32).copy()
            
            glUnmapBuffer(GL_PIXEL_PACK_BUFFER)
            glBindBuffer(GL_PIXEL_PACK_BUFFER, 0)

            valid_mask = ids != 0
            if not np.any(valid_mask):
                best_id = 0
            else:
                valid_ids = ids[valid_mask]
                valid_dist2 = self._dist2[valid_mask]
                min_idx = np.argmin(valid_dist2)
                best_id = int(valid_ids[min_idx])

            self.pending_pick = False
            self.last_pick_id = best_id

            return best_id, self.pending_x, self.pending_y
        except Exception as e:
            logger.error(f"check_pick hatası: {e}")
            self.pending_pick = False
            glBindBuffer(GL_PIXEL_PACK_BUFFER, 0)
            return 0, self.pending_x, self.pending_y

    def pick_rect(self, x0, y0, x1, y1, fbo, viewport_size) -> list[int]:
        """Verilen viewport FBO'sundan dikdörtgen bölgedeki benzersiz ID'leri okur."""
        if self.fbo is None:
            return []
        xa, xb = sorted((int(x0), int(x1)))
        ya, yb = sorted((int(y0), int(y1)))
        w = max(1, xb - xa)
        h = max(1, yb - ya)
        vw, vh = viewport_size
        xa = max(0, min(xa, vw - 1))
        ya = max(0, min(ya, vh - 1))
        w = min(w, vw - xa)
        h = min(h, vh - ya)
        y_gl = vh - ya - h

        glBindFramebuffer(GL_READ_FRAMEBUFFER, fbo)
        glReadBuffer(GL_COLOR_ATTACHMENT1)
        buf = np.zeros((h, w), dtype=np.uint32)
        glReadPixels(xa, y_gl, w, h, GL_RED_INTEGER, GL_UNSIGNED_INT, buf)
        glBindFramebuffer(GL_READ_FRAMEBUFFER, 0)

        unique_ids = np.unique(buf)
        return [int(uid) for uid in unique_ids if uid > 0]

    def cleanup(self):
        try:
            buffers = [self.fbo, self.texture, self.depth_rbo] + self.pbos
            for buf in buffers:
                if buf and glIsBuffer(buf):
                    glDeleteBuffers(1, [buf])
                elif buf and glIsFramebuffer(buf):
                    glDeleteFramebuffers(1, [buf])
                elif buf and glIsRenderbuffer(buf):
                    glDeleteRenderbuffers(1, [buf])
                elif buf and glIsTexture(buf):
                    glDeleteTextures(1, [buf])
            self.fbo = self.texture = self.depth_rbo = None
            self.pbos = [None, None]
        except Exception as e:
            logger.error(f"Cleanup hatası: {e}")