# ui/base/panel_base.py
from __future__ import annotations

from copy import deepcopy
from enum import StrEnum
from typing import Any

from imgui_bundle import imgui
from ui.helpers.apply_bar import draw_apply_bar


class Category(StrEnum):
    FILE = "File"
    EDIT = "Edit"
    DRAW = "Draw"
    VIEW = "View"
    LOADS = "Loads"
    MANAGEMENT = "Management"
    TOOLS = "Tools"


CATEGORY_ORDER: tuple[Category, ...] = tuple(Category)


class PanelBase:
    __abstract__ = True
    panel_name: str | None = None
    title: str = ""
    category: Category = Category.TOOLS
    quick: bool = False
    menu_label: str | None = None
    icon: str | None = None
    shortcut: str | None = None
    context: tuple[str, ...] = ()

    # ---- UI durumu ----
    app = None
    visible: bool = False
    width: int = 480
    height: int = 600
    pos_first_use: tuple[float, float] | None = None

    # ---- Draft/commit ----
    _original: Any = None
    draft: Any = None
    _dirty: bool = False
    uses_draft: bool = True
    show_apply_bar: bool = True
    preview_flags: dict[str, bool] | None = None

    # ---- Layout ----
    use_standard_layout: bool = False

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "panel_name" in cls.__dict__ and cls.__dict__["panel_name"]:
            cls.__abstract__ = False

    def __init__(self, app=None, **overrides):
        self.app = app
        self._preview_snapshot: dict[str, bool] | None = None
        for k, v in overrides.items():
            setattr(self, k, v)

    # ================================================================
    # Yaşam döngüsü
    # ================================================================
    def open(self, **kw) -> None:
        self.visible = True
        if self.uses_draft:
            self._refresh_draft()
        self._apply_preview(True)

    def close(self) -> None:
        self._apply_preview(False)
        self.visible = False
        self._original = None
        self.draft = None
        self._dirty = False

    # ================================================================
    # Context
    # ================================================================
    def set_context(self, ctx: dict) -> None:
        for key in self.context:
            if key in ctx:
                setattr(self, key, ctx[key])
        self._on_context_ready()
        self._refresh_draft()

    def _on_context_ready(self) -> None:
        """Alt sınıf override eder — context geldiğinde bir kez."""

    # ================================================================
    # Draft yönetimi
    # ================================================================
    def _refresh_draft(self) -> None:
        project = getattr(self.app, "current_project", None)
        if project is None:
            self._original = None
            self.draft = None
            self._dirty = False
            return
        self._original = project
        self.draft = deepcopy(project)
        self._dirty = False

    def reset(self) -> None:
        self._refresh_draft()

    # ================================================================
    # Apply
    # ================================================================
    def apply(self) -> bool:
        if not self._dirty or self.draft is None:
            return False
        try:
            self._emit_commands()
            return True
        except Exception:
            from logging_config import CadLogger
            CadLogger.get(__name__).exception(
                "[%s] apply hatası", self.panel_name
            )
            return False

    def _emit_commands(self) -> None:
        raise NotImplementedError

    # ================================================================
    # Draw — giriş noktası
    # ================================================================
    def draw(self) -> None:
        if not self.visible:
            return
        imgui.set_next_window_size(imgui.ImVec2(self.width, self.height),
                                   imgui.Cond_.first_use_ever)
        if self.pos_first_use:
            imgui.set_next_window_pos(imgui.ImVec2(*self.pos_first_use),
                                      imgui.Cond_.first_use_ever)

        win_id = f"{self.title}###{self.panel_name or id(self)}"
        expanded, opened = imgui.begin(win_id, True)
        try:
            if not opened:
                self.close()
                return
            if expanded:
                if self.uses_draft or self.show_apply_bar:
                    self._draw_apply_bar()
                    imgui.separator()
                self.draw_content()
        finally:
            imgui.end()

    def _draw_apply_bar(self) -> None:
        if self.uses_draft:
            draw_apply_bar(
                dirty=self._dirty,
                on_apply=self._on_apply_clicked,
                on_reset=self._on_reset_clicked,
            )
        else:
            dirty = bool(self.has_pending_changes())
            draw_apply_bar(
                dirty=dirty,
                on_apply=self._on_apply_clicked,
                on_reset=self._on_reset_clicked,
            )

    def has_pending_changes(self) -> bool:
        return False

    def _on_apply_clicked(self) -> None:
        if self.uses_draft:
            if self.apply():
                self._refresh_draft()
                ui = getattr(self.app, "ui", None)
                if ui is not None:
                    ui.on_panel_applied(self)
        else:
            self.on_apply_action()
            self._dirty = False

    def on_apply_action(self) -> None:
        pass

    def _on_reset_clicked(self) -> None:
        if self.uses_draft:
            self.reset()
        else:
            self.on_reset_action()

    def on_reset_action(self) -> None:
        pass

    # ================================================================
    # İçerik — iki mod: standart layout veya serbest draw_content
    # ================================================================
    def draw_content(self) -> None:
        if self.use_standard_layout:
            self.draw_standard_layout()
        # else: alt sınıf override eder (boş)

    # ================================================================
    # Standart Layout — Header / Settings / Visual / Table / Actions
    # ================================================================
    def draw_standard_layout(self) -> None:
        self.draw_header()
        imgui.separator()
        self.draw_settings()
        imgui.separator()

        if self._has_visual():
            self.draw_visual()
            imgui.separator()

        if self._has_table():
            self.draw_table()
            imgui.separator()

        self.draw_actions()

    def draw_header(self) -> None:
        """1. Seçili eleman özeti. Override eder."""

    def draw_settings(self) -> None:
        """2. Form alanları (enum, input). Override eder."""

    def draw_visual(self) -> None:
        """3. Görsel (canvas/plot). Opsiyonel — override etmezse atlanır."""

    def draw_table(self) -> None:
        """4. Tablo. Opsiyonel — override etmezse atlanır."""

    def draw_actions(self) -> None:
        """5. Alt butonlar ([UYGULA] [Temizle] [Yenile]). Override eder."""

    def _has_visual(self) -> bool:
        return type(self).draw_visual is not PanelBase.draw_visual

    def _has_table(self) -> bool:
        return type(self).draw_table is not PanelBase.draw_table

    # ================================================================
    # Layout yardımcıları — panellerin ortak kullandığı küçük parçalar
    # ================================================================
    def section_label(self, text: str) -> None:
        imgui.text_colored(imgui.ImVec4(0.7, 0.8, 0.9, 1.0), text)

    def action_button(
        self,
        label: str,
        width: int = 80,
        enabled: bool = True,
    ) -> bool:
        if not enabled:
            imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.3, 0.3, 0.3, 1.0))
        clicked = imgui.button(label, imgui.ImVec2(width, 0))
        if not enabled:
            imgui.pop_style_color()
        return clicked and enabled

    def status_line(self, text: str, kind: str = "info") -> None:
        if kind == "info":
            col = imgui.ImVec4(0.6, 0.8, 0.6, 1.0)
        elif kind == "warn":
            col = imgui.ImVec4(1.0, 0.6, 0.3, 1.0)
        elif kind == "error":
            col = imgui.ImVec4(1.0, 0.4, 0.4, 1.0)
        else:
            col = imgui.ImVec4(0.7, 0.7, 0.7, 1.0)
        imgui.text_colored(col, text)

    # ================================================================
    # Yardımcılar
    # ================================================================
    def mark_dirty(self) -> None:
        self._dirty = True

    def queue(self):
        return self.app.ui.command_queue

    def _apply_preview(self, active: bool) -> None:
        flags = self.preview_flags
        if not flags:
            return
        app = getattr(self, "app", None)
        eng = getattr(app, "engine", None) if app else None
        if eng is None:
            return

        if active:
            if self._preview_snapshot is None:
                self._preview_snapshot = {k: eng.show.get(k, True) for k in flags}
            for k, v in flags.items():
                eng.show[k] = bool(v)
        else:
            if self._preview_snapshot:
                for k, v in self._preview_snapshot.items():
                    eng.show[k] = v
                self._preview_snapshot = None

        if eng.renderer is not None and getattr(app, "current_project", None) is not None:
            eng.renderer.update_geo(eng.math_model)