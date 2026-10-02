# test_light.py

from OpenGL.GL import *
import glm
import numpy as np
import sys
import ctypes
from pathlib import Path
import logging
import logging
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from render.shaderprogram import ShaderProgram
from render.lightingsystem import LightingSystem
from render.light_ubo import LightUBO  # YENİ
from core.camera import Camera
from tools.scenebuilder import SceneBuilder
from domain.definition import Section, SectionType, Material, MatType
from domain.element import Section as RenderSection
from geometry.frame_builder import FrameBuilder  # YENİ: FrameBuilder

logging.basicConfig(level=logging.WARNING, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")

# Malzeme ve kesitler
steel = Material("STEEL", MatType.STEEL, E=2.1e8, density=7850)
render_box = RenderSection("B400x15", SectionType.BOX, {"b": 400, "h": 200, "t": 15}, (1, 0, 0))
render_ipe = RenderSection("IPE300", SectionType.I, {"b": 150, "h": 300, "tw": 10, "tf": 14}, (1, 1, 1))
render_l = RenderSection("L100x10", SectionType.L, {"b": 100, "h": 100, "t": 10}, (1, 0, 1))

# Scene oluştur
builder = SceneBuilder()
node1 = builder.create_node(0, 0, 0)
node2 = builder.create_node(1000, 0, 0)
frame1 = builder.create_frame(node1, node2, render_ipe, 45)

# YENİ: FrameBuilder ile geometry oluştur
frame_builder = FrameBuilder()
verts, colors, idxs = frame_builder.build(frame1)  # direkt (verts, colors, idxs)

# logger.debug(f"Vertex count: {len(verts) // 6}")
# logger.debug(f"Index count: {len(idxs)}")
# logger.debug(f"First few indices: {idxs[:12]}")

def main():
    if not glfw.init():
        # logger.debug("GLFW başlatılamadı!")
        return
    
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 4)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 6)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    
    window = glfw.create_window(800, 600, "Işık Testi - UBO", None, None)
    if not window:
        # logger.debug("Pencere oluşturulamadı!")
        glfw.terminate()
        return
    
    glfw.make_context_current(window)
    glfw.swap_interval(1)
    
    # logger.debug(f"OpenGL: {glGetString(GL_VERSION).decode()}")
    
    # ===== SHADER ===== (standard shader kullan)
    shader = ShaderProgram("standard", "d:/program/cad3/src/cad3/render/shaders/standard.vert", 
                                      "d:/program/cad3/src/cad3/render/shaders/standard.frag")
    shader.use()
    
    # ===== LIGHTING ve UBO =====
    lighting = LightingSystem()
    lighting.pos = [
        [2.0, 2.0, 2.0],
        [-2.0, 2.0, 2.0],
        [2.0, -2.0, -2.0],
    ]
    lighting.colors = [
        [1.0, 0.0, 0.0],  # Kırmızı
        [0.0, 1.0, 0.0],  # Yeşil
        [0.0, 0.0, 1.0],  # Mavi
    ]
    lighting.intensities = [1.0, 1.0, 1.0]
    lighting.diffuse = 1.2
    lighting.specular = 0.8
    lighting.shininess = 64.0
    
    # YENİ: LightUBO oluştur
    light_ubo = LightUBO()
    
    # ===== CAMERA =====
    camera = Camera()
    camera.target = glm.vec3(0.5, 0, 0)  # Kirişin ortası (mm cinsinden)
    camera.distance = 2.0
    camera.pitch = 30.0
    camera.yaw = 45.0
    camera.model_size = 1.0  # mm -> m için
    camera._update_position()
    
    # ===== VAO/VBO/EBO =====
    vao = glGenVertexArrays(1)
    vbo = glGenBuffers(1)
    ebo = glGenBuffers(1)
    
    glBindVertexArray(vao)
    
    # VBO - YENİ: verts zaten [x,y,z,nx,ny,nz] formatında
    glBindBuffer(GL_ARRAY_BUFFER, vbo)
    glBufferData(GL_ARRAY_BUFFER, verts.nbytes, verts, GL_STATIC_DRAW)
    
    # Position (location=0)
    glEnableVertexAttribArray(0)
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6*4, ctypes.c_void_p(0))
    
    # Normal (location=1)
    glEnableVertexAttribArray(1)
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6*4, ctypes.c_void_p(12))
    
    # EBO
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, idxs.nbytes, idxs, GL_STATIC_DRAW)
    
    glBindVertexArray(0)
    
    # OpenGL state
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    
    # Ana döngü
    while not glfw.window_should_close(window):
        glfw.poll_events()
        
        # Kamera kontrolü
        if glfw.get_key(window, glfw.KEY_LEFT) == glfw.PRESS:
            camera.yaw -= 1.0
            camera._update_position()
        if glfw.get_key(window, glfw.KEY_RIGHT) == glfw.PRESS:
            camera.yaw += 1.0
            camera._update_position()
        if glfw.get_key(window, glfw.KEY_UP) == glfw.PRESS:
            camera.pitch = min(89.0, camera.pitch + 1.0)
            camera._update_position()
        if glfw.get_key(window, glfw.KEY_DOWN) == glfw.PRESS:
            camera.pitch = max(-89.0, camera.pitch - 1.0)
            camera._update_position()
        if glfw.get_key(window, glfw.KEY_W) == glfw.PRESS:
            camera.distance -= 0.1
            camera._update_position()
        if glfw.get_key(window, glfw.KEY_S) == glfw.PRESS:
            camera.distance += 0.1
            camera._update_position()
        
        # Render
        glClearColor(0.1, 0.1, 0.1, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        shader.use()
        
        # MVP
        view = camera.get_view_matrix()
        proj = camera.get_projection_matrix()
        model = glm.mat4(1.0)
        # model = glm.rotate(model, glfw.get_time(), glm.vec3(0.0, 1.0, 0.0))
        
        # YENİ: normalMatrix hesapla
        normal_matrix = glm.transpose(glm.inverse(glm.mat3(model)))
        
        shader.set_mat4("mvp", proj * view * model)
        shader.set_mat4("model", model)
        shader.set_mat3("normalMatrix", normal_matrix)
        shader.set_int("useVertexColor", 0)
        shader.set_vec3("objectColor", 1.0, 1.0, 1.0)
        shader.set_float("alpha", 1.0)
        
        # YENİ: UBO'yu güncelle (tek sefer)
        light_ubo.update(lighting, (camera.position.x, camera.position.y, camera.position.z))
        
        # Çizim
        glBindVertexArray(vao)
        glDrawElements(GL_TRIANGLES, len(idxs), GL_UNSIGNED_INT, None)
        glBindVertexArray(0)
        
        glfw.swap_buffers(window)
    
    # Temizlik
    glDeleteVertexArrays(1, [vao])
    glDeleteBuffers(1, [vbo])
    glDeleteBuffers(1, [ebo])
    light_ubo.cleanup()
    shader.cleanup()
    glfw.terminate()

if __name__ == "__main__":
    main()