# tools/s2kloader.py

import re
from typing import Dict, Optional
from pathlib import Path
import pandas as pd

from data.enums import SectionType
from domain.definition import GeneralProjectInfo, ProjectInfo, Section, SiteInformation
from domain.project import Project
from geometry.scenebuilder import SceneBuilder
from tools.s2k_utils import LoadContext, _assign_loads, _create_areas, _create_frames, _create_links, _create_nodes, build_router, build_sorted_router

from logging_config import CadLogger
logger = CadLogger.get(__name__)


def build_scene_into_project(ctx: LoadContext, project: Project) -> Project:
    logger.info("[Scene] İnşa başlıyor")
    _register_definitions(project, ctx)

    if getattr(ctx, 'grid_lines', None):
        project.grid_lines = list(ctx.grid_lines)
        project.sync_grid_from_s2k_lines()
        logger.info(f"[Scene] {len(ctx.grid_lines)} grid line aktarıldı")

    if getattr(ctx, 'joint_constraints', None):
        project.joint_constraints = dict(ctx.joint_constraints)

    builder = SceneBuilder(project)

    logger.info("[Scene] Node'lar oluşturuluyor...")
    node_map = _create_nodes(builder, ctx)
    logger.info(f"[Scene]   → {len(node_map)} düğüm")

    logger.info("[Scene] Frame'ler oluşturuluyor...")
    frame_map, n_frames = _create_frames(builder, ctx, node_map)
    logger.info(f"[Scene]   → {n_frames} çubuk")

    logger.info("[Scene] Area'lar oluşturuluyor...")
    area_map, n_areas = _create_areas(builder, ctx, node_map)
    logger.info(f"[Scene]   → {n_areas} alan")

    logger.info("[Scene] Link'ler oluşturuluyor...")
    n_links = _create_links(builder, ctx, node_map)
    logger.info(f"[Scene]   → {n_links} bağ")

    logger.info("[Scene] Yükler atanıyor...")
    _assign_loads(ctx, node_map, frame_map, area_map)
    logger.info("[Scene] Yükler atandı")

    scene = builder.scene
    scene.units = str(ctx.units)
    if hasattr(scene, "mark_dirty"):
        scene.mark_dirty()
    project.scene = scene

    logger.info(
        f"[Scene] TAMAM: {len(node_map)} düğüm, {n_frames} çubuk, "
        f"{n_areas} alan, {n_links} bağ"
    )
    return project


def _register_definitions(project: Project, ctx: LoadContext):
    logger.info(f"[Defs] Başlıyor: materials={len(ctx.materials)}, "
                f"sections={len(ctx.sections)}, link_props={len(ctx.link_props)}")
    project.project_info = ctx.project_info

    for mat in ctx.materials.values():
        project.add_material(mat)
    for sec in ctx.sections.values():
        project.add_section(sec)
    for prop in ctx.link_props.values():
        project.add_link_prop(prop)

    # ✅ Kesit yoksa DEFAULT fallback ekle (project'e de)
    if not project.sections:
        logger.warning("[Defs] Hiç kesit yok — DEFAULT fallback oluşturuluyor")
        default = Section(
            name="DEFAULT",
            profile_type=SectionType.RECT,
            profile_params={"h": 200.0, "b": 100.0},
            color=(0.5, 0.5, 0.5),
        )
        project.add_section(default)
        ctx.sections["DEFAULT"] = default

    project.load_patterns = ctx.load_patterns
    project.load_cases = ctx.load_cases
    project.modal_cases = ctx.modal_cases
    project.combinations = ctx.load_combos
    project.mass_source_map = dict(ctx.mass_source_map)
    project.spectrum_functions = ctx.spectrum_functions
    project.response_spectrum_cases = ctx.response_spectrum_cases
    project.auto_seismics = ctx.auto_seismics
    project.section_cuts = getattr(ctx, 'section_cuts', {})
    logger.info(f"[Defs] Bitti: {len(project.sections)} kesit, "
                f"{len(project.materials)} malzeme")

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
        # --- TEŞHİS: tablo listesi ---
        for tname in sorted(self.tables.keys()):
            logger.info(f"[Parser] TABLO: '{tname}' ({len(self.tables[tname])} satır)")

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
                logger.info(f"[Loader] S2K'da YOK: '{table_name}'")
                continue

            df = tables[table_name]
            processed_tables.add(table_name)

            if df.empty:
                logger.info(f"[Loader] BOŞ: '{table_name}'")
                continue

            try:
                handler(ctx, df)
                logger.info(f"[Loader] İŞLENDİ: '{table_name}' ({len(df)} satır)")
            except Exception as e:
                logger.error(f"[Loader] HATA: '{table_name}': {e}", exc_info=True)

        # Kalan Tablolar
        for table_name, df in tables.items():
            if table_name in processed_tables or df.empty:
                continue

            handler = router.get(table_name)
            if handler:
                try:
                    handler(ctx, df)
                    logger.info(f"[Loader] İŞLENDİ (kalan): '{table_name}' ({len(df)} satır)")
                except Exception as e:
                    logger.error(f"[Loader] HATA (kalan): '{table_name}': {e}", exc_info=True)
            else:
                logger.info(f"[Loader] ROUTER'DA YOK: '{table_name}' ({len(df)} satır)")

        self.units = ctx.units
        project = build_scene_into_project(ctx, project)
        project._migrate_materials()
        logger.info("[Loader Debug] Model yükleme ve inşa süreci tamamlandı.")
        
        return project