# render/pickpass.py
import numpy as np
import glm
from OpenGL.GL import *
import ctypes
from logging_config import CadLogger
import time
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
        self.main_fbo = None  # Ana FBO (MRT'li)
        self.viewport_width = 0
        self.viewport_height = 0
        
        # Element map
        self.elements = {}
        self.renderers = {}
        
        # Timeout mekanizması
        self.pick_start_time = 0
        self.pick_timeout = 0.5  # 500ms timeout
        
        # 1x1 FBO oluştur (yedek, asıl picking MRT'den)
        self._create_resources()
        
        # logger.debug("PickPass başlatıldı - MRT picking modu")
    
    def _create_resources(self):
        """1x1 FBO ve PBO'ları oluştur (yedek)"""
        try:
            # FBO
            self.fbo = glGenFramebuffers(1)
            glBindFramebuffer(GL_FRAMEBUFFER, self.fbo)
            
            # 1x1 Color texture (unsigned int)
            self.texture = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self.texture)
            glTexImage2D(
                GL_TEXTURE_2D, 0, GL_R32UI, 
                1, 1, 0, 
                GL_RED_INTEGER, GL_UNSIGNED_INT, None
            )
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glFramebufferTexture2D(
                GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, 
                GL_TEXTURE_2D, self.texture, 0
            )
            
            # 1x1 Depth buffer
            self.depth_rbo = glGenRenderbuffers(1)
            glBindRenderbuffer(GL_RENDERBUFFER, self.depth_rbo)
            glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, 1, 1)
            glFramebufferRenderbuffer(
                GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
                GL_RENDERBUFFER, self.depth_rbo
            )
            
            # FBO kontrolü
            status = glCheckFramebufferStatus(GL_FRAMEBUFFER)
            if status != GL_FRAMEBUFFER_COMPLETE:
                raise RuntimeError(f"FBO tamamlanamadı: {status}")
            
            # İki PBO oluştur
            for i in range(2):
                self.pbos[i] = glGenBuffers(1)
                glBindBuffer(GL_PIXEL_PACK_BUFFER, self.pbos[i])
                glBufferData(GL_PIXEL_PACK_BUFFER, 4, None, GL_STREAM_READ)
            
            glBindBuffer(GL_PIXEL_PACK_BUFFER, 0)
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
            
        except Exception as e:
            logger.error(f"PickPass kaynak oluşturma hatası: {e}")
            raise
    
    def set_main_fbo(self, fbo):
        """Ana MRT FBO'sunu set et"""
        self.main_fbo = fbo
    
    def register(self, pick_id, element, renderer):
        """Tek bir elementi kaydet"""
        if pick_id > 0:
            self.elements[pick_id] = element
            self.renderers[pick_id] = renderer
    
    def unregister(self, pick_id):
        """Elementi kayıttan çıkar"""
        self.elements.pop(pick_id, None)
        self.renderers.pop(pick_id, None)

    def clear_registry(self):
        """Tüm kayıtlı element/renderer eşlemelerini temizle."""
        self.elements.clear()
        self.renderers.clear()
    
    def get_element(self, pick_id):
        """Pick ID'den elementi bul"""
        return self.elements.get(pick_id)
    
    def get_renderer(self, pick_id):
        """Pick ID'den renderer'ı bul"""
        return self.renderers.get(pick_id)
    
    def set_viewport(self, width, height):
        """Viewport boyutunu güncelle"""
        self.viewport_width = width
        self.viewport_height = height

    def pick_async(self, x, y):
        """
        MRT ile halihazırda çizilmiş olan ID buffer'dan asenkron okuma başlatır.
        """
        
        # 1. Bekleyen pick varsa timeout kontrolü
        if self.pending_pick:
            if time.time() - self.pick_start_time > self.pick_timeout:
                self.pending_pick = False
                # logger.debug("Pick timeout - sıfırlandı")
            else:
                return False

        # 2. Koordinat kontrolü
        if x < 0 or x >= self.viewport_width or y < 0 or y >= self.viewport_height:
            self.last_pick_id = 0
            return True

        try:
            # 3. ANA FBO'yu bağla (MRT FBO)
            if self.main_fbo:
                glBindFramebuffer(GL_READ_FRAMEBUFFER, self.main_fbo)
                glReadBuffer(GL_COLOR_ATTACHMENT1)
            else:
                # Main FBO yoksa varsayılan framebuffer'ı kullan
                glBindFramebuffer(GL_READ_FRAMEBUFFER, 0)
                glReadBuffer(GL_FRONT) # Default FB için
            
            # 4. Okuma yapılacak buffer'ı seç (location = 1 olan ID buffer)
            #glReadBuffer(GL_COLOR_ATTACHMENT1)
            
            # 5. PBO'ya yazma emri ver
            glBindBuffer(GL_PIXEL_PACK_BUFFER, self.pbos[self.current_pbo])
            
            # OpenGL'de Y koordinatı aşağıdan yukarı
            opengl_y = self.viewport_height - y - 1
            
            glPixelStorei(GL_PACK_ALIGNMENT, 1)
            
            # 1 piksellik uint ID verisini oku
            glReadPixels(int(x), int(opengl_y), 1, 1, 
                        GL_RED_INTEGER, GL_UNSIGNED_INT, 0)
            
            # 6. Durum yönetimi
            self.pending_pick = True
            self.pending_x = x
            self.pending_y = y
            self.pick_start_time = time.time()
            self.read_pbo = self.current_pbo
            self.current_pbo = 1 - self.current_pbo  # Ping-pong

            # 7. Temizlik
            glBindBuffer(GL_PIXEL_PACK_BUFFER, 0)
            glBindFramebuffer(GL_READ_FRAMEBUFFER, 0)
            
            return True

        except Exception as e:
            logger.error(f"pick_async (MRT) hatası: {e}")
            self.pending_pick = False
            return False

    def check_pick(self):
        """Pick sonucunu kontrol et - 0 döndürebilir!"""
        if not self.pending_pick:
            return None, None, None

        try:
            read_pbo = self.pbos[self.read_pbo]
            glBindBuffer(GL_PIXEL_PACK_BUFFER, read_pbo)
            
            ptr = glMapBuffer(GL_PIXEL_PACK_BUFFER, GL_READ_ONLY)
            if ptr:
                char_ptr = ctypes.cast(ptr, ctypes.POINTER(ctypes.c_uint32))
                pick_id = int(char_ptr[0])
                glUnmapBuffer(GL_PIXEL_PACK_BUFFER)
            else:
                pick_id = 0
                
            glBindBuffer(GL_PIXEL_PACK_BUFFER, 0)

            self.pending_pick = False
            self.last_pick_id = pick_id
            
            # 0 döndürebiliriz - bu boşluk demek
            return pick_id, self.pending_x, self.pending_y

        except Exception as e:
            logger.error(f"check_pick hatası: {e}")
            self.pending_pick = False
            glBindBuffer(GL_PIXEL_PACK_BUFFER, 0)
            return None, None, None
    
    def cleanup(self):
        """Kaynakları temizle"""
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
            logger.debug(f"Cleanup hatası: {e}")