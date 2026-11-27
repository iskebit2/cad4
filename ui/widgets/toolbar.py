# ui/widgets/toolbar.py
from __future__ import annotations

from typing import Any, Callable

from imgui_bundle import imgui

import app.commands as cmd
from app.services.toolbar_builder import ToolbarBuilder, UnifiedSpec
from app.settings.categories import category_label
from core.units import UnitSystem
from ui.widgets.icon_manager import IconManager


def _v4(r: float, g: float, b: float, a: float = 1.0) -> imgui.ImVec4:
    return imgui.ImVec4(r, g, b, a)


def _vec2(x: float, y: float) -> imgui.ImVec2:
    return imgui.ImVec2(x, y)


class Toolbar:
    def __init__(
        self,
        put_command: Callable[[Any], None],
        builder: ToolbarBuilder,
        app_getter: Callable[[], Any] | None = None,
        extra_menus: list[tuple[str, Callable[[], None]]] | None = None,
    ) -> None:
        self._put = put_command
        self._builder = builder
        self._app_getter = app_getter
        self._extra_menus: list[tuple[str, Callable[[], None]]] = list(extra_menus or [])
        self.icon_mgr = IconManager()
        self._specs: list[UnifiedSpec] = []
        self._by_key: dict[str, UnifiedSpec] = {}
        self._by_category: dict[str, list[UnifiedSpec]] = {}
        self._tex_cache: dict[str, int | None] = {}
        self._menu_bar_height: float = 0.0
        self._quick_bar_height: float = 34.0
        self._rebuild()

    @property
    def total_height(self) -> float:
        return self._menu_bar_height + self._quick_bar_height

    def _rebuild(self) -> None:
        self._specs = self._builder.build()
        self._by_key = {s.key: s for s in self._specs}
        self._by_category = {}
        for s in self._specs:
            self._by_category.setdefault(s.category, []).append(s)

        self._tex_cache.clear()
        for s in self._specs:
            # print(s)
            if s.icon and s.icon not in self._tex_cache:
                tex = self.icon_mgr.get_texture(s.icon)
                self._tex_cache[s.icon] = tex[0] if tex else None

    def refresh(self) -> None:
        self._rebuild()

    def _fire(self, key: str) -> None:
        spec = self._by_key.get(key)
        if spec is None:
            return
        if spec.is_panel and spec.panel_name:
            self._put(cmd.TogglePanel(spec.panel_name))
            return
        if spec.cmd is not None:
            self._put(spec.cmd)

    def draw(self, model_text: str = "", current_unit=None, project=None) -> None:
        self._draw_main_menu_bar(model_text=model_text, current_unit=current_unit)
        self._draw_quick_bar()

    def _draw_main_menu_bar(self, model_text: str = "", current_unit=None) -> None:
        if not imgui.begin_main_menu_bar():
            return

        self._menu_bar_height = imgui.get_window_size().y
        layout = self._builder.layout_store.load()
        extra_map = {name: fn for name, fn in self._extra_menus}

        rendered_categories: set[str] = set()
        for category in layout.category_order:
            items = self._by_category.get(category, [])
            extra_drawer = extra_map.pop(category, None)
            if not items and extra_drawer is None:
                continue

            rendered_categories.add(category)
            title = layout.category_labels.get(category, category_label(category))
            if imgui.begin_menu(f"{title}##cat_{category}"):
                for spec in items:
                    self._draw_menu_item(spec)
                if items and extra_drawer is not None:
                    imgui.separator()
                if extra_drawer is not None:
                    extra_drawer()
                imgui.end_menu()

        for category, items in self._by_category.items():
            if category in rendered_categories or not items:
                continue
            title = layout.category_labels.get(category, category_label(category))
            if imgui.begin_menu(f"{title}##cat_{category}"):
                for spec in items:
                    self._draw_menu_item(spec)
                imgui.end_menu()

        for name, extra_drawer in extra_map.items():
            title = layout.category_labels.get(name, category_label(name))
            if imgui.begin_menu(f"{title}##extra_{name}"):
                extra_drawer()
                imgui.end_menu()

        self._draw_right_status(model_text=model_text, current_unit=current_unit)
        imgui.end_main_menu_bar()

    def _draw_menu_item(self, spec: UnifiedSpec) -> None:
        active = self._is_active(spec)
        clicked, _ = imgui.menu_item(
            f"{spec.label}##mi_{spec.key}",
            spec.shortcut or "",
            active,
        )
        if clicked:
            self._fire(spec.key)

    def _draw_right_status(self, model_text: str, current_unit) -> None:
        unit_label = getattr(current_unit, "label", None) or (str(current_unit) if current_unit else "Unit")
        right_text = f"{model_text}  |  {unit_label}" if model_text else unit_label
        text_w = imgui.calc_text_size(right_text).x + 28.0
        avail = imgui.get_content_region_avail().x
        if avail > text_w:
            imgui.same_line(spacing=avail - text_w)

        if imgui.begin_menu(f"{unit_label}##unit_menu"):
            for unit in UnitSystem:
                u_lbl = getattr(unit, "label", unit.name)
                if imgui.menu_item(u_lbl, "", current_unit == unit)[0]:
                    self._put(cmd.SetUnitSystem(unit))
            imgui.end_menu()

        if model_text:
            imgui.same_line(spacing=10.0)
            imgui.text_disabled(model_text)

    def _draw_quick_bar(self) -> None:
        quick_specs = [s for s in self._specs if s.quick]
        if not quick_specs:
            self._quick_bar_height = 0.0
            return

        self._quick_bar_height = 34.0
        viewport = imgui.get_main_viewport()
        bar_pos = _vec2(viewport.pos.x, viewport.pos.y + self._menu_bar_height)
        bar_size = _vec2(viewport.size.x, self._quick_bar_height)

        imgui.set_next_window_pos(bar_pos)
        imgui.set_next_window_size(bar_size)

        flags = (
            imgui.WindowFlags_.no_title_bar
            | imgui.WindowFlags_.no_resize
            | imgui.WindowFlags_.no_move
            | imgui.WindowFlags_.no_scrollbar
            | imgui.WindowFlags_.no_scroll_with_mouse
            | imgui.WindowFlags_.no_collapse
            | imgui.WindowFlags_.no_saved_settings
            | imgui.WindowFlags_.no_docking
        )

        imgui.push_style_var(imgui.StyleVar_.window_rounding, 0.0)
        imgui.push_style_var(imgui.StyleVar_.window_border_size, 1.0)
        imgui.push_style_var(imgui.StyleVar_.window_padding, _vec2(8.0, 4.0))
        imgui.push_style_var(imgui.StyleVar_.item_spacing, _vec2(4.0, 4.0))
        imgui.push_style_color(imgui.Col_.window_bg, _v4(0.12, 0.14, 0.18, 0.98))

        if imgui.begin("##QuickToolbar", None, flags):
            last_category: str | None = None
            first = True
            for spec in quick_specs:
                if not first and spec.category != last_category:
                    imgui.same_line(spacing=4.0)
                    imgui.text_disabled("│")
                    imgui.same_line(spacing=4.0)
                elif not first:
                    imgui.same_line(spacing=2.0)
                first = False
                last_category = spec.category
                self._draw_button(spec)

        imgui.end()
        imgui.pop_style_color(1)
        imgui.pop_style_var(4)

    def _draw_button(self, spec: UnifiedSpec) -> None:
        active = self._is_active(spec)
        pushed = 0
        if active:
            imgui.push_style_color(imgui.Col_.button, _v4(0.22, 0.42, 0.72))
            imgui.push_style_color(imgui.Col_.button_hovered, _v4(0.28, 0.50, 0.82))
            imgui.push_style_color(imgui.Col_.button_active, _v4(0.32, 0.56, 0.90))
            pushed = 3

        imgui.push_id(f"tb_{spec.key}")
        tex = self._tex_cache.get(spec.icon)
        if tex is not None:
            clicked = imgui.image_button(
                "##i", imgui.ImTextureRef(tex),
                _vec2(20.0, 20.0), _vec2(0.0, 0.0), _vec2(1.0, 1.0),
            )
        else:
            clicked = imgui.button(spec.label[:2] or "?", _vec2(28.0, 24.0))

        if imgui.is_item_hovered():
            tip = spec.tooltip
            if spec.shortcut:
                tip = f"{tip}  ({spec.shortcut})"
            imgui.set_tooltip(tip)

        if clicked:
            self._fire(spec.key)

        imgui.pop_id()
        if pushed:
            imgui.pop_style_color(pushed)

    def _is_active(self, spec: UnifiedSpec) -> bool:
        if spec.is_panel and spec.panel_name:
            return self._builder.panel_registry.is_visible(spec.panel_name)
        if callable(spec.check_state):
            app = self._app_getter() if self._app_getter else None
            return bool(spec.check_state(app))
        return False