# core/camera_controller.py
import glfw

from core.input_manager import LEFT, RIGHT, MIDDLE


class CameraController:

    def __init__(self, engine, app):
        self.engine = engine
        self.app = app
        self.is_active = True
        self._middle_mode = None

    # --------------------------------------------------------------
    def _active_camera(self):
        vm = getattr(self.engine, "viewport_manager", None)
        if vm is not None:
            vp = vm.active
            if vp is not None:
                return vp.camera
        return self.engine.cam

    def _active_viewport(self):
        vm = getattr(self.engine, "viewport_manager", None)
        return vm.active if vm is not None else None

    # --------------------------------------------------------------
    def handle_click(self, x, y, button) -> bool:
        if not self.is_active:
            return False
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
            vp = self._active_viewport()
            if eng.marquee:
                eng.marquee.start_selection(
                    x, y,
                    camera=vp.camera if vp is not None else None,
                    viewport_size=(vp.width, vp.height) if vp is not None else None,
                    viewport_name=vp.name if vp is not None else None,
                )
                eng.update_world_pos(x, y)
                eng.start_hover_pick(int(x), int(y))
                return True
        return False

    def handle_release(self, x, y, button) -> bool:
        if not self.is_active:
            return False
        eng = self.engine
        if button == MIDDLE:
            self._middle_mode = None
            return True
        if button == LEFT:
            if eng.marquee and eng.marquee.is_active:
                was_drag = eng.marquee.end_selection()
                if not was_drag:
                    vp = self._active_viewport()
                    if vp is not None:
                        self._pick_at_viewport(vp, x, y)
                    else:
                        eng.handle_pick_from_hover(eng.input.is_ctrl())
                return True
        return False

    def handle_move(self, x, y, dx, dy) -> bool:
        if not self.is_active:
            return False
        eng = self.engine
        cam = self._active_camera()
        if cam._is_2d_locked():
            if self._middle_mode == "orbit":
                cam.pan(dx, dy)   # orbit yerine pan
                eng.clear_hover()
                return True
            if eng.input.state.buttons.get(LEFT) and eng.input.is_shift():
                cam.pan(dx, dy)
                eng.clear_hover()
                return True
        if self._middle_mode == "orbit":
            cam.orbit(dx, dy)
            eng.clear_hover()
            return True
        if self._middle_mode == "pan":
            cam.pan(dx, dy)
            eng.clear_hover()
            return True
        if eng.input.state.buttons.get(LEFT) and eng.input.is_shift():
            cam.orbit(dx, dy)
            eng.clear_hover()
            return True
        if eng.marquee and eng.marquee.is_active:
            eng.marquee.update_selection(x, y)
            return True
        eng.update_world_pos(x, y)
        vp = self._active_viewport()
        if vp is not None:
            eng.start_viewport_hover_pick(vp, int(x), int(y))
        else:
            eng.start_hover_pick(int(x), int(y))
        return False

    def handle_key(self, key, mods) -> bool:
        if not self.is_active:
            return False
        if key == glfw.KEY_ESCAPE:
            self._on_escape()
            return True
        return False

    def handle_scroll(self, delta) -> bool:
        if not self.is_active:
            return False
        self._active_camera().zoom(delta)
        return True

    def _pick_at_viewport(self, vp, x_px, y_px):
        eng = self.engine
        pick_pass = getattr(eng, "pick_pass", None)
        if pick_pass is None:
            return
        element = vp.pick_at(pick_pass, int(x_px), int(y_px))
        if element is None:
            if not eng.input.is_ctrl():
                eng.sel_mgr.clear()
            return
        # ★ visible_ids kontrolü — O(1)
        if vp.visible_ids is not None and element.unique_id not in vp.visible_ids:
            return
        eng.sel_mgr.select(element, additive=eng.input.is_ctrl())

    def _on_escape(self):
        eng = self.engine
        if eng.marquee and eng.marquee.is_active:
            eng.marquee.cancel_selection()
        eng.clear_hover()
        eng.sel_mgr.clear()