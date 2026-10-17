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
    builder = SceneBuilder(project)

    _register_definitions(project, ctx)
    node_map = _create_nodes(builder, ctx)
    logger.info(f"[S2KLoader Debug] -> Oluşturulan düğüm (node) sayısı: {len(node_map)}")

    frame_map, n_frames = _create_frames(builder, ctx, node_map)
    logger.info(f"[S2KLoader Debug] -> Oluşturulan çubuk (frame) sayısı: {n_frames}")

    area_map, n_areas = _create_areas(builder, ctx, node_map)
    logger.info(f"[S2KLoader Debug] -> Oluşturulan döşeme/alan (area) sayısı: {n_areas}")

    n_links = _create_links(builder, ctx, node_map)
    logger.info(f"[S2KLoader Debug] -> Oluşturulan bağ (link) sayısı: {n_links}")

    _assign_loads(ctx, node_map, frame_map, area_map)
    logger.info("[S2KLoader Debug] -> Yükler elemanlara atandı.")

    # Scene
    scene = builder.scene
    scene.units = str(ctx.units)
    project.scene = scene

    # Section cuts
    if hasattr(ctx, 'section_cuts'):
        project.section_cuts = ctx.section_cuts
        logger.info(f"[S2KLoader Debug] -> {len(ctx.section_cuts)} adet Section Cut yüklendi.")

    # Proje bilgileri
    if isinstance(ctx.project_info, dict):
        gen = ctx.project_info.get("gen")
        site = ctx.project_info.get("site")
        if isinstance(gen, GeneralProjectInfo):
            project.general_info = gen
            project.info = ProjectInfo(
                name=gen.project_name or "Untitled",
                description=gen.model_description or "",
                author=gen.engineer or "",
            )
            logger.info(f"[S2KLoader Debug] -> Proje Adı: {gen.project_name}")
        if isinstance(site, SiteInformation):
            project.site_info = site

    logger.info("[S2KLoader Debug] Sahne projeye başarıyla bağlandı.")
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


class S2KParser:
    PAIR_PATTERN = re.compile(r'(\w+)=("[^"]*"|[^\s]+)')

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path
        self.tables: Dict[str, pd.DataFrame] = {}
        if self.file_path:
            self._parse(self.file_path)

    def _parse(self, file_path: str):
        path = Path(file_path)
        if not path.exists():
            logger.error(f"[Parser Debug] Dosya bulunamadı: {file_path}")
            return

        try:
            content = path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            logger.error(f"[Parser Debug] Dosya okuma hatası: {e}")
            return

        logger.info(f"[Parser Debug] Dosya okundu: {path.name}, Boyut: {len(content)} bytes")

        content = re.sub(r' _\r?\n', ' ', content)
        raw_tables = re.split(r'TABLE:\s*"*', content)
        logger.info(f"[Parser Debug] Toplam {len(raw_tables)} ham tablo bloğu ayrıştırıldı.")

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

        logger.info(f"[Parser Debug] Başarıyla DataFrame'e çevrilen tablo sayısı: {len(self.tables)}")
        logger.info(f"[Parser Debug] Bulunan Tablo İsimleri: {list(self.tables.keys())}")

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

        # Sıralı Router İşlemleri
        for table_name, handler in build_sorted_router():
            if table_name not in tables:
                logger.debug(f"[Loader Debug] Tablo atlandı (Dosyada yok): {table_name}")
                continue

            df = tables[table_name]
            processed_tables.add(table_name)

            if df.empty:
                logger.warning(f"[Loader Debug] Tablo boş, işlenmedi: {table_name}")
                continue

            try:
                handler(ctx, df)
                logger.info(f"[Loader Debug] ✅ Tablo işlendi (Sıralı): {table_name} ({len(df)} satır)")
            except Exception as e:
                logger.error(f"[Loader Debug] ❌ '{table_name}' handler hatası: {e}", exc_info=True)

        # Kalan Tablolar
        for table_name, df in tables.items():
            if table_name in processed_tables or df.empty:
                continue

            handler = router.get(table_name)
            if handler:
                try:
                    handler(ctx, df)
                    logger.info(f"[Loader Debug] ✅ Tablo işlendi (Kalanlar): {table_name} ({len(df)} satır)")
                except Exception as e:
                    logger.error(f"[Loader Debug] ❌ '{table_name}' handler hatası: {e}", exc_info=True)
            else:
                logger.warning(f"[Loader Debug] ⚠️ Tanımsız tablo (Router'da handler yok): {table_name}")

        self.units = ctx.units
        project = build_scene_into_project(ctx, project)
        logger.info("[Loader Debug] Model yükleme ve Inşa süreci tamamlandı.")
        return project