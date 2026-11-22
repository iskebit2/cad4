# app/services/panel_registry.py

from __future__ import annotations

import inspect
import logging

from typing import Any, Callable

from app.settings.categories import Category
from ui.helpers.panel_specs import PANELS, PanelSpec


logger = logging.getLogger(__name__)


class PanelRegistry:
    """Panel tanımlarını ve çalışma zamanı örneklerini yönetir."""

    def __init__(self, app=None) -> None:
        self.app = app

        # Statik panel tanımları
        self._by_name: dict[str, PanelSpec] = {}

        # Runtime panel nesneleri
        self._instances: dict[str, Any] = {}

        # Kategori indeksleri
        self._by_category: dict[Category | str, list[str]] = {}

        if app is not None:
            self.load_from_specs(PANELS)

    # ---------------------------------------------------------
    # Initialization
    # ---------------------------------------------------------

    def _create_instance(self, cls: type) -> Any:
        """Constructor imzasına uygun şekilde panel oluşturur."""

        signature = inspect.signature(cls)
        params = signature.parameters

        app_param = params.get("app")

        if app_param is not None:
            if app_param.kind == inspect.Parameter.POSITIONAL_ONLY:
                return cls(self.app)

            return cls(app=self.app)

        if any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in params.values()
        ):
            return cls(app=self.app)

        return cls()

    def load_from_specs(
        self,
        specs: dict[int, PanelSpec],
    ) -> None:
        for idx, spec in sorted(specs.items()):
            try:
                instance = self._create_instance(spec.cls)
                self.register(spec, instance)

            except Exception as exc:
                raise RuntimeError(
                    f"Panel oluşturulamadı: "
                    f"id={idx}, name={spec.name}, "
                    f"class={spec.cls.__qualname__}"
                ) from exc

    # ---------------------------------------------------------
    # Registration
    # ---------------------------------------------------------

    @staticmethod
    def _normalize_category(
        category: Category | str,
    ) -> Category | str:
        if isinstance(category, Category):
            return category

        try:
            return Category(category)
        except ValueError:
            return category

    def register(
        self,
        spec: PanelSpec,
        instance: Any | None = None,
    ) -> None:
        name = spec.name

        previous = self._by_name.get(name)

        if previous is not None:
            old_category = self._normalize_category(previous.category)
            names = self._by_category.get(old_category, [])

            if name in names:
                names.remove(name)

        self._by_name[name] = spec

        category = self._normalize_category(spec.category)
        names = self._by_category.setdefault(category, [])

        if name not in names:
            names.append(name)

        names.sort(key=lambda n: self._by_name[n].order)

        if instance is not None:
            self._instances[name] = instance

    # ---------------------------------------------------------
    # Lookup
    # ---------------------------------------------------------

    def get(self, name: str) -> PanelSpec | None:
        return self._by_name.get(name)

    def instance(self, name: str) -> Any | None:
        return self._instances.get(name)

    def get_instance(self, name: str) -> Any | None:
        return self.instance(name)

    def all(self) -> list[PanelSpec]:
        return list(self._by_name.values())

    def all_instances(self) -> list[tuple[PanelSpec, Any]]:
        return [
            (spec, self._instances[name])
            for name, spec in self._by_name.items()
            if name in self._instances
        ]

    # ---------------------------------------------------------
    # Visibility
    # ---------------------------------------------------------

    def is_visible(self, name: str) -> bool:
        instance = self.instance(name)

        return bool(
            getattr(instance, "visible", False)
        ) if instance is not None else False

    def visible(self) -> list[PanelSpec]:
        return [
            spec
            for name, spec in self._by_name.items()
            if self.is_visible(name)
        ]

    def visible_instances(self) -> list[tuple[PanelSpec, Any]]:
        return [
            (spec, instance)
            for spec, instance in self.all_instances()
            if getattr(instance, "visible", False)
        ]

    # ---------------------------------------------------------
    # Categories
    # ---------------------------------------------------------

    def categories(self) -> dict[Category | str, list[str]]:
        return {
            category: list(names)
            for category, names in self._by_category.items()
        }

    def by_category(
        self,
        category: Category | str,
    ) -> list[PanelSpec]:
        category = self._normalize_category(category)

        return [
            self._by_name[name]
            for name in self._by_category.get(category, [])
            if name in self._by_name
        ]

    # ---------------------------------------------------------
    # Toolbar
    # ---------------------------------------------------------

    def toolbar_specs(self) -> list[PanelSpec]:
        return self.all()

    def toolbar_commands(
        self,
        put_command: Callable[[Any], None],
    ) -> dict[str, Callable[[], None]]:
        from app.commands import project_commands as PC

        return {
            name: (
                lambda n=name: put_command(PC.TogglePanel(n))
            )
            for name in self._by_name
        }

    def toolbar_states(self) -> dict[str, Callable[[], bool]]:
        return {
            name: (
                lambda n=name: self.is_visible(n)
            )
            for name in self._by_name
        }





