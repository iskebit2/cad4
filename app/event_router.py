# app/event_router.py
"""
EventRouter — GLFW event'lerini davranışa çevirir.

Sorumluluk:
  - GLFW callback'lerini kuyruğa alır (ImGui gecikmesi için).
  - Frame içinde kuyruğu işler.
  - Her event için DOĞRU davranışı seçer:
      * modifier'ları GLFW'den okuyup InputManager'a yazar
      * sol tık → marquee başlat / pick
      * orta tık → pan veya orbit (ctrl'ye göre)
      * Shift+sol → orbit
      * F3..F11 → engine komutları
      * Ctrl+Z/Y/N/F → engine komutları
  - ImGui panelleri açıkken sahne event'lerini filtreler.

Sınır:
  - Backend'i (GLFW) BİLİR — ama sadece bu dosya.
  - Engine'i BİLİR — API üzerinden.
  - InputManager'ın iç yapısını BİLMEZ — sadece public metotlarını çağırır.

KRİTİK KURAL:
  Modifier durumunu GLFW'den HER EVENT'te yeniden oku ve InputManager'a yaz.
  Böylece modifier "yapışması" imkânsız hale gelir.
"""
import time
import imgui
import numpy as np
import glfw

from core.input_manager import (
    MOUSE_BUTTON_LEFT, MOUSE_BUTTON_RIGHT, MOUSE_BUTTON_MIDDLE,
)
from logging_config import CadLogger
logger = CadLogger.get(__name__)


class EventRouter:
    """GLFW event'lerini kuyruğa alır, ImGui frame'inden sonra işler."""

    MIDDLE_DOUBLE_CLICK_INTERVAL = 0.25
    MIDDLE_DOUBLE_CLICK_MAX_DRAG = 4.0

    def __init__(self, app):
        self.app = app
        self.window = app.window

        # Event kuyruğu
        self._pending = []

        # Mouse durum takibi (router'ın kendi iç durumu)
        self._mouse_pressed = set()

        # Middle double-click
        self._last_middle_click_time = 0.0
        self._middle_press_pos = (0.0, 0.0)
        self._middle_dragged = False

    # ==================================================================
    # ENGINE ERİŞİMİ (property — kopya almıyoruz)
    # ==================================================================
    @property
    def engine(self):
        return self.app.engine

    # ==================================================================
    # YARDIMCILAR — SORUMLULUĞU NET
    # ==================================================================
    def _mods_to_dict(self, glfw_mods: int) -> dict:
        """GLFW bit mask'ını InputManager dict'ine çevir."""
        return {
            "shift": bool(glfw_mods & glfw.MOD_SHIFT),
            "ctrl":  bool(glfw_mods & glfw.MOD_CONTROL),
            "alt":   bool(glfw_mods & glfw.MOD_ALT),
        }

    def _read_mods_from_glfw(self) -> dict:
        """
        GLFW'nin anlık klavye durumundan modifier'ları oku.

        Neden: `key_up` callback'i mods parametresi İÇERMEZ.
        Bu yüzden modifier'ı "bırakma" anını yakalamak için
        doğrudan GLFW state'ini sorgularız.
        """
        w = self.window.window
        mods = 0
        if (glfw.get_key(w, glfw.KEY_LEFT_SHIFT)    == glfw.PRESS or
            glfw.get_key(w, glfw.KEY_RIGHT_SHIFT)   == glfw.PRESS):
            mods |= glfw.MOD_SHIFT
        if (glfw.get_key(w, glfw.KEY_LEFT_CONTROL)  == glfw.PRESS or
            glfw.get_key(w, glfw.KEY_RIGHT_CONTROL) == glfw.PRESS):
            mods |= glfw.MOD_CONTROL
        if (glfw.get_key(w, glfw.KEY_LEFT_ALT)      == glfw.PRESS or
            glfw.get_key(w, glfw.KEY_RIGHT_ALT)     == glfw.PRESS):
            mods |= glfw.MOD_ALT
        return self._mods_to_dict(mods)

    def _sync_modifiers(self):
        """InputManager'a modifier'ları GLFW'den yaz. Her event'ten önce çağrılır."""
        eng = self.engine
        if eng is None or eng.input is None:
            return
        eng.input.update_modifiers(self._read_mods_from_glfw())

    def _mouse_over_ui(self) -> bool:
        """Fare bir ImGui panelinin üstünde mi veya widget yakalıyor mu?"""
        try:
            import imgui
            if imgui.get_io().want_capture_mouse:
                return True
            for panel in self.app._all_panels():
                if getattr(panel, "is_hovered", False):
                    return True
        except Exception:
            pass
        return False

    def _keyboard_captured_by_ui(self) -> bool:
        try:
            import imgui
            if imgui.get_io().want_capture_keyboard:
                return True
            for panel in self.app._all_panels():
                if getattr(panel, "is_focused", False):
                    return True
        except Exception:
            pass
        return False

    # ==================================================================
    # GLFW CALLBACK'LERİ → KUYRUĞA
    # ==================================================================
    def on_key_down(self, key, scancode, mods):
        # 1) ImGui'ye ANLIK ilet
        try:
            import imgui
            io = imgui.get_io()
            io.keys_down[key] = True
        except Exception:
            pass

        # 2) Router kuyruğu (sahne kısayolları için)
        self._pending.append(("key_down", (key, scancode, mods)))
        return True

    def on_key_up(self, key, scancode):
        # 1) ImGui'ye ANLIK ilet
        try:
            import imgui
            io = imgui.get_io()
            io.keys_down[key] = False
        except Exception:
            pass

        # 2) Router kuyruğu
        self._pending.append(("key_up", (key, scancode)))
        return True

    def on_char(self, codepoint):
        
        try:
            import imgui
            io = imgui.get_io()
            # Mevcut input chars
            
            io.add_input_character(codepoint)
            
        except Exception as e:
            print(f"[ROUTER_CHAR] HATA: {e}")
        return True

    def on_mouse_button(self, button, action, mods):
        self._pending.append(("button", (button, action, mods)))
        return True

    def on_mouse_move(self, x, y):
        self._pending.append(("move", (x, y)))
        return True

    def on_scroll(self, xoffset, yoffset):
        try:
            import imgui
            io = imgui.get_io()
            io.mouse_wheel += yoffset
        except Exception:
            pass
        self._pending.append(("scroll", (xoffset, yoffset)))
        return True

    def on_window_focus(self, focused: bool):
        """Pencere fokus kaybında modifier'ları temizle."""
        if not focused:
            eng = self.engine
            if eng and eng.input:
                eng.input.clear_modifiers()

    # ==================================================================
    # KUYRUĞU İŞLE  (CadApp.frame içinden ImGui çizildikten sonra)
    # ==================================================================
    def process_pending(self):
        if not self._pending:
            return
        events = self._pending
        self._pending = []
        for kind, args in events:
            try:
                if kind == "move":
                    self._handle_move(*args)
                elif kind == "button":
                    self._handle_button(*args)
                elif kind == "scroll":
                    self._handle_scroll(*args)
                elif kind == "key_down":
                    self._handle_key_down(*args)
                elif kind == "key_up":
                    self._handle_key_up(*args)
                # "char" — SİL
            except Exception:
                logger.exception("Event işleme hatası: %s %s", kind, args)

    # ==================================================================
    # MODIFIER SENKRONU
    # ==================================================================
    def _sync_from_glfw_mods(self, mods: int):
        """Key/button event'lerindeki mods parametresini InputManager'a yaz."""
        eng = self.engine
        if eng and eng.input:
            eng.input.update_modifiers(self._mods_to_dict(mods))

    # ==================================================================
    # HANDLER — MOUSE BUTTON
    # ==================================================================
    def _handle_button(self, button, action, mods):
        eng = self.engine
        if eng is None:
            return

        # 1) Modifier'ları GLFW'den senkronla (yapışmayı önler)
        self._sync_from_glfw_mods(mods)

        # 2) ImGui fareyi yakalıyorsa sahneye iletme
        if self._mouse_over_ui():
            return

        # 3) Button adı → sabit
        x, y = self.window.get_mouse_pos()

        if button == glfw.MOUSE_BUTTON_LEFT:
            kivy_btn, name = MOUSE_BUTTON_LEFT,   "left"
        elif button == glfw.MOUSE_BUTTON_RIGHT:
            kivy_btn, name = MOUSE_BUTTON_RIGHT,  "right"
        elif button == glfw.MOUSE_BUTTON_MIDDLE:
            kivy_btn, name = MOUSE_BUTTON_MIDDLE, "middle"
        else:
            return

        # 4) InputManager'a buton durumunu yaz
        if eng.input:
            eng.input.update_mouse_position(x, y)
            eng.input.set_button_state(kivy_btn, action == glfw.PRESS)

        # 5) Davranışı seç
        if action == glfw.PRESS:
            self._mouse_pressed.add(name)
            self._on_down(name, x, y)
        elif action == glfw.RELEASE:
            self._mouse_pressed.discard(name)
            self._on_up(name, x, y)

    def _on_down(self, name, x, y):
        eng = self.engine

        # Smart plane modu
        if eng.active_smart_plane_mode:
            eng.smart_analyzer.handle_mouse_click((x, y))
            return

        if name == "middle":
            self._middle_down(x, y)
        elif name == "right":
            self._right_down()
        elif name == "left":
            self._left_down(x, y)

    def _on_up(self, name, x, y):
        eng = self.engine

        if name == "left":
            self._left_up(x, y)
        elif name == "right":
            eng.pending_pick_check = False
        elif name == "middle":
            eng.pending_pick_check = False
            eng.clear_hover()

    # --- Sol tık ---
    def _left_down(self, x, y):
        eng = self.engine
        if eng.draw_mgr.is_active:
            eng.draw_mgr.on_mouse_click(x, y)
            return
        if eng.input.is_shift_pressed():
            return  # Shift+sol → orbit (move handler yakalar)
        eng.marquee.start_selection(x, y)
        eng.update_world_pos(x, y)
        eng.start_hover_pick(int(x), int(y))

    def _left_up(self, x, y):
        eng = self.engine
        if eng.draw_mgr.is_active:
            return
        if eng.input.is_shift_pressed():
            return
        if eng.marquee.is_active:
            was_drag = eng.marquee.end_selection()
            if not was_drag:
                ctrl = eng.input.is_ctrl_pressed()
                eng.handle_pick_from_hover(ctrl)

    

    # --- Sağ tık ---
    def _right_down(self):
        eng = self.engine
        element = None
        if eng.hover_id > 0:
            element = eng.renderer.get_element_from_id(eng.hover_id)
        if element:
            self.app.open_inspector(element)
        else:
            self.app.inspector.close()

    # --- Orta tuş ---
    def _middle_down(self, x, y):
        eng = self.engine
        eng.pending_pick_check = False
        eng.clear_hover()

        now = time.time()
        if now - self._last_middle_click_time < self.MIDDLE_DOUBLE_CLICK_INTERVAL:
            self._last_middle_click_time = 0.0
            eng.fit_view()
            return
        self._last_middle_click_time = now
        self._middle_press_pos = (x, y)
        self._middle_dragged = False

    # ==================================================================
    # HANDLER — MOUSE MOVE
    # ==================================================================
    def _handle_move(self, x, y):
        eng = self.engine
        if eng is None:
            return

        # ImGui fareyi yakalıyorsa sahneye iletme
        if self._mouse_over_ui():
            return

        # InputManager'a pozisyonu yaz (kendi delta'sını hesaplar)
        if eng.input:
            eng.input.update_mouse_position(x, y)
        dx = eng.input.mouse_delta.x if eng.input else 0
        dy = eng.input.mouse_delta.y if eng.input else 0

        # Modifier GLFW'den taze olsun (hareket sırasında Shift basılıysa)
        self._sync_modifiers()

        # --- Öncelik sırası (bir tanesi işler, gerisi atlanır) ---

        # 1) Orta tuş basılı → pan / orbit
        if "middle" in self._mouse_pressed:
            self._middle_move(dx, dy, x, y)
            return

        # 2) Shift + sol tuş → orbit
        if "left" in self._mouse_pressed and eng.input.is_shift_pressed():
            eng.cam.orbit(dx, dy)
            if eng.hover_id != 0:
                eng.clear_hover()
            return

        # 3) Draw mode
        if eng.draw_mgr.is_active:
            eng.draw_mgr.on_mouse_move(x, y)
            return

        # 4) Sağ tuş basılı → hiçbir şey
        if "right" in self._mouse_pressed:
            return

        # 5) Marquee seçim
        if eng.marquee and eng.marquee.is_active:
            eng.marquee.update_selection(x, y)
            return

        # 6) Hover / pick
        eng.update_world_pos(x, y)
        eng.start_hover_pick(int(x), int(y))

        # 7) Smart plane
        if eng.active_smart_plane_mode:
            view = np.array(eng.cam.get_view_matrix(), dtype=float)
            proj = np.array(eng.cam.get_projection_matrix(), dtype=float)
            eng.smart_analyzer.handle_mouse_move(
                (x, y), view, proj,
                (self.window.fb_width, self.window.fb_height),
            )

    def _middle_move(self, dx, dy, x, y):
        eng = self.engine

        # Double-click eşiği
        if not self._middle_dragged:
            px, py = self._middle_press_pos
            dist = ((x - px) ** 2 + (y - py) ** 2) ** 0.5
            if dist > self.MIDDLE_DOUBLE_CLICK_MAX_DRAG:
                self._middle_dragged = True
                self._last_middle_click_time = 0.0

        if eng.input.is_ctrl_pressed():
            eng.cam.orbit(dx, dy)
        else:
            eng.cam.pan(dx, dy)

        eng.pending_pick_check = False
        eng.clear_hover()

    # ==================================================================
    # HANDLER — SCROLL
    # ==================================================================
    def _handle_scroll(self, xoffset, yoffset):
        
        eng = self.engine
        if eng is None:
            return
        if self._mouse_over_ui():
            return
        if yoffset > 0:
            eng.cam.zoom(1.0)
        elif yoffset < 0:
            eng.cam.zoom(-1.0)

    # ==================================================================
    # HANDLER — KLAVYE
    # ==================================================================
    def _handle_key_down(self, key, scancode, mods):
        eng = self.engine
        if eng is None:
            return

        self._sync_from_glfw_mods(mods)

        # ImGui klavyeyi yakalıyorsa (text input odakta) sahne kısayollarını engelle
        if self._keyboard_captured_by_ui():
            if key == glfw.KEY_ESCAPE:
                self._on_escape()
            return

        if eng.input:
            eng.input.handle_key_down(key)

        if eng.active_smart_plane_mode:
            if eng.smart_analyzer.handle_key_press(key):
                return

        self._dispatch_key(key, eng)

    def _dispatch_key(self, key, eng):
        # --- ESC ---
        if key == glfw.KEY_ESCAPE:
            self._on_escape()
            return

        # --- Render modu ---
        # if key == glfw.KEY_F2:
        #     cam = self.engine.cam
        #     if self.engine.scene and self.engine.scene.nodes:
        #         # Modelin z-ortalaması
        #         z_vals = [n.z for n in self.engine.scene.nodes.values()]
        #         z_mid = (min(z_vals) + max(z_vals)) / 2
        #         self.engine.apply_plane_filter("XY", offset=z_mid, direction="positive")
        #         logger.info("F2 → XY filtresi uygulandı (offset=%.1f)", z_mid)
        #     return
        if key == glfw.KEY_F3:
            if eng.renderer:
                eng.renderer.toggle_render_mode()
            return
        if key == glfw.KEY_F4:
            eng.renderer.set_node_point_size(1.0); return
        if key == glfw.KEY_F5:
            eng.renderer.set_node_point_size(8.0); return
        if key == glfw.KEY_F6:
            self.app.toggle_view_filter_panel(); return
        if key == glfw.KEY_F7:
            eng.apply_plane_filter(None); return
        if key == glfw.KEY_F8:
            eng.cam.set_view_preset("front"); return
        if key == glfw.KEY_F9:
            eng.cam.set_view_preset("top"); return
        if key == glfw.KEY_F10:
            eng.cam.set_view_preset("right"); return
        if key == glfw.KEY_F11:
            if self.app.create_work_plane_from_selection():
                return

        # --- Draw mode ---
        if key == glfw.KEY_D:
            self._toggle_draw(); return
        if key == glfw.KEY_C:
            if eng.draw_mgr.is_active:
                eng.draw_mgr.close()
            return

        # --- Delete ---
        if key == glfw.KEY_DELETE:
            deleted, rejected = eng.sel_mgr.delete_selected()
            logger.info("Silindi: %s, Reddedildi: %s", deleted, rejected)
            return

        # --- Ctrl kombinasyonları ---
        if eng.input.is_ctrl_pressed():
            if key == glfw.KEY_Z:
                eng.sel_mgr.undo(); return
            if key == glfw.KEY_Y:
                eng.sel_mgr.redo(); return
            if key == glfw.KEY_N:
                self.app.open_new_element_dialog(
                    "node",
                    defaults={"label": "N", "x": 0.0, "y": 0.0, "z": 0.0},
                    repeat=True,
                )
                return
            if key == glfw.KEY_F:
                self.app.open_new_element_dialog("frame", defaults={
                    "label": "F1", "node_i_id": "", "node_j_id": "",
                    "section_name": "",
                })
                return
            if key == glfw.KEY_P:
                self.app.open_inspector()
                return

            if key == glfw.KEY_R:
                self.app.open_definitions()
                return

            if key == glfw.KEY_G:
                self.app.open_grid()
                return

    def _handle_key_up(self, key, scancode):
        eng = self.engine
        if eng is None:
            return

        # Tuşu bırak
        if eng.input:
            eng.input.handle_key_up(key)

        # Modifier'ları GLFW'den yeniden oku (yapışmayı önler)
        self._sync_modifiers()


    # ==================================================================
    # DAVRANIŞ: ESC / DRAW
    # ==================================================================
    def _on_escape(self):
        eng = self.engine
        if eng is None:
            return
        # if self.app.inspector.visible:
        #     self.app.inspector.close()
        #     return
        if eng.draw_mgr.is_active:
            eng.draw_mgr.cancel()
            return
        if eng.marquee and eng.marquee.is_active:
            eng.marquee.cancel_selection()
            eng.clear_hover()
            return
        if eng.pending_pick_check:
            eng.pending_pick_check = False
        eng.clear_hover()
        eng.sel_mgr.clear()

    def _toggle_draw(self):
        eng = self.engine
        if eng.draw_mgr.is_active:
            eng.draw_mgr.close()
        else:
            eng.draw_mgr.start()