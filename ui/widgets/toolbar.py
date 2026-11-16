# ui/widgets/toolbar.py
from __future__ import annotations

from typing import Any, Callable

from imgui_bundle import imgui

from ui.widgets.icon_manager import IconManager


def _tex_ref(tex_id: int):
    return imgui.ImTextureRef(int(tex_id))


def _v4(r, g, b, a=1.0):
    return imgui.ImVec4(r, g, b, a)


def _vec2(x, y):
    return imgui.ImVec2(x, y)


class Toolbar:
    def __init__(
        self,
        commands: dict[str, Callable],
        panel_states: dict[str, Callable[[], bool]],
        specs: list[Any] | None = None,
        categories: list[str] | None = None,
        extra_menus=None,
    ) -> None:
        self.specs: list[Any] = list(specs or [])
        self.categories: list[str] = list(categories or [])
        self.commands = commands
        self.panel_states = panel_states
        self.icon_mgr = IconManager()
        self._extra_menus = list(extra_menus or [])
        self._ctx: dict[str, Any] = {"model_text": "", "current_unit": None, "project": None}
        self._pending_fires: list[tuple[str, tuple]] = []
        self._buckets = self._compose_buckets()

    def _compose_buckets(self) -> dict[str, list]:
        buckets: dict[str, list] = {}
        for spec in self.specs:
            cat = str(getattr(spec, "category", "") or "")
            if not cat:
                continue
            buckets.setdefault(cat, []).append(spec)
        return buckets

    def set_specs(self, specs: list[Any], categories: list[str] | None = None) -> None:
        self.specs = list(specs)
        if categories is not None:
            self.categories = list(categories)
        self._buckets = self._compose_buckets()

    def draw(self, model_text: str = "", current_unit=None, project=None) -> None:
        self._ctx = {"model_text": model_text, "current_unit": current_unit, "project": project}

        if imgui.begin_main_menu_bar():
            self._draw_menus()
            self._draw_quick_icons()
            self._draw_unit_selector()
            self._draw_model_label()
            imgui.end_main_menu_bar()

        fires, self._pending_fires = self._pending_fires, []
        for key, args in fires:
            fn = self.commands.get(key)
            if callable(fn):
                fn(*args)

    def _draw_menus(self) -> None:
        drawn: set[str] = set()
        for category in self.categories:
            items = self._buckets.get(category)
            if not items:
                continue
            if imgui.begin_menu(category):
                for spec in items:
                    self._draw_menu_item(spec)
                imgui.end_menu()
            drawn.add(category)

        for category, items in self._buckets.items():
            if category in drawn or not items:
                continue
            if imgui.begin_menu(category):
                for spec in items:
                    self._draw_menu_item(spec)
                imgui.end_menu()

        for title, callback in self._extra_menus:
            if imgui.begin_menu(title):
                callback()
                imgui.end_menu()

    def _draw_menu_item(self, spec: Any) -> None:
        name = getattr(spec, "name", "")
        label = getattr(spec, "menu_label", None) or name
        shortcut_text = getattr(spec, "shortcut", None) or ""
        active = self._state(name)

        tex = self._icon(getattr(spec, "icon", None))
        if tex is not None:
            imgui.image(_tex_ref(tex), _vec2(14, 14))
            imgui.same_line(spacing=6)

        clicked, _ = imgui.menu_item(label, shortcut_text, active)
        if clicked:
            self._pending_fires.append((name, ()))

    def _draw_quick_icons(self) -> None:
        quick = [s for s in self.specs if getattr(s, "quick", False)]
        if not quick:
            return

        imgui.separator()
        for spec in quick:
            name = getattr(spec, "name", "")
            label = getattr(spec, "menu_label", None) or name
            active = self._state(name)

            if active:
                imgui.push_style_color(imgui.Col_.button, _v4(0.22, 0.42, 0.72, 1.0))
                imgui.push_style_color(imgui.Col_.button_hovered, _v4(0.28, 0.50, 0.82, 1.0))
                imgui.push_style_color(imgui.Col_.button_active, _v4(0.32, 0.56, 0.90, 1.0))

            imgui.push_id(f"qb_{name}")
            tex = self._icon(getattr(spec, "icon", None))
            if tex is not None:
                if imgui.image_button("##i", _tex_ref(tex), _vec2(16, 16), _vec2(0, 0), _vec2(1, 1)):
                    self._pending_fires.append((name, ()))
            else:
                if imgui.button(label, _vec2(0, 20)):
                    self._pending_fires.append((name, ()))
            imgui.pop_id()

            if active:
                imgui.pop_style_color(3)

            if imgui.is_item_hovered():
                imgui.set_tooltip(label)
            imgui.same_line(spacing=2)

    def _state(self, key: str) -> bool:
        fn = self.panel_states.get(key)
        return bool(fn()) if callable(fn) else False

    def _icon(self, name: str | None) -> int | None:
        if not name:
            return None
        tex = self.icon_mgr.get_texture(name)
        return tex[0] if tex else None

    def _draw_unit_selector(self) -> None:
        from core.units import UnitSystem
        cu = self._ctx.get("current_unit")
        if isinstance(cu, str):
            cu = UnitSystem.from_sap(cu)
        label = f"Unit: {cu.name}" if cu else "Unit: N-mm"

        if imgui.begin_menu(label):
            for unit in UnitSystem:
                clicked, _ = imgui.menu_item(
                    f"{unit.name} ({unit.force_unit}, {unit.length_unit})",
                    "", cu == unit,
                )
                if clicked:
                    self._pending_fires.append(("on_unit_change", (unit,)))
            imgui.end_menu()

    def _draw_model_label(self) -> None:
        text = self._ctx.get("model_text") or ""
        if not text:
            return
        imgui.text_colored(_v4(0.60, 0.65, 0.72), text)