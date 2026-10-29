# ui/s2k_panel.py
"""
Birleşik S2K İçe/Dışa Aktarma Paneli.

- Tek panel, iki mod: "import" ve "export"
- Import: dosya seç → tabloları listele → seçilenleri yükle → sahne inşa
- Export: sahne/kapsam seç → dosya seç → tablo içeriklerini önizle → yaz
- Ortak: dosya seçici, log alanı, tablo önizleme ağacı
"""
from __future__ import annotations

import os
from collections.abc import Callable

import pandas as pd
from imgui_bundle import imgui

from domain.project import Project
from logging_config import CadLogger
from tools.s2k import LoadContext, S2KLoader, S2KParser
from tools.s2k.handlers import build_router, build_sorted_router
from tools.s2k_exporter import S2KExporter
from ui.base_panel import BasePanel
from ui.file_dialog import ImGuiFileDialog

logger = CadLogger.get(__name__)


CORE_DEPENDENCIES: set[str] = {
    "MATERIAL PROPERTIES 01 - GENERAL",
    "FRAME SECTION PROPERTIES 01 - GENERAL",
    "JOINT COORDINATES",
    "CONNECTIVITY - FRAME",
}


class S2KPanel(BasePanel):
    """S2K import ve export'u tek arayüzde birleştirir."""

    MODE_IMPORT = "import"
    MODE_EXPORT = "export"

    def __init__(
        self,
        on_import_complete: Callable[[Project], None] | None = None,
        get_project: Callable[[], Project | None] | None = None,
        get_selected_elements: Callable[[], list] | None = None,
    ):
        self.visible = False
        self.mode = self.MODE_IMPORT

        self.file_dialog = ImGuiFileDialog()

        self.on_import_complete = on_import_complete
        self.get_project = get_project
        self.get_selected_elements = get_selected_elements

        # --- IMPORT ---
        self.import_path: str | None = None
        self.parser: S2KParser | None = None
        self.import_tables: dict[str, pd.DataFrame] = {}
        self.selected_tables: dict[str, bool] = {}
        self.is_parsed = False

        # --- EXPORT ---
        self.export_path: str | None = None
        self.export_scope = "all"          # "all" | "selected"
        self.export_text: str | None = None
        self.export_table_summary: list[tuple] = []   # [(name, row_count)]
        self.export_table_selected: dict[str, bool] = {}

        # --- LOG ---
        self.log_messages: list[str] = []

    # ==================================================================
    # PUBLIC
    # ==================================================================
    def open(self, mode: str = MODE_IMPORT, file_path: str | None = None):
        self.visible = True
        self.mode = mode
        if mode == self.MODE_IMPORT and file_path:
            self._load_import_file(file_path)
        elif mode == self.MODE_EXPORT and file_path:
            self.export_path = file_path

    def close(self):
        self.visible = False

    # ==================================================================
    # LOG
    # ==================================================================
    def _log_info(self, msg: str):
        self.log_messages.append(f"[BİLGİ] {msg}")

    def _log_warn(self, msg: str):
        self.log_messages.append(f"[UYARI] {msg}")

    def _log_error(self, msg: str):
        self.log_messages.append(f"[HATA] {msg}")

    # ==================================================================
    # DOSYA SEÇİCİ
    # ==================================================================
    def _open_import_dialog(self):
        self.file_dialog.open(
            mode="open",
            filters=[".s2k", ".S2K", ".$2k"],
            title="S2K Dosyası Seç",
            initial_dir=os.path.dirname(self.import_path) if self.import_path else os.getcwd(),
            on_select=self._load_import_file,
        )

    def _open_export_dialog(self):
        self.file_dialog.open(
            mode="save",
            filters=[".s2k"],
            title="S2K Olarak Kaydet",
            initial_dir=os.path.dirname(self.export_path) if self.export_path else os.getcwd(),
            default_name="model.s2k",
            on_select=self._set_export_path,
        )

    # ==================================================================
    # IMPORT
    # ==================================================================
    def _load_import_file(self, file_path: str):
        """S2K dosyasını parse et, tablo listesini hazırla."""
        self.import_path = file_path
        self.log_messages.clear()
        self.selected_tables.clear()
        self.is_parsed = False
        self.import_tables = {}

        self._log_info(f"Dosya inceleniyor: {os.path.basename(file_path)}")

        try:
            self.parser = S2KParser(file_path)
            all_tables = self.parser.get_all_tables()
            if not all_tables:
                self._log_error("Dosyada geçerli tablo bulunamadı.")
                return

            self.import_tables = all_tables
            for name in all_tables:
                self.selected_tables[name] = True
            self.is_parsed = True

            has_cuts = any("SECTION CUTS" in n for n in all_tables)
            if has_cuts:
                self._log_info("Section Cut tanımları bulundu.")
            else:
                self._log_warn("Section Cut tablosu yok.")

            self._log_info(f"Ayrıştırma başarılı: {len(all_tables)} tablo.")
        except Exception as e:
            logger.exception("S2K parse hatası")
            self._log_error(f"S2K okuma hatası: {e}")

    def _execute_import(self):
        if not self.parser:
            self._log_error("Aktarılacak dosya seçilmedi.")
            return

        ctx = self._run_handlers()

        loader = S2KLoader()
        loader.parser = self.parser
        try:
            new_project, meta = loader.load_with_metadata(ctx=ctx)
        except Exception:
            logger.exception("[Import] Scene inşası başarısız")
            self._log_error("Model oluşturulurken hata oluştu.")
            return

        self._log_info(
            f"{meta.program_name} {meta.version} | "
            f"CurrUnits: {meta.curr_units_raw} → {meta.unit_system.value}"
        )
        scn = new_project.scene
        self._log_info(f"✓ {len(scn.frames)} çubuk, {len(scn.nodes)} düğüm")

        if not callable(self.on_import_complete):
            self._log_error("Callback bağlı değil.")
            return
        try:
            self.on_import_complete(new_project)
            self._log_info("İçe aktarma tamamlandı.")
        except Exception:
            logger.exception("[Import] callback hatası")
            self._log_error("Callback sırasında hata oluştu.")

    def _run_handlers(self) -> LoadContext:
        """Seçili tabloları sıralı + kalan router ile ctx'ye aktar."""
        ctx = LoadContext()
        router = build_router()
        processed: set[str] = set()

        # Öncelikli tablolar
        for name, handler in build_sorted_router():
            if not self._should_process(name):
                continue
            processed.add(name)
            self._apply_handler(ctx, name, self.import_tables[name], handler)

        # Kalan tablolar
        for name, df in self.import_tables.items():
            if name in processed or not self._should_process(name):
                continue
            handler = router.get(name)
            if handler:
                self._apply_handler(ctx, name, df, handler)

        return ctx

    def _should_process(self, name: str) -> bool:
        return (
            name in self.import_tables
            and self.selected_tables.get(name, False)
            and not self.import_tables[name].empty
        )

    def _apply_handler(self, ctx: LoadContext, name: str, df: pd.DataFrame, handler):
        try:
            handler(ctx, df)
            self._log_info(f"✓ {name}")
        except Exception as e:
            logger.exception("[Import] Handler hatası: %s", name)
            self._log_error(f"✗ {name}: {e}")

    # ==================================================================
    # EXPORT
    # ==================================================================
    def _set_export_path(self, file_path: str):
        self.export_path = file_path
        self._log_info(f"Export yolu: {file_path}")

    def _resolve_project(self) -> Project | None:
        if callable(self.get_project):
            return self.get_project()
        return None

    def _resolve_selected(self) -> list:
        if callable(self.get_selected_elements):
            return list(self.get_selected_elements() or [])
        return []

    def _build_export_text(self) -> bool:
        project = self._resolve_project()
        if project is None:
            self._log_error("Aktif proje yok.")
            return False

        selected = None
        if self.export_scope == "selected":
            sel = self._resolve_selected()
            if not sel:
                self._log_warn("Seçili eleman yok — tüm sahne export edilecek.")
            else:
                selected = sel

        try:
            text = S2KExporter.export(project, selected_elements=selected)
        except Exception as e:
            logger.exception("Export hatası")
            self._log_error(f"Export üretilemedi: {e}")
            return False

        self.export_text = text
        self.export_table_summary = self._parse_table_summary(text)
        self.export_table_selected = {name: True for name, _ in self.export_table_summary}

        self._log_info(
            f"Export metni hazır: {len(text)} karakter, "
            f"{len(self.export_table_summary)} tablo."
        )
        return True

    @staticmethod
    def _parse_table_summary(text: str) -> list[tuple]:
        """TABLO: "NAME" başlıklarını ve satır sayılarını çıkar."""
        summary: list[tuple] = []
        current = None
        count = 0
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("TABLE:"):
                if current is not None:
                    summary.append((current, count))
                name = stripped[len("TABLE:"):].strip().strip('"')
                current = name
                count = 0
            elif stripped.startswith("END TABLE DATA"):
                break
            elif current is not None and stripped:
                count += 1
        if current is not None:
            summary.append((current, count))
        return summary

    def _write_export_file(self):
        if not self.export_text:
            self._log_error("Önce export metni üretilmeli.")
            return
        path = self.export_path
        if not path:
            self._log_error("Kayıt yolu seçilmedi.")
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.export_text)
            self._log_info(f"Yazıldı: {path}")
        except Exception as e:
            logger.exception("Dosya yazma hatası")
            self._log_error(f"Yazma hatası: {e}")

    # ==================================================================
    # DRAW
    # ==================================================================
    def draw(self):
        if not self.visible:
            return

        self.file_dialog.draw()

        imgui.set_next_window_size(imgui.ImVec2(780, 640), imgui.Cond_.once)
        _, opened = imgui.begin("S2K İçe / Dışa Aktarma", True)
        try:
            if not opened:
                self.close()
                return

            self._draw_mode_selector()
            imgui.separator()

            if self.mode == self.MODE_IMPORT:
                self._draw_import_ui()
            else:
                self._draw_export_ui()

            imgui.separator()
            self._draw_log_area()
        finally:
            imgui.end()

    def _draw_mode_selector(self):
        if imgui.radio_button("İçe Aktar (Import)", self.mode == self.MODE_IMPORT):
            self.mode = self.MODE_IMPORT
        imgui.same_line()
        if imgui.radio_button("Dışa Aktar (Export)", self.mode == self.MODE_EXPORT):
            self.mode = self.MODE_EXPORT

    def _draw_import_ui(self):
        name = os.path.basename(self.import_path) if self.import_path else "Henüz dosya seçilmedi"
        imgui.text_colored(imgui.ImVec4(0.4, 0.8, 1.0, 1.0), f'Dosya: {name}')
        imgui.same_line()
        if imgui.button("📂 Dosya Seç"):
            self._open_import_dialog()

        if not self.is_parsed:
            imgui.text_colored(imgui.ImVec4(0.8, 0.8, 0.3, 1.0), 'Bir S2K dosyası seçin.')
            return

        if imgui.button("Tümünü Seç"):
            for k in self.selected_tables:
                self.selected_tables[k] = True
        imgui.same_line()
        if imgui.button("Tümünü Kaldır"):
            for k in self.selected_tables:
                self.selected_tables[k] = False
        imgui.same_line()
        if imgui.button("Sadece Zorunlular"):
            for k in self.selected_tables:
                self.selected_tables[k] = k in CORE_DEPENDENCIES

        imgui.separator()
        imgui.text("İçe Aktarılacak Tablolar:")
        imgui.begin_child("##ImportTableList", imgui.ImVec2(0, 130))
        try:
            for tbl_name, df in self.import_tables.items():
                is_core = tbl_name in CORE_DEPENDENCIES
                label = f"{tbl_name} ({len(df)} satır)"
                if is_core:
                    imgui.text_colored(imgui.ImVec4(0.9, 0.7, 0.2, 1.0), '[Zorunlu]')
                    imgui.same_line()
                changed, val = imgui.checkbox(label, self.selected_tables.get(tbl_name, False))
                if changed:
                    self.selected_tables[tbl_name] = val
        finally:
            imgui.end_child()

        imgui.separator()
        if imgui.button("Modeli İnşa Et", imgui.ImVec2(200, 30)):
            self._execute_import()
        imgui.same_line()
        if imgui.button("Kapat", imgui.ImVec2(80, 30)):
            self.close()

    def _draw_export_ui(self):
        imgui.text("Kapsam:")
        imgui.same_line()
        if imgui.radio_button("Tüm Sahne", self.export_scope == "all"):
            self.export_scope = "all"
        imgui.same_line()
        if imgui.radio_button("Sadece Seçili", self.export_scope == "selected"):
            self.export_scope = "selected"

        path = self.export_path or "Henüz dosya seçilmedi"
        imgui.text_colored(imgui.ImVec4(0.4, 0.8, 1.0, 1.0), f'Kayıt: {path}')
        imgui.same_line()
        if imgui.button("📂 Kayıt Yeri Seç"):
            self._open_export_dialog()

        imgui.separator()
        if imgui.button("Export Üret", imgui.ImVec2(160, 28)):
            self._build_export_text()

        if self.export_text and self.export_table_summary:
            imgui.same_line()
            if imgui.button("Dosyaya Yaz", imgui.ImVec2(160, 28)):
                self._write_export_file()

            imgui.separator()
            imgui.text("Oluşan Tablolar (önizleme):")
            imgui.begin_child(
                "##ExportTableList",
                imgui.ImVec2(0, 240),
                imgui.ChildFlags_.borders,
            )
            try:
                for tbl_name, count in self.export_table_summary:
                    imgui.text_colored(imgui.ImVec4(0.75, 0.9, 0.75, 1.0), f'{tbl_name}  [{count} satır]')
            finally:
                imgui.end_child()

            imgui.separator()
            if imgui.button("Metni Panoya Kopyala", imgui.ImVec2(200, 26)):
                imgui.set_clipboard_text(self.export_text)
                self._log_info("Export metni panoya kopyalandı.")

        imgui.separator()
        if imgui.button("Kapat", imgui.ImVec2(80, 26)):
            self.close()

    def _draw_log_area(self):
        imgui.text("Günlük:")
        imgui.begin_child("##LogArea", imgui.ImVec2(0, 130))
        try:
            for msg in self.log_messages:
                if "[HATA]" in msg:
                    imgui.text_colored(imgui.ImVec4(1.0, 0.3, 0.3, 1.0), msg)
                elif "[UYARI]" in msg:
                    imgui.text_colored(imgui.ImVec4(1.0, 0.8, 0.2, 1.0), msg)
                else:
                    imgui.text_colored(imgui.ImVec4(0.7, 0.9, 0.7, 1.0), msg)
            if imgui.get_scroll_y() >= imgui.get_scroll_max_y():
                imgui.set_scroll_here_y(1.0)
        finally:
            imgui.end_child()