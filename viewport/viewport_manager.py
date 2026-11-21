from __future__ import annotations

from viewport.viewport import ViewUCS, ViewVolume, Viewport


class ViewportManager:
    def __init__(self, engine) -> None:
        self.engine = engine
        self.viewports: dict[str, Viewport] = {}
        self.active_name: str | None = None
        self._counter = 0

    def create_viewport(
        self,
        name: str | None = None,
        width: int = 640,
        height: int = 480,
        preset: str | None = None,
        ucs: ViewUCS | None = None,
        volume: ViewVolume | None = None,
        element_filter=None,
        is_2d: bool = False,
    ) -> Viewport:
        if name is None:
            self._counter += 1
            name = f"Viewport {self._counter}"
        if name in self.viewports:
            raise ValueError(f"Viewport zaten var: {name}")

        vp = Viewport(
            name=name,
            width=width,
            height=height,
            ucs=ucs,
            volume=volume,
            element_filter=element_filter,
            is_2d=is_2d,
        )
        if preset:
            vp.camera.set_view_preset(preset)

        self.viewports[name] = vp
        if self.active_name is None:
            self.active_name = name

        eng = self.engine
        b = eng._combined_bounds() if eng else None
        if ucs is not None or volume is not None:
            vp.focus_on_volume(
                fallback_center=b.center if b is not None else None,
                fallback_radius=float(b.size) if b is not None else 2000.0,
            )
        elif b is not None:
            vp.camera.update_bounds(b.center, b.size)
            vp.camera.focus_on_model()

        return vp

    def next_name(self, base: str) -> str:
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

    def invalidate_all(self) -> None:
        for vp in self.viewports.values():
            vp.invalidate()

    def render_all(self) -> None:
        eng = self.engine
        if eng is None:
            return
        math_model = getattr(eng, "math_model", None)
        for vp in self.viewports.values():
            if not vp.visible:
                continue
            vp.rebuild_visible_ids(math_model)
            eng.render_viewport(vp)

    def cleanup(self) -> None:
        renderer = getattr(self.engine, "renderer", None)
        for name, vp in list(self.viewports.items()):
            if renderer is not None:
                renderer.remove_viewport(name)
            vp.cleanup()
        self.viewports.clear()
        self.active_name = None