# core/commands/bulk_update.py
"""
BulkUpdateCommand — Birden fazla elemana aynı anda alan uygular.

- execute(): plan'daki tüm (element, after) çiftlerini uygular
- undo():    ters sırayla before değerlerini geri koyar
- Tek bir Command → CommandManager'da tek undo/redo kaydı
"""

from typing import Any, Callable, Dict, List, Tuple

from core.commands.base import Command
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class BulkUpdateCommand(Command):
    """
    plan: List[(element, before_dict, after_dict)]
    setter: setter(element, field, value)
    """

    def __init__(self,
                 plan: List[Tuple[Any, Dict[str, Any], Dict[str, Any]]],
                 setter: Callable[[Any, str, Any], None]):
        self.plan = plan
        self.setter = setter

    def execute(self):
        """Tüm alanları sırayla uygula."""
        for element, _before, after in self.plan:
            for field, value in after.items():
                self.setter(element, field, value)
            # Dirty flag — renderer bir sonraki update'te yeniden build etsin
            if hasattr(element, "mark_dirty"):
                element.mark_dirty()

        logger.debug(f"[BulkUpdate] {len(self.plan)} eleman güncellendi")

    def undo(self):
        """Ters sırayla eski değerleri geri koy."""
        for element, before, _after in reversed(self.plan):
            # Alanları da ters sırayla geri al
            for field in reversed(list(before.keys())):
                self.setter(element, field, before[field])
            if hasattr(element, "mark_dirty"):
                element.mark_dirty()

        logger.debug(f"[BulkUpdate] {len(self.plan)} eleman geri alındı")

    @property
    def name(self) -> str:
        return f"BulkUpdate({len(self.plan)})"