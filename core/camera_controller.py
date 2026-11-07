# core/camera_controller.py

import glfw

from core.input_manager import LEFT, RIGHT, MIDDLE


class CameraController:

    def __init__(self, engine, app):
        self.engine = engine
        self.app = app
        self.is_active = True
        self._middle_mode = None

    def handle_click(self, x, y, button) -> bool:
        eng = self.engine
        if button == MIDDLE:
            self._middle_mode = "orbit" if eng.input.is_shift() else "pan"
            return True
        if button == RIGHT:
            if eng.hover_id > 0:
                self.app.actions.toggle_panel("inspector")
                return True
            return False
        if button == LEFT:
            if eng.marquee:
                eng.marquee.start_selection(x, y)
                eng.update_world_pos(x, y)
                eng.start_hover_pick(int(x), int(y))
                return True
        return False

    def handle_release(self, x, y, button) -> bool:
        eng = self.engine
        if button == MIDDLE:
            self._middle_mode = None
            return True
        if button == LEFT:
            if eng.marquee and eng.marquee.is_active:
                was_drag = eng.marquee.end_selection()
                if not was_drag:
                    eng.handle_pick_from_hover(eng.input.is_ctrl())
                return True
        return False

    def handle_move(self, x, y, dx, dy) -> bool:
        eng = self.engine
        if self._middle_mode == "orbit":
            eng.cam.orbit(dx, dy)
            eng.clear_hover()
            return True
        if self._middle_mode == "pan":
            eng.cam.pan(dx, dy)
            eng.clear_hover()
            return True
        if eng.input.state.buttons.get(LEFT) and eng.input.is_shift():
            eng.cam.orbit(dx, dy)
            eng.clear_hover()
            return True
        if eng.marquee and eng.marquee.is_active:
            eng.marquee.update_selection(x, y)
            return True
        eng.update_world_pos(x, y)
        eng.start_hover_pick(int(x), int(y))
        return False

    def handle_key(self, key, mods) -> bool:
        if key == glfw.KEY_ESCAPE:
            self._on_escape()
            return True
        return False

    def handle_scroll(self, delta) -> bool:
        self.engine.cam.zoom(delta)
        return True

    def _on_escape(self):
        eng = self.engine
        if eng.marquee and eng.marquee.is_active:
            eng.marquee.cancel_selection()
        eng.clear_hover()
        eng.sel_mgr.clear()