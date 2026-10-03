# core/selection_manager.py
from typing import List, Set
from core.selection_policy import SelectionMode
from core.commands import CommandManager, DeleteElementsCommand
from logging_config import CadLogger
from logging_config import CadLogger

logger = CadLogger.get(__name__)

class SelectionManager:
    """Seçim durumunu yönet - TEK KAYNAK"""
    
    def __init__(self, scene_renderer):
        self.r = scene_renderer
        self.selected: Set[int] = set()
        self.cmd_mgr = CommandManager(max_history=100)

        self.on_selection_changed = None   # callable veya None
    
    def _update(self):
        """Renkleri güncelle + callback çağır."""
        if self.r:
            self.r.update_sel()

        if self.on_selection_changed:
            try:
                self.on_selection_changed(list(self.get_selected()))
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(
                    f"selection_changed callback hatası: {e}"
                )
        
    def _update_geometry_renderers(self, scene):
        """Geometriyi güncelle (eleman ekleme/silme/değiştirme için)"""
        logger.debug("[SelectionManager] _update_geometry_renderers called")
        if self.r:
            logger.debug(f"  Calling scene_renderer.update_geo()")
            self.r.update_geo(scene)
        else:
            logger.warning("  No scene_renderer available!")
    
    def _clear_all(self):
        """Tüm seçimleri temizle"""
        if not self.r.scene: return
        for e in self.r.scene.all_elements.values():
            if e.unique_id in self.selected:
                e.is_selected = False
        self.selected.clear()
    
    def select(self, element, additive=False):
        """Tek eleman seç"""
        if not additive:
            self._clear_all()
            self.selected.add(element.unique_id)
            element.is_selected = True
        else:
            if element.unique_id in self.selected:
                self.selected.remove(element.unique_id)
                element.is_selected = False
            else:
                self.selected.add(element.unique_id)
                element.is_selected = True
        self._update()
    
    def select_multiple(self, elements: List, mode=SelectionMode.REPLACE):
        """Çoklu eleman seç"""
        if mode == SelectionMode.REPLACE:
            self._clear_all()
            for e in elements:
                self.selected.add(e.unique_id)
                e.is_selected = True
        
        elif mode == SelectionMode.ADD:
            for e in elements:
                if e.unique_id not in self.selected:
                    self.selected.add(e.unique_id)
                    e.is_selected = True
        
        elif mode == SelectionMode.TOGGLE:
            for e in elements:
                if e.unique_id in self.selected:
                    self.selected.remove(e.unique_id)
                    e.is_selected = False
                else:
                    self.selected.add(e.unique_id)
                    e.is_selected = True
        
        self._update()
    
    def clear(self):
        """Tüm seçimleri temizle"""
        for e in self.get_selected():
            e.is_selected = False
        self.selected.clear()
        self._update()
    
    def get_selected(self):
        """Seçili elemanları döndür"""
        if not self.r.scene: return []
        return [e for e in self.r.scene.all_elements.values() 
                if e.unique_id in self.selected]
    
    def count(self): return len(self.selected)
    def is_selected(self, e): return e.unique_id in self.selected

    def delete_selected(self) -> tuple:
        """
        Seçili elemanları sil (Command pattern).
        Returns: (silinen_sayı, reddedilen_sayı)
        """
        if not self.r or not self.r.scene:
            return 0, 0
        
        selected = list(self.get_selected())
        if not selected:
            return 0, 0
        
        # Komut oluştur ve çalıştır
        cmd = DeleteElementsCommand(self.r.scene, selected)
        ok = self.cmd_mgr.execute(cmd)
        
        if not ok:
            return 0, 0
        
        # Silinen ve reddedilen elemanları seçimden çıkar
        self.selected.clear()
        
        # Geometry'yi güncelle (buffer'lar yeniden üretilir)
        self._update_geometry_renderers(self.r.scene)
        
        return len(cmd.deleted), len(cmd.rejected)
    
    def undo(self) -> bool:
        """Son komutu geri al."""
        if not self.cmd_mgr.can_undo():
            return False
        
        ok = self.cmd_mgr.undo()
        if ok:
            self.selected.clear()
            self._update_geometry_renderers(self.r.scene)
        return ok
    
    def redo(self) -> bool:
        """Son geri alınanı yeniden yap."""
        if not self.cmd_mgr.can_redo():
            return False
        
        ok = self.cmd_mgr.redo()
        if ok:
            self.selected.clear()
            self._update_geometry_renderers(self.r.scene)
        return ok