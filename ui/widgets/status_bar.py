# ui/widgets/status_bar.py
from __future__ import annotations

from typing import Any, Callable

from imgui_bundle import imgui

import app.commands as cmd
from core.units import UnitSystem


_BTN_W = 22.0
_BTN_H = 20.0
_PAD = 4.0


def _v4(r: float, g: float, b: float, a: float = 1.0) -> imgui.ImVec4:
    return imgui.ImVec4(r, g, b, a)


def _vec2(x: float, y: float) -> imgui.ImVec2:
    return imgui.ImVec2(x, y)


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
    return str(getattr(unit, "value", unit))


class StatusBar:
    def __init__(self, height: float = 26.0, icon_manager=None) -> None:
        self.height = height
        self.icon_mgr = icon_manager
        self.last_key_text: str = "-"
        self.last_event_text: str = "Komut bekleniyor..."
        self.selection_text: str = "Seçim: Yok"

    # ------------------------------------------------------------------
    def notify_key(self, key: int, action: int, mods: int) -> None:
        if action == 1:
            self.last_key_text = f"Key:{key} (mods:{mods})"
            self.last_event_text = f"Tuş basıldı -> {key}"

    def notify_command(self, text: str) -> None:
        self.last_event_text = text

    def notify_selection(self, selected: list) -> None:
        self.selection_text = _format_selection(selected)

    # ------------------------------------------------------------------
    def draw(self, app) -> None:
        viewport = imgui.get_main_viewport()
        bar_pos = _vec2(viewport.pos.x, viewport.pos.y + viewport.size.y - self.height)
        bar_size = _vec2(viewport.size.x, self.height)

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
        imgui.push_style_var(imgui.StyleVar_.window_padding, _vec2(10.0, 3.0))
        imgui.push_style_color(imgui.Col_.window_bg, _v4(0.10, 0.12, 0.16, 0.96))

        if imgui.begin("##StatusBar", None, flags):
            self._draw_left(app)
            imgui.same_line()
            self._draw_right(app)

        imgui.end()
        imgui.pop_style_color(1)
        imgui.pop_style_var(2)

    # ------------------------------------------------------------------
    def _draw_left(self, app) -> None:
        eng = app.engine
        inp = eng.input.state if eng is not None and eng.input is not None else None
        ucs_name = getattr(eng.input, "mouse_ucs_name", "Global") if (eng and eng.input) else "Global"
        ucs_pos = getattr(eng.input, "mouse_ucs_pos", None) if (eng and eng.input) else None

        if ucs_pos is not None:
            ux, uy, uz = ucs_pos
            ucs_text = f"{ucs_name}: ({ux:8.1f}, {uy:8.1f}, {uz:6.1f})"
            ucs_color = _v4(0.55, 0.90, 0.75)
        else:
            ucs_text = f"{ucs_name}: (-, -, -)"
            ucs_color = _v4(0.55, 0.58, 0.65)

        items: list[tuple[imgui.ImVec4, str]] = [
            (
                _v4(0.25, 0.88, 0.45) if eng is not None else _v4(0.92, 0.30, 0.30),
                "● Engine" if eng is not None else "● Engine: YOK",
            ),
            (_v4(0.85, 0.88, 0.94), self.last_event_text),
            (
                _v4(0.40, 0.85, 1.00) if self.selection_text != "Seçim: Yok" else _v4(0.60, 0.64, 0.72),
                self.selection_text,
            ),
            (ucs_color, ucs_text),
        ]
        for idx, (color, text) in enumerate(items):
            if idx > 0:
                imgui.same_line(spacing=10.0)
                imgui.text_disabled("│")
                imgui.same_line(spacing=10.0)
            imgui.text_colored(color, text)

    # ------------------------------------------------------------------
    def _draw_right(self, app) -> None:
        right_items = [
            self._icon_button("layout", "XY viewport", lambda: self._emit(app, cmd.OpenViewport("xy"))),
            self._icon_button("columns", "XZ viewport", lambda: self._emit(app, cmd.OpenViewport("xz"))),
            self._icon_button("sidebar", "YZ viewport", lambda: self._emit(app, cmd.OpenViewport("yz"))),
            self._icon_button("box", "Iso viewport", lambda: self._emit(app, cmd.OpenViewport("iso"))),
            "SEP",
            self._icon_button(
                "axes",
                "Global eksenler",
                lambda: self._emit(
                    app,
                    cmd.ToggleRenderFlag("global_axis", not bool(app.engine.show.get("global_axis", True))),
                ),
                active=lambda: bool(app.engine.show.get("global_axis", True)) if app.engine else False,
            ),
            self._icon_button(
                "crosshair",
                "Yerel eksenler",
                lambda: self._emit(app, cmd.ToggleLocalAxes()),
                active=lambda: bool(app.engine and app.engine.scene and app.engine.scene.show_local_axes),
            ),
            "SEP",
            self._icon_button(
                "loads",
                "Yük görünürlüğü",
                lambda: self._emit(
                    app,
                    cmd.ToggleLoadsVisible(not app.visibility_service.get_loads_visible()),
                ),
                active=lambda: bool(app.visibility_service.get_loads_visible()),
            ),
            "SEP",
            self._icon_button(
                "2d3d",
                "2D / 3D",
                lambda: self._emit(app, cmd.Toggle2D()),
                active=lambda: bool(
                    app.viewport_manager
                    and app.viewport_manager.active
                    and app.viewport_manager.active.is_2d
                ),
            ),
            self._icon_button(
                "render",
                "Render modu",
                lambda: self._emit(app, cmd.ToggleRenderMode()),
                active=lambda: False,
            ),
            "SEP",
        ]

        draw_list = imgui.get_window_draw_list()
        total_w = 0.0
        for item in right_items:
            total_w += _BTN_W + _PAD if item != "SEP" else 8.0
        unit_label = _format_unit_label(
            app.current_project.unit_system if app.current_project else None
        )
        unit_w = imgui.calc_text_size(unit_label).x + 14.0
        fps_text = "60.0 FPS"
        fps_w = imgui.calc_text_size(fps_text).x
        total_w += unit_w + 10.0 + 8.0 + 10.0 + fps_w

        avail = imgui.get_content_region_avail().x
        imgui.set_cursor_pos_x(imgui.get_cursor_pos_x() + max(0.0, avail - total_w))

        first = True
        for item in right_items:
            if not first:
                imgui.same_line(spacing=_PAD)
            first = False
            if item == "SEP":
                cur = imgui.get_cursor_screen_pos()
                y0 = cur.y + 2.0
                y1 = cur.y + _BTN_H - 2.0
                draw_list.add_line(_vec2(cur.x, y0), _vec2(cur.x, y1), imgui.get_color_u32(_v4(0.35, 0.38, 0.45)))
                imgui.dummy(_vec2(8.0, _BTN_H))
                continue
            item()

        imgui.same_line(spacing=10.0)
        self._unit_button(app, unit_label)
        imgui.same_line(spacing=10.0)
        imgui.text_disabled("│")
        imgui.same_line(spacing=10.0)
        imgui.text_disabled(fps_text)

    # ------------------------------------------------------------------
    def _emit(self, app, cmd) -> None:
        app.put_command(cmd)

    def _icon_button(
        self,
        icon: str,
        tooltip: str,
        on_click: Callable[[], None],
        active: Callable[[], bool] | None = None,
    ) -> Callable[[], None]:
        def _render() -> None:
            is_active = bool(active()) if active is not None else False
            pushed = 0
            if is_active:
                imgui.push_style_color(imgui.Col_.button, _v4(0.22, 0.42, 0.72, 1.0))
                imgui.push_style_color(imgui.Col_.button_hovered, _v4(0.28, 0.50, 0.82, 1.0))
                imgui.push_style_color(imgui.Col_.button_active, _v4(0.32, 0.56, 0.90, 1.0))
                pushed = 3
            tex = self._icon_texture(icon)
            imgui.push_id(f"sb_{icon}_{tooltip}")
            if tex is not None:
                clicked = imgui.image_button(
                    "##i", imgui.ImTextureRef(tex),
                    _vec2(16.0, 16.0), _vec2(0.0, 0.0), _vec2(1.0, 1.0),
                )
            else:
                clicked = imgui.button(tooltip[:2], _vec2(_BTN_W, _BTN_H))
            if imgui.is_item_hovered():
                imgui.set_tooltip(tooltip)
            if clicked:
                on_click()
            imgui.pop_id()
            if pushed:
                imgui.pop_style_color(pushed)
        return _render

    def _icon_texture(self, name: str) -> int | None:
        if self.icon_mgr is None:
            return None
        tex = self.icon_mgr.get_texture(name)
        return tex[0] if tex else None

    def _unit_button(self, app, unit_label: str) -> None:
        imgui.push_style_color(imgui.Col_.button, _v4(0.18, 0.24, 0.34, 1.0))
        imgui.push_style_color(imgui.Col_.button_hovered, _v4(0.24, 0.34, 0.48, 1.0))
        imgui.push_style_color(imgui.Col_.button_active, _v4(0.28, 0.40, 0.58, 1.0))
        imgui.push_style_var(imgui.StyleVar_.frame_padding, _vec2(7.0, 1.0))
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
            current = app.current_project.unit_system if app.current_project else None
            for unit in UnitSystem:
                selected = current == unit
                if imgui.menu_item(f"{_format_unit_label(unit)}##unit_{unit.name}", "", selected)[0]:
                    if not selected:
                        self._emit(app, cmd.SetUnitSystem(unit, reason="status_bar"))
            imgui.end_popup()