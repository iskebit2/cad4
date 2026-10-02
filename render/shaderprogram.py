# render/shaderprogram.py
from OpenGL.GL import *
import glm
from typing import Dict, Optional, Any
import logging
import numpy as np

logger = logging.getLogger(__name__)

class ShaderProgram:
    def __init__(self, name, vertex_path, fragment_path):
        self.name = name
        self.program = self._create_program(vertex_path, fragment_path)
        self._uniform_cache = {}  # Cache eklendi!
        # self.location_cache = {}
    
    def _read_file(self, path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
        
    def _compile(self, source, shader_type):
        shader = glCreateShader(shader_type)
        glShaderSource(shader, source)
        glCompileShader(shader)

        if not glGetShaderiv(shader, GL_COMPILE_STATUS):
            error = glGetShaderInfoLog(shader).decode()
            raise Exception(f"{self.name} compile error:\n{error}")

        return shader
    
    def _create_program(self, vert_path, frag_path):
        vert_source = self._read_file(vert_path)
        frag_source = self._read_file(frag_path)

        vert_shader = self._compile(vert_source, GL_VERTEX_SHADER)
        frag_shader = self._compile(frag_source, GL_FRAGMENT_SHADER)

        program = glCreateProgram()
        glAttachShader(program, vert_shader)
        glAttachShader(program, frag_shader)
        glLinkProgram(program)

        if not glGetProgramiv(program, GL_LINK_STATUS):
            error = glGetProgramInfoLog(program).decode()
            raise Exception(f"{self.name} link error:\n{error}")

        glDeleteShader(vert_shader)
        glDeleteShader(frag_shader)

        return program
        
    def _compile_shader(self, source, shader_type):
        shader = glCreateShader(shader_type)
        glShaderSource(shader, source)
        glCompileShader(shader)
        
        if not glGetShaderiv(shader, GL_COMPILE_STATUS):
            log = glGetShaderInfoLog(shader).decode()
            logger.error(f"Shader derleme hatası ({self.name}):\n{log}")
            glDeleteShader(shader)
            return None
        
        return shader
    
    def use(self):
        if self.program:
            glUseProgram(self.program)
            # # logger.debug(f"[Shader] Activated: {self.name} (ID: {self.program})")
    
    def set_int(self, name: str, value: int):
        loc = self.get_uniform_location(name)
        if loc != -1:
            glUniform1i(loc, value)
    
    
    def get_uniform_location(self, name: str) -> int:
        """Uniform lokasyonunu cache'leyerek döndür"""
        if name not in self._uniform_cache:
            loc = glGetUniformLocation(self.program, name)
            self._uniform_cache[name] = loc
            if loc == -1:
                logger.debug(f"[{self.name}] Uniform '{name}' not found")
        return self._uniform_cache[name]
    
    # get_loc'u KALDIR veya get_uniform_location'a yönlendir
    def get_loc(self, name: str) -> int:
        return self.get_uniform_location(name)
    
    def set_float(self, name: str, value: float):
        loc = self.get_uniform_location(name)
        if loc != -1:
            glUniform1f(loc, value)
    
    def set_vec3(self, name: str, x: float, y: float, z: float):
        loc = self.get_uniform_location(name)
        if loc != -1:
            glUniform3f(loc, x, y, z)
    
    def set_vec3_list(self, name: str, values):
        loc = self.get_uniform_location(name)
        if loc != -1:
            glUniform3f(loc, values[0], values[1], values[2])

    def set_mat3(self, name: str, mat):  # <-- YENİ METOD
        """3x3 matris gönder (normalMatrix için)"""
        loc = self.get_loc(name)
        if loc != -1:
            if isinstance(mat, glm.mat3):
                glUniformMatrix3fv(loc, 1, GL_FALSE, glm.value_ptr(mat))
            else:
                # numpy array ise
                glUniformMatrix3fv(loc, 1, GL_FALSE, mat.astype(np.float32).ctypes.data)
    
    def set_mat4(self, name: str, matrix):
        loc = self.get_uniform_location(name)
        if loc != -1:
            glUniformMatrix4fv(loc, 1, GL_FALSE, glm.value_ptr(matrix))
    
    def set_int_array(self, name: str, values, count: int):
        loc = self.get_uniform_location(name)
        if loc != -1:
            glUniform1iv(loc, count, values)
    
    def set_float_array(self, name: str, values, count: int):
        loc = self.get_uniform_location(name)
        if loc != -1:
            glUniform1fv(loc, count, values)
    
    def set_vec3_array(self, name: str, values, count: int):
        """Vec3 array gönder"""
        for i in range(count):
            elem_loc = glGetUniformLocation(self.program, f"{name}[{i}]")
            if elem_loc != -1:
                glUniform3f(elem_loc, values[i][0], values[i][1], values[i][2])
    
    def cleanup(self):
        try:
            if self.program != 0 and glIsProgram(self.program):
                glDeleteProgram(self.program)
                # logger.debug(f"[{self.name}] Shader temizlendi")
        except Exception as e:
            logger.debug(f"[{self.name}] Cleanup hatası: {e}")
        finally:
            self.program = 0
            self._uniform_cache.clear()