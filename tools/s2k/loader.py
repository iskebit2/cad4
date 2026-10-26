# tools/s2k/loader.py
"""S2K dosya parser'ı + yüksek seviye loader."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from core.units import UnitSystem
from domain.project import Project
from geometry.project_builder import ProjectBuilder
from tools.s2k.context import LoadContext
from tools.s2k.handlers import build_router, build_sorted_router
from tools.s2k.scene_builder import (
    assign_joint_loads, assign_loads, create_areas, create_frames, create_links, create_nodes,
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
        self.units: Optional[UnitSystem] = None

    def load_from_context(
        self,
        ctx: LoadContext,
        project: Optional[Project] = None,
    ) -> Project:
        """Hazır bir LoadContext'ten Project üretir (panel/import için)."""
        if project is None:
            project = Project()

        logger.info("[Loader] Model inşa başlıyor (harici ctx)")

        s2k_sys = UnitSystem.from_sap(ctx.units_source_string)
        self.units = s2k_sys
        logger.info("[Loader] S2K CurrUnits = %s", s2k_sys.value)

        builder = ProjectBuilder(project, s2k_sys)
        self._apply_ctx_to_builder(ctx, builder)
        self._build_scene_into_builder(ctx, builder)
        builder.finalize_and_convert(UnitSystem.N_MM)

        project._migrate_materials()
        logger.info("[Loader] Bitti")
        return project
    
    def load(self, project: Optional[Project] = None) -> Project:
        if project is None:
            project = Project()
        if self.parser is None:
            return project
        ctx = self._run_handlers()
        return self.load_from_context(ctx, project)

    # ------------------------------------------------------------------
    def _run_handlers(self) -> LoadContext:
        ctx = LoadContext()
        tables = self.parser.get_all_tables()
        router = build_router()
        processed = set()

        for table_name, handler in build_sorted_router():
            if table_name not in tables or tables[table_name].empty:
                continue
            processed.add(table_name)
            try:
                handler(ctx, tables[table_name])
                logger.info("[Loader] %s (%d satır)", table_name, len(tables[table_name]))
            except Exception as e:
                logger.error("[Loader] HATA '%s': %s", table_name, e, exc_info=True)

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

        return ctx

    def _apply_ctx_to_builder(self, ctx: LoadContext, builder: ProjectBuilder) -> None:
        # Materials
        for mat in ctx.materials.values():
            builder.add_material(
                mat.name, mat_type=mat.mat_type,
                E1=mat.E1, G12=mat.G12, density=mat.density,
                fy=getattr(mat, "fy", 235.0),
                fu=getattr(mat, "fu", 360.0),
                nu12=mat.nu12,
            )
        # Sections
        for sec in ctx.sections.values():
            mat = builder.materials.get(sec.material.name) if sec.material else None
            builder.add_section(
                sec.name, profile_type=sec.profile_type,
                profile_params=sec.profile_params,
                material=mat, sd_section=getattr(sec, "sd_section", None),
                catalog_props=getattr(sec, "catalog_props", {}),
                catalog_source=getattr(sec, "catalog_source", ""),
            )
        # Load patterns
        for lp in ctx.load_patterns.values():
            builder.add_load_pattern(
                lp.name, design_type=lp.design_type,
                self_wt_mult=lp.self_wt_mult,
            )
        # Load cases
        for lc in ctx.load_cases.values():
            builder.add_load_case(
                lc.name, case_type=lc.case_type,
                initial_cond=lc.initial_cond,
                design_type=lc.design_type,
                auto_type=lc.auto_type,
                run_case=lc.run_case,
            )
        # Combos
        for combo in ctx.load_combos.values():
            builder.add_combination(
                combo.name, combo_type=combo.combo_type,
                auto_design=combo.auto_design,
            )
        # Grid / constraints
        if ctx.grid_lines:
            builder.set_grid_lines(ctx.grid_lines)
        if ctx.joint_constraints:
            builder.set_joint_constraints(ctx.joint_constraints)

    def _build_scene_into_builder(self, ctx: LoadContext, builder: ProjectBuilder) -> None:
        node_map = create_nodes(builder, ctx)
        frame_map, n_frames = create_frames(builder, ctx, node_map)
        area_map, n_areas = create_areas(builder, ctx, node_map)
        n_links = create_links(builder, ctx, node_map)
        assign_loads(ctx, node_map, frame_map, area_map)
        assign_joint_loads(ctx, node_map)

        logger.info("[Scene] %d düğüm, %d çubuk, %d alan, %d bağ",
                    len(node_map), n_frames, n_areas, n_links)