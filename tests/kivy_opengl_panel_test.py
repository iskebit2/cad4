"""Minimal Kivy + PyOpenGL viewport/panel diagnostic.

Run: python kivy_opengl_panel_test.py
Requirements: pip install kivy PyOpenGL

This is a desktop OpenGL 3.3 test first. Android may require GLES-compatible
shaders and a PyOpenGL build that matches Kivy's EGL/OpenGL ES context.
"""
import ctypes
import logging
import time

from kivy.app import App
from kivy.core.window import Window
from kivy.graphics import Callback, Color, RoundedRectangle
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from OpenGL.GL import *

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gl_panel_test")

VERTEX = """#version 330 core
layout(location=0) in vec3 aPos;
layout(location=1) in vec3 aColor;
out vec3 vColor;
void main() { gl_Position = vec4(aPos, 1.0); vColor = aColor; }
"""
FRAGMENT = """#version 330 core
in vec3 vColor;
out vec4 FragColor;
void main() { FragColor = vec4(vColor, 1.0); }
"""


def make_shader(kind, source):
    shader = glCreateShader(kind)
    glShaderSource(shader, source)
    glCompileShader(shader)
    if not glGetShaderiv(shader, GL_COMPILE_STATUS):
        message = glGetShaderInfoLog(shader)
        raise RuntimeError(f"Shader compilation failed: {message!r}")
    return shader


class GLViewport(Widget):
    """Raw OpenGL drawing confined to this widget's rectangle."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ready = False
        self.program = self.vao = self.vbo = None
        self.last_log = 0.0
        # reset_context tells Kivy to restore its expected GL state after callback.
        with self.canvas.after:
            Callback(self.draw_gl, reset_context=True)

    def init_gl(self):
        if self.ready:
            return

        vs = make_shader(GL_VERTEX_SHADER, VERTEX)
        fs = make_shader(GL_FRAGMENT_SHADER, FRAGMENT)
        program = glCreateProgram()
        glAttachShader(program, vs)
        glAttachShader(program, fs)
        glLinkProgram(program)
        if not glGetProgramiv(program, GL_LINK_STATUS):
            raise RuntimeError(f"Program link failed: {glGetProgramInfoLog(program)!r}")
        glDeleteShader(vs)
        glDeleteShader(fs)

        # Each vertex: xyz position, rgb color.
        vertices = (GLfloat * 18)(
            -0.72, -0.58, 0.0,  1.0, 0.20, 0.18,
             0.72, -0.58, 0.0,  0.20, 0.90, 0.35,
             0.00,  0.72, 0.0,  0.20, 0.50, 1.00,
        )
        vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, ctypes.sizeof(vertices), vertices, GL_STATIC_DRAW)
        stride = 6 * ctypes.sizeof(GLfloat)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(3 * ctypes.sizeof(GLfloat)))
        glBindVertexArray(0)
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glUseProgram(0)

        self.program, self.vao, self.vbo = program, vao, vbo
        self.ready = True
        log.info("GL resources initialized once (program=%s, vao=%s, vbo=%s)", program, vao, vbo)

    def draw_gl(self, *_):
        if self.width < 2 or self.height < 2:
            return
        try:
            if not self.ready:
                self.init_gl()

            # Kivy widget coordinates and OpenGL viewport both use bottom-left origin.
            x, y = int(self.x), int(self.y)
            w, h = max(1, int(self.width)), max(1, int(self.height))
            glEnable(GL_SCISSOR_TEST)
            glScissor(x, y, w, h)
            glViewport(x, y, w, h)
            glClearColor(0.055, 0.075, 0.11, 1.0)
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            glDisable(GL_DEPTH_TEST)
            glUseProgram(self.program)
            glBindVertexArray(self.vao)
            glDrawArrays(GL_TRIANGLES, 0, 3)

            # Restore the states this demo changed. Kivy's callback reset is an
            # additional safeguard, not a substitute for correct FBO handling.
            glBindVertexArray(0)
            glUseProgram(0)
            glDisable(GL_SCISSOR_TEST)

            now = time.time()
            if now - self.last_log > 5:
                log.info("Draw callback running; GL resources are being reused.")
                self.last_log = now
        except Exception:
            log.exception("OpenGL drawing failed")
            # Prevent repeating a failing initialization every frame.
            self.ready = True


class DemoRoot(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.add_widget(GLViewport())

        toolbar = BoxLayout(
            orientation="horizontal", size_hint=(None, None), size=(380, 48),
            pos_hint={"x": 0.02, "top": 0.98}, spacing=6, padding=4,
        )
        self.toggle_btn = Button(text="Paneli Kapat")
        self.toggle_btn.bind(on_release=self.toggle_panel)
        toolbar.add_widget(self.toggle_btn)
        toolbar.add_widget(Label(text="Kivy + PyOpenGL", size_hint_x=None, width=170))
        self.add_widget(toolbar)

        self.panel = BoxLayout(
            orientation="vertical", size_hint=(None, None), size=(280, 240),
            pos_hint={"right": 0.98, "top": 0.84}, padding=10, spacing=8,
        )
        with self.panel.canvas.before:
            Color(0.13, 0.16, 0.22, 0.98)
            self.panel_bg = RoundedRectangle(pos=self.panel.pos, size=self.panel.size, radius=[10])
        self.panel.bind(pos=self._sync_panel_bg, size=self._sync_panel_bg)
        self.panel.add_widget(Label(text="Normal Kivy Paneli", size_hint_y=None, height=36))
        self.panel.add_widget(Label(
            text="Paneli açıp kapatın. Eski görüntü kalıyor mu gözlemleyin.",
            halign="left", valign="middle", size_hint_y=None, height=48,
        ))
        self.panel.add_widget(TextInput(
            hint_text="Buraya yazmayı deneyin", multiline=False, size_hint_y=None, height=42
        ))
        self.panel.add_widget(Button(text="Kapat", size_hint_y=None, height=42,
                                     on_release=self.toggle_panel))
        self.add_widget(self.panel)
        self.panel_open = True

    def _sync_panel_bg(self, widget, _value):
        self.panel_bg.pos = widget.pos
        self.panel_bg.size = widget.size

    def toggle_panel(self, *_):
        self.panel_open = not self.panel_open
        self.panel.opacity = 1 if self.panel_open else 0
        self.panel.disabled = not self.panel_open
        self.toggle_btn.text = "Paneli Kapat" if self.panel_open else "Paneli Aç"


class GLPanelTestApp(App):
    def build(self):
        Window.size = (1100, 720)
        Window.clearcolor = (0.055, 0.075, 0.11, 1.0)
        return DemoRoot()


if __name__ == "__main__":
    GLPanelTestApp().run()
