# app/commands/__init__.py
from app.commands.base import Command, CommandManager, CommandMeta, CommandResult, bind_app
from app.commands.registry import get_registry
def __getattr__(name: str):
    from .registry import get_registry

    registry = get_registry()

    for cmd_type in registry._types.values():
        if cmd_type.__name__ == name:
            return cmd_type

    raise AttributeError(
        f"module 'app.commands' has no attribute {name!r}"
    )

__all__ = [
    "Command",
    "CommandManager",
    "CommandMeta",
    "CommandResult",
    "get_registry",
    "bind_app"
    ]