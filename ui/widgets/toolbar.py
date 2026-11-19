# ui/widgets/toolbar.py
from __future__ import annotations

from typing import Any, Callable

from imgui_bundle import imgui

from app.services.toolbar_builder import (
    UnifiedSpec, build_unified_specs, group_by_category, CATEGORY_ORDER,
)
from app.services.toolbar_specs import CommandSpec
from ui.widgets.icon_manager import IconManager


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def _tex_ref(tex_id: int):
    return imgui.ImTextureRef(int(tex_id))


def _v4(r, g, b, a=1.0):
    return imgui.ImVec4(r, g, b, a)


def _vec2(x, y):
    return imgui.ImVec2(x, y)


# IconManager'da olmayan/eksik olan anahtarlar için Unicode fallback.
# assets/icons_base64.py'nizde bu isimler varsa kullanılmaz.
_FALLBACK_GLYPHS = {
    "file-new":   "🗋",
    "folder-open":"📂",
    "save":       "💾",
    "save-as":    "💾+",
    "import":     "⬇",
    "export":     "⬆",
    "quit":       "⏻",
    "undo":       "↩",
    "redo":       "↪",
    "trash":      "🗑",
    "deselect":   "⨯",
    "fit":        "⛶",
    "fit-sel":    "🎯",
    "2d3d":       "◫",
    "axes":       "✛",
    "loads":      "⇣",
    "render":     "◐",
    "line-draw":  "╱",
    "poly-draw":  "⬡",
    "plane-draw": "▱",
    "plane-3pt":  "△",
    "plane-2ptz": "◺",
    "to-link":    "⇄",
    "log-in":     "☰",
    "⌨":          "⌨",
    "grid":       "▦",
    "wind":       "🌪",
    "s2k":        "📄",
    "inspector":  "🔎",
}


# ---------------------------------------------------------------------------
class Toolbar:
    """Menü + quick icon bar. Panel ve komutları tek arayüzde toplar."""

    def __init__(
        self,
        put_command: Callable[[Any], None],
        panel_registry,
        extra_commands: list[CommandSpec] | None = None,
        extra_menus: list[tuple[str, Callable]] | None = None,
        app_getter: Callable[[], Any] | None = None,
    ) -> None:
        self._put = put_command
        self._registry = panel_registry
        self._extra_commands = extra_commands
        self._extra_menus = list(extra_menus or [])
        self._app_getter = app_getter

        self.icon_mgr = IconManager()

        self._specs: list[UnifiedSpec] = []
        self._buckets: dict[str, list[UnifiedSpec]] = {}
        self._by_key: dict[str, UnifiedSpec] = {}
        self._tex_cache: dict[str, int | None] = {}   # icon key → tex id (None = yok)
        self._shortcut_map: list[tuple[UnifiedSpec, tuple]] = []

        self._rebuild()

        self._ctx: dict[str, Any] = {
            "model_text": "", "current_unit": None, "project": None,
        }
        self._pending: list[str] = []

    # --- spec yönetimi -----------------------------------------------------
    def _rebuild(self) -> None:
        if self._extra_commands is None:
            # İlk seferde oluştur, sonra cache'le. App her seferinde yeniden
            # örnek yaratmaz; toggle komutları stateless.
            from app.services.toolbar_specs import default_commands
            self._extra_commands = default_commands()

        self._specs = build_unified_specs(self._registry, self._extra_commands)
        self._buckets = group_by_category(self._specs)
        self._by_key = {s.key: s for s in self._specs}

        # Icon texture cache (bir kez)
        self._tex_cache.clear()
        for s in self._specs:
            self._tex_cache[s.icon] = None if not s.icon else self._resolve_icon(s.icon)

        # Kısayol map: (spec, (need_ctrl, need_shift, need_alt, Key)) — bir kez
        self._shortcut_map.clear()
        for s in self._specs:
            parsed = _parse_shortcut(s.shortcut)
            if parsed is not None:
                self._shortcut_map.append((s, parsed))

    def refresh(self) -> None:
        self._rebuild()

    def _resolve_icon(self, name: str) -> int | None:
        tex = self.icon_mgr.get_texture(name)
        return tex[0] if tex else None

    def _icon(self, name: str | None) -> int | None:
        if not name:
            return None
        return self._tex_cache.get(name)

    # --- ana çizim --------------------------------------------------------
    def draw(self, model_text: str = "", current_unit=None, project=None) -> None:
        self._ctx = {"model_text": model_text, "current_unit": current_unit, "project": project}

        if imgui.begin_main_menu_bar():
            self._draw_menus()
            self._draw_quick_icons()
            self._draw_unit_selector()
            self._draw_model_label()
            imgui.end_main_menu_bar()

        fires = self._pending
        self._pending = []
        for key in fires:
            self._fire(key)

    # --- fire ---------------------------------------------------------------
    def _fire(self, key: str) -> None:
        spec = self._by_key.get(key)
        if spec is None:
            return
        if spec.is_panel:
            from app.commands import project_commands as PC
            self._put(PC.TogglePanel(spec.panel_name))
        else:
            self._put(spec.cmd)

    # --- menü --------------------------------------------------------------
    def _draw_menus(self) -> None:
        drawn: set[str] = set()
        for category in CATEGORY_ORDER:
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

    def _draw_menu_item(self, spec: UnifiedSpec) -> None:
        active = self._is_active(spec)

        # NOT: menü içinde image() kullanmak layout'u bozar — sadece glif.
        glyph = _FALLBACK_GLYPHS.get(spec.icon, "")
        label = f"{glyph}  {spec.label}" if glyph else spec.label
        clicked, _ = imgui.menu_item(label, spec.shortcut, active)
        if clicked:
            self._pending.append(spec.key)

    # --- quick icon bar ----------------------------------------------------
    def _draw_quick_icons(self) -> None:
        quick = [s for s in self._specs if s.quick]
        if not quick:
            return

        imgui.separator()

        last_cat = None
        first = True
        for spec in quick:
            if not first:
                imgui.same_line(spacing=2)
            first = False

            if last_cat is not None and spec.category != last_cat:
                imgui.same_line(spacing=6)
                imgui.text_disabled("│")
                imgui.same_line(spacing=6)
            last_cat = spec.category

            self._draw_icon_button(spec)

    def _draw_icon_button(self, spec: UnifiedSpec) -> None:
        active = self._is_active(spec)
        pushed = 0
        if active:
            imgui.push_style_color(imgui.Col_.button,         _v4(0.22, 0.42, 0.72, 1.0))
            imgui.push_style_color(imgui.Col_.button_hovered, _v4(0.28, 0.50, 0.82, 1.0))
            imgui.push_style_color(imgui.Col_.button_active,  _v4(0.32, 0.56, 0.90, 1.0))
            pushed = 3

        imgui.push_id(f"tb_{spec.key}")
        try:
            tex = self._icon(spec.icon)
            clicked = False
            if tex is not None:
                clicked = imgui.image_button(
                    "##i", _tex_ref(tex), _vec2(18, 18), _vec2(0, 0), _vec2(1, 1),
                )
            else:
                glyph = _FALLBACK_GLYPHS.get(spec.icon) or (spec.label[:1] or "?")
                clicked = imgui.button(glyph, _vec2(24, 22))

            if imgui.is_item_hovered():
                tip = spec.tooltip
                if spec.shortcut:
                    tip = f"{tip}  ({spec.shortcut})"
                imgui.set_tooltip(tip)

            if clicked:
                self._pending.append(spec.key)
        finally:
            imgui.pop_id()
            if pushed:
                imgui.pop_style_color(pushed)

    # --- durum -------------------------------------------------------------
    def _is_active(self, spec: UnifiedSpec) -> bool:
        if spec.is_panel:
            return bool(self._registry.is_visible(spec.panel_name))
        if callable(spec.check_state):
            app = self._app_getter() if self._app_getter else self._ctx.get("app")
            try:
                return bool(spec.check_state(app))
            except Exception:
                return False
        return False

    # --- birim -------------------------------------------------------------
    def _draw_unit_selector(self) -> None:
        from core.units import UnitSystem
        cu = self._ctx.get("current_unit")
        if isinstance(cu, str):
            try:
                cu = UnitSystem.from_sap(cu)
            except Exception:
                cu = None
        label = f"Unit: {cu.name}" if cu else "Unit: N-mm"

        if imgui.begin_menu(label):
            for unit in UnitSystem:
                clicked, _ = imgui.menu_item(
                    f"{unit.name} ({unit.force_unit}, {unit.length_unit})",
                    "", cu == unit,
                )
                if clicked:
                    from app.commands import project_commands as PC
                    self._put(PC.SetUnitSystem(unit, reason="toolbar"))
            imgui.end_menu()

    def _draw_model_label(self) -> None:
        text = self._ctx.get("model_text") or ""
        if not text:
            return
        imgui.text_colored(_v4(0.60, 0.65, 0.72), text)

    # --- klavye kısayolları ------------------------------------------------
    def handle_shortcuts(self) -> None:
        """Global kısayol yakalama. CadApp update döngüsünde çağırın."""
        io = imgui.get_io()
        if io.want_text_input:
            return

        ctrl = io.key_ctrl
        shift = io.key_shift
        alt = io.key_alt

        for spec, (need_ctrl, need_shift, need_alt, key) in self._shortcut_map:
            if need_ctrl != ctrl or need_shift != shift or need_alt != alt:
                continue
            if imgui.is_key_pressed(key, False):
                self._pending.append(spec.key)
                return


# ---------------------------------------------------------------------------
# Kısayol eşleme (bir kez parse, cache'lenir)
# ---------------------------------------------------------------------------
_KEY_TABLE = {
    "Del":  imgui.Key.delete,
    "Esc":  imgui.Key.escape,
    "F1":   imgui.Key.f1, "F2": imgui.Key.f2, "F3": imgui.Key.f3,
    "F4":   imgui.Key.f4, "F5": imgui.Key.f5, "F6": imgui.Key.f6,
    "F7":   imgui.Key.f7, "F8": imgui.Key.f8, "F9": imgui.Key.f9,
    "F10":  imgui.Key.f10, "F11": imgui.Key.f11, "F12": imgui.Key.f12,
    "F": imgui.Key.f, "L": imgui.Key.l, "P": imgui.Key.p,
    "T": imgui.Key.t, "Y": imgui.Key.y, "N": imgui.Key.n,
    "O": imgui.Key.o, "S": imgui.Key.s, "Z": imgui.Key.z,
    "E": imgui.Key.e, "D": imgui.Key.d, "R": imgui.Key.r,
    "G": imgui.Key.g, "H": imgui.Key.h, "C": imgui.Key.c, "V": imgui.Key.v,
}


def _parse_shortcut(shortcut: str) -> tuple[bool, bool, bool, int] | None:
    """'Ctrl+Shift+S' → (True, True, False, Key.s). Geçersizse None."""
    if not shortcut:
        return None
    parts = [p.strip() for p in shortcut.split("+") if p.strip()]
    if not parts:
        return None
    key_name = parts[-1]
    need_ctrl = "Ctrl" in parts[:-1]
    need_shift = "Shift" in parts[:-1]
    need_alt = "Alt" in parts[:-1]

    # Hem büyük hem küçük harf dene: kullanıcı 'Ctrl+s' de yazabilir
    key = _KEY_TABLE.get(key_name) or _KEY_TABLE.get(key_name.upper())
    if key is None:
        return None
    return need_ctrl, need_shift, need_alt, key