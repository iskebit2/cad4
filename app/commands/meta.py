from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class CommandMeta:
    label: str
    icon: str
    category: str
    default_shortcut: str = ""
    tooltip: str = ""
    quick: bool = False
    visible_in_ui: bool = True
    check_state: Callable[[Any], bool] | None = None
    factory: Callable[[], Any] | None = None