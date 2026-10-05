# core/commands/update.py
from typing import Any, Dict, Callable
from logging_config import CadLogger

from core.commands.base import Command

logger = CadLogger.get(__name__)


class UpdateElementCommand(Command):
    """
    Bir elemanın alanlarını değiştirir.
    before/after: {field_name: value}
    setter: setter(element, field, value)
    """

    def __init__(self, element, before: Dict[str, Any],
                 after: Dict[str, Any],
                 setter: Callable[[Any, str, Any], None]):
        self.element = element
        self.before = dict(before)
        self.after = dict(after)
        self.setter = setter

    def execute(self):
        for f, v in self.after.items():
            self.setter(self.element, f, v)

    def undo(self):
        # Ters sırayla — bağımlı alanlar için
        for f in reversed(list(self.before.keys())):
            self.setter(self.element, f, self.before[f])

    @property
    def name(self) -> str:
        return f"Update({type(self.element).__name__}, {len(self.after)} alan)"