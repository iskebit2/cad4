# app/input_bindings.py
from __future__ import annotations

import glfw

from app.commands import project_commands as PC


def build_bindings(command_queue) -> dict:
    q = command_queue
    return {
        # --- Kamera / projeksiyon ---
        glfw.KEY_F2: lambda: q.put(PC.Toggle2D()),
        glfw.KEY_F3: lambda: q.put(PC.ToggleRenderMode()),
        glfw.KEY_F4: lambda: q.put(PC.ShowEntireModel()),
        glfw.KEY_F5: lambda: q.put(PC.ZoomExtents()),

        # --- Seçim ---
        glfw.KEY_DELETE: lambda: q.put(PC.DeleteSelected()),

        # --- Plane ---
        (glfw.KEY_W, glfw.MOD_SHIFT): lambda: q.put(PC.StartPlaneTool()),

        # --- Undo / Redo ---
        (glfw.KEY_Z, glfw.MOD_CONTROL): lambda: q.put(PC.Undo()),
        (glfw.KEY_Y, glfw.MOD_CONTROL): lambda: q.put(PC.Redo()),
    }