# viewport/viewport_manager.py
from __future__ import annotations

from logging_config import CadLogger
from viewport.viewport import Viewport

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
                        preset: str | None = None, plane=None,
                        is_2d: bool = False) -> Viewport:
        if name is None:
            self._counter += 1
            name = f"Viewport {self._counter}"
        if name in self.viewports:
            raise ValueError(f"Viewport zaten var: {name}")
        vp = Viewport(name=name, width=width, height=height)
        vp.is_2d = bool(is_2d)
        if preset:
            vp.camera.set_view_preset(preset)

        self.viewports[name] = vp
        if self.active_name is None:
            self.active_name = name

        if plane is not None:
            self.bind_plane(vp, plane, is_2d=is_2d, refocus=True)
        else:
            eng = self.engine
            b = eng._combined_bounds() if eng else None
            if b is not None:
                vp.camera.update_bounds(b.center, b.size)
                vp.camera.focus_on_model()

        logger.info("[ViewportManager] create: %s preset=%s plane=%s",
                    name, preset, getattr(plane, "name", None))
        return vp

    def bind_plane(self, vp: Viewport, plane, *, is_2d: bool | None = None,
                   refocus: bool = True) -> None:
        """Bir viewport'u verilen plane'e bağlar, filtreyi ve kamerayı günceller."""
        vp.plane = plane
        if is_2d is not None:
            vp.is_2d = bool(is_2d)
        vp.invalidate_visible_ids()
        if refocus and plane is not None:
            self.focus_viewport_on_plane(vp, plane)

    def sync_plane(self, plane, refocus: bool = False) -> None:
        """Plane sınırları/derinliği/modu değiştiğinde bağlı tüm viewport'ları günceller."""
        if plane is None:
            return
        eng = self.engine
        if eng and getattr(eng, "math_model", None):
            plane.refresh_assoc(eng.math_model, getattr(eng, "scene", None))

        for vp in self.viewports.values():
            if getattr(vp, "plane", None) is plane:
                vp.invalidate_visible_ids()
                if refocus:
                    self.focus_viewport_on_plane(vp, plane)

    def ensure_viewport_plane(self, vp: Viewport, project=None):
        plane = getattr(vp, "plane", None)
        if plane is not None:
            return plane

        from plane.plane import Plane
        plane = Plane.from_axis_offset("z", 0.0, name=f"{vp.name}_UCS")
        eng = self.engine
        if eng is not None and getattr(eng, "math_model", None) is not None:
            plane.fit_to_math_model(eng.math_model, include_depth=True)
        if project is not None:
            project.add_plane(plane)
        vp.plane = plane
        vp.invalidate_visible_ids()
        return plane

    def focus_viewport_on_plane(self, vp: Viewport, plane=None) -> None:
        plane = plane or getattr(vp, "plane", None)
        if plane is None:
            return

        if None not in (plane.u_min, plane.u_max, plane.v_min, plane.v_max):
            uc = 0.5 * (plane.u_min + plane.u_max)
            vc = 0.5 * (plane.v_min + plane.v_max)
            wc = 0.5 * (plane.depth_plus - plane.depth_minus)
            center = plane.local_to_world((uc, vc, wc))
            half_u = 0.5 * abs(plane.u_max - plane.u_min)
            half_v = 0.5 * abs(plane.v_max - plane.v_min)
            fit_radius = max(half_u, half_v, 100.0) * 1.25
        else:
            center = plane.origin
            b = self.engine._combined_bounds() if self.engine else None
            fit_radius = float(b.size) if b else 2000.0

        if getattr(vp, "is_2d", False):
            vp.camera.look_at_plane(
                origin=center,
                u=plane.u,
                v=plane.v,
                n=plane.normal,
                fit_radius=fit_radius,
            )
        else:
            vp.camera.look_at_plane_iso(
                origin=center,
                u=plane.u,
                v=plane.v,
                n=plane.normal,
                fit_radius=fit_radius,
            )

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
        logger.info("[ViewportManager] remove: %s", name)
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
        plane_rev = getattr(plane, "association_revision", None) if plane is not None else None
        if (
            not getattr(vp, "_visible_ids_dirty", True)
            and getattr(vp, "_last_plane_rev", None) == plane_rev
            and getattr(vp, "_last_plane_id", None) == getattr(plane, "plane_id", None)
        ):
            return
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
        
        vp._last_plane_rev = plane_rev
        vp._last_plane_id = getattr(plane, "plane_id", None)
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