from __future__ import annotations

import shlex

import glfw

from app.commands.registry import CommandRegistry
from app.settings.shortcut_store import ShortcutStore

_MOD_MASK = {
    "ctrl": glfw.MOD_CONTROL,
    "shift": glfw.MOD_SHIFT,
    "alt": glfw.MOD_ALT,
    "super": glfw.MOD_SUPER,
}

_KEY_TABLE: dict[str, int] = {
    "delete": glfw.KEY_DELETE,
    "escape": glfw.KEY_ESCAPE,
    "enter": glfw.KEY_ENTER,
    "space": glfw.KEY_SPACE,
    "tab": glfw.KEY_TAB,
    "backspace": glfw.KEY_BACKSPACE,
    "up": glfw.KEY_UP,
    "down": glfw.KEY_DOWN,
    "left": glfw.KEY_LEFT,
    "right": glfw.KEY_RIGHT,
    "home": glfw.KEY_HOME,
    "end": glfw.KEY_END,
    "pageup": glfw.KEY_PAGE_UP,
    "pagedown": glfw.KEY_PAGE_DOWN,
    "insert": glfw.KEY_INSERT,
}

for _i in range(1, 26):
    _KEY_TABLE[f"f{_i}"] = getattr(glfw, f"KEY_F{_i}")

for _c in "abcdefghijklmnopqrstuvwxyz":
    _KEY_TABLE[_c] = getattr(glfw, f"KEY_{_c.upper()}")

for _d in "0123456789":
    _KEY_TABLE[_d] = getattr(glfw, f"KEY_{_d}")


def parse_shortcut(combo: str) -> tuple[int, int] | None:
    if not combo:
        return None
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    if not parts:
        return None
    *mods, key_name = parts
    key = _KEY_TABLE.get(key_name)
    if key is None:
        return None
    mask = 0
    for m in mods:
        flag = _MOD_MASK.get(m)
        if flag is None:
            return None
        mask |= flag
    return key, mask


def _build_command(registry: CommandRegistry, expr: str):
    parts = shlex.split(expr.strip())
    if not parts:
        return None
    if len(parts) == 1:
        return registry.build_instance(parts[0])
    return registry.build_by_name(parts[0], parts[1:])


def apply_shortcuts(
    engine_input,
    command_queue,
    registry: CommandRegistry,
    shortcut_store: ShortcutStore,
) -> list[str]:
    if hasattr(engine_input, "clear_bindings"):
        engine_input.clear_bindings()

    dropped: list[str] = []
    overrides = shortcut_store.load()
    bound_expressions: set[str] = set()

    for cmd_id, _cmd_type, meta in registry.all_meta():
        default_combo = meta.default_shortcut if meta.visible_in_ui else ""
        combo = shortcut_store.resolve(cmd_id, default_combo)
        bound_expressions.add(cmd_id)
        if not combo:
            continue
        parsed = parse_shortcut(combo)
        if parsed is None:
            dropped.append(cmd_id)
            continue
        key, mask = parsed

        def _emit(expr=cmd_id) -> None:
            cmd = _build_command(registry, expr)
            if cmd is not None:
                command_queue.put(cmd)

        engine_input.bind(key, mask, _emit)

    for expr, combo in overrides.items():
        if expr in bound_expressions or not combo:
            continue
        parsed = parse_shortcut(combo)
        if parsed is None:
            dropped.append(expr)
            continue
        key, mask = parsed

        def _emit_override(raw=expr) -> None:
            cmd = _build_command(registry, raw)
            if cmd is not None:
                command_queue.put(cmd)

        engine_input.bind(key, mask, _emit_override)

    return dropped