# tools/s2kloader.py
"""
SAP2000 .s2k dosya yükleyici.
"""
from typing import Optional

from logging_config import CadLogger
from domain.scene import Scene

from tools.s2k import S2KParser, LoadContext, build_scene
from tools.s2k.router import build_sorted_router, build_router

logger = CadLogger.get(__name__)


def show_file_dialog() -> Optional[str]:
    from tools.s2k.dialog import show_file_dialog as _dlg
    return _dlg()


class S2KLoader:
    """SAP2000 .$2k dosyasından Scene yükler."""
    
    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path or show_file_dialog()
        
        if not self.file_path:
            logger.warning("[Loader] Dosya seçilmedi")
            self.parser = None
            return
        
        self.parser = S2KParser(self.file_path)
        self.units = None

    def load(self) -> Scene:
        """S2K dosyasını yükle → Scene."""
        if self.parser is None:
            return Scene()
        
        logger.info("[Loader] Model inşa ediliyor...")
        
        ctx = LoadContext()
        tables = self.parser.get_all_tables()
        router = build_router()
        processed_tables = set()
        
        # ───── SIRALI HANDLER ÇAĞRISI ─────
        for table_name, handler in build_sorted_router():
            if table_name not in tables:
                continue
            
            df = tables[table_name]
            processed_tables.add(table_name)
            
            if df.empty:
                continue
            
            try:
                handler(ctx, df)
            except Exception as e:
                logger.error(f"'{table_name}' handler hatası: {e}", exc_info=True)
        
        # ───── SIRADA OLMAYAN/EK TABLOLARI İŞLE ─────
        for table_name, df in tables.items():
            if table_name in processed_tables or df.empty:
                continue
            
            handler = router.get(table_name)
            if handler:
                try:
                    handler(ctx, df)
                    logger.debug(f"Ek tablo işlendi: {table_name}")
                except Exception as e:
                    logger.error(f"'{table_name}': {e}", exc_info=True)

        self.units = ctx.units
        scene = build_scene(ctx)
        
        logger.info("[Scene] "
                    f"{len(scene.nodes)} node, "
                    f"{len(scene.frames)} frame, "
                    f"{len(scene.areas)} area, "
                    f"{len(scene.links)} link")
        
        return scene