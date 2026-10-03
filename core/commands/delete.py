# core/commands/delete.py
from typing import List
from logging_config import CadLogger

from core.commands.base import Command


from logging_config import CadLogger

logger = CadLogger.get(__name__)


class DeleteElementsCommand(Command):
    """
    Seçili elemanları sil. Node bağlı ise reddedilir.
    Undo → silinen elemanları geri koyar.
    """
    
    def __init__(self, scene, elements: List):
        """
        Parameters
        ----------
        scene : Scene
        elements : List[Element] — silinecek objeler (kopya, orijinal değil)
        """
        self.scene = scene
        # Kopya al — kullanıcı seçimi sonradan değişebilir
        self.elements = list(elements)
        
        # Sonuçlar — execute() dolduracak
        self.deleted = []       # başarıyla silinen
        self.rejected = []      # bağlı olduğu için reddedilen
    
    def execute(self):
        """Elemanları sil."""
        self.deleted.clear()
        self.rejected.clear()
        
        for e in self.elements:
            # Silinebilir mi?
            ok, _ = self.scene.can_remove(e)
            if not ok:
                self.rejected.append(e)
                continue
            
            if self.scene.remove_element(e):
                self.deleted.append(e)
        
        logger.debug(
            f"[DeleteCmd] {len(self.deleted)} silindi, "
            f"{len(self.rejected)} reddedildi"
        )
    
    def undo(self):
        """Silinenleri geri koy."""
        for e in self.deleted:
            self.scene.restore_element(e)
        
        logger.debug(f"[DeleteCmd] {len(self.deleted)} geri alındı")
    
    @property
    def name(self) -> str:
        return f"Delete({len(self.deleted)} eleman)"