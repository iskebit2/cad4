# ui/s2k_import_panel.py
"""
S2K Gelişmiş İçe Aktarma Paneli (Dahili Dosya Seçicili)
"""

from typing import Dict, List, Optional, Callable
import os
import imgui
import pandas as pd

from ui.file_dialog import ImGuiFileDialog
from tools.s2kloader import S2KParser, LoadContext, build_scene_into_project, _register_definitions
from tools.s2k_utils import build_router, build_sorted_router
from domain.project import Project
from logging_config import CadLogger

logger = CadLogger.get(__name__)

CORE_DEPENDENCIES = {
    "MATERIAL PROPERTIES 01 - GENERAL",
    "FRAME SECTION PROPERTIES 01 - GENERAL",
    "JOINT COORDINATES",
    "CONNECTIVITY - FRAME",
}

class S2KImportPanel:
    def __init__(self, on_import_complete: Optional[Callable[[Project], None]] = None):
        self.visible = False
        self.file_path: Optional[str] = None
        self.parser: Optional[S2KParser] = None
        self.on_import_complete = on_import_complete

        # Dosya seçici diyalog
        self.file_dialog = ImGuiFileDialog()

        # Tablo seçim durumları
        self.selected_tables: Dict[str, bool] = {}
        self.log_messages: List[str] = []
        self.is_parsed = False

    def open(self, file_path: Optional[str] = None):
        """Paneli açar. Dosya verildiyse ayrıştırır, verilmediyse boş açar."""
        self.visible = True
        if file_path:
            self.load_file(file_path)

    def close(self):
        self.visible = False

    def load_file(self, file_path: str):
        """Seçilen yeni bir S2K dosyasını inceler ve tabloları listeler."""
        self.file_path = file_path
        self.log_messages.clear()
        self.selected_tables.clear()
        self.is_parsed = False

        self._log_info(f"Dosya İncelemeye Alındı: {os.path.basename(file_path)}")
        
        try:
            self.parser = S2KParser(file_path)
            all_tables = self.parser.get_all_tables()
            
            if not all_tables:
                self._log_error("Dosyada geçerli bir tablo bulunamadı.")
                return

            for tbl_name in all_tables.keys():
                self.selected_tables[tbl_name] = True

            self.is_parsed = True
            
            # Özel tablo kontrolü örneği (Örn: Section Cuts)
            has_section_cuts = any("SECTION CUTS" in name for name in all_tables.keys())
            if has_section_cuts:
                self._log_info("✓ Bu dosyada Section Cut tanımları mevcut!")
            else:
                self._log_warn("! Bu dosyada Section Cut tablosu BULUNAMADI.")

            self._log_info(f"Ayrıştırma Başarılı. Toplam {len(all_tables)} tablo bulundu.")
            
        except Exception as e:
            self._log_error(f"S2K Okuma Hatası: {e}")

    def _open_file_dialog(self):
        """Panel içinden dosya seçiciyi başlatır."""
        self.file_dialog.open(
            mode="open",
            filters=[".s2k", ".S2K", ".$2k"],
            title="S2K Dosyası Seç",
            initial_dir=os.path.dirname(self.file_path) if self.file_path else os.getcwd(),
            on_select=self.load_file,
        )

    def _log_info(self, msg: str):
        self.log_messages.append(f"[BİLGİ] {msg}")

    def _log_warn(self, msg: str):
        self.log_messages.append(f"[UYARI] {msg}")

    def _log_error(self, msg: str):
        self.log_messages.append(f"[HATA] {msg}")

    def draw(self):
        if not self.visible:
            return

        # Dosya seçici penceresi çizimi
        self.file_dialog.draw()

        imgui.set_next_window_size(720, 580, imgui.ONCE)
        expanded, opened = imgui.begin("S2K Gelişmiş İçe Aktarma Paneli", True)
        if not opened:
            self.close()
            imgui.end()
            return

        # --- DOSYA SEÇİM ALANI ---
        current_file_name = os.path.basename(self.file_path) if self.file_path else "Henüz dosya seçilmedi"
        imgui.text_colored(f"Aktif Dosya: {current_file_name}", 0.4, 0.8, 1.0)
        imgui.same_line()
        if imgui.button("📂 S2K Dosyası Seç / Değiştir"):
            self._open_file_dialog()

        imgui.separator()

        if not self.is_parsed:
            imgui.text_colored("Lütfen incelemek için bir S2K dosyası seçin...", 0.8, 0.8, 0.3)
            self._draw_log_area()
            imgui.end()
            return

        # --- HIZLI SEÇİM BUTONLARI ---
        if imgui.button("Tümünü Seç"):
            for k in self.selected_tables:
                self.selected_tables[k] = True

        imgui.same_line()
        if imgui.button("Tümünü Kaldır"):
            for k in self.selected_tables:
                self.selected_tables[k] = False

        imgui.same_line()
        if imgui.button("Sadece Asgari Bağımlılıklar"):
            for k in self.selected_tables:
                self.selected_tables[k] = (k in CORE_DEPENDENCIES)

        imgui.separator()

        # --- TABLO LİSTESİ ---
        imgui.text("İçe Aktarılacak Tablolar:")
        imgui.begin_child("TableListChild", 0.0, 240.0, border=True)
        
        all_tables = self.parser.get_all_tables()
        for tbl_name, df in all_tables.items():
            is_core = tbl_name in CORE_DEPENDENCIES
            row_count = len(df)
            label = f"{tbl_name} ({row_count} satır)"

            if is_core:
                imgui.text_colored("[Zorunlu]", 0.9, 0.7, 0.2, 1.0)
                imgui.same_line()

            val = self.selected_tables.get(tbl_name, False)
            changed, new_val = imgui.checkbox(label, val)
            if changed:
                self.selected_tables[tbl_name] = new_val

        imgui.end_child()

        imgui.separator()

        # --- LOG ALANI ---
        imgui.text("Analiz & İçe Aktarma Günlüğü:")
        self._draw_log_area()

        # --- AKSİYON BUTONLARI ---
        imgui.separator()
        if imgui.button("Modeli İnşa Et ve Sahneye Aktar", width=240, height=30):
            self._execute_import()

        imgui.same_line()
        if imgui.button("Kapat", width=80, height=30):
            self.close()

        imgui.end()

    def _draw_log_area(self):
        imgui.begin_child("LogConsoleChild", 0.0, 110.0, border=True)
        for msg in self.log_messages:
            if "[HATA]" in msg:
                imgui.text_colored(msg, 1.0, 0.3, 0.3, 1.0)
            elif "[UYARI]" in msg:
                imgui.text_colored(msg, 1.0, 0.8, 0.2, 1.0)
            else:
                imgui.text_colored(msg, 0.7, 0.9, 0.7, 1.0)
        
        if imgui.get_scroll_y() >= imgui.get_scroll_max_y():
            imgui.set_scroll_here_y(1.0)

        imgui.end_child()

    def _execute_import(self):
        if not self.parser:
            self._log_error("Aktarılacak dosya/parser seçilmedi.")
            return

        ctx = LoadContext()
        tables = self.parser.get_all_tables()
        router = build_router()
        processed_tables = set()

        for table_name, handler in build_sorted_router():
            if table_name not in tables or not self.selected_tables.get(table_name, False):
                continue
            df = tables[table_name]
            processed_tables.add(table_name)
            if not df.empty:
                try:
                    handler(ctx, df)
                    self._log_info(f"✓ {table_name} aktarıldı.")
                except Exception as e:
                    self._log_error(f"✗ {table_name} hatası: {e}")

        for table_name, df in tables.items():
            if table_name in processed_tables or not self.selected_tables.get(table_name, False) or df.empty:
                continue
            handler = router.get(table_name)
            if handler:
                try:
                    handler(ctx, df)
                    self._log_info(f"✓ {table_name} aktarıldı.")
                except Exception as e:
                    self._log_error(f"✗ {table_name} hatası: {e}")

        try:
            new_project = Project()
            
            # 1. S2K LoadContext içindeki grid_lines verisini erkenden projeye aktar ve senkronize et
            if hasattr(ctx, 'grid_lines') and ctx.grid_lines:
                new_project.grid_lines = list(ctx.grid_lines)
                new_project.sync_grid_from_s2k_lines()
            
            if hasattr(ctx, 'joint_constraints') and ctx.joint_constraints:
                new_project.joint_constraints = dict(ctx.joint_constraints)

            # 2. Malzeme, kesit ve tanımları yeni projeye işle
            _register_definitions(new_project, ctx)
            
            # 3. Sahne elemanlarını inşa et ve projeye bağla
            new_project = build_scene_into_project(ctx, new_project)
            
            self._log_info("Model başarıyla sahneye inşa edildi!")
            
            if callable(self.on_import_complete):
                self.on_import_complete(new_project)
                
        except Exception as e:
            self._log_error(f"Sahnede model oluşturulurken hata: {e}")