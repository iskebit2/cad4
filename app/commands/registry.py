# app/commands/registry.py
from __future__ import annotations

import dataclasses
import importlib
import pkgutil
import re
from typing import Any, Callable, get_args, get_origin, get_type_hints

from app.commands.base import Command, CommandMeta


_BOOL_TRUE = {"1", "true", "yes", "on", "evet", "e"}
_BOOL_FALSE = {"0", "false", "no", "off", "hayir", "hayır", "h"}
_SNAKE_RE = re.compile(r"(?<!^)(?=[A-Z])")
_FACTORY_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


# def _snake(name: str) -> str:
#     return _SNAKE_RE.sub("_", name).lower()


def _parse_scalar(raw: str, target: Any) -> Any:
    if target is bool:
        low = raw.lower()
        if low in _BOOL_TRUE:
            return True
        if low in _BOOL_FALSE:
            return False
        raise ValueError(raw)
    if target is int:
        return int(raw)
    if target is float:
        return float(raw)
    if target is str:
        return raw
    origin = get_origin(target)
    if origin is list:
        args = get_args(target)
        inner = args[0] if args else str
        return [_parse_scalar(x.strip(), inner) for x in raw.split(",") if x.strip()]
    return raw


def _build_auto_factory(cmd_type: type) -> Callable[[list[str]], Command | None]:
    if not dataclasses.is_dataclass(cmd_type):
        payload_type = getattr(cmd_type, "__payload_type__", None)
        if payload_type is not None:
            def build_payload(args: list[str]) -> Command | None:
                if len(args) != 1:
                    return None
                try:
                    payload = _parse_scalar(args[0], payload_type)
                except (ValueError, TypeError):
                    return None
                if not isinstance(payload, payload_type):
                    return None
                return cmd_type(payload)

            return build_payload

        def no_args(args: list[str]) -> Command | None:
            return None if args else cmd_type()

        return no_args

    fields = dataclasses.fields(cmd_type)
    hints = get_type_hints(cmd_type)

    def build(args: list[str]) -> Command | None:
        if len(args) > len(fields):
            return None
        kwargs: dict[str, Any] = {}
        for idx, f in enumerate(fields):
            if idx >= len(args):
                if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING:
                    return None
                break
            try:
                kwargs[f.name] = _parse_scalar(args[idx], hints.get(f.name, str))
            except (ValueError, TypeError):
                return None
        try:
            return cmd_type(**kwargs)
        except TypeError:
            return None

    return build


def _usage_for(cmd_type: type) -> str:
    if not dataclasses.is_dataclass(cmd_type):
        return ""
    hints = get_type_hints(cmd_type)
    parts = []
    for f in dataclasses.fields(cmd_type):
        has_default = (
            f.default is not dataclasses.MISSING
            or f.default_factory is not dataclasses.MISSING
        )
        t = hints.get(f.name, str)
        name = getattr(t, "__name__", "str")
        parts.append(f"[{f.name}:{name}]" if has_default else f"<{f.name}:{name}>")
    return " ".join(parts)


class CommandRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, Callable[[list[str]], Command | None]] = {}
        self._types: dict[str, type] = {}
        self._metas: dict[type, CommandMeta] = {}
        self._usages: dict[str, str] = {}

    def register(self, cmd_type: type, meta: CommandMeta | None = None) -> None:
        # name = _snake(cmd_type.__name__)
        name = cmd_type.__name__
        if name.endswith("_command"):
            name = name[: -len("_command")]
        meta = meta or CommandMeta(label=cmd_type.__name__)
        self._types[name] = cmd_type
        self._factories[name] = (
            meta.factory
            if meta.factory is not None
            else _build_auto_factory(cmd_type)
        )
        self._usages[name] = _usage_for(cmd_type)
        self._metas[cmd_type] = meta

    def get_meta(self, cmd_type: type) -> CommandMeta | None:
        return self._metas.get(cmd_type)

    def get_meta_by_name(self, name: str) -> CommandMeta | None:
        cmd_type = self._types.get(name)
        return self._metas.get(cmd_type) if cmd_type else None

    def all_meta(self) -> list[tuple[str, type, CommandMeta]]:
        return sorted(
            ((name, t, self._metas.get(t, CommandMeta(label=t.__name__)))
             for name, t in self._types.items()),
            key=lambda x: x[0],
        )

    def build(self, name: str, args: list[str]) -> Command | None:
        factory = self._factories.get(name)
        return factory(args) if factory else None

    def build_instance(self, name: str) -> Command | None:
        return self.build(name, [])

    def get_usage(self, name: str) -> str:
        return self._usages.get(name, "")

    def catalog(self) -> list[tuple[str, str]]:
        return [(n, self._usages.get(n, "")) for n in sorted(self._factories)]

    def list_names(self) -> list[str]:
        return sorted(self._factories)

    def has(self, name: str) -> bool:
        return name in self._factories

from app.commands.impl import *

def _parse_unit(args: list[str]) -> SetUnitSystem | None:
    if not args:
        return None
    from core.units import UnitSystem
    raw = " ".join(args).strip()
    key = raw.upper()
    if key in UnitSystem.__members__:
        return SetUnitSystem(UnitSystem[key])
    return SetUnitSystem(UnitSystem.from_sap(raw))

# ---------------------------------------------------------------------------
# Meta kayıtları
# ---------------------------------------------------------------------------

_META: list[tuple[type, CommandMeta]] = [
    (SetUnitSystem, CommandMeta(
    label="Birim Sistemi",
    icon="set_unit",
    category="Settings",
    tooltip="Birim sistemini değiştir",
    visible_in_ui=True,
    factory=_parse_unit,
)),
    (FitView, CommandMeta(label="Tüm Modeli Sığdır", icon="fit_view", category="View",
                          default_shortcut="F", quick=True, tooltip="Modeli sığdır", visible_in_ui=True)),
    (ZoomExtents, CommandMeta(label="Sınırlara Yaklaş", icon="zoom_extents", category="View",
                              default_shortcut="Ctrl+Shift+F", tooltip="Sınırları yenile")),
    (DeleteSelected, CommandMeta(label="Seçilileri Sil", icon="delete_selected", category="Edit",
                                 default_shortcut="Delete", quick=True, visible_in_ui=True)),
    (Undo, CommandMeta(label="Geri Al", icon="undo", category="Edit",
                       default_shortcut="Ctrl+Z", quick=True, visible_in_ui=True)),
    (Redo, CommandMeta(label="Yinele", icon="redo", category="Edit",
                       default_shortcut="Ctrl+Y", quick=True, visible_in_ui=True)),
    (NewProject, CommandMeta(label="Yeni Proje", icon="new_project", category="File",
                             default_shortcut="Ctrl+N", quick=True, visible_in_ui=True)),
    (OpenProject, CommandMeta(label="Proje Aç...", icon="open_project", category="File",
                              default_shortcut="Ctrl+O", quick=True, visible_in_ui=True)),
    (SaveProject, CommandMeta(label="Kaydet", icon="save_project", category="File",
                              default_shortcut="Ctrl+S", quick=True, visible_in_ui=True)),
    (SaveProjectAs, CommandMeta(label="Farklı Kaydet...", icon="save_project_as", category="File",
                                default_shortcut="Ctrl+Shift+S", quick=False, visible_in_ui=True)),
    (CloseProject, CommandMeta(label="Projeyi Kapat", icon="close_project", category="File",
                               default_shortcut="Ctrl+W", visible_in_ui=True)),
    (StartDrawLine, CommandMeta(
        label="Draw Line",
        icon="line",
        category="Draw",
        visible_in_ui=True,
    )),
    (StartDrawPoly, CommandMeta(
        label="Draw Poly",
        icon="poly",
        category="Draw",
        visible_in_ui=True,
    )),
    (StartPlane3pt, CommandMeta(
        label="3 Nokta ile Düzlem",
        icon="start_plane3pt",
        category="Draw",
        visible_in_ui=True
        )
        ),
    (StartPlane2ptZ, CommandMeta(label="2 Nokta + Z Düzlem",
                                    icon="start_plane2pt_z",
                                    category="Draw",
                                    visible_in_ui=True)),
    (ConvertFramesToLinks, CommandMeta(label="Çubukları Link'e Dönüştür",
                                       icon="convert_frames_to_links", category="Convert",
                                       visible_in_ui=True)),
    (ReplicateSelected, CommandMeta(
            label="Replicate",
            icon="rep",
            category="Edit",
            visible_in_ui=True,
        )),
]

_SKIP_MODULES = {"__init__", "base", "registry"}


def _discover_package(pkg_name: str = "app.commands") -> None:
    pkg = importlib.import_module(pkg_name)
    for info in pkgutil.iter_modules(pkg.__path__):
        if info.name in _SKIP_MODULES or info.name.startswith("_"):
            continue
        importlib.import_module(f"{pkg_name}.{info.name}")


_REGISTRY: CommandRegistry | None = None


def get_registry() -> CommandRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = CommandRegistry()
        register_all(_REGISTRY)
    return _REGISTRY

def register_all(registry) -> None:
    from app.commands import polygon_commands
    from app.commands import visibility
    for cmd_type in _ALL_COMMAND_TYPES:
        meta = next((m for t, m in _META if t is cmd_type), None)
        registry.register(cmd_type, meta)
    polygon_commands.register(registry)
    visibility.register(registry)


_ALL_COMMAND_TYPES = [t for t in globals().values()
                      if isinstance(t, type) and issubclass(t, Command) and t is not Command]