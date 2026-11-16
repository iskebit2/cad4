# app/input_bindings.py
import glfw


def build_bindings(app):
    """GLFW event → CadApp metodu eşlemesi.

    Not: Tüm handler'lar artık doğrudan CadApp üzerinde.
    AppActions sınıfı silindi (CadApp + UIHost'a bölündü).
    """
    def eng():
        return app.engine

    return {
        # --- Kamera / projeksiyon ---
        glfw.KEY_F2: app.toggle_2d,
        glfw.KEY_F3: lambda: eng().renderer.toggle_render_mode(),
        glfw.KEY_F4: app.show_entire_model,
        glfw.KEY_F5: lambda: eng().zoom_extents(),

        # --- Seçim ---
        glfw.KEY_DELETE: lambda: eng().sel_mgr.delete_selected,

        # --- Çizim ---
        glfw.KEY_D: lambda: (app.ui.toggle_draw(None) if app.ui else None),

        # --- Yük görünürlüğü ---
        glfw.KEY_L: lambda: app.set_loads_visible(not app.get_loads_visible()),

        # --- Plane ---
        (glfw.KEY_W, glfw.MOD_SHIFT): lambda: (app.ui.toggle_plane() if app.ui else None),

        # --- Undo / Redo ---
        (glfw.KEY_Z, glfw.MOD_CONTROL): lambda: eng().sel_mgr.undo(),
        (glfw.KEY_Y, glfw.MOD_CONTROL): lambda: eng().sel_mgr.redo(),
    }