# app/ui_capture.py
"""
ImGui / GLFW bağımlı küçük yardımcılar.

InputManager buraya bağımlı OLMAMALI; bu modül üst katman
(cad_app) tarafından import edilir.
"""


def mouse_over_ui() -> bool:
    """ImGui fareyi yakalıyor mu?"""
    try:
        import imgui
        return bool(imgui.get_io().want_capture_mouse)
    except Exception:
        return False


def keyboard_captured_by_ui() -> bool:
    """ImGui klavyeyi yakalıyor mu?"""
    try:
        import imgui
        return bool(imgui.get_io().want_capture_keyboard)
    except Exception:
        return False


def sync_modifiers_from_glfw(window) -> dict:
    """GLFW penceresinden anlık modifier durumunu dict olarak döndürür."""
    try:
        import glfw
    except Exception:
        return {"shift": False, "ctrl": False, "alt": False}

    mods = 0
    if (glfw.get_key(window, glfw.KEY_LEFT_SHIFT) == glfw.PRESS or
            glfw.get_key(window, glfw.KEY_RIGHT_SHIFT) == glfw.PRESS):
        mods |= glfw.MOD_SHIFT
    if (glfw.get_key(window, glfw.KEY_LEFT_CONTROL) == glfw.PRESS or
            glfw.get_key(window, glfw.KEY_RIGHT_CONTROL) == glfw.PRESS):
        mods |= glfw.MOD_CONTROL
    if (glfw.get_key(window, glfw.KEY_LEFT_ALT) == glfw.PRESS or
            glfw.get_key(window, glfw.KEY_RIGHT_ALT) == glfw.PRESS):
        mods |= glfw.MOD_ALT

    return {
        "shift": bool(mods & glfw.MOD_SHIFT),
        "ctrl":  bool(mods & glfw.MOD_CONTROL),
        "alt":   bool(mods & glfw.MOD_ALT),
    }


def mods_to_dict(glfw_mods: int) -> dict:
    """GLFW event callback'inden gelen mods bitfield'ini dict'e çevir."""
    try:
        import glfw
    except Exception:
        return {"shift": False, "ctrl": False, "alt": False}

    return {
        "shift": bool(glfw_mods & glfw.MOD_SHIFT),
        "ctrl":  bool(glfw_mods & glfw.MOD_CONTROL),
        "alt":   bool(glfw_mods & glfw.MOD_ALT),
    }