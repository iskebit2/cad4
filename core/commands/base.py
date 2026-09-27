# core/commands/base.py
from abc import ABC, abstractmethod
from collections import deque
import logging

logger = logging.getLogger(__name__)


class Command(ABC):
    """Tüm komutların arayüzü."""
    
    @abstractmethod
    def execute(self):
        """İşlemi uygula."""
        pass
    
    @abstractmethod
    def undo(self):
        """İşlemi geri al."""
        pass
    
    def redo(self):
        """Yeniden uygula (varsayılan: execute)."""
        self.execute()
    
    @property
    def name(self) -> str:
        """Debug/log için okunabilir isim."""
        return self.__class__.__name__


class CommandManager:
    """
    Komut geçmişi ve undo/redo yönetimi.
    
    Kullanım:
        mgr = CommandManager()
        mgr.execute(DeleteElementsCommand(scene, elements))
        mgr.undo()
        mgr.redo()
    """
    
    def __init__(self, max_history: int = 100):
        self._undo_stack: deque = deque(maxlen=max_history)
        self._redo_stack: deque = deque(maxlen=max_history)
        self._listeners = []   # komut sonrası tetiklenecek callback'ler
    
    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------
    
    def execute(self, command: Command) -> bool:
        """Komutu çalıştır ve geçmişe ekle."""
        try:
            command.execute()
        except Exception as e:
            logger.error(f"[Cmd] {command.name} execute hatası: {e}")
            return False
        
        self._undo_stack.append(command)
        self._redo_stack.clear()
        
        logger.debug(f"[Cmd] {command.name} uygulandı (undo={len(self._undo_stack)})")
        self._notify()
        return True
    
    def undo(self) -> bool:
        """Son komutu geri al."""
        if not self._undo_stack:
            return False
        
        cmd = self._undo_stack.pop()
        try:
            cmd.undo()
        except Exception as e:
            logger.error(f"[Cmd] {cmd.name} undo hatası: {e}")
            # Hata olursa komutu geri koyma — kullanıcı tekrar deneyebilir
            return False
        
        self._redo_stack.append(cmd)
        logger.debug(f"[Cmd] {cmd.name} geri alındı")
        self._notify()
        return True
    
    def redo(self) -> bool:
        """Son geri alınanı yeniden uygula."""
        if not self._redo_stack:
            return False
        
        cmd = self._redo_stack.pop()
        try:
            cmd.redo()
        except Exception as e:
            logger.error(f"[Cmd] {cmd.name} redo hatası: {e}")
            return False
        
        self._undo_stack.append(cmd)
        logger.debug(f"[Cmd] {cmd.name} yeniden yapıldı")
        self._notify()
        return True
    
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0
    
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0
    
    def clear(self):
        """Tüm geçmişi temizle."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        logger.debug("[Cmd] Geçmiş temizlendi")
    
    # ---------------------------------------------------------
    # LISTENERS (opsiyonel — UI güncellemeleri için)
    # ---------------------------------------------------------
    
    def add_listener(self, callback):
        """Komut sonrası tetiklenecek callback ekle."""
        self._listeners.append(callback)
    
    def _notify(self):
        for cb in self._listeners:
            try:
                cb()
            except Exception as e:
                logger.error(f"[Cmd] Listener hatası: {e}")