# app/toolbar.py
from __future__ import annotations

from imgui_bundle import imgui

from app.panel_registry import (
    CATEGORY_ORDER,
    PANEL_SPECS,
    WIDGET_SPECS,
    IconManager,
)
from logging_config import CadLogger

logger = CadLogger.get(__name__)


def _tex_ref(tex_id: int):
    try:
        return imgui.ImTextureRef(int(tex_id))
    except AttributeError:
        return int(tex_id)


def _v4(r, g, b, a=1.0):
    return imgui.ImVec4(r, g, b, a)


def _vec2(x, y):
    return imgui.ImVec2(x, y)


class Toolbar:
    HEIGHT = 32.0

    def __init__(self, commands, panel_states):
        self.panels = PANEL_SPECS
        self.categories = CATEGORY_ORDER
        self.widgets = WIDGET_SPECS
        self.commands = commands
        self.panel_states = panel_states
        self.icon_mgr = IconManager()

        self._ctx: dict = {"model_text": "", "current_unit": None}
        self._pending_fires: list[tuple[str, tuple]] = []

    # ==================================================================
    def draw(self, model_text: str = "", current_unit=None, project=None) -> None:
        self._ctx = {
            "model_text": model_text,
            "current_unit": current_unit,
            "project": project,
        }

        if imgui.begin_main_menu_bar():
            try:
                self._draw_registry_menus()
                self._draw_quick_icons()
                self._draw_widgets()
            finally:
                imgui.end_main_menu_bar()

        # KOMUTLARI MENÜ KAPANDIKTAN SONRA ÇALIŞTIR
        fires = self._pending_fires
        self._pending_fires = []
        for key, args in fires:
            self._run_command(key, args)

    def _run_command(self, key: str, args: tuple) -> None:
        fn = self.commands.get(key)
        if not callable(fn):
            return
        try:
            fn(*args)
        except Exception:
            logger.exception("[Toolbar] Command hatası: %s", key)

    def _fire_deferred(self, key: str, *args) -> None:
        self._pending_fires.append((key, args))

    # ==================================================================
    def _draw_registry_menus(self) -> None:
        buckets: dict[str, list[dict]] = {c: [] for c in self.categories}
        for spec in self.panels:
            buckets.setdefault(spec["category"], []).append(spec)

        for category in self.categories:
            items = buckets.get(category, [])
            if not items:
                continue

            opened = imgui.begin_menu(category)
            try:
                if opened:
                    for spec in items:
                        self._draw_menu_item(spec)
            finally:
                if opened:
                    imgui.end_menu()
            imgui.separator()

    def _draw_menu_item(self, spec: dict) -> None:
        label = spec.get("menu_label") or spec["name"]
        shortcut_text = spec.get("shortcut") or ""    # ← str zorunlu

        kind = spec.get("kind", "panel")
        active = bool(self._state(spec["name"]))

        tex = self._icon(spec.get("icon"))
        if tex is not None:
            imgui.image(_tex_ref(tex), _vec2(16, 16))
            imgui.same_line(spacing=6)

        highlight = (kind == "action" and active)
        if highlight:
            imgui.push_style_color(imgui.Col_.text, _v4(0.4, 0.9, 0.4))
        try:
            clicked, _ = imgui.menu_item(label, shortcut_text, active)   # ← None değil ""
            if clicked:
                self._fire_deferred(spec["name"])
        finally:
            if highlight:
                imgui.pop_style_color(1)

    # ==================================================================
    def _draw_quick_icons(self) -> None:
        quick = [s for s in self.panels if s.get("quick", False)]
        if not quick:
            return
        imgui.separator()
        for spec in quick:
            self._icon_button(
                scope=f"tb_{spec['name']}",
                icon_name=spec.get("icon"),
                fallback=spec.get("menu_label") or spec["name"],
                tooltip=spec.get("menu_label") or spec["name"],
                on_click=lambda n=spec["name"]: self._fire_deferred(n),
            )

    def _draw_widgets(self) -> None:
        for w in self.widgets:
            fn = w.get("render")
            if callable(fn):
                try:
                    fn(self)
                except Exception:
                    logger.exception("[Toolbar] Widget hatası: %s", w.get("name"))

    # ==================================================================
    def _icon_button(self, scope, *, icon_name=None, fallback="?", label="",
                     icon_size=(16, 16), tooltip="", base_color=None, on_click=None):
        styled = base_color is not None
        if styled:
            r, g, b, a = base_color
            imgui.push_style_color(imgui.Col_.button, _v4(r, g, b, a))
            imgui.push_style_color(imgui.Col_.button_hovered,
                                   _v4(min(r+0.08,1), min(g+0.08,1), min(b+0.08,1), a))
            imgui.push_style_color(imgui.Col_.button_active,
                                   _v4(min(r+0.15,1), min(g+0.15,1), min(b+0.15,1), a))
            imgui.push_style_var(imgui.StyleVar_.frame_rounding, 4.0)

        imgui.push_id(scope)
        clicked = False
        try:
            tex = self._icon(icon_name)
            if tex is not None:
                if imgui.image_button("##img", _tex_ref(tex),
                                      _vec2(*icon_size), _vec2(0, 0), _vec2(1, 1)):
                    clicked = True
                if label:
                    imgui.same_line(spacing=2)
                    if imgui.button(label):
                        clicked = True
            elif label:
                if imgui.button(label, _vec2(*icon_size)):
                    clicked = True
            else:
                text = (fallback or "?")[:3]
                if imgui.button(text, _vec2(*icon_size)):
                    clicked = True
        finally:
            imgui.pop_id()
            if styled:
                imgui.pop_style_var(1)
                imgui.pop_style_color(3)

        if tooltip and imgui.is_item_hovered():
            imgui.set_tooltip(tooltip)

        if clicked and callable(on_click):
            try:
                on_click()
            except Exception:
                logger.exception("[Toolbar] on_click hatası: %s", scope)
        return clicked

    # ==================================================================
    def _state(self, key):
        fn = self.panel_states.get(key)
        if not callable(fn):
            return False
        try:
            return bool(fn())
        except Exception:
            return False

    def _icon(self, name):
        if not name:
            return None
        try:
            tex = self.icon_mgr.get_texture(name)
            return tex[0] if tex else None
        except Exception:
            return None

    # ==================================================================
    def _render_unit_selector(self) -> None:
        from core.units import UnitSystem
        cu = self._ctx.get("current_unit")
        if isinstance(cu, str):
            cu = UnitSystem.from_sap(cu)
        label = f"Birim: {cu.name}" if cu else "Birim: N-mm"

        opened = imgui.begin_menu(label)
        try:
            if opened:
                for unit in UnitSystem:
                    clicked, _ = imgui.menu_item(
                        f"{unit.name} ({unit.force_unit}, {unit.length_unit})",
                        "", cu == unit,             # ← None değil ""
                    )
                    if clicked:
                        self._fire_deferred("on_unit_change", unit)
        finally:
            if opened:
                imgui.end_menu()

    def _render_model_label(self) -> None:
        text = self._ctx.get("model_text") or ""
        if not text:
            return

        imgui.text_colored(_v4(0.60, 0.65, 0.72), text)
        if imgui.is_item_hovered() and imgui.is_mouse_clicked(0):
            self._print_project_summary()

    def _print_project_summary(self) -> None:
        """Projenin özetini terminale bas. `_ctx` içinden project al."""
        project = self._ctx.get("project")
        if project is None:
            print("[summary] project yok")
            return
        try:
            if hasattr(project, "summary"):
                print(project.summary())
            else:
                print(project)
                if hasattr(project, "scene"):
                    print(project.scene)
        except Exception as e:
            print(f"[summary] hata: {e}")