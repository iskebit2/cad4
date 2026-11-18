# app/commands/registry.py
from __future__ import annotations

import importlib
import re
from typing import TYPE_CHECKING, Any, Callable

from app.commands.result import CommandResult

if TYPE_CHECKING:
    from app.cad_app import CadApp


CommandHandler = Callable[["CadApp", Any], CommandResult]
CommandFactory = Callable[[list[str]], "Any | None"]

_SNAKE_RE = re.compile(r"(?<!^)(?=[A-Z])")
_FACTORY_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _snake(name: str) -> str:
    return _SNAKE_RE.sub("_", name).lower()


def _no_args_factory(cmd_type: type) -> CommandFactory:
    def build(args: list[str]) -> Any | None:
        if args:
            return None
        try:
            return cmd_type()
        except TypeError:
            return None
    return build


class CommandRegistry:
    def __init__(self) -> None:
        self._handlers: dict[type, CommandHandler] = {}
        self._factories: dict[str, CommandFactory] = {}
        self._conflicts: list[str] = []
        self._usages: dict[str, str] = {}
        
    def register(self, cmd_type: type, handler: CommandHandler) -> None:
        if cmd_type in self._handlers:
            self._conflicts.append(
                f"handler çakışması: {cmd_type.__name__} "
                f"({self._handlers[cmd_type].__module__} vs {handler.__module__})"
            )
        self._handlers[cmd_type] = handler
        name = _snake(cmd_type.__name__)
        if name not in self._factories:
            factory_fn, usage = _auto_factory(cmd_type)
            self._factories[name] = factory_fn
            self._usages[name] = usage

    def get_usage(self, name: str) -> str:
        return self._usages.get(name, "")

    def get_command_catalog(self) -> list[tuple[str, str]]:
        """(komut_adi, kullanim_imzasi) çiftlerini alfabetik döndürür."""
        return [(name, self._usages.get(name, "")) for name in sorted(self._factories.keys())]

    def add_factory(self, name: str, factory: CommandFactory) -> None:
        if not _FACTORY_NAME_RE.match(name):
            self._conflicts.append(f"geçersiz factory adı: {name!r}")
            return
        if name in self._factories:
            prev = self._factories[name]
            if not getattr(prev, "_is_auto", False):
                prev_mod = getattr(prev, "__module__", "?")
                new_mod = getattr(factory, "__module__", "?")
                if prev_mod != new_mod:
                    self._conflicts.append(
                        f"factory çakışması: {name!r} "
                        f"({prev_mod} vs {new_mod})"
                    )
        self._factories[name] = factory

    def list_names(self) -> list[str]:
        return sorted(self._factories.keys())

    def list_types(self) -> list[type]:
        return sorted(self._handlers.keys(), key=lambda t: t.__name__)

    def has_factory(self, name: str) -> bool:
        return name in self._factories

    def has_handler(self, cmd_type: type) -> bool:
        return cmd_type in self._handlers

    def build_by_name(self, name: str, args: list[str]) -> Any | None:
        factory = self._factories.get(name)
        if factory is None:
            return None
        return factory(args)

    def dispatch(self, app: "CadApp", cmd: Any) -> CommandResult:
        handler = self._handlers.get(type(cmd))
        if handler is None:
            return CommandResult(
                handled=False,
                message=f"Handler bulunamadı: {type(cmd).__name__}",
                level="warn",
            )
        return handler(app, cmd)

    @property
    def conflicts(self) -> list[str]:
        return list(self._conflicts)


# ---------------------------------------------------------------------------
# Global kayıt havuzu
# ---------------------------------------------------------------------------

_HANDLERS: list[tuple[type, CommandHandler]] = []
_FACTORIES: list[tuple[str, CommandFactory]] = []


def command(cmd_type: type) -> Callable[[CommandHandler], CommandHandler]:
    if not isinstance(cmd_type, type):
        raise TypeError(
            f"@command beklediği: type, aldığı: {type(cmd_type).__name__}"
        )

    def decorator(handler: CommandHandler) -> CommandHandler:
        if not callable(handler):
            raise TypeError(f"@command handler callable değil: {handler!r}")
        _HANDLERS.append((cmd_type, handler))
        return handler
    return decorator


def factory(name: str) -> Callable[[CommandFactory], CommandFactory]:
    if not _FACTORY_NAME_RE.match(name):
        raise ValueError(
            f"@factory adı geçersiz: {name!r} "
            f"(beklenen: ^[a-z][a-z0-9_]*$)"
        )

    def decorator(fn: CommandFactory) -> CommandFactory:
        if not callable(fn):
            raise TypeError(f"@factory fn callable değil: {fn!r}")
        _FACTORIES.append((name, fn))
        return fn
    return decorator


# ---------------------------------------------------------------------------
# Modül keşfi
# ---------------------------------------------------------------------------

def _discover_modules() -> list[str]:
    import pkgutil
    import app.commands as pkg

    skip = {"registry", "result", "base", "__init__"}
    names = []
    for info in pkgutil.iter_modules(pkg.__path__):
        if info.name in skip or info.name.startswith("_"):
            continue
        names.append(info.name)
    return sorted(names)


def _import_command_modules() -> None:
    for name in _discover_modules():
        importlib.import_module(f"app.commands.{name}")


def build_registry() -> CommandRegistry:
    _HANDLERS.clear()
    _FACTORIES.clear()

    _import_command_modules()

    reg = CommandRegistry()
    for cmd_type, handler in _HANDLERS:
        reg.register(cmd_type, handler)
    for name, fn in _FACTORIES:
        reg.add_factory(name, fn)

    if reg.conflicts:
        from logging_config import CadLogger
        log = CadLogger.get(__name__)
        for c in reg.conflicts:
            log.warning("[registry] %s", c)

    return reg

import dataclasses
from typing import get_type_hints


def _auto_factory(cmd_type: type) -> tuple[CommandFactory, str]:
    """Dataclass alanlarından otomatik CLI parser ve kullanım imzası üretir."""
    if not dataclasses.is_dataclass(cmd_type):
        return _no_args_factory(cmd_type), ""

    fields = dataclasses.fields(cmd_type)
    hints = get_type_hints(cmd_type)
    usage_parts = []

    for f in fields:
        has_default = (
            f.default is not dataclasses.MISSING
            or f.default_factory is not dataclasses.MISSING
        )
        t_name = getattr(hints.get(f.name, Any), "__name__", "str")
        token = f"[{f.name}:{t_name}]" if has_default else f"<{f.name}:{t_name}>"
        usage_parts.append(token)

    usage = " ".join(usage_parts)

    def build(args: list[str]) -> Any | None:
        if len(args) > len(fields):
            return None
        kwargs: dict[str, Any] = {}
        for idx, f in enumerate(fields):
            if idx >= len(args):
                has_default = (
                    f.default is not dataclasses.MISSING
                    or f.default_factory is not dataclasses.MISSING
                )
                if not has_default:
                    return None
                break

            raw = args[idx]
            target_t = hints.get(f.name, str)
            try:
                if target_t is bool:
                    kwargs[f.name] = raw.lower() in ("1", "true", "yes", "on", "evet")
                elif target_t is int:
                    kwargs[f.name] = int(raw)
                elif target_t is float:
                    kwargs[f.name] = float(raw)
                elif target_t is list[int]:
                    kwargs[f.name] = [int(x) for x in raw.split(",") if x.strip()]
                else:
                    kwargs[f.name] = raw
            except (ValueError, TypeError):
                return None

        try:
            return cmd_type(**kwargs)
        except TypeError:
            return None
    build._is_auto = True  # type: ignore[attr-defined]
    return build, usage

_REGISTRY: "CommandRegistry | None" = None


def get_registry() -> CommandRegistry:
    """Süreç başına tek registry. build_registry() import maliyetini tekrarlamaz."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = build_registry()
    return _REGISTRY