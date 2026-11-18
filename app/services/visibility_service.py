# app/services/visibility_service.py
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.cad_app import CadApp


class VisibilityService:
    """show_only / hide / show_all — filtre state'i burada tutulur."""

    def __init__(self, app: "CadApp"):
        self.app = app
        self.show_only_ids: set[int] | None = None
        self.hidden_ids: set[int] | None = None

    def show_only(self, uids: list[int] | None) -> bool:
        self.show_only_ids = set(uids) if uids else None
        model = self._model()
        if model is None:
            return False
        if hasattr(model, "set_render_filter"):
            model.set_render_filter(self.show_only_ids)
        else:
            model._render_filter = self.show_only_ids
        return True

    def hide(self, uids: list[int]) -> bool:
        if self.hidden_ids is None:
            self.hidden_ids = set()
        self.hidden_ids.update(uids)
        model = self._model()
        if model is None:
            return False
        if hasattr(model, "set_hidden"):
            model.set_hidden(uids)
        else:
            for el in model.all_elements.values():
                if el.unique_id in self.hidden_ids:
                    if hasattr(el, "is_visible"):
                        el.is_visible = False
                    elif hasattr(el, "visible"):
                        el.visible = False
        return True

    def show_all(self) -> None:
        self.show_only_ids = None
        self.hidden_ids = None
        model = self._model()
        if model is None:
            return
        if hasattr(model, "set_render_filter"):
            model.set_render_filter(None)
        else:
            model._render_filter = None
        if hasattr(model, "set_all_visible"):
            model.set_all_visible(True)
        else:
            for el in model.all_elements.values():
                if hasattr(el, "is_visible"):
                    el.is_visible = True
                elif hasattr(el, "visible"):
                    el.visible = True

    def _model(self):
        eng = self.app.engine
        return eng.math_model if eng else None