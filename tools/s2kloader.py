# tools/s2kloader.py

import re
from typing import Dict, Optional
from pathlib import Path
import pandas as pd

from domain.definition import GeneralProjectInfo, ProjectInfo, SiteInformation
from domain.scene import Scene
from domain.definition_manager import DefinitionManager
from domain.project import Project
from geometry.scenebuilder import SceneBuilder
from tools.s2k_utils import LoadContext, _assign_loads, _create_areas, _create_frames, _create_links, _create_nodes, build_router, build_sorted_router

from logging_config import CadLogger
logger = CadLogger.get(__name__)


def build_scene_into_project(ctx: LoadContext, project: Project) -> Project:
    builder = SceneBuilder()

    _register_definitions(builder, ctx)
    node_map = _create_nodes(builder, ctx)
    frame_map, n_frames = _create_frames(builder, ctx, node_map)
    area_map, n_areas = _create_areas(builder, ctx, node_map)
    n_links = _create_links(builder, ctx, node_map)
    _assign_loads(ctx, node_map, frame_map, area_map)

    logger.info(...)

    # Scene
    scene = builder.scene
    scene.units = str(ctx.units)
    project.scene = scene

    # Definitions
    project.definitions = builder.def_mgr
    if hasattr(ctx, 'section_cuts'):
        project.definitions.section_cuts = ctx.section_cuts

    # Proje bilgileri — DÜZELTİLDİ
    if isinstance(ctx.project_info, dict):
        gen = ctx.project_info.get("gen")
        site = ctx.project_info.get("site")
        if isinstance(gen, GeneralProjectInfo):
            project.general_info = gen
            # ProjectInfo metadata'sını gen'den türet
            project.info = ProjectInfo(
                name=gen.project_name or "Untitled",
                description=gen.model_description or "",
                author=gen.engineer or "",
            )
        if isinstance(site, SiteInformation):
            project.site_info = site

    return project

def _register_definitions(builder: SceneBuilder, ctx: LoadContext):
    def_mgr = builder.def_mgr

    def_mgr.project_info = ctx.project_info
    for mat in ctx.materials.values():
        def_mgr.add_material(mat)
    for sec in ctx.sections.values():
        def_mgr.add_section(sec)
    for prop in ctx.link_props.values():
        def_mgr.add_link_prop(prop)

    def_mgr.load_patterns = ctx.load_patterns
    def_mgr.load_cases = ctx.load_cases
    def_mgr.modal_cases = ctx.modal_cases
    def_mgr.combinations = ctx.load_combos
    def_mgr.mass_source_map = dict(ctx.mass_source_map)

    def_mgr.spectrum_functions = ctx.spectrum_functions
    def_mgr.response_spectrum_cases = ctx.response_spectrum_cases
    def_mgr.auto_seismics = ctx.auto_seismics
    def_mgr.section_cuts = ctx.section_cuts
    
class S2KParser:
    """SAP2000 .s2k dosyası → tablo DataFrame'leri."""

    PAIR_PATTERN = re.compile(r'(\w+)=("[^"]*"|[^\s]+)')

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path
        self.tables: Dict[str, pd.DataFrame] = {}
        if self.file_path:
            self._parse(self.file_path)

    def _parse(self, file_path: str):
        path = Path(file_path)
        if not path.exists():
            logger.error(f"Dosya bulunamadı: {file_path}")
            return

        try:
            content = path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            logger.error(f"Dosya okuma hatası: {e}")
            return

        logger.info(f"[Parser] Dosya: {path.name}, boyut: {len(content)} bytes")

        content = re.sub(r' _\r?\n', ' ', content)
        raw_tables = re.split(r'TABLE:\s*"*', content)
        logger.info(f"[Parser] {len(raw_tables)} potansiyel tablo")

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
                if pairs:
                    row = {}
                    for k, v in pairs:
                        if v.startswith('"') and v.endswith('"'):
                            v = v[1:-1]
                        row[k] = v
                    rows.append(row)

            if rows:
                self.tables[table_name] = pd.DataFrame(rows)

        logger.info(f"[Parser] {len(self.tables)} tablo yüklendi")

    def get_table(self, name: str) -> pd.DataFrame:
        return self.tables.get(name, pd.DataFrame())

    def get_all_tables(self) -> Dict[str, pd.DataFrame]:
        return self.tables

class S2KLoader:
    """SAP2000 .s2k dosyasından verileri okuyup Project nesnesine yükler."""

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path

        if not self.file_path:
            logger.warning("[Loader] Dosya seçilmedi")
            self.parser = None
            return

        self.parser = S2KParser(self.file_path)
        self.units = None

    def load(self, project: Optional[Project] = None) -> Project:
        """S2K dosyasını yükle ve verilen ya da yeni oluşturulan Project nesnesini doldur."""
        if project is None:
            project = Project()

        if self.parser is None:
            return project

        logger.info("[Loader] Model inşa ediliyor...")

        ctx = LoadContext()
        tables = self.parser.get_all_tables()
        router = build_router()
        processed_tables = set()

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

        for table_name, df in tables.items():
            if table_name in processed_tables or df.empty:
                continue

            handler = router.get(table_name)
            if handler:
                try:
                    handler(ctx, df)
                except Exception as e:
                    logger.error(f"'{table_name}': {e}", exc_info=True)

        self.units = ctx.units
        project = build_scene_into_project(ctx, project)

        

        return project