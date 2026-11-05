# app/input_router.py
from __future__ import annotations

import time

import glfw
import numpy as np
from pyglm import glm

from app.ui_capture import (
    keyboard_captured_by_ui, mods_to_dict, mouse_over_ui,
    sync_modifiers_from_glfw,
)
from core.input_manager import (
    MOUSE_BUTTON_LEFT, MOUSE_BUTTON_MIDDLE, MOUSE_BUTTON_RIGHT,
)


class InputRouter:

    def __init__(self, app):
        self.app = app
        self.pending: list[tuple] = []
        self.mouse_pressed: set[str] = set()

    # ------------------------------------------------------------------
    def wire_window(self, window) -> None:
        window.on_key_down = self.on_key_down
        window.on_key_up = self.on_key_up
        window.on_mouse_button = self.on_mouse_button
        window.on_mouse_move = self.on_mouse_move
        window.on_scroll = self.on_scroll
        window.on_char = self.on_char
        window.on_focus = self.on_focus

    # ------------------------------------------------------------------
    def on_char(self, codepoint):
        return True

    def on_key_down(self, key, scancode, mods):
        self.pending.append(("key_down", (key, scancode, mods)))
        return True

    def on_key_up(self, key, scancode):
        self.pending.append(("key_up", (key, scancode)))
        return True

    def on_mouse_button(self, button, action, mods):
        self.pending.append(("button", (button, action, mods)))
        return True

    def on_mouse_move(self, x, y):
        self.pending.append(("move", (x, y)))
        return True

    def on_scroll(self, xoffset, yoffset):
        self.pending.append(("scroll", (xoffset, yoffset)))
        return True

    def on_focus(self, focused: bool) -> None:
        eng = self.app.engine
        if not focused and eng and eng.input:
            eng.input.clear_modifiers()

    # ------------------------------------------------------------------
    def process_pending(self) -> None:
        if not self.pending:
            return
        events = self.pending
        self.pending = []
        dispatch = {
            "move": self._handle_move,
            "button": self._handle_button,
            "scroll": self._handle_scroll,
            "key_down": self._handle_key_down,
            "key_up": self._handle_key_up,
        }
        for kind, args in events:
            fn = dispatch.get(kind)
            if fn is not None:
                fn(*args)

    # ------------------------------------------------------------------
    def _handle_button(self, button, action, mods):
        eng = self.app.engine
        if eng is None:
            return
        self._sync_from_glfw_mods(mods)

        x, y = self.app.window.get_mouse_pos()
        if mouse_over_ui():
            return

        axis = self._axis()
        if axis is not None:
            hit = axis.pick(x, y)
            if hit:
                axis.apply_view(hit, eng.cam)
                return

        if action == glfw.PRESS and button == glfw.MOUSE_BUTTON_LEFT:
            if self._double_click(x, y):
                return

        pdm = getattr(eng, "plane_draw_mgr", None)
        if pdm is not None and pdm.is_active:
            if action == glfw.PRESS and button == glfw.MOUSE_BUTTON_LEFT:
                if pdm.on_mouse_click(x, y):
                    return

        kivy_btn, name = self._map_button(button)
        if kivy_btn is None:
            return

        if eng.input:
            eng.input.update_mouse_position(x, y)
            eng.input.set_button_state(kivy_btn, action == glfw.PRESS)

        if action == glfw.PRESS:
            self.mouse_pressed.add(name)
            self._on_down(name, x, y)
        elif action == glfw.RELEASE:
            self.mouse_pressed.discard(name)
            self._on_up(name, x, y)

    def _axis(self):
        eng = self.app.engine
        if eng and eng.presentation_renderer:
            return eng.presentation_renderer.global_axis
        return None

    def _double_click(self, x, y) -> bool:
        eng = self.app.engine
        if not eng.input.begin_left_click(x, y, time.monotonic()):
            return False
        pr = getattr(eng, "presentation_renderer", None)
        grid_r = getattr(pr, "grid", None) if pr else None
        if grid_r is None or not hasattr(grid_r, "pick_line"):
            return False
        cam = eng.cam
        hit = grid_r.pick_line(
            x, y,
            cam.get_view_matrix(),
            cam.get_projection_matrix(),
            self.app.window.fb_width,
            self.app.window.fb_height,
            tolerance_px=8.0,
        )
        if not hit:
            return False
        self.app.actions.toggle_panel("grid")
        return True

    @staticmethod
    def _map_button(button):
        if button == glfw.MOUSE_BUTTON_LEFT:
            return MOUSE_BUTTON_LEFT, "left"
        if button == glfw.MOUSE_BUTTON_RIGHT:
            return MOUSE_BUTTON_RIGHT, "right"
        if button == glfw.MOUSE_BUTTON_MIDDLE:
            return MOUSE_BUTTON_MIDDLE, "middle"
        return None, None

    # ------------------------------------------------------------------
    def _on_down(self, name, x, y):
        if name == "middle":
            self._middle_down(x, y)
        elif name == "right":
            self._right_down()
        elif name == "left":
            self._left_down(x, y)

    def _on_up(self, name, x, y):
        eng = self.app.engine
        if name == "left":
            self._left_up(x, y)
        else:
            eng.pending_pick_check = False
            if name == "middle":
                eng.clear_hover()

    def _left_down(self, x, y):
        eng = self.app.engine
        if eng.draw_mgr.is_active:
            eng.draw_mgr.on_mouse_click(x, y)
            return
        if eng.input.is_shift_pressed():
            return
        eng.marquee.start_selection(x, y)
        eng.update_world_pos(x, y)
        eng.start_hover_pick(int(x), int(y))

    def _left_up(self, x, y):
        eng = self.app.engine
        if eng.draw_mgr.is_active or eng.input.is_shift_pressed():
            return
        if eng.marquee.is_active:
            was_drag = eng.marquee.end_selection()
            if not was_drag:
                eng.handle_pick_from_hover(eng.input.is_ctrl_pressed())

    def _right_down(self):
        eng = self.app.engine
        if eng.hover_id > 0 and eng._find_element(eng.hover_id):
            self.app.actions.toggle_panel("inspector")

    def _middle_down(self, x, y):
        eng = self.app.engine
        eng.pending_pick_check = False
        eng.clear_hover()
        if eng.input.begin_middle_click(x, y, time.time()):
            eng.fit_view()

    def _middle_move(self, dx, dy, x, y):
        eng = self.app.engine
        eng.input.update_middle_drag(x, y)
        if eng.input.is_shift_pressed():
            eng.cam.orbit(dx, dy)
        else:
            eng.cam.pan(dx, dy)
        eng.pending_pick_check = False
        eng.clear_hover()

    # ------------------------------------------------------------------
    def _handle_move(self, x, y):
        eng = self.app.engine
        if eng is None or mouse_over_ui():
            return

        if eng.input:
            eng.input.update_mouse_position(x, y)
        dx = eng.input.mouse_delta.x if eng.input else 0
        dy = eng.input.mouse_delta.y if eng.input else 0

        axis = self._axis()
        if axis is not None:
            axis.update_hover(x, y)

        self._sync_modifiers()

        pdm = getattr(eng, "plane_draw_mgr", None)
        if pdm and pdm.is_active:
            pdm.on_mouse_move(x, y)
            eng.update_world_pos(x, y)
            eng.start_hover_pick(int(x), int(y))
            return

        if "middle" in self.mouse_pressed:
            self._middle_move(dx, dy, x, y)
            return

        if "left" in self.mouse_pressed and eng.input.is_shift_pressed():
            eng.cam.orbit(dx, dy)
            if eng.hover_id != 0:
                eng.clear_hover()
            return

        if eng.draw_mgr and eng.draw_mgr.is_active:
            eng.draw_mgr.on_mouse_move(x, y)
            return

        if "right" in self.mouse_pressed:
            return

        if eng.marquee and eng.marquee.is_active:
            eng.marquee.update_selection(x, y)
            return

        eng.update_world_pos(x, y)
        eng.start_hover_pick(int(x), int(y))

    def _handle_scroll(self, xoffset, yoffset):
        eng = self.app.engine
        if eng is None or mouse_over_ui():
            return
        if yoffset > 0:
            eng.cam.zoom(1.0)
        elif yoffset < 0:
            eng.cam.zoom(-1.0)

    # ------------------------------------------------------------------
    def _handle_key_down(self, key, scancode, mods):
        eng = self.app.engine
        if not eng:
            return
        self._sync_from_glfw_mods(mods)

        if eng.draw_mgr and eng.draw_mgr.is_active:
            if eng.draw_mgr.on_key_press(key):
                return

        if keyboard_captured_by_ui():
            if key == glfw.KEY_ESCAPE:
                self._on_escape()
            return

        pdm = getattr(eng, "plane_draw_mgr", None)
        if pdm and pdm.is_active and pdm.on_key_press(key):
            return

        for entry in self.app.panels.values():
            panel = entry["instance"]
            handler = getattr(panel, "on_key_press", None)
            if (getattr(panel, "visible", False)
                    and callable(handler) and handler(key)):
                return

        if eng.input:
            eng.input.handle_key_down(key)

        self._dispatch_key(key, eng)

    def _handle_key_up(self, key, scancode):
        eng = self.app.engine
        if eng is None:
            return
        if eng.input:
            eng.input.handle_key_up(key)
        self._sync_modifiers()

    def _dispatch_key(self, key, eng):
        if key == glfw.KEY_ESCAPE:
            self._on_escape()
            return

        entry = self.app._key_shortcuts.get(key)
        if entry:
            panel_name, needs_ctrl, needs_shift = entry
            if (eng.input.is_ctrl_pressed() == needs_ctrl
                    and eng.input.is_shift_pressed() == needs_shift):
                self.app.actions.toggle_panel(panel_name)
                return

        if key == glfw.KEY_F2:
            self.app._toggle_2d()
            return
        if key == glfw.KEY_F3:
            eng.renderer.toggle_render_mode()
            return
        if key == glfw.KEY_F5:
            eng.zoom_extents()
            return
        if key == glfw.KEY_D and not eng.input.is_ctrl_pressed():
            self.toggle_draw(None)
            return
        if key == glfw.KEY_W and eng.input.is_shift_pressed():
            self.toggle_plane()
            return
        if key == glfw.KEY_C and eng.draw_mgr.is_active:
            eng.draw_mgr.close()
            return
        if key == glfw.KEY_L and not eng.input.is_ctrl_pressed():
            self.toggle_loads()
            return
        if key == glfw.KEY_DELETE:
            eng.sel_mgr.delete_selected()
            return

        if eng.input.is_ctrl_pressed():
            if key == glfw.KEY_J:
                self.toggle_show_only()
            elif key == glfw.KEY_Z:
                eng.sel_mgr.undo()
            elif key == glfw.KEY_Y:
                eng.sel_mgr.redo()
            elif key == glfw.KEY_S:
                if eng.input.is_shift_pressed():
                    self.app.actions.save_as_dialog()
                else:
                    self.app.actions.quick_save()
            elif key == glfw.KEY_O:
                self.app.actions.open_dialog()
            elif key == glfw.KEY_E:
                self.app.actions.s2k_export()

    def _on_escape(self):
        eng = self.app.engine
        if eng is None:
            return
        pdm = getattr(eng, "plane_draw_mgr", None)
        if pdm and pdm.is_active:
            pdm._step_back()
            return
        if eng.draw_mgr.is_active:
            eng.draw_mgr.cancel()
            return
        if eng.marquee and eng.marquee.is_active:
            eng.marquee.cancel_selection()
            eng.clear_hover()
            return
        eng.pending_pick_check = False
        eng.clear_hover()
        eng.sel_mgr.clear()

    # ------------------------------------------------------------------
    def toggle_draw(self, sender=None):
        eng = self.app.engine
        if not eng or not eng.draw_mgr:
            return
        mgr = eng.draw_mgr
        if mgr.is_active:
            mgr.cancel()
            return
        if sender:
            panel_name = "polygon_properties" if sender == "poly" else "line_properties"
            mode = "sequential" if sender == "poly" else "line"
            panel = self.app.panels.get(panel_name, {}).get("instance")
            if panel is not None and not getattr(panel, "visible", False):
                self.app.actions.prepare_panel(panel_name, panel)
                panel.open()
            mgr.start(mode=mode)

    def toggle_plane(self):
        pdm = getattr(self.app.engine, "plane_draw_mgr", None)
        if pdm is None:
            return
        if pdm.is_active:
            pdm.cancel()
            return
        for entry in self.app.panels.values():
            p = entry["instance"]
            if getattr(p, "visible", False):
                p.close()
        pdm.start()

    def toggle_local_axes(self):
        if self.app.engine and self.app.engine.scene:
            self.app.engine.scene.show_local_axes = not self.app.engine.scene.show_local_axes

    def toggle_loads(self):
        self.set_loads_visible(not self.get_loads_visible())

    def get_loads_visible(self) -> bool:
        panel = getattr(self.app, "load_display_panel", None)
        if panel is not None:
            return bool(panel.show_loads)
        pres = self.app.engine.presentation_renderer if self.app.engine else None
        if pres and pres.loads:
            return bool(pres.loads.enabled)
        return False

    def set_loads_visible(self, enabled: bool):
        panel = getattr(self.app, "load_display_panel", None)
        pres = self.app.engine.presentation_renderer if self.app.engine else None
        scene = self.app.engine.scene if self.app.engine else None

        if panel is not None:
            panel.set_loads_visible(
                enabled,
                renderer=self.app.engine.renderer if self.app.engine else None,
                scene=scene,
            )
            return

        if pres and pres.loads:
            pres.loads.enabled = bool(enabled)
            if enabled and scene:
                pres.update_loads(scene, camera_scale=1.0, scene_size=1.0)

    def toggle_show_only(self):
        eng = self.app.engine
        if not eng or not eng.scene:
            return
        scn = eng.scene
        if self.app._show_only_ids is None:
            selected = scn.get_selected()
            if not selected:
                return
            self.app._show_only_ids = {e.unique_id for e in selected}
        else:
            self.app._show_only_ids = None
        scn._render_filter = self.app._show_only_ids
        if self.app._show_only_ids is not None:
            eng.renderer.update_geo(scn)
        else:
            eng.set_scene(scn)

    def apply_frame_load(self, frames, load_set):
        if not frames or not load_set.segments:
            return
        pattern = load_set.pattern_name
        for frame in frames:
            frame.dist_load_sets[pattern] = _copy_load(load_set)
            frame.mark_dirty()
        self.set_loads_visible(True)
        eng = self.app.engine
        if eng and eng.scene and eng.renderer:
            eng.renderer.update_geo(eng.scene)
            eng.scene.clear_dirty()

    def on_area_transfer_complete(self, frames):
        if not frames:
            return
        self.set_loads_visible(True)
        eng = self.app.engine
        if eng and eng.scene and eng.renderer:
            eng.renderer.update_geo(eng.scene)
            eng.scene.clear_dirty()

    def convert_frames_to_links(self, link_prop_name="DefaultLink",
                                 delete_original=True):
        from tools import frame_to_link

        eng = self.app.engine
        if not eng or not eng.scene:
            return
        scn = eng.scene
        frames = [e for e in scn.get_selected() if e.__class__.__name__ == "Frame"]
        if not frames:
            return

        report = frame_to_link.convert_frames_to_links(
            scene=scn,
            project=self.app.current_project,
            frames=frames,
            link_prop_name=link_prop_name,
            delete_original=delete_original,
        )

        if self.app._show_only_ids is not None:
            removed = {f.unique_id for f in frames}
            self.app._show_only_ids -= removed
            self.app._show_only_ids.update(l.unique_id for l in report["new_links"])
            scn._render_filter = self.app._show_only_ids

        if eng.sel_mgr:
            eng.sel_mgr.clear()

    # ------------------------------------------------------------------
    def draw_hud(self):
        eng = self.app.engine
        if not eng:
            return
        snap = eng.snap
        if snap is None or not getattr(eng, "hover_visual_enabled", True):
            return
        if not eng.draw_mgr:
            return
        if not (eng.draw_mgr.is_active or eng.hover_id > 0):
            return

        w, h = self.app.window.fb_width, self.app.window.fb_height

        if eng.draw_mgr.is_active:
            hover = eng.draw_mgr.hover_node
            if hover is not None:
                mvp = eng.cam.get_projection_matrix() @ eng.cam.get_view_matrix()
                clip = mvp * glm.vec4(hover.x, hover.y, hover.z, 1.0)
                if clip.w > 0:
                    ndc = glm.vec3(clip) / clip.w
                    nx = (ndc.x + 1.0) * w / 2.0
                    ny = (1.0 - ndc.y) * h / 2.0
                    snap.draw_snap(nx, ny, w, h, active=True, hover_node=True)
                    return

        mx = eng.input.mouse_pos.x if eng.input else 0.0
        my = eng.input.mouse_pos.y if eng.input else 0.0
        snap.draw_snap(mx, my, w, h, active=True, hover_node=False)

    def draw_pdm_hud(self):
        from imgui_bundle import imgui

        pdm = getattr(self.app.engine, "plane_draw_mgr", None)
        if pdm is None or not pdm.is_active:
            return

        text = {
            pdm.STAGE_P0: "p0: İlk noktayı seç",
            pdm.STAGE_P1: "p1: U vektörünü belirle",
            pdm.STAGE_P2: "p2: V vektörünü belirle",
            pdm.STAGE_DEPTH_PLUS: f"depth_plus: {pdm.depth_plus:.0f}mm",
            pdm.STAGE_DEPTH_MINUS: f"depth_minus: {pdm.depth_minus:.0f}mm",
        }.get(pdm.stage, "")

        io = imgui.get_io()
        w, _ = io.display_size
        imgui.set_next_window_pos(imgui.ImVec2(w / 2 - 200, 20))
        imgui.set_next_window_size(imgui.ImVec2(400, 40))
        expanded, _ = imgui.begin(
            "##pdm_hud", False,
            imgui.WindowFlags_.no_title_bar
            | imgui.WindowFlags_.no_resize
            | imgui.WindowFlags_.no_scrollbar
            | imgui.WindowFlags_.no_inputs,
        )
        if expanded:
            imgui.text_colored(imgui.ImVec4(1.0, 0.9, 0.4, 1.0), text)
        imgui.end()

    # ------------------------------------------------------------------
    def _sync_modifiers(self):
        eng = self.app.engine
        if eng is None or eng.input is None:
            return
        eng.input.update_modifiers(sync_modifiers_from_glfw(self.app.window.window))

    def _sync_from_glfw_mods(self, mods: int):
        eng = self.app.engine
        if eng and eng.input:
            eng.input.update_modifiers(mods_to_dict(mods))


def _copy_load(load_set):
    from copy import deepcopy
    return deepcopy(load_set)