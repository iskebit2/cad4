# app/debug_panel.py
from imgui_bundle import imgui


class DebugPanel:
    def __init__(self, engine= None):
        self.engine = engine
        self.visible = False

    def set_context(self, ctx: dict):
        self.engine = ctx.get("engine")
        print("self.engine:", self.engine)

    def open(self):  self.visible = True
    def close(self): self.visible = False
        
    def draw(self):
        if not self.visible:
            return
        if imgui.begin("Debug##dbg", True)[0]:
            eng = self.engine
            if eng is None:
                imgui.text("Engine yok")
                imgui.end()
                return

            imgui.text(f"is_initialized: {self.app.initialized}")
            imgui.separator()

            imgui.text("=== InputManager ===")
            imgui.text(f"handlers: {[type(h).__name__ for h in eng.input._handlers]}")
            imgui.text(f"bindings: {len(eng.input._bindings)}")
            imgui.text(f"fallback: {type(eng.input._fallback).__name__ if eng.input._fallback else 'None'}")
            imgui.text(f"mouse: ({eng.input.state.mouse_pos.x:.0f}, {eng.input.state.mouse_pos.y:.0f})")
            imgui.text(f"delta: ({eng.input.state.mouse_delta.x:.1f}, {eng.input.state.mouse_delta.y:.1f})")
            imgui.text(f"buttons: {dict(eng.input.state.buttons)}")
            imgui.text(f"modifiers: {eng.input.state.modifiers}")
            imgui.text(f"is_shift: {eng.input.is_shift()}")

            imgui.separator()
            imgui.text("=== Handlers ===")
            for h in eng.input._handlers:
                name = type(h).__name__
                active = getattr(h, "is_active", False)
                imgui.text(f"{name}: active={active}")

            imgui.separator()
            imgui.text("=== Tools ===")
            dm = eng.draw_mgr
            pdm = eng.plane_draw_mgr
            imgui.text(f"draw_mgr: active={dm.is_active} mode={dm.mode} points={len(dm.points)}")
            imgui.text(f"plane_mgr: active={pdm.is_active} stage={pdm.stage} mode={pdm.mode}")

            imgui.separator()
            imgui.text("=== Bindings (key→action) ===")
            import glfw
            for (key, mods), action in eng.input._bindings.items():
                key_name = glfw.get_key_name(key, 0) or str(key)
                mod_str = ""
                if mods & glfw.MOD_CONTROL: mod_str += "CTRL+"
                if mods & glfw.MOD_SHIFT: mod_str += "SHIFT+"
                if mods & glfw.MOD_ALT: mod_str += "ALT+"
                fn = getattr(action, "__name__", type(action).__name__)
                imgui.text(f"{mod_str}{key_name} → {fn}")

        imgui.end()