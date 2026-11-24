# app/services/panel_registry.py

from __future__ import annotations

from typing import Any, Callable

from app.settings.categories import Category
from logging_config import CadLogger
from ui.helpers.panel_specs import PANELS, PanelSpec

logger = CadLogger.get(__name__)


class PanelRegistry:
    def __init__(self, app=None) -> None:
        self.app = app
        self._by_name: dict[str, PanelSpec] = {}
        self._instances: dict[str, Any] = {}
        self._by_category: dict[Category, list[str]] = {}
        self._broken: dict[str, str] = {}
        if app is not None:
            self.load_from_specs(PANELS)

    # ------------------------------------------------------------------
    @staticmethod
    def _create_instance(cls: type, app) -> Any:
        params = cls.__init__.__annotations__
        _ = params
        signature_names = cls.__init__.__code__.co_varnames[: cls.__init__.__code__.co_argcount]
        if "app" in signature_names:
            return cls(app=app)
        return cls()

    def load_from_specs(self, specs: list[PanelSpec]) -> None:
        for spec in sorted(specs, key=lambda s: s.order):
            try:
                instance = self._create_instance(spec.cls, self.app)
            except Exception as exc:
                self._broken[spec.name] = f"{type(exc).__name__}: {exc}"
                logger.warning(
                    "[PanelRegistry] %s oluşturulamadı (%s): %s",
                    spec.name, spec.cls.__qualname__, exc,
                )
                continue
            self.register(spec, instance)

    # ------------------------------------------------------------------
    def register(self, spec: PanelSpec, instance: Any | None = None) -> None:
        name = spec.name
        previous = self._by_name.get(name)
        if previous is not None:
            names = self._by_category.get(previous.category, [])
            if name in names:
                names.remove(name)

        self._by_name[name] = spec
        names = self._by_category.setdefault(spec.category, [])
        if name not in names:
            names.append(name)
        names.sort(key=lambda n: self._by_name[n].order)

        self._broken.pop(name, None)
        if instance is not None:
            self._instances[name] = instance

    # ------------------------------------------------------------------
    def get(self, name: str) -> PanelSpec | None:
        return self._by_name.get(name)

    def instance(self, name: str) -> Any | None:
        return self._instances.get(name)

    def all(self) -> list[PanelSpec]:
        return sorted(self._by_name.values(), key=lambda s: s.order)

    def all_instances(self) -> list[tuple[PanelSpec, Any]]:
        return [
            (spec, self._instances[spec.name])
            for spec in self.all()
            if spec.name in self._instances
        ]

    def broken(self) -> dict[str, str]:
        return dict(self._broken)

    # ------------------------------------------------------------------
    def is_visible(self, name: str) -> bool:
        instance = self._instances.get(name)
        return bool(getattr(instance, "visible", False)) if instance is not None else False

    def visible(self) -> list[PanelSpec]:
        return [spec for spec in self.all() if self.is_visible(spec.name)]

    def visible_instances(self) -> list[tuple[PanelSpec, Any]]:
        return [
            (spec, instance)
            for spec, instance in self.all_instances()
            if getattr(instance, "visible", False)
        ]

    # ------------------------------------------------------------------
    def categories(self) -> dict[Category, list[str]]:
        return {category: list(names) for category, names in self._by_category.items()}

    def by_category(self, category: Category) -> list[PanelSpec]:
        return [
            self._by_name[name]
            for name in self._by_category.get(category, [])
            if name in self._by_name
        ]