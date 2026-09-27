#render/gizmo.py
import OpenGL.GL as gl
import glm
import numpy as np
import ctypes
import logging
logger = logging.getLogger(__name__)

class GizmoAxes:
    """OpenGL 3.3 için VAO kullanan Gizmo eksen çizici"""
    def __init__(self, camera=None):
        self.camera = camera
        self.gizmo_size = 80
        self.shader = None
        self.VAO = None
        self.VBO = None
        
        # Eksen verileri: [x, y, z, r, g, b]
        vertices = np.array([
            # X ekseni (kırmızı)
            0.0, 0.0, 0.0,  1.0, 0.0, 0.0,
            1.0, 0.0, 0.0,  1.0, 0.0, 0.0,
            
            # Y ekseni (yeşil)
            0.0, 0.0, 0.0,  0.0, 1.0, 0.0,
            0.0, 1.0, 0.0,  0.0, 1.0, 0.0,
            
            # Z ekseni (mavi)
            0.0, 0.0, 0.0,  0.0, 0.0, 1.0,
            0.0, 0.0, 1.0,  0.0, 0.0, 1.0,
        ], dtype=np.float32)
        
        try:
            # VAO ve VBO oluştur
            self.VAO = gl.glGenVertexArrays(1)
            self.VBO = gl.glGenBuffers(1)
            
            # VAO'yu bağla
            gl.glBindVertexArray(self.VAO)
            
            # VBO'yu bağla ve veriyi yükle
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self.VBO)
            gl.glBufferData(gl.GL_ARRAY_BUFFER, vertices.nbytes, vertices, gl.GL_STATIC_DRAW)
            
            # Vertex attribute'larını ayarla
            # Position (location = 0)
            gl.glEnableVertexAttribArray(0)
            gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, 
                                    6 * ctypes.sizeof(ctypes.c_float), 
                                    ctypes.c_void_p(0))
            
            # Color (location = 1)
            gl.glEnableVertexAttribArray(1)
            gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, 
                                    6 * ctypes.sizeof(ctypes.c_float), 
                                    ctypes.c_void_p(3 * ctypes.sizeof(ctypes.c_float)))
            
            # Bağlamaları serbest bırak
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
            gl.glBindVertexArray(0)
            
            # Shader oluştur
            self.shader = self.create_simple_shader()
            if self.shader is None:
                logger.debug("✗ Shader oluşturulamadı!")
                return
                
            logger.debug(f"✓ GizmoAxes initialized (OpenGL 3.3), Shader ID: {self.shader}, VAO: {self.VAO}")
            
        except Exception as e:
            logger.debug(f"✗ GizmoAxes initialization failed: {e}")
            import traceback
            traceback.logger.debug_exc()

    def create_simple_shader(self):
        """Çok basit bir shader oluştur"""
        vertex_shader = """
        #version 330 core
        layout(location = 0) in vec3 position;
        layout(location = 1) in vec3 color;
        
        out vec3 fragColor;
        uniform mat4 mvp;
        
        void main() {
            gl_Position = mvp * vec4(position, 1.0);
            fragColor = color;
        }
        """
        
        fragment_shader = """
        #version 330 core
        in vec3 fragColor;
        out vec4 outColor;
        
        void main() {
            outColor = vec4(fragColor, 1.0);
        }
        """
        
        try:
            # Vertex shader
            vs = gl.glCreateShader(gl.GL_VERTEX_SHADER)
            gl.glShaderSource(vs, vertex_shader)
            gl.glCompileShader(vs)
            
            # Derleme kontrolü
            if not gl.glGetShaderiv(vs, gl.GL_COMPILE_STATUS):
                error = gl.glGetShaderInfoLog(vs).decode()
                logger.debug(f"Vertex Shader Compile Error:\n{error}")
                gl.glDeleteShader(vs)
                return None
            
            # Fragment shader
            fs = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
            gl.glShaderSource(fs, fragment_shader)
            gl.glCompileShader(fs)
            
            # Derleme kontrolü
            if not gl.glGetShaderiv(fs, gl.GL_COMPILE_STATUS):
                error = gl.glGetShaderInfoLog(fs).decode()
                logger.debug(f"Fragment Shader Compile Error:\n{error}")
                gl.glDeleteShader(vs)
                gl.glDeleteShader(fs)
                return None
            
            # Program
            program = gl.glCreateProgram()
            gl.glAttachShader(program, vs)
            gl.glAttachShader(program, fs)
            gl.glLinkProgram(program)
            
            # Link kontrolü
            if not gl.glGetProgramiv(program, gl.GL_LINK_STATUS):
                error = gl.glGetProgramInfoLog(program).decode()
                logger.debug(f"Shader Program Link Error:\n{error}")
                gl.glDeleteShader(vs)
                gl.glDeleteShader(fs)
                gl.glDeleteProgram(program)
                return None
            
            # Temizlik
            gl.glDeleteShader(vs)
            gl.glDeleteShader(fs)
            
            return program
            
        except Exception as e:
            logger.debug(f"Shader creation error: {e}")
            return None

    def render(self):
        """Gizmo'yu ekranın sol alt köşesine çiz (GLM uyumlu)"""
        try:
            if not self.camera: return
            
            # Mevcut viewport'u yedekle
            old_viewport = gl.glGetIntegerv(gl.GL_VIEWPORT)
            
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glLineWidth(2.0) # Eksenler biraz daha belirgin olsun
            
            # Sol alt köseye küçük bir kare aç
            gl.glViewport(10, 10, self.gizmo_size, self.gizmo_size)
            
            # 1. Projeksiyon: Ortografik (Eksenlerin boyu uzaklığa göre değişmesin)
            projection = glm.ortho(-1.5, 1.5, -1.5, 1.5, -1.0, 1.0)
            
            # 2. View: Kameranın bakış rotasyonunu al
            # Önemli: Translation (konum) verisini sıfırlıyoruz, sadece dönme lazım
            view_mat = self.camera.get_view_matrix()
            view_rotation = glm.mat4(glm.mat3(view_mat)) # Sadece rotasyonu al, transpose etme!
            
            # 3. Model: Eksenleri biraz küçültelim ki kutuya sığsın
            model = glm.scale(glm.mat4(1.0), glm.vec3(0.8))
            
            # 4. MVP birleştirme
            mvp = projection * view_rotation * model
            
            gl.glUseProgram(self.shader)
            
            # MVP'yi Shader'a gönder (glm.value_ptr ile)
            mvp_loc = gl.glGetUniformLocation(self.shader, "mvp")
            gl.glUniformMatrix4fv(mvp_loc, 1, gl.GL_FALSE, glm.value_ptr(mvp))
            
            gl.glBindVertexArray(self.VAO)
            gl.glDrawArrays(gl.GL_LINES, 0, 6)
            gl.glBindVertexArray(0)
            
            # Her şeyi eski haline getir
            gl.glViewport(*old_viewport)
            gl.glEnable(gl.GL_DEPTH_TEST)
            
        except Exception as e:
            logger.debug(f"Gizmo render hatası: {e}")

    def cleanup(self):
        """Kaynakları temizle"""
        try:
            if self.VAO is not None:
                gl.glDeleteVertexArrays(1, [self.VAO])
                self.VAO = None
                
            if self.VBO is not None:
                gl.glDeleteBuffers(1, [self.VBO])
                self.VBO = None
                
            if self.shader is not None:
                gl.glDeleteProgram(self.shader)
                self.shader = None
                
            logger.debug("✓ GizmoAxes cleaned up")
                
        except Exception as e:
            logger.debug(f"Gizmo cleanup error: {e}")