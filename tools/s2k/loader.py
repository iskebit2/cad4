# tools/s2k/loader.py
"""S2K dosya parser'ı + yüksek seviye loader."""
import logging
import re
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from data.enums import SectionType
from domain.definition import Section
from domain.project import Project
from geometry.scenebuilder import SceneBuilder
from tools.s2k.context import LoadContext
from tools.s2k.handlers import build_router, build_sorted_router
from tools.s2k.scene_builder import (
    create_nodes, create_frames, create_areas, create_links, assign_loads,
)

logger = logging.getLogger(__name__)


# ============================================================================
# PARSER
# ============================================================================
class S2KParser:
    PAIR_PATTERN = re.compile(r'(\w+)=(?:"([^"]*)"|(\S+))')

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path
        self.tables: Dict[str, pd.DataFrame] = {}
        self.curr_units: Optional[str] = None
        if self.file_path:
            self._parse(self.file_path)

    def _parse(self, file_path: str) -> None:
        path = Path(file_path)
        if not path.exists():
            logger.error("[Parser] Dosya yok: %s", file_path)
            return
        content = path.read_text(encoding="utf-8", errors="ignore")

        m = re.search(r'CurrUnits\s*=\s*"([^"]+)"', content)
        if m:
            self.curr_units = m.group(1)
            logger.info("[Parser] CurrUnits: %s", self.curr_units)

        content = re.sub(r'[ ]_\r?\n', ' ', content)
        raw_tables = re.split(r'TABLE:\s*"*', content)

        for raw in raw_tables:
            if not raw.strip():
                continue
            lines = raw.strip().split("\n")
            name = lines[0].strip().strip('"')
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
                    row[key] = quoted if quoted else (unquoted.replace(",", ".") if "," in unquoted else unquoted)
                rows.append(row)
            if rows:
                self.tables[name] = pd.DataFrame(rows)

        logger.info("[Parser] %d tablo parse edildi", len(self.tables))

    def get_table(self, name: str) -> pd.DataFrame:
        return self.tables.get(name, pd.DataFrame())

    def get_all_tables(self) -> Dict[str, pd.DataFrame]:
        return self.tables


# ============================================================================
# LOADER
# ============================================================================
class S2KLoader:
    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path
        self.parser = S2KParser(file_path) if file_path else None
        self.units = None

    def load(self, project: Optional[Project] = None) -> Project:
        if project is None:
            project = Project()
        if self.parser is None:
            return project

        logger.info("[Loader] Model inşa başlıyor")
        ctx = LoadContext()
        tables = self.parser.get_all_tables()
        router = build_router()
        processed = set()

        # Öncelikli tablolar
        for table_name, handler in build_sorted_router():
            if table_name not in tables or tables[table_name].empty:
                continue
            processed.add(table_name)
            try:
                handler(ctx, tables[table_name])
                logger.info("[Loader] %s (%d satır)", table_name, len(tables[table_name]))
            except Exception as e:
                logger.error("[Loader] HATA '%s': %s", table_name, e, exc_info=True)

        # Kalan tablolar
        for table_name, df in tables.items():
            if table_name in processed or df.empty:
                continue
            handler = router.get(table_name)
            if handler:
                try:
                    handler(ctx, df)
                    logger.info("[Loader] (kalan) %s", table_name)
                except Exception as e:
                    logger.error("[Loader] HATA (kalan) '%s': %s", table_name, e, exc_info=True)

        self.units = ctx.units
        project = self._build_scene(ctx, project)
        project._migrate_materials()
        logger.info("[Loader] Bitti")
        return project

    # ------------------------------------------------------------------
    def _build_scene(self, ctx: LoadContext, project: Project) -> Project:
        _register_definitions(project, ctx)

        if ctx.grid_lines:
            project.grid_lines = list(ctx.grid_lines)
            project.sync_grid_from_s2k_lines()
        if ctx.joint_constraints:
            project.joint_constraints = dict(ctx.joint_constraints)

        builder = SceneBuilder(project)
        node_map = create_nodes(builder, ctx)
        frame_map, n_frames = create_frames(builder, ctx, node_map)
        area_map, n_areas = create_areas(builder, ctx, node_map)
        n_links = create_links(builder, ctx, node_map)
        assign_loads(ctx, node_map, frame_map, area_map)

        scene = builder.scene
        scene.units = str(ctx.units.system.value)
        if hasattr(scene, "mark_dirty"):
            scene.mark_dirty()
        project.scene = scene

        logger.info("[Scene] %d düğüm, %d çubuk, %d alan, %d bağ",
                    len(node_map), n_frames, n_areas, n_links)
        return project


def _register_definitions(project: Project, ctx: LoadContext) -> None:
    project.project_info = ctx.project_info
    for m in ctx.materials.values():
        project.add_material(m)
    for s in ctx.sections.values():
        project.add_section(s)
    for p in ctx.link_props.values():
        project.add_link_prop(p)

    if not project.sections:
        logger.warning("[Defs] Kesit yok — DEFAULT ekleniyor")
        default = Section(name="DEFAULT", profile_type=SectionType.RECT,
                          profile_params={"h": 200.0, "b": 100.0}, color=(0.5, 0.5, 0.5))
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
    project.section_cuts = ctx.section_cuts