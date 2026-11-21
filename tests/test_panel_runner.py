
import glfw
from imgui_bundle import imgui
from imgui_bundle.python_backends.glfw_backend import GlfwRenderer

from queue import Queue
from core.input_manager import InputManager
from domain.project import Project
from assets.themes import _load_fonts, _apply_dark_theme

class MockObject:
    """Eksik özelliklerde güvenli varsayılanlar döndürür."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __getattr__(self, name):
        return None


class MockEngine(MockObject):
    def __init__(self):
        super().__init__(
            input=MockObject(),
            show={},
            renderer=None,
            math_model=None,
        )
        self.input = InputManager()


class MockUI(MockObject):
    def __init__(self):
        super().__init__(
            command_queue=Queue(),
            on_panel_applied=lambda panel: None,
        )


class MockApp(MockObject):
    def __init__(self):
        super().__init__(
            current_project=None,
            ui=MockUI(),
            engine=MockEngine(),
        )
        self.current_project = Project()

import ui.panels as panels_package
from ui.helpers.registry import discover_panels


# --------------------------------------------------
# Mock App
# --------------------------------------------------

app = MockApp()


# --------------------------------------------------
# Panel discovery
# --------------------------------------------------

specs = discover_panels(panels_package)
specs.sort(key=lambda s: s.name)


# --------------------------------------------------
# GLFW / ImGui
# --------------------------------------------------

if not glfw.init():
    raise RuntimeError("GLFW başlatılamadı")

window = glfw.create_window(1100, 750, "CAD4 Panel Tester", None, None)

if not window:
    glfw.terminate()
    raise RuntimeError("GLFW window oluşturulamadı")

glfw.make_context_current(window)
glfw.swap_interval(1)

imgui.create_context()
io = imgui.get_io()
io.config_flags |= imgui.ConfigFlags_.docking_enable
io.config_windows_move_from_title_bar_only = True

impl = GlfwRenderer(window)
_load_fonts()
_apply_dark_theme()


# --------------------------------------------------
# Panel
# --------------------------------------------------

active_panel = None
active_spec = None


def select_panel(spec):
    global active_panel, active_spec

    if active_panel is not None:
        active_panel.close()

    active_spec = spec
    active_panel = spec.cls(app=app)
    active_panel.open()

for spec in specs:
    print(spec)

print(spec.__dict__)
# --------------------------------------------------
# Main loop
# --------------------------------------------------

while not glfw.window_should_close(window):

    glfw.poll_events()
    impl.process_inputs()

    imgui.new_frame()

    # Panel seçici
    imgui.set_next_window_size(
        imgui.ImVec2(230, 700),
        imgui.Cond_.first_use_ever
    )

    imgui.begin("Panel List")

    for spec in specs:
        selected = active_spec == spec
        
        if imgui.selectable(
            f"{spec.title}##{spec.name}",
            selected
        )[0]:
            select_panel(spec)

    imgui.end()

    # Aktif panel
    if active_panel is not None:
        active_panel.draw()

    imgui.render()

    width, height = glfw.get_framebuffer_size(window)

    from OpenGL.GL import (
        glViewport,
        glClearColor,
        glClear,
        GL_COLOR_BUFFER_BIT,
    )

    glViewport(0, 0, width, height)
    glClearColor(0.12, 0.13, 0.15, 1.0)
    glClear(GL_COLOR_BUFFER_BIT)

    impl.render(imgui.get_draw_data())

    glfw.swap_buffers(window)


# --------------------------------------------------
# Cleanup
# --------------------------------------------------

if active_panel is not None:
    active_panel.close()

impl.shutdown()
imgui.destroy_context()
glfw.terminate()
