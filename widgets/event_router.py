# widgets/event_router.py
"""
EventRouter — Klavye ve fare olaylarını Engine API'sine çevirir.
KivyCADWidget'ı sadece glue olarak bırakır.
"""

import time
from kivy.core.window import Window
from core.input_manager import (
    MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT, MOUSE_BUTTON_MIDDLE,
)
from logging_config import CadLogger
logger = CadLogger.get(__name__)


class EventRouter:
    def __init__(self, widget):
        self.w = widget

    # ------------------------------------------------------------------
    # KLAVYE
    # ------------------------------------------------------------------
    def on_key_down(self, key, scancode, codepoint, modifiers):
        w = self.w
        eng = w.engine

        if eng and eng.input:
            eng.input.update_modifiers(modifiers)

        # --- Kısayol tablosu ---
        # Format: key: (handler, pass_engine_arg)
        if key == 27:                      # ESC
            return self._on_escape()
        if key == 284:                     # F3 render mode
            eng.renderer.toggle_render_mode()
            return True
        if key == 285:                     # F4 node point size 1
            eng.renderer.set_node_point_size(1.0)
            return True
        if key == 286:                     # F5 node point size 8
            eng.renderer.set_node_point_size(8.0)
            return True
        if key == 287:                     # F6 view filter panel
            w.panels.toggle_view_filter_panel()
            return True
        if key == 288:                     # F7 plan filter kapat
            eng.apply_plane_filter(None)
            return True
        if key == 289:                     # F8 front
            eng.cam.set_view_preset("front")
            return True
        if key == 290:                     # F9 top
            eng.cam.set_view_preset("top")
            return True
        if key == 100:                     # D — draw mode toggle
            self._toggle_draw_mode()
            return True
        if key == 99:                      # C — draw close
            if eng.draw_mgr.is_active:
                eng.draw_mgr.close()
            return True
        if key == 127:                     # Delete
            deleted, rejected = eng.sel_mgr.delete_selected()
            logger.info(f"Silindi: {deleted}, Reddedildi: {rejected}")
            return True
        if key == 122 and 'ctrl' in modifiers:   # Ctrl+Z
            eng.sel_mgr.undo()
            return True
        if key == 121 and 'ctrl' in modifiers:   # Ctrl+Y
            eng.sel_mgr.redo()
            return True
        if key == 110 and 'ctrl' in modifiers:   # Ctrl+N yeni node
            w.properties_panel.show_new_element(
                "node", defaults={"label": "N", "x": 0.0, "y": 0.0, "z": 0.0},
                repeat=True,
            )
            return True
        if key == 102 and 'ctrl' in modifiers:   # Ctrl+F yeni frame
            w.properties_panel.show_new_element("frame", defaults={
                "label": "F1", "node_i_id": "", "node_j_id": "", "section_name": "",
            })
            return True

        return False

    def _on_escape(self):
        w = self.w
        eng = w.engine
        if w.properties_panel and w.properties_panel.opacity > 0:
            w.properties_panel.hide()
            return True
        if eng.draw_mgr.is_active:
            eng.draw_mgr.cancel()
            return True
        if eng.marquee and eng.marquee.is_active:
            eng.marquee.cancel_selection()
            eng.clear_hover()
            return True
        if eng.pending_pick_check:
            eng.pending_pick_check = False
        eng.clear_hover()
        eng.sel_mgr.clear()
        return True

    def _toggle_draw_mode(self):
        eng = self.w.engine
        if eng.draw_mgr.is_active:
            eng.draw_mgr.close()
        else:
            eng.draw_mgr.start()

    # ------------------------------------------------------------------
    # FARE — DOWN
    # ------------------------------------------------------------------
    def on_touch_down(self, touch):
        w = self.w
        eng = w.engine
        if not eng:
            return False
        if not w.collide_point(*touch.pos):
            return False

        x = touch.x - w.x
        y = w.height - (touch.y - w.y)

        touch.grab(w)
        eng.input.update_mouse_position(x, y)

        if touch.button == 'scrollup':
            eng.cam.zoom(-1.0)
            touch.ungrab(w)
            return True
        if touch.button == 'scrolldown':
            eng.cam.zoom(1.0)
            touch.ungrab(w)
            return True
        if touch.button == 'middle':
            self._on_middle_down(x, y, touch)
            return True
        if touch.button == 'right':
            self._on_right_down()
            return True
        if touch.button == 'left':
            self._on_left_down(x, y)
            return True
        return True

    def on_touch_move(self, touch):
        w = self.w
        eng = w.engine
        if touch.grab_current is not w or not eng:
            return False

        x = touch.x - w.x
        y = w.height - (touch.y - w.y)
        dx, dy = touch.dx, -touch.dy

        eng.input.update_mouse_position(x, y)

        if touch.button == 'middle':
            self._on_middle_move(dx, dy, x, y)
            return True
        if touch.button == 'left' and eng.input.is_shift_pressed():
            eng.cam.orbit(dx, dy)
            if eng.hover_id != 0:
                eng.clear_hover()
            return True
        if eng.draw_mgr.is_active:
            eng.draw_mgr.on_mouse_move(x, y)
            return True
        if touch.button == 'right':
            return True
        if eng.marquee and eng.marquee.is_active:
            eng.marquee.update_selection(x, y)
            return True
        eng.update_world_pos(x, y)
        eng.start_hover_pick(int(x), int(y))
        return True

    def on_touch_up(self, touch):
        w = self.w
        eng = w.engine
        if touch.grab_current is not w:
            return False

        x = touch.x - w.x
        y = w.height - (touch.y - w.y)

        if touch.button == 'left':
            self._on_left_up(x, y)
        elif touch.button == 'right':
            eng.input.set_button_state(MOUSE_BUTTON_RIGHT, False)
        elif touch.button == 'middle':
            eng.input.set_button_state(MOUSE_BUTTON_MIDDLE, False)
            eng.pending_pick_check = False
            eng.clear_hover()

        touch.ungrab(w)
        return True

    def on_global_mouse_move(self, pos):
        w = self.w
        eng = w.engine
        if not eng or not w.collide_point(*pos):
            return
        x = pos[0] - w.x
        y = w.height - (pos[1] - w.y)
        if eng.draw_mgr.is_active:
            eng.input.update_mouse_position(x, y)
            eng.draw_mgr.on_mouse_move(x, y)

    # ------------------------------------------------------------------
    # ALT HANDLER'LAR
    # ------------------------------------------------------------------
    def _on_right_down(self):
        w = self.w
        eng = w.engine
        eng.input.set_button_state(MOUSE_BUTTON_RIGHT, True)
        element = None
        if eng.hover_id > 0:
            element = eng.renderer.get_element_from_id(eng.hover_id)
        if w.properties_panel:
            if element:
                w.properties_panel.show_element(element)
            else:
                w.properties_panel.hide()

    def _on_left_down(self, x, y):
        eng = self.w.engine
        eng.input.set_button_state(MOUSE_BUTTON_LEFT, True)
        if eng.draw_mgr.is_active:
            eng.draw_mgr.on_mouse_click(x, y)
            return
        if eng.input.is_shift_pressed():
            return
        eng.marquee.start_selection(x, y)
        eng.update_world_pos(x, y)
        eng.start_hover_pick(int(x), int(y))

    def _on_left_up(self, x, y):
        w = self.w
        eng = w.engine
        eng.input.set_button_state(MOUSE_BUTTON_LEFT, False)
        if eng.draw_mgr.is_active:
            return
        if eng.input.is_shift_pressed():
            return
        if eng.marquee.is_active:
            was_drag = eng.marquee.end_selection()
            if not was_drag:
                ctrl = eng.input.is_ctrl_pressed()
                eng.handle_pick_from_hover(ctrl)
                # Panel güncellemesi — widget callback'i üzerinden
                if w.properties_panel and w.properties_panel.opacity > 0:
                    selected = eng.sel_mgr.get_selected()
                    if not selected:
                        w.properties_panel.hide()
                    elif len(selected) == 1:
                        w.properties_panel.show_element(selected[0])
                    else:
                        w.properties_panel.show_selection_summary(selected)

    def _on_middle_down(self, x, y, touch):
        w = self.w
        eng = w.engine
        eng.input.set_button_state(MOUSE_BUTTON_MIDDLE, True)
        eng.pending_pick_check = False
        eng.clear_hover()

        now = time.time()
        if now - w._last_middle_click_time < w.MIDDLE_DOUBLE_CLICK_INTERVAL:
            w._last_middle_click_time = 0
            w.engine.fit_view()
            touch.ungrab(w)
            return
        w._last_middle_click_time = now
        w._middle_press_pos = (x, y)
        w._middle_dragged = False

    def _on_middle_move(self, dx, dy, x, y):
        w = self.w
        eng = w.engine
        if not w._middle_dragged:
            px, py = w._middle_press_pos
            if ((x - px) ** 2 + (y - py) ** 2) ** 0.5 > w.MIDDLE_DOUBLE_CLICK_MAX_DRAG:
                w._middle_dragged = True
                w._last_middle_click_time = 0
        if eng.input.is_ctrl_pressed():
            eng.cam.orbit(dx, dy)
        else:
            eng.cam.pan(dx, dy)
        eng.pending_pick_check = False
        eng.clear_hover()