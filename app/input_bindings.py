# app/input_bindings.py
import glfw


def build_bindings(app):
    eng = lambda: app.engine
    return {
        glfw.KEY_F2: app._toggle_2d,
        glfw.KEY_F3: lambda: eng().renderer.toggle_render_mode(),
        glfw.KEY_F4: app.actions.show_entire_model,
        glfw.KEY_F5: lambda: eng().zoom_extents(),
        glfw.KEY_DELETE: lambda: eng().sel_mgr.delete_selected(),
        glfw.KEY_D: lambda: app.actions.toggle_draw(None),
        glfw.KEY_L: app.actions.toggle_loads,
        glfw.KEY_F12: app.actions.set_app,
        
        (glfw.KEY_W, glfw.MOD_SHIFT): app.actions.toggle_plane,
        (glfw.KEY_Z, glfw.MOD_CONTROL): lambda: eng().sel_mgr.undo(),
        (glfw.KEY_Y, glfw.MOD_CONTROL): lambda: eng().sel_mgr.redo(),
        (glfw.KEY_S, glfw.MOD_CONTROL): app.actions.quick_save,
        (glfw.KEY_S, glfw.MOD_CONTROL | glfw.MOD_SHIFT): app.actions.save_as_dialog,
        (glfw.KEY_O, glfw.MOD_CONTROL): app.actions.open_dialog,
        (glfw.KEY_E, glfw.MOD_CONTROL): app.actions.s2k_export,
        (glfw.KEY_J, glfw.MOD_CONTROL): app.actions.toggle_show_only,
        (glfw.KEY_H, glfw.MOD_CONTROL): app.actions.toggle_hide_selected,
    }