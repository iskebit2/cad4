# app/toolbar.py
"""
ImGui Toolbar — tamamen registry-driven.

Toolbar hiçbir menü/aksiyon/widget adını bilmez. PANEL_SPECS ve
WIDGET_SPECS'i sırayla döner, callback'ler üzerinden davranır.
"""
from typing import Callable, Dict, List, Optional, Tuple
import imgui

from app.panel_registry import (
    IconManager, PANEL_SPECS, CATEGORY_ORDER, WIDGET_SPECS,
)


class Toolbar:
    HEIGHT = 32.0

    def __init__(
        self,
        commands: Dict[str, Callable],
        panel_states: Dict[str, Callable],
    ):
        self.panels = PANEL_SPECS
        self.categories = CATEGORY_ORDER
        self.widgets = WIDGET_SPECS
        self.commands = commands
        self.panel_states = panel_states
        self.icon_mgr = IconManager()

    # ==================================================================
    def draw(self, model_text: str = "", current_unit=None):
        # current_unit & model_text widget render'larına taşınır
        self._ctx = {"model_text": model_text, "current_unit": current_unit}
        if imgui.begin_main_menu_bar():
            self._draw_registry_menus()
            self._draw_quick_icons()
            self._draw_widgets()
            imgui.text("Test: → ← ≤ ≥ ✓ ✗ ⚙ ▲ ▼ ● ○ ☀ ⚠ ℃ α β Δ ³ ₂ ▶ ◀ ▴ ▾ ▸ ◂")
            imgui.end_main_menu_bar()

    # ==================================================================
    def _draw_registry_menus(self):
        buckets: Dict[str, List[dict]] = {c: [] for c in self.categories}
        for spec in self.panels:
            buckets.setdefault(spec["category"], []).append(spec)

        for category in self.categories:
            items = buckets.get(category, [])
            if not items:
                continue
            if imgui.begin_menu(category):
                for spec in items:
                    self._draw_menu_item(spec)
                imgui.end_menu()
            imgui.separator()      # kategoriler arası görsel ayırıcı

    def _draw_menu_item(self, spec: dict):
        label = spec.get("menu_label") or spec["name"]
        if spec.get("shortcut"):
            label = f"{label} ({spec['shortcut']})"

        kind = spec.get("kind", "panel")
        active = bool(self._state(spec["name"]))

        # İkon (varsa)
        tex = self.icon_mgr.get_texture(spec.get("icon")) if spec.get("icon") else None
        if tex:
            tex_id, _, _ = tex
            imgui.image(tex_id, 16, 16)
            imgui.same_line(spacing=6)

        if kind == "action" and active:
            imgui.push_style_color(imgui.COLOR_TEXT, 0.4, 0.9, 0.4, 1.0)

        if imgui.menu_item(label, selected=active)[0]:
            self._fire(spec["name"])

        if kind == "action" and active:
            imgui.pop_style_color(1)

    # ==================================================================
    def _draw_quick_icons(self):
        quick = [s for s in self.panels if s.get("quick", False)]
        if not quick:
            return
        imgui.separator()
        for spec in quick:
            self._button(
                f"tb_{spec['name']}",
                icon_name=spec.get("icon"),
                tooltip=spec.get("menu_label") or spec["name"],
                on_click=lambda n=spec["name"]: self._fire(n),
            )

    # ==================================================================
    def _draw_widgets(self):
        for w in self.widgets:
            render = w.get("render")
            if callable(render):
                render(self)

    # ==================================================================
    # Tek tip buton (önceki cevaptan aynı, değişmedi)
    # ==================================================================
    def _button(self, scope: str, *, label="", icon_name=None,
                icon_size=(16, 16), tooltip="", base_color=None,
                on_click=None) -> bool:
        styled = base_color is not None
        if styled:
            r, g, b, a = base_color
            hovered = (min(r + 0.08, 1.0), min(g + 0.08, 1.0),
                       min(b + 0.08, 1.0), a)
            active = (min(r + 0.15, 1.0), min(g + 0.15, 1.0),
                      min(b + 0.15, 1.0), a)
            imgui.push_style_color(imgui.COLOR_BUTTON, *base_color)
            imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, *hovered)
            imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, *active)
            imgui.push_style_var(imgui.STYLE_FRAME_ROUNDING, 4.0)

        imgui.push_id(scope)
        clicked = False
        tex = self.icon_mgr.get_texture(icon_name) if icon_name else None

        if tex:
            tex_id, _, _ = tex
            if imgui.image_button(tex_id, icon_size[0], icon_size[1],
                                  (0, 0), (1, 1)):
                clicked = True
            if label:
                imgui.same_line(spacing=2)
                if imgui.button(label):
                    clicked = True
        elif label:
            if imgui.button(label):
                clicked = True
        else:
            if imgui.button("##no_label"):
                clicked = True

        imgui.pop_id()

        if styled:
            imgui.pop_style_var(1)
            imgui.pop_style_color(3)
        if tooltip and imgui.is_item_hovered():
            imgui.set_tooltip(tooltip)
        if clicked and callable(on_click):
            on_click()
        return clicked

    # ==================================================================
    def _state(self, key: str) -> bool:
        fn = self.panel_states.get(key)
        return bool(fn()) if callable(fn) else False

    def _fire(self, key: str):
        fn = self.commands.get(key)
        if callable(fn):
            fn()

    # ==================================================================
    # Widget render'ları (WIDGET_SPECS'ten çağrılır)
    # ==================================================================
    def _render_unit_selector(self):
        """Birim seçici — widget olarak çağrılır."""
        from data.enums import UnitSystem
        cu = self._ctx.get("current_unit")
        label = f"Birim: {cu.name}" if cu else "Birim: N-mm"
        if imgui.begin_menu(label):
            for unit in UnitSystem:
                if imgui.menu_item(
                    f"{unit.name} ({unit.force_unit}, {unit.length_unit})",
                    selected=(cu == unit),
                )[0]:
                    fn = self.commands.get("on_unit_change")
                    if callable(fn):
                        fn(unit)
            imgui.end_menu()

    def _render_model_label(self):
        text = self._ctx.get("model_text") or ""
        if text:
            imgui.text_colored(text, 0.60, 0.65, 0.72, 1.00)

    