# render/snapsquare.py - Güncellenmiş SnapSquareRenderer

from OpenGL.GL import *
from OpenGL.GL.shaders import compileProgram, compileShader

import numpy as np
import logging
logger = logging.getLogger(__name__)

class SnapSquareRenderer:
    def __init__(self):
        self.shader = None
        self.u_color_loc = -1
        self._init_shader()
        
        # Bufferlar
        self.vao = None
        self.vbo = None
        
        # Snap square özellikleri
        self.base_size = 0.02  # Temel boyut
        self.hover_size_multiplier = {
            'node': 1.5,    # Node üzerinde %50 daha büyük
            'frame': 1.2,   # Frame üzerinde %20 daha büyük
            'area': 1.0,    # Area üzerinde normal boyut
            'link': 1.0,    # Link üzerinde normal boyut
            None: 1.0       # Hiçbir şey yoksa normal boyut
        }
        
        # Renkler
        self.colors = {
            -1: (0.5, 0.5, 0.5, 0.8),     # Gri (hiçbir şey yok)
            0: (0.0, 0.0, 1.0, 0.9),      # Mavi (area/link)
            1: (1.0, 0.0, 0.0, 0.9),      # Kırmızı (frame)
            2: (1.0, 1.0, 0.0, 1.0)       # Sarı (node) - daha opak
        }
        
        # Mevcut hover durumu
        self.current_priority = -1
        self.current_element_type = None

    def _init_shader(self):
        vertex_src = """
        #version 330 core
        layout(location = 0) in vec2 aPos;
        void main() { gl_Position = vec4(aPos, 0.0, 1.0); }
        """
        frag_src = """
        #version 330 core
        uniform vec4 uColor;  // vec4 oldu (alpha ile)
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
        
        logger.debug(f"SnapSquare uColor Loc: {self.u_color_loc}")
    
    def set_hover_type(self, priority, element_type=None):
        """
        Hover durumunu güncelle - priority ve element tipine göre snap square değişir
        
        Args:
            priority: -1 (yok), 0 (area/link), 1 (frame), 2 (node)
            element_type: 'node', 'frame', 'area', 'link' veya None
        """
        self.current_priority = priority
        self.current_element_type = element_type
        logger.debug(f"SnapSquare hover set: priority={priority}, type={element_type}")
    
    def get_current_size(self):
        """Mevcut hover durumuna göre snap square boyutunu hesapla"""
        multiplier = self.hover_size_multiplier.get(self.current_element_type, 1.0)
        return self.base_size * multiplier
    
    def get_current_color(self):
        """Mevcut hover durumuna göre snap square rengini al"""
        return self.colors.get(self.current_priority, self.colors[-1])
    
    def draw(self, win, mouse_x, mouse_y, hover_id=0, hover_type=None, w=None, h=None):
        # 1. Eğer genişlik/yükseklik dışarıdan verilmediyse win nesnesinden almayı dene
        if w is None or h is None:
            if win is not None and hasattr(win, "w") and hasattr(win, "h"):
                # Qt Widget nesnesinden boyut alma
                w, h = win.w, win.h
            elif win is not None and hasattr(win, "width") and hasattr(win, "height"):
                w, h = win.width(), win.height()
            else:
                # Yedek varsayılan boyut (Çökmeyi önler)
                w, h = 1200, 800
        """
        Snap square'i çiz
        
        """
        self.current_priority=-1

        if not self.shader: return
        
        if hover_id > 0 and hover_type:
            # Hover var ve tipi biliniyor
            if hover_type == 'node':
                self.current_priority=2      # Sarı
            elif hover_type == 'frame':
                self.current_priority=1      # Kırmızı
            elif hover_type in ['area', 'link']:
                self.current_priority=0      # Mavi
            else:
                self.current_priority=-1      # Gri
        else:
            self.current_priority=-1          # Gri
        
        # Lazy Initialization
        if self.vao is None:
            self.vao = glGenVertexArrays(1)
            self.vbo = glGenBuffers(1)

        

        # Mevcut hover durumuna göre renk ve boyut
        color = self.get_current_color()
        size = self.get_current_size()
        
        r, g, b, a = color
        nx, ny = (mouse_x / w) * 2 - 1, 1 - (mouse_y / h) * 2
        asp = w/h
        
        # Kare boyutunu aspect ratio'ya göre ayarla
        square_w = size
        square_h = size * asp  # Yatayda daha büyük görünmemesi için
        
        # Vertex'leri oluştur
        vertices = np.array([
            # Crosshair (yatay çizgi)
            nx - size*2, ny, nx + size*2, ny,
            # Crosshair (dikey çizgi)
            nx, ny - size*2*asp, nx, ny + size*2*asp,
            # Square (hover durumuna göre boyut değişir)
            nx - square_w/2, ny - square_h/2,
            nx + square_w/2, ny - square_h/2,
            nx + square_w/2, ny + square_h/2,
            nx - square_w/2, ny + square_h/2
        ], dtype=np.float32)

        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        
        glUseProgram(self.shader)
        
        # Veriyi gönder
        glBindVertexArray(self.vao)
        glBindBuffer(GL_ARRAY_BUFFER, self.vbo)
        glBufferData(GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL_STREAM_DRAW)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, None)
        glEnableVertexAttribArray(0)

        # CROSSHAIR (her zaman gri, yarı saydam)
        glUniform4f(self.u_color_loc, 0.3, 0.3, 0.3, 0.6)
        glDrawArrays(GL_LINES, 0, 4)

        # SQUARE (hover durumuna göre renkli)
        glUniform4f(self.u_color_loc, r, g, b, a)
        glDrawArrays(GL_LINE_LOOP, 4, 4)

        glUseProgram(0)
        glBindVertexArray(0)
        
        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)
    
    def cleanup(self):
        """Kaynakları temizle"""
        try:
            if self.shader is not None and glIsProgram(self.shader):
                glDeleteProgram(self.shader)
                self.shader = None
                logger.debug("Shader silindi")
            
            if self.vao is not None and glIsVertexArray(self.vao):
                glDeleteVertexArrays(1, [self.vao])
                self.vao = None
                logger.debug("VAO silindi")
            
            if self.vbo is not None and glIsBuffer(self.vbo):
                glDeleteBuffers(1, [self.vbo])
                self.vbo = None
                logger.debug("VBO silindi")
        except Exception as e:
            logger.debug(f"Cleanup hatası: {e}")