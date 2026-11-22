from __future__ import annotations

from typing import Any, Callable

from imgui_bundle import imgui
from core.units import UnitSystem
from app.commands import project_commands as PC

def _v4(r: float, g: float, b: float, a: float = 1.0):
    return imgui.ImVec4(r, g, b, a)


def _format_selection(selected: list) -> str:
    if not selected:
        return "Seçim: Yok"
    if len(selected) == 1:
        el = selected[0]
        kind = type(el).__name__
        uid = getattr(el, "unique_id", "?")
        label = getattr(el, "label", "")
        suffix = f" ({label})" if label else ""
        return f"Seçim: {kind} #{uid}{suffix}"

    counts: dict[str, int] = {}
    for el in selected:
        kind = type(el).__name__
        counts[kind] = counts.get(kind, 0) + 1
    summary = ", ".join(f"{cnt} {k}" for k, cnt in counts.items())
    return f"Seçim: {len(selected)} eleman ({summary})"


def _format_unit_label(unit: Any) -> str:
    if unit is None:
        return "Birim: -"
    label = getattr(unit, "label", None)
    if label:
        return str(label)
    value = getattr(unit, "value", None)
    if value:
        return str(value)
    return str(unit)


class StatusBar:
    def __init__(self, height: float = 26.0) -> None:
        self.height = height
        self.last_key_text: str = "-"
        self.last_event_text: str = "Komut bekleniyor..."
        self.selection_text: str = "Seçim: Yok"

    def notify_key(self, key: int, action: int, mods: int) -> None:
        if action == 1:
            self.last_key_text = f"Key:{key} (mods:{mods})"
            self.last_event_text = f"Tuş basıldı -> {key}"

    def notify_command(self, text: str) -> None:
        self.last_event_text = text

    def notify_selection(self, selected: list) -> None:
        self.selection_text = _format_selection(selected)

    def draw(
        self,
        app,
        engine_connected: bool,
        app_status: str,
        mouse_pos: tuple[float, float],
        mouse_buttons: dict[int, bool],
        modifiers: int,
        fps: float,
        ucs_name: str = "Global",
        ucs_pos: tuple[float, float, float] | None = None,
        current_unit: Any = None,
        on_unit_selected: Callable[[UnitSystem], None] | None = None,
    ) -> None:
        viewport = imgui.get_main_viewport()
        bar_pos = imgui.ImVec2(viewport.pos.x, viewport.pos.y + viewport.size.y - self.height)
        bar_size = imgui.ImVec2(viewport.size.x, self.height)

        imgui.set_next_window_pos(bar_pos)
        imgui.set_next_window_size(bar_size)

        flags = (
            imgui.WindowFlags_.no_title_bar
            | imgui.WindowFlags_.no_resize
            | imgui.WindowFlags_.no_move
            | imgui.WindowFlags_.no_scrollbar
            | imgui.WindowFlags_.no_scroll_with_mouse
            | imgui.WindowFlags_.no_saved_settings
            | imgui.WindowFlags_.no_docking
        )

        imgui.push_style_var(imgui.StyleVar_.window_rounding, 0.0)
        imgui.push_style_var(imgui.StyleVar_.window_padding, imgui.ImVec2(10.0, 4.0))
        imgui.push_style_color(imgui.Col_.window_bg, _v4(0.10, 0.12, 0.16, 0.96))

        if imgui.begin("##StatusBar", None, flags):
            unit_label = _format_unit_label(current_unit)
            fps_text = f"{fps:5.1f} FPS"
            unit_btn_w = imgui.calc_text_size(unit_label).x + 14.0
            fps_w = imgui.calc_text_size(fps_text).x
            sep_w = imgui.calc_text_size("|").x
            right_block_w = unit_btn_w + 10.0 + sep_w + 10.0 + fps_w
            right_start_x = max(40.0, bar_size.x - right_block_w - 10.0)

            self._draw_left_items(
                max_x=right_start_x - 12.0,
                engine_connected=engine_connected,
                app_status=app_status,
                mouse_pos=mouse_pos,
                mouse_buttons=mouse_buttons,
                modifiers=modifiers,
                ucs_name=ucs_name,
                ucs_pos=ucs_pos,
            )

            imgui.same_line(spacing=10.0)
            self._draw_unit_selector(unit_label, current_unit, on_unit_selected)
            imgui.same_line(spacing=10.0)
            self._draw_view_mode_selector(app)
            imgui.same_line(spacing=10.0)
            self._draw_render_mode_selector(app)
            imgui.same_line(spacing=10.0)
            imgui.text_disabled("|")
            
            imgui.same_line(spacing=10.0)
            imgui.text_disabled(fps_text)

        imgui.end()
        imgui.pop_style_color(1)
        imgui.pop_style_var(2)

    def _draw_left_items(
        self,
        max_x: float,
        engine_connected: bool,
        app_status: str,
        mouse_pos: tuple[float, float],
        mouse_buttons: dict[int, bool],
        modifiers: int,
        ucs_name: str,
        ucs_pos: tuple[float, float, float] | None,
    ) -> None:
        mx, my = mouse_pos
        b_l = "L" if mouse_buttons.get(0) else "-"
        b_m = "M" if mouse_buttons.get(2) else "-"
        b_r = "R" if mouse_buttons.get(1) else "-"

        if ucs_pos is not None:
            ux, uy, uz = ucs_pos
            ucs_text = f"{ucs_name}: ({ux:8.1f}, {uy:8.1f}, {uz:6.1f})"
            ucs_color = _v4(0.55, 0.90, 0.75)
        else:
            ucs_text = f"{ucs_name}: (-, -, -)"
            ucs_color = _v4(0.55, 0.58, 0.65)

        mod_list = []
        if modifiers & 1:
            mod_list.append("SHIFT")
        if modifiers & 2:
            mod_list.append("CTRL")
        if modifiers & 4:
            mod_list.append("ALT")
        mod_str = "+".join(mod_list) if mod_list else "-"

        items: list[tuple[imgui.ImVec4, str]] = [
            (
                _v4(0.25, 0.88, 0.45) if engine_connected else _v4(0.92, 0.30, 0.30),
                "● Engine: BAĞLI" if engine_connected else "● Engine: YOK",
            ),
            (_v4(0.85, 0.88, 0.94), f"App: {app_status}"),
            (
                _v4(0.40, 0.85, 1.00) if self.selection_text != "Seçim: Yok" else _v4(0.60, 0.64, 0.72),
                self.selection_text,
            ),
            # (_v4(0.85, 0.88, 0.94), f"Mouse: ({mx:4.0f}, {my:4.0f}) [{b_l}{b_m}{b_r}]"),
            (ucs_color, ucs_text),
            # (_v4(0.95, 0.78, 0.30), f"{self.last_key_text} | Mods: {mod_str}"),
        ]

        sep_w = imgui.calc_text_size("|").x
        for idx, (color, text) in enumerate(items):
            item_w = imgui.calc_text_size(text).x
            extra_w = (12.0 + sep_w + 12.0) if idx > 0 else 0.0
            if imgui.get_cursor_pos_x() + extra_w + item_w > max_x:
                break
            if idx > 0:
                imgui.same_line(spacing=12.0)
                imgui.text_disabled("|")
                imgui.same_line(spacing=12.0)
            imgui.text_colored(color, text)

    def _draw_unit_selector(
        self,
        unit_label: str,
        current_unit: Any,
        on_unit_selected: Callable[[UnitSystem], None] | None,
    ) -> None:
        imgui.push_style_color(imgui.Col_.button, _v4(0.18, 0.24, 0.34, 1.0))
        imgui.push_style_color(imgui.Col_.button_hovered, _v4(0.24, 0.34, 0.48, 1.0))
        imgui.push_style_color(imgui.Col_.button_active, _v4(0.28, 0.40, 0.58, 1.0))
        imgui.push_style_var(imgui.StyleVar_.frame_padding, imgui.ImVec2(7.0, 1.0))
        imgui.push_style_var(imgui.StyleVar_.frame_rounding, 3.0)

        clicked = imgui.button(f"{unit_label}##status_unit_btn")
        if imgui.is_item_hovered():
            imgui.set_tooltip("Proje birim sistemini değiştir")

        imgui.pop_style_var(2)
        imgui.pop_style_color(3)

        if clicked:
            imgui.open_popup("##status_unit_popup")

        if imgui.begin_popup("##status_unit_popup"):
            imgui.text_disabled("BİRİM SİSTEMİ")
            imgui.separator()
            for unit in UnitSystem:
                item_label = _format_unit_label(unit)
                selected = current_unit == unit
                if imgui.menu_item(f"{item_label}##unit_{unit.name}", "", selected)[0]:
                    if not selected and on_unit_selected is not None:
                        on_unit_selected(unit)
            imgui.end_popup()

    def _draw_render_mode_selector(self, app) -> None:
        eng = app.engine
        current_mode = (
            eng.renderer.get_render_mode()
            if eng.renderer else "simple"
        )

        next_mode = "shaded" if current_mode == "simple" else "simple"

        

        imgui.push_style_color(
            imgui.Col_.button, _v4(0.18, 0.24, 0.34, 1.0)
        )
        imgui.push_style_color(
            imgui.Col_.button_hovered, _v4(0.24, 0.34, 0.48, 1.0)
        )
        imgui.push_style_color(
            imgui.Col_.button_active, _v4(0.28, 0.40, 0.58, 1.0)
        )
        imgui.push_style_var(
            imgui.StyleVar_.frame_padding, imgui.ImVec2(7.0, 1.0)
        )
        imgui.push_style_var(imgui.StyleVar_.frame_rounding, 3.0)

        clicked = imgui.button(f"{current_mode}##status_render_mode_btn")

        if imgui.is_item_hovered():
            imgui.set_tooltip(f"Render mode: {current_mode}")

        imgui.pop_style_var(2)
        imgui.pop_style_color(3)

        if clicked:
            app.command_queue.put(PC.SetRenderMode(next_mode))
    
    def _draw_view_mode_selector(self, app) -> None:
        camera = app.view_service._active_camera()       
        is_2d = camera.is_2d
        on_toggle = app.view_service.toggle_2d
        label = "2D" if is_2d else "3D"

        imgui.push_style_color(
            imgui.Col_.button, _v4(0.18, 0.24, 0.34, 1.0)
        )
        imgui.push_style_color(
            imgui.Col_.button_hovered, _v4(0.24, 0.34, 0.48, 1.0)
        )
        imgui.push_style_color(
            imgui.Col_.button_active, _v4(0.28, 0.40, 0.58, 1.0)
        )
        imgui.push_style_var(
            imgui.StyleVar_.frame_padding, imgui.ImVec2(7.0, 1.0)
        )
        imgui.push_style_var(imgui.StyleVar_.frame_rounding, 3.0)

        clicked = imgui.button(f"{label}##status_view_mode_btn")

        if imgui.is_item_hovered():
            imgui.set_tooltip("2D / 3D görünümünü değiştir")

        imgui.pop_style_var(2)
        imgui.pop_style_color(3)

        if clicked and on_toggle is not None:
            on_toggle()