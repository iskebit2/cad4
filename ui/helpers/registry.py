# ui/registry.py
from __future__ import annotations
import importlib, inspect, logging, pkgutil
from dataclasses import dataclass
from ..base.panel_base import PanelBase, Category

log = logging.getLogger(__name__)

@dataclass(frozen=True)
class PanelSpec:
    name: str
    cls: type
    title: str
    category: Category
    quick: bool = False
    menu_label: str | None = None
    icon: str | None = None
    shortcut: str | None = None
    context: tuple[str, ...] = ()

def discover_panels(package) -> list["PanelSpec"]:
    specs: dict[str, PanelSpec] = {}

    for info in pkgutil.iter_modules(package.__path__):
        full = f"{package.__name__}.{info.name}"
        try:
            mod = importlib.import_module(full)
        except Exception:
            log.exception("Panel modülü import edilemedi: %s", full)
            continue

        for _, cls in inspect.getmembers(mod, inspect.isclass):
            if cls.__module__ != mod.__name__:
                continue
            if getattr(cls, "__abstract__", False):
                continue
            name = getattr(cls, "panel_name", None)
            if not name:
                continue

            try:
                cat = Category(getattr(cls, "category", Category.TOOLS))
            except ValueError:
                log.error("Geçersiz kategori: %r → %s", cls.category, cls.__name__)
                continue

            if name in specs:
                log.error("panel_name çakışması: %r (%s ↔ %s)",
                          name, specs[name].cls.__name__, cls.__name__)
                continue

            specs[name] = PanelSpec(
                name=name,
                cls=cls,
                title=getattr(cls, "title", name),
                category=cat,
                quick=bool(getattr(cls, "quick", False)),
                menu_label=getattr(cls, "menu_label", None),
                icon=getattr(cls, "icon", None),
                shortcut=getattr(cls, "shortcut", None),
                context=tuple(getattr(cls, "context", ()) or ()),
            )

    log.info("discover_panels: %d panel bulundu (%s)",
             len(specs), ", ".join(sorted(specs)))
    return list(specs.values())


def validate(specs: list, actions: list) -> None:
    seen_names, seen_shortcuts = set(), {}
    for s in specs:
        if s.name in seen_names:
            log.error("Duplicate name: %s", s.name)
        seen_names.add(s.name)
        if getattr(s, "shortcut", None):
            if s.shortcut in seen_shortcuts:
                log.warning("Shortcut çakışması %s: %s ↔ %s",
                            s.shortcut, seen_shortcuts[s.shortcut], s.name)
            seen_shortcuts[s.shortcut] = s.name
        if s.category not in Category.__members__.values() and s.category not in Category:
            log.error("Geçersiz kategori: %r (%s)", s.category, s.name)
    for a in actions:
        if a.name in seen_names:
            log.error("Action ismi panel ile çakışıyor: %s", a.name)