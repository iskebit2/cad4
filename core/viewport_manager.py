# core/viewport_manager.py
from __future__ import annotations

from logging_config import CadLogger
from core.viewport import Viewport

logger = CadLogger.get(__name__)


class ViewportManager:
    """Eşit viewport'lar. "Ana" yok. Tüm viewport'lar `engine` renderer'larını paylaşır."""

    def __init__(self, engine):
        self.engine = engine
        self.viewports: dict[str, Viewport] = {}
        self.active_name: str | None = None
        self._counter = 0

    # ------------------------------------------------------------------
    def create_viewport(self, name=None, width=640, height=480,
                    preset: str | None = None, plane=None) -> Viewport:
        if name is None:
            self._counter += 1
            name = f"Viewport {self._counter}"
        if name in self.viewports:
            raise ValueError(f"Viewport zaten var: {name}")
        vp = Viewport(name=name, width=width, height=height)
        if preset:
            vp.camera.set_view_preset(preset)
        vp.plane = plane
        eng = self.engine
        if eng is not None:
            b = eng._combined_bounds()
            if b is not None:
                vp.camera.update_bounds(b.center, b.size)
                vp.camera.focus_on_model()
        self.viewports[name] = vp
        if self.active_name is None:
            self.active_name = name
        logger.debug("[ViewportManager] create: %s preset=%s", name, preset)
        return vp

    def next_name(self, base: str) -> str:
        """'top 2', 'top 3' gibi çakışmayan isim üretir."""
        if base not in self.viewports:
            return base
        n = 1
        while f"{base} {n}" in self.viewports:
            n += 1
        return f"{base} {n}"

    def remove_viewport(self, name: str) -> bool:
        vp = self.viewports.pop(name, None)
        if vp is None:
            return False
        renderer = getattr(self.engine, "renderer", None)
        if renderer is not None:
            renderer.remove_viewport(name)
        vp.cleanup()
        if self.active_name == name:
            self.active_name = next(iter(self.viewports), None)
        logger.debug("[ViewportManager] remove: %s", name)
        return True

    def get(self, name: str) -> Viewport | None:
        return self.viewports.get(name)

    @property
    def active(self) -> Viewport | None:
        if self.active_name is None:
            return None
        return self.viewports.get(self.active_name)

    def set_active(self, name: str) -> None:
        if name in self.viewports:
            self.active_name = name

    # ------------------------------------------------------------------
    def _ensure_visible_ids(self, vp) -> None:
        if not getattr(vp, "_visible_ids_dirty", True):
            return
        eng = self.engine
        math_renderer = getattr(eng, "math_model_renderer", None) if eng else None
        if math_renderer is None:
            vp.visible_ids = None
            vp._visible_ids_dirty = False
            return

        plane = getattr(vp, "plane", None)
        cam = vp.camera
        
        # 1) Plane section filtresi
        plane_ids = None
        if plane is not None or cam.section_active:
            plane_ids = set()
            for elems in math_renderer._render_elements.values():
                for e in elems:
                    if math_renderer._element_in_section(e, cam, plane):
                        plane_ids.add(e.unique_id)
        
        # 2) Element filter
        element_ids = None
        query = getattr(vp, "element_filter", None)
        if query is not None and not query.is_empty():
            from tools.filter_query import ModelFilterEngine
            if getattr(vp, "_element_filter_dirty", True):
                vp._element_filter_ids = ModelFilterEngine.filter_to_ids(
                    eng.math_model, query,
                )
                vp._element_filter_dirty = False
            element_ids = set(vp._element_filter_ids)
        
        # 3) Kesişim
        if plane_ids is not None and element_ids is not None:
            vp.visible_ids = plane_ids & element_ids
        elif plane_ids is not None:
            vp.visible_ids = plane_ids
        elif element_ids is not None:
            vp.visible_ids = element_ids
        else:
            vp.visible_ids = None   # kısıtlama yok
        
        vp._visible_ids_dirty = False


    def render_all(self) -> None:
        eng = self.engine
        if eng is None:
            return
        for vp in self.viewports.values():
            if not vp.visible:
                continue
            self._ensure_visible_ids(vp)
            eng.render_viewport(vp)


    def invalidate_all_visible_ids(self) -> None:
        for vp in self.viewports.values():
            vp.invalidate_visible_ids()

    # ------------------------------------------------------------------
    def cleanup(self):
        renderer = getattr(self.engine, "renderer", None)
        for name, vp in list(self.viewports.items()):
            if renderer is not None:
                renderer.remove_viewport(name)
            vp.cleanup()
        self.viewports.clear()
        self.active_name = None