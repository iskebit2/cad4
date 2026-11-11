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
    def render_all(self) -> None:
        """Tüm viewport'ları sırayla ortak MRT üzerinden kendi FBO'larına çizer."""
        eng = self.engine
        if eng is None:
            return
        for vp in self.viewports.values():
            if not vp.visible:
                continue
            eng.render_viewport(vp)

    # ------------------------------------------------------------------
    def cleanup(self):
        renderer = getattr(self.engine, "renderer", None)
        for name, vp in list(self.viewports.items()):
            if renderer is not None:
                renderer.remove_viewport(name)
            vp.cleanup()
        self.viewports.clear()
        self.active_name = None