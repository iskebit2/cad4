# core/commands/create.py
from typing import Any, Dict, Callable
from logging_config import CadLogger

from core.commands.base import Command

logger = CadLogger.get(__name__)


class CreateElementCommand(Command):
    """
    Yeni bir eleman oluşturup scene'e ekler.

    - execute(): factory ile üretir, add_element ile ekler (bağlantılar kurulur)
    - undo():    remove_element ile çıkarır (bağlantılar temizlenir)
    - redo():    aynı objeyi restore_element ile geri koyar (yeni obje DEĞİL)
    """

    def __init__(self, scene, element_type: str,
                 factory: Callable[[Dict[str, Any]], Any],
                 values: Dict[str, Any]):
        self.scene = scene
        self.element_type = element_type
        self.factory = factory
        self.values = dict(values)
        self.created = None

    def execute(self):
        if self.created is None:
            # İlk kez — nesneyi üret
            self.created = self.factory(self.values)
            if not self.scene.add_element(self.created):
                raise RuntimeError(
                    f"add_element başarısız: {self.element_type}"
                )
        else:
            # Redo — aynı objeyi geri koy
            self.scene.restore_element(self.created)

        logger.debug(f"[CreateCmd] {self.element_type} eklendi")

    def undo(self):
        if self.created is None:
            return
        if not self.scene.remove_element(self.created):
            logger.warning(
                f"[CreateCmd] undo reddedildi: {self.element_type} "
                "(bağlı eleman olabilir)"
            )
            raise RuntimeError("Geri alınamadı: bağlı eleman var")
        logger.debug(f"[CreateCmd] {self.element_type} geri alındı")

    @property
    def name(self) -> str:
        return f"Create({self.element_type})"