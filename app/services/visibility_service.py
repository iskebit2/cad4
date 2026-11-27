# app/services/visibility_service.py
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.cad_app import CadApp


class VisibilityService:
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

    def unhide(self, uids: list[int]) -> bool:
        if not uids:
            return False
        if self.hidden_ids is not None:
            self.hidden_ids.difference_update(uids)
        model = self._model()
        if model is None:
            return False
        if hasattr(model, "set_visible"):
            model.set_visible(list(uids), True)
        else:
            for el in model.all_elements.values():
                if el.unique_id in uids:
                    if hasattr(el, "is_visible"):
                        el.is_visible = True
                    elif hasattr(el, "visible"):
                        el.visible = True
        return True
    
    def show_all(self) -> None:
        prev_hidden = self.hidden_ids or set()
        self.show_only_ids = None
        self.hidden_ids = None
        model = self._model()
        if model is None:
            return
        if hasattr(model, "set_render_filter"):
            model.set_render_filter(None)
        else:
            model._render_filter = None

        # ✅ Sadece bu servisin gizlediklerini geri aç
        if prev_hidden:
            if hasattr(model, "set_visible"):
                model.set_visible(list(prev_hidden), True)
            else:
                for el in model.all_elements.values():
                    if el.unique_id in prev_hidden:
                        if hasattr(el, "is_visible"):
                            el.is_visible = True
                        elif hasattr(el, "visible"):
                            el.visible = True

    def get_loads_visible(self) -> bool:
        eng = self.app.engine
        if eng is None:
            return False
        return bool(eng.show.get("loads", False))

    def set_loads_visible(self, enabled: bool) -> None:
        eng = self.app.engine
        if eng is None:
            return
        state = bool(enabled)
        eng.show["loads"] = state
        pres = getattr(eng, "presentation_renderer", None)
        if pres is not None:
            pres.loads.enabled = state
            if state and eng.math_model is not None:
                pres.update_loads(eng.math_model, camera_scale=1.0, scene_size=1.0)

    def toggle_loads_visible(self, enabled: bool | None = None) -> bool:
        target = (not self.get_loads_visible()) if enabled is None else bool(enabled)
        self.set_loads_visible(target)
        return target

    def _model(self):
        eng = self.app.engine
        return eng.math_model if eng else None