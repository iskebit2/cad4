# tools/s2kloader.py

import re
from typing import Dict, Optional
from pathlib import Path
import pandas as pd

from domain.definition import GeneralProjectInfo, ProjectInfo, SiteInformation
from domain.project import Project
from geometry.scenebuilder import SceneBuilder
from tools.s2k_utils import LoadContext, _assign_loads, _create_areas, _create_frames, _create_links, _create_nodes, build_router, build_sorted_router

from logging_config import CadLogger
logger = CadLogger.get(__name__)


def build_scene_into_project(ctx: LoadContext, project: Project) -> Project:
    logger.info("[S2KLoader Debug] Sahne inşası başlatılıyor...")
    _register_definitions(project, ctx)          # <-- TEK YER

    # Grid ve joint constraint'leri sahne kurulmadan önce aktar
    if getattr(ctx, 'grid_lines', None):
        project.grid_lines = list(ctx.grid_lines)
        project.sync_grid_from_s2k_lines()
        logger.info(f"-> {len(ctx.grid_lines)} Grid Line aktarıldı.")

    if getattr(ctx, 'joint_constraints', None):
        project.joint_constraints = dict(ctx.joint_constraints)

    builder = SceneBuilder(project)
    node_map = _create_nodes(builder, ctx)
    frame_map, n_frames = _create_frames(builder, ctx, node_map)
    area_map, n_areas  = _create_areas(builder, ctx, node_map)
    n_links            = _create_links(builder, ctx, node_map)
    _assign_loads(ctx, node_map, frame_map, area_map)

    scene = builder.scene
    scene.units = str(ctx.units)

    # Sahneyi MUTLAKA dirty işaretle — renderer yeniden yüklesin
    if hasattr(scene, "mark_dirty"):
        scene.mark_dirty()
    elif hasattr(scene, "_is_dirty"):
        scene._is_dirty = True

    project.scene = scene

    logger.info(
        f"Sahne hazır: {len(node_map)} düğüm, {n_frames} çubuk, "
        f"{n_areas} alan, {n_links} bağ"
    )
    return project


def _register_definitions(project: Project, ctx: LoadContext):
    logger.info("[S2KLoader Debug] Tanımlar projeye kaydediliyor...")
    project.project_info = ctx.project_info
    
    logger.info(f"  - Malzeme sayısı: {len(ctx.materials)}")
    for mat in ctx.materials.values():
        project.add_material(mat)

    logger.info(f"  - Kesit sayısı: {len(ctx.sections)}")
    for sec in ctx.sections.values():
        project.add_section(sec)

    logger.info(f"  - Link Prop sayısı: {len(ctx.link_props)}")
    for prop in ctx.link_props.values():
        project.add_link_prop(prop)

    project.load_patterns = ctx.load_patterns
    project.load_cases = ctx.load_cases
    project.modal_cases = ctx.modal_cases
    project.combinations = ctx.load_combos
    project.mass_source_map = dict(ctx.mass_source_map)
    project.spectrum_functions = ctx.spectrum_functions
    project.response_spectrum_cases = ctx.response_spectrum_cases
    project.auto_seismics = ctx.auto_seismics
    project.section_cuts = getattr(ctx, 'section_cuts', {})
    logger.info("[S2KLoader Debug] Tüm tanımlar aktarıldı.")


# class S2KParser:
#     PAIR_PATTERN = re.compile(r'(\w+)=("[^"]*"|[^\s]+)')

#     def __init__(self, file_path: Optional[str] = None):
#         self.file_path = file_path
#         self.tables: Dict[str, pd.DataFrame] = {}
#         if self.file_path:
#             self._parse(self.file_path)

#     def _parse(self, file_path: str):
#         path = Path(file_path)
#         if not path.exists():
#             logger.error(f"[Parser Debug] Dosya bulunamadı: {file_path}")
#             return

#         try:
#             content = path.read_text(encoding='utf-8', errors='ignore')
#         except Exception as e:
#             logger.error(f"[Parser Debug] Dosya okuma hatası: {e}")
#             return

#         logger.info(f"[Parser Debug] Dosya okundu: {path.name}, Boyut: {len(content)} bytes")

#         content = re.sub(r' _\r?\n', ' ', content)
#         raw_tables = re.split(r'TABLE:\s*"*', content)
#         logger.info(f"[Parser Debug] Toplam {len(raw_tables)} ham tablo bloğu ayrıştırıldı.")

#         # Optimize edilmiş satır parse döngüsü
#         parsed_tables = {}
#         for raw in raw_tables:
#             if not raw.strip():
#                 continue

#             lines = raw.strip().split('\n')
#             table_name = lines[0].strip().strip('"')
#             rows = []

#             for line in lines[1:]:
#                 line = line.strip()
#                 if not line:
#                     continue
#                 pairs = self.PAIR_PATTERN.findall(line)
#                 if pairs:
#                     row = {k: (v[1:-1] if v.startswith('"') and v.endswith('"') else v) for k, v in pairs}
#                     rows.append(row)

#             if rows:
#                 parsed_tables[table_name] = pd.DataFrame(rows)

#         self.tables = parsed_tables
#         logger.info(f"[Parser Debug] Başarıyla DataFrame'e çevrilen tablo sayısı: {len(self.tables)}")

#     def get_table(self, name: str) -> pd.DataFrame:
#         return self.tables.get(name, pd.DataFrame())

#     def get_all_tables(self) -> Dict[str, pd.DataFrame]:
#         return self.tables
class S2KParser:
    # Key=Value; değer ya tırnaklı ya da boşluksuz tek token
    PAIR_PATTERN = re.compile(r'(\w+)=(?:"([^"]*)"|(\S+))')

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path
        self.tables: Dict[str, pd.DataFrame] = {}
        self.curr_units: Optional[str] = None
        if self.file_path:
            self._parse(self.file_path)

    def _parse(self, file_path: str):
        path = Path(file_path)
        if not path.exists():
            logger.error(f"[Parser] Dosya yok: {file_path}")
            return

        content = path.read_text(encoding='utf-8', errors='ignore')

        # Birim etiketi
        m = re.search(r'CurrUnits\s*=\s*"([^"]+)"', content)
        if m:
            self.curr_units = m.group(1)
            logger.info(f"[Parser] Birim: {self.curr_units}")

        # Satır devamı: " _" ile biten satırlar birleştirilir
        content = re.sub(r'[ ]_\r?\n', ' ', content)

        raw_tables = re.split(r'TABLE:\s*"*', content)
        logger.info(f"[Parser] {len(raw_tables)} ham tablo bloğu")

        parsed_tables: Dict[str, pd.DataFrame] = {}
        for raw in raw_tables:
            if not raw.strip():
                continue

            lines = raw.strip().split('\n')
            table_name = lines[0].strip().strip('"')
            rows = []

            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                pairs = self.PAIR_PATTERN.findall(line)
                if not pairs:
                    continue
                row = {}
                for key, quoted, unquoted in pairs:
                    if quoted:
                        # Tırnaklı metin — DOKUNMA
                        row[key] = quoted
                    else:
                        # Tırnaksız — virgül varsa ondalık ayracıdır
                        row[key] = unquoted.replace(',', '.') if ',' in unquoted else unquoted
                rows.append(row)

            if rows:
                parsed_tables[table_name] = pd.DataFrame(rows)

        self.tables = parsed_tables
        logger.info(f"[Parser] {len(self.tables)} tablo parse edildi.")

        self._convert_units_to_n_mm()

    def _convert_units_to_n_mm(self):
        """Eğer dosya birimi Ton, m, C ise, N ve mm cinsine dönüştürür."""
        if not self.curr_units or "Ton" not in self.curr_units or "m" not in self.curr_units:
            return

        logger.info("[Parser Debug] Birim dönüşümü tetiklendi: Ton, m -> N, mm dönüştürülüyor...")
        
        # Dönüşüm Çarpanları:
        # 1 Ton = 10,000 N (veya yerçekimiyle 9806.65 ama yapısal yazılımlarda genellikle 1 tf = 9.80665 kN = 9806.65 N veya 1 ton = 10 kN baz alınır. Projenizin standart katsayısına göre 9806.65 veya 10000 kullanılabilir). Standard SAP2000 ton-kN-m dönüşümlerinde 1 tf = 9.80665 kN, yani N cinsinden 9806.65 tir. Veya düz tablolarda kuvvet birimi ton ise Newton'a çevrilir.
        # Uzunluk: 1 m = 1000 mm
        
        force_factor = 9806.65  # Ton -> N (veya projeye göre 10000)
        length_factor = 1000.0  # m -> mm
        
        # Koordinat ve uzunluk içeren sütunlar (örneğin X, Y, Z, Length vb.) length_factor ile çarpılmalı
        # Kuvvet/Yük içeren sütunlar force_factor ile (veya basınca bağlı olarak stress birimleri değişir)
        
        length_cols = {'X', 'Y', 'Z', 'CoordX', 'CoordY', 'CoordZ', 'Length', 'Span'}
        
        for table_name, df in self.tables.items():
            for col in df.columns:
                # Sütun adı uzunluk içeriyorsa veya koordinatsa mm'ye çevir
                if col in length_cols or any(lc in col.lower() for lc in ['x', 'y', 'z', 'length', 'width', 'height', 'thick']):
                    try:
                        df[col] = pd.to_numeric(df[col], errors='ignore')
                        if pd.api.types.is_numeric_dtype(df[col]):
                            df[col] = df[col] * length_factor
                    except Exception:
                        pass
                        
                # Kuvvet/Yük kolonları için dönüştürme eklenebilir (İhtiyaca göre özelleştirilebilir)

    def get_table(self, name: str) -> pd.DataFrame:
        return self.tables.get(name, pd.DataFrame())

    def get_all_tables(self) -> Dict[str, pd.DataFrame]:
        return self.tables

class S2KLoader:
    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path
        if not self.file_path:
            logger.warning("[Loader Debug] Dosya seçilmedi")
            self.parser = None
            return

        self.parser = S2KParser(self.file_path)
        self.units = None

    def load(self, project: Optional[Project] = None) -> Project:
        if project is None:
            project = Project()

        if self.parser is None:
            return project

        logger.info("[Loader Debug] Model inşa süreci başlatılıyor...")

        ctx = LoadContext()
        tables = self.parser.get_all_tables()
        router = build_router()
        processed_tables = set()

        # Sıralı Router İşlemleri (Öncelikli tablolar önce işlenir)
        for table_name, handler in build_sorted_router():
            if table_name not in tables:
                continue

            df = tables[table_name]
            processed_tables.add(table_name)

            if df.empty:
                continue

            try:
                handler(ctx, df)
                logger.debug(f"[Loader Debug] Tablo işlendi (Sıralı): {table_name}")
            except Exception as e:
                logger.error(f"[Loader Debug] '{table_name}' handler hatası: {e}", exc_info=True)

        # Kalan Tablolar
        for table_name, df in tables.items():
            if table_name in processed_tables or df.empty:
                continue

            handler = router.get(table_name)
            if handler:
                try:
                    handler(ctx, df)
                    logger.debug(f"[Loader Debug] Tablo işlendi (Kalan): {table_name}")
                except Exception as e:
                    logger.error(f"[Loader Debug] '{table_name}' handler hatası: {e}", exc_info=True)

        self.units = ctx.units
        project = build_scene_into_project(ctx, project)
        logger.info("[Loader Debug] Model yükleme ve inşa süreci tamamlandı.")
        
        return project