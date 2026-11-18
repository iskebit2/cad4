# ui/context_resolvers.py
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from app.cad_app import CadApp


ContextResolver = Callable[["_ContextBag"], Any]


class _ContextBag:
    """Resolver'ların ihtiyaç duyduğu referansları tek seferde toplar."""

    __slots__ = ("host", "app", "engine", "project", "scene", "math_model",
                 "renderer", "camera", "selection", "selection_manager",
                 "selection_policy")

    def __init__(self, host, app: "CadApp"):
        self.host = host
        self.app = app
        self.engine = app.engine
        self.project = app.project_service.project
        self.scene = self.engine.scene if self.engine else getattr(self.project, "scene", None)
        self.math_model = self.engine.math_model if self.engine else getattr(self.project, "math_model", None)
        self.renderer = getattr(self.engine, "renderer", None) if self.engine else None
        self.camera = getattr(self.engine, "cam", None) if self.engine else None
        self.selection_manager = getattr(self.engine, "sel_mgr", None) if self.engine else None
        self.selection_policy = getattr(self.engine, "sel_policy", None) if self.engine else None
        self.selection = self._compute_selection()

    def _compute_selection(self) -> list:
        if self.selection_manager is not None:
            return list(self.selection_manager.get_selected())
        if self.math_model is not None:
            return list(self.math_model.get_selected())
        return []


def _sel_of(t):
    return lambda b: [e for e in b.selection if isinstance(e, t)]


_BASE_RESOLVERS: dict[str, ContextResolver] = {
    "engine":              lambda b: b.engine,
    "scene":               lambda b: b.scene,
    "math_model":          lambda b: b.math_model,
    "project":             lambda b: b.project,
    "catalog":             lambda b: b.app.project_service.catalog,
    "selection":           lambda b: b.selection,
    "selection_count":     lambda b: len(b.selection),
    "selection_manager":   lambda b: b.selection_manager,
    "selection_policy":    lambda b: b.selection_policy,
    "renderer":            lambda b: b.renderer,
    "math_model_renderer": lambda b: b.renderer.math_model_renderer if b.renderer else None,
    "camera":              lambda b: b.camera,
    "wind_analysis_ref":   lambda b: b.app.wind_service.state(),
    "patterns":            lambda b: list(getattr(b.project, "load_patterns", {}).keys()),
    "sections":            lambda b: list(getattr(b.project, "sections", {}).keys()),
    "materials":           lambda b: list(getattr(b.project, "materials", {}).keys()),
}

_TYPED_RESOLVERS: dict[str, ContextResolver] | None = None


def _get_typed_resolvers() -> dict[str, ContextResolver]:
    global _TYPED_RESOLVERS
    if _TYPED_RESOLVERS is None:
        from domain.element import Area, Frame, Link, Node
        from domain.polygon import Polygon
        _TYPED_RESOLVERS = {
            "selection_frames":   _sel_of(Frame),
            "selection_areas":    _sel_of(Area),
            "selection_polygons": _sel_of(Polygon),
            "selection_links":    _sel_of(Link),
            "selection_nodes":    _sel_of(Node),
        }
    return _TYPED_RESOLVERS


def resolve_context(host, app: "CadApp", keys: list[str]) -> dict[str, Any]:
    if not keys:
        return {}
    bag = _ContextBag(host, app)
    typed = _get_typed_resolvers()
    out: dict[str, Any] = {}
    for key in keys:
        resolver = _BASE_RESOLVERS.get(key) or typed.get(key)
        if resolver is not None:
            out[key] = resolver(bag)
    return out