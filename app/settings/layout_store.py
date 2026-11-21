
# app/settings/layout_store.py

from __future__ import annotations

import json
import logging
import os
import tempfile

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.settings.app_paths import toolbar_layout_file
from app.settings.categories import Category, CATEGORY_ORDER, CATEGORY_LABELS


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------

_DEFAULT_ORDER = tuple(category.value for category in CATEGORY_ORDER)

_DEFAULT_LABELS = {
    category.value: CATEGORY_LABELS[category]
    for category in CATEGORY_ORDER
}


# ---------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------

def _strings(value: Any) -> list[str]:
    """Tekrarsız, geçerli string listesi üretir."""

    if not isinstance(value, (list, tuple, set)):
        return []

    result = []
    seen = set()

    for item in value:
        if not isinstance(item, str):
            continue

        item = item.strip()

        if item and item not in seen:
            result.append(item)
            seen.add(item)

    return result


def _category_order(value: Any) -> list[str]:
    """Kayıtlı sırayı korur, yeni kategorileri sona ekler."""

    order = _strings(value)

    for category in _DEFAULT_ORDER:
        if category not in order:
            order.append(category)

    return order


def _category_labels(value: Any) -> dict[str, str]:
    """Varsayılan etiketleri kullanıcı tanımlarıyla birleştirir."""

    labels = dict(_DEFAULT_LABELS)

    if isinstance(value, dict):
        for key, label in value.items():
            if isinstance(key, str) and isinstance(label, str):
                labels[key] = label

    return labels


def _item_order(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}

    return {
        key.strip(): _strings(items)
        for key, items in value.items()
        if isinstance(key, str) and key.strip()
    }


def _quick_override(value: Any) -> dict[str, bool]:
    if not isinstance(value, dict):
        return {}

    return {
        name.strip(): state
        for name, state in value.items()
        if isinstance(name, str) and name.strip() and type(state) is bool
    }


def _hidden(value: Any) -> set[str]:
    return set(_strings(value))


# ---------------------------------------------------------------------
# Toolbar Layout
# ---------------------------------------------------------------------

@dataclass
class ToolbarLayout:
    category_order: list[str] = field(
        default_factory=lambda: list(_DEFAULT_ORDER)
    )

    category_labels: dict[str, str] = field(
        default_factory=lambda: dict(_DEFAULT_LABELS)
    )

    item_order: dict[str, list[str]] = field(default_factory=dict)

    hidden: set[str] = field(default_factory=set)

    quick_override: dict[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.category_order = _category_order(self.category_order)
        self.category_labels = _category_labels(self.category_labels)
        self.item_order = _item_order(self.item_order)
        self.hidden = _hidden(self.hidden)
        self.quick_override = _quick_override(self.quick_override)

    @classmethod
    def defaults(cls) -> ToolbarLayout:
        return cls()

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ToolbarLayout:
        if not isinstance(data, dict):
            raise ValueError("Toolbar layout JSON kök nesnesi dict olmalı.")
        
        return cls(
            category_order=data.get("category_order"),
            category_labels=data.get("category_labels"),
            item_order=data.get("item_order"),
            hidden=data.get("hidden"),
            quick_override=data.get("quick_override"),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "category_order": _category_order(self.category_order),
            "category_labels": _category_labels(self.category_labels),
            "item_order": _item_order(self.item_order),
            "hidden": sorted(_hidden(self.hidden)),
            "quick_override": _quick_override(self.quick_override),
        }


# ---------------------------------------------------------------------
# Layout Store
# ---------------------------------------------------------------------

class LayoutStore:
    """Toolbar yerleşim ayarlarının kalıcı deposu."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else toolbar_layout_file()
        self._layout: ToolbarLayout | None = None

    @property
    def layout(self) -> ToolbarLayout:
        return self.load()

    def load(self) -> ToolbarLayout:
        """Ayarları diskten bir kez okur."""

        if self._layout is not None:
            return self._layout

        if not self.path.exists():
            self._layout = ToolbarLayout.defaults()
            return self._layout

        try:
            raw = json.loads(
                self.path.read_text(encoding="utf-8")
            )

            self._layout = ToolbarLayout.from_json(raw)

        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            logger.exception(
                "[LayoutStore] Layout okunamadı: %s",
                self.path,
            )
            self._layout = ToolbarLayout.defaults()

        return self._layout

    def save(self, layout: ToolbarLayout | None = None) -> None:
        """Ayarları atomik olarak diske yazar."""

        if layout is None:
            layout = self.load()

        if not isinstance(layout, ToolbarLayout):
            raise TypeError("layout bir ToolbarLayout olmalı.")

        self.path.parent.mkdir(parents=True, exist_ok=True)

        content = json.dumps(
            layout.to_json(),
            indent=2,
            ensure_ascii=False,
        )

        temp_path = None

        try:
            fd, temp_name = tempfile.mkstemp(
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
            )
            temp_path = Path(temp_name)

            with os.fdopen(fd, "w", encoding="utf-8") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())

            os.replace(temp_path, self.path)

        except Exception:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            raise

        self._layout = layout

        logger.debug("[LayoutStore] Kaydedildi: %s", self.path)

    def reload(self) -> ToolbarLayout:
        """Bellekteki önbelleği atar ve dosyayı yeniden okur."""

        self._layout = None
        return self.load()

    def reset(self) -> ToolbarLayout:
        """Varsayılan yerleşimi oluşturur ve kaydeder."""

        layout = ToolbarLayout.defaults()
        self.save(layout)
        return layout
