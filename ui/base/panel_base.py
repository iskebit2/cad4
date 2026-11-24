# ui/base/panel_base.py
from __future__ import annotations

from copy import deepcopy
from typing import Any

from imgui_bundle import imgui

from app.settings.categories import Category
from ui.helpers.apply_bar import draw_apply_bar


_STATUS_COLORS: dict[str, imgui.ImVec4] = {
    "info": imgui.ImVec4(0.6, 0.8, 0.6, 1.0),
    "warn": imgui.ImVec4(1.0, 0.6, 0.3, 1.0),
    "error": imgui.ImVec4(1.0, 0.4, 0.4, 1.0),
}
_DEFAULT_STATUS_COLOR = imgui.ImVec4(0.7, 0.7, 0.7, 1.0)


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

    app = None
    visible: bool = False
    width: int = 480
    height: int = 600
    pos_first_use: tuple[float, float] | None = None

    _original: Any = None
    draft: Any = None
    _dirty: bool = False
    uses_draft: bool = True
    show_apply_bar: bool = True
    preview_flags: dict[str, bool] | None = None

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

    def _resolve_project(self) -> Any:
        proj = getattr(self, "project", None)
        if proj is not None:
            return proj
        if self.app is None:
            return None
        current = getattr(self.app, "current_project", None)
        if current is not None:
            return current
        svc = getattr(self.app, "project_service", None)
        return getattr(svc, "project", None) if svc is not None else None

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

    def set_context(self, ctx: dict) -> None:
        for key in self.context:
            if key in ctx:
                setattr(self, key, ctx[key])
        self._on_context_ready()
        self._refresh_draft()

    def _on_context_ready(self) -> None:
        pass

    def _refresh_draft(self) -> None:
        if not self.uses_draft:
            self._original = None
            self.draft = None
            self._dirty = False
            return
        project = self._resolve_project()
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

    def apply(self) -> bool:
        if not self._dirty or self.draft is None:
            return False
        self._emit_commands()
        return True

    def _emit_commands(self) -> None:
        raise NotImplementedError

    def draw(self) -> None:
        if not self.visible:
            return
        imgui.set_next_window_size(
            imgui.ImVec2(self.width, self.height),
            imgui.Cond_.first_use_ever,
        )
        if self.pos_first_use:
            imgui.set_next_window_pos(
                imgui.ImVec2(*self.pos_first_use),
                imgui.Cond_.first_use_ever,
            )

        win_id = f"{self.title}###{self.panel_name or id(self)}"
        expanded, opened = imgui.begin(win_id, True)
        if not opened:
            imgui.end()
            self.close()
            return
        if expanded:
            if self.uses_draft or self.show_apply_bar:
                self._draw_apply_bar()
                imgui.separator()
            self.draw_content()
        imgui.end()

    def _draw_apply_bar(self) -> None:
        dirty = self._dirty if self.uses_draft else bool(self.has_pending_changes())
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
                if ui is not None and hasattr(ui, "on_panel_applied"):
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

    def draw_content(self) -> None:
        if self.use_standard_layout:
            self.draw_standard_layout()

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
        pass

    def draw_settings(self) -> None:
        pass

    def draw_visual(self) -> None:
        pass

    def draw_table(self) -> None:
        pass

    def draw_actions(self) -> None:
        pass

    def _has_visual(self) -> bool:
        return type(self).draw_visual is not PanelBase.draw_visual

    def _has_table(self) -> bool:
        return type(self).draw_table is not PanelBase.draw_table

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
        col = _STATUS_COLORS.get(kind, _DEFAULT_STATUS_COLOR)
        imgui.text_colored(col, text)

    def mark_dirty(self) -> None:
        self._dirty = True

    def queue(self):
        return getattr(self.app, "command_queue", None)

    def _apply_preview(self, active: bool) -> None:
        flags = self.preview_flags
        if not flags:
            return
        app = getattr(self, "app", None)
        eng = getattr(app, "engine", None) if app else None
        if eng is None:
            return

        show = getattr(eng, "show", None)
        if active:
            if self._preview_snapshot is None and isinstance(show, dict):
                self._preview_snapshot = {k: show.get(k, True) for k in flags}
            if isinstance(show, dict):
                for k, v in flags.items():
                    show[k] = bool(v)
        else:
            if self._preview_snapshot and isinstance(show, dict):
                for k, v in self._preview_snapshot.items():
                    show[k] = v
            self._preview_snapshot = None

        pipeline = getattr(eng, "pipeline", None)
        renderer = getattr(eng, "renderer", None) or getattr(pipeline, "renderer", None)
        math_model = getattr(eng, "math_model", None)
        if renderer is not None and self._resolve_project() is not None and math_model is not None:
            renderer.update_geo(math_model)