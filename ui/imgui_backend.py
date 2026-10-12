# ui/imgui_backend.py
import glfw
import imgui
from imgui.integrations.glfw import GlfwRenderer
from ui.theme import load_fonts, apply_dark_theme


# ui/imgui_backend.py
class UiBackend:
    def __init__(self, window):
        self.window = window
        self.impl = None
        self.font_info = None
        self._font_ctx = None    # with bloğu için context

    def setup(self):
        imgui.create_context()
        self.impl = GlfwRenderer(self.window)
        from ui.theme import load_fonts, apply_dark_theme
        self.font_info = load_fonts(font_size=16, impl=self.impl)
        apply_dark_theme()

    def begin_frame(self):
        self.impl.process_inputs()
        imgui.new_frame()

        # Font stack'e at
        if self.font_info and self.font_info.get("font"):
            imgui.push_font(self.font_info["font"])

    def end_frame(self):
        # Font stack'ten çıkar
        if self.font_info and self.font_info.get("font"):
            imgui.pop_font()

        imgui.render()
        self.impl.render(imgui.get_draw_data())

    def shutdown(self):
        if self.impl:
            self.impl.shutdown()