# tools/s2k/loader.py
"""S2K dosya parser'ı + yüksek seviye loader."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from core.units import UnitSystem
from domain.project import Project
from geometry.project_builder import ProjectBuilder
from logging_config import CadLogger
from tools.s2k.context import LoadContext
from tools.s2k.handlers import build_router, build_sorted_router
from tools.s2k.scene_builder import (
    assign_joint_loads, assign_loads, create_areas, create_frames,
    create_links, create_nodes,
)

logger = CadLogger.get(__name__)


# ============================================================================
# PARSER
# ============================================================================
class S2KParser:
    """S2K dosyasını tablo DataFrame'lerine ayrıştırır.

    S2K formatı:
      - Satır sonu `_` ile devam eder (multi-line kayıtlar)
      - `Key=Value` çiftleri, değerler tırnaklı veya tırnaksız
      - `TABLE:  "İSİM"` başlıkları
    """

    # Key=Value veya Key="quoted value"
    PAIR_PATTERN = re.compile(r'(\w+)=(?:"([^"]*)"|(\S+))')

    # Multi-line: `_` (satır sonu) + girinti → tek boşluk
    LINE_JOIN = re.compile(r'[ \t]*_[ \t]*\r?\n[ \t]*')

    # Tablo başlığı: `TABLE:  "NAME"`
    TABLE_HEADER = re.compile(r'TABLE:\s*"*')

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path
        self.tables: Dict[str, pd.DataFrame] = {}
        self.curr_units: Optional[str] = None
        if self.file_path:
            self._parse(self.file_path)

    # ------------------------------------------------------------------
    def _parse(self, file_path: str) -> None:
        path = Path(file_path)
        if not path.exists():
            logger.error("[Parser] Dosya yok: %s", file_path)
            return

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.error("[Parser] Dosya okunamadı: %s (%s)", file_path, e)
            return

        # Birim sistemi
        m = re.search(r'CurrUnits\s*=\s*"([^"]+)"', content)
        if m:
            self.curr_units = m.group(1)
            logger.info("CurrUnits: %s", self.curr_units)

        # Multi-line kayıtları birleştir
        content = self.LINE_JOIN.sub(' ', content)

        # Tabloları ayır
        raw_tables = self.TABLE_HEADER.split(content)

        for raw in raw_tables:
            if not raw.strip():
                continue

            lines = raw.strip().split("\n")
            name = lines[0].strip().strip('"')
            if not name:
                continue

            rows = self._parse_rows(lines[1:])
            if rows:
                self.tables[name] = pd.DataFrame(rows)

        logger.info("[Parser] %d tablo parse edildi", len(self.tables))

    def _parse_rows(self, lines) -> list:
        rows = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            pairs = self.PAIR_PATTERN.findall(line)
            if not pairs:
                continue
            row = {}
            for key, quoted, unquoted in pairs:
                if quoted:
                    row[key] = quoted
                else:
                    # Sayısal değerlerde virgülü noktaya çevir
                    row[key] = unquoted.replace(",", ".") if "," in unquoted else unquoted
            rows.append(row)
        return rows

    # ------------------------------------------------------------------
    def get_table(self, name: str) -> pd.DataFrame:
        return self.tables.get(name, pd.DataFrame())

    def get_all_tables(self) -> Dict[str, pd.DataFrame]:
        return self.tables


# ============================================================================
# LOADER
# ============================================================================
class S2KLoader:
    """S2K → Project dönüşümü.

    İki yol:
        load(path)             → dosyayı parse et + ctx oluştur + project üret
        load_from_context(ctx) → hazır ctx'ten project üret (panel kullanır)
    """

    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path
        self.parser = S2KParser(file_path) if file_path else None
        self.units: Optional[UnitSystem] = None

    # ------------------------------------------------------------------
    # PUBLIC
    # ------------------------------------------------------------------
    def load(self, project: Optional[Project] = None) -> Project:
        """Dosyayı parse et + handler'ları çalıştır + project üret."""
        if project is None:
            project = Project()
        if self.parser is None:
            return project

        ctx = self._run_handlers()
        return self.load_from_context(ctx, project)

    def load_from_context(
        self,
        ctx: LoadContext,
        project: Optional[Project] = None,
    ) -> Project:
        """Hazır bir LoadContext'ten Project üretir."""
        if project is None:
            project = Project()

        logger.info("[Loader] Model inşa başlıyor")

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

    # ------------------------------------------------------------------
    # HANDLERS
    # ------------------------------------------------------------------
    def _run_handlers(self) -> LoadContext:
        """Sıralı + kalan router ile tüm tabloları ctx'ye uygula."""
        ctx = LoadContext()
        tables = self.parser.get_all_tables()

        if not tables:
            logger.warning("[Loader] Tablo yok")
            return ctx

        sorted_router = self._sorted_router()
        fallback_router = self._fallback_router()
        processed = set()

        # 1. Öncelikli handler'lar (sıralı)
        for table_name, handler in sorted_router:
            df = tables.get(table_name)
            if df is None or df.empty:
                continue
            processed.add(table_name)
            self._safe_call(handler, ctx, df, table_name)

        # 2. Kalan tablolar (router'da tanımlıysa)
        for table_name, df in tables.items():
            if table_name in processed or df.empty:
                continue
            handler = fallback_router.get(table_name)
            if handler:
                self._safe_call(handler, ctx, df, table_name, prefix="(kalan) ")

        return ctx

    def _safe_call(self, handler, ctx: LoadContext, df, table_name: str, prefix: str = ""):
        try:
            handler(ctx, df)
            logger.info("[Loader] %s%s (%d satır)", prefix, table_name, len(df))
        except Exception as e:
            logger.error("[Loader] HATA %s'%s': %s", prefix, table_name, e, exc_info=True)

    # ------------------------------------------------------------------
    # BUILDER
    # ------------------------------------------------------------------
    def _apply_ctx_to_builder(self, ctx: LoadContext, builder: ProjectBuilder) -> None:
        # Materials
        for mat in ctx.materials.values():
            builder.add_material(
                mat.name,
                mat_type=mat.mat_type,
                E1=mat.E1, G12=mat.G12, density=mat.density,
                fy=getattr(mat, "fy", 235.0),
                fu=getattr(mat, "fu", 360.0),
                nu12=mat.nu12,
            )

        # Sections
        for sec in ctx.sections.values():
            mat = None
            if sec.material is not None:
                mat = builder.materials.get(sec.material.name)
            builder.add_section(
                sec.name,
                profile_type=sec.profile_type,
                profile_params=sec.profile_params,
                material=mat,
                color=getattr(sec, "color", (0.8, 0.8, 0.8)),
                sd_section=getattr(sec, "sd_section", None),
                catalog_props=getattr(sec, "catalog_props", {}),
                catalog_source=getattr(sec, "catalog_source", ""),
            )

        # Load patterns
        for lp in ctx.load_patterns.values():
            builder.add_load_pattern(
                lp.name,
                design_type=lp.design_type,
                self_wt_mult=lp.self_wt_mult,
            )

        # Load cases
        for lc in ctx.load_cases.values():
            builder.add_load_case(
                lc.name,
                case_type=lc.case_type,
                initial_cond=lc.initial_cond,
                design_type=lc.design_type,
                auto_type=lc.auto_type,
                run_case=lc.run_case,
            )

        # Combinations
        for combo in ctx.load_combos.values():
            builder.add_combination(
                combo.name,
                combo_type=combo.combo_type,
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

        logger.info(
            "[Scene] %d düğüm, %d çubuk, %d alan, %d bağ",
            len(node_map), n_frames, n_areas, n_links,
        )

    # ------------------------------------------------------------------
    # ROUTER CACHE
    # ------------------------------------------------------------------
    @staticmethod
    @lru_cache(maxsize=1)
    def _sorted_router():
        """build_sorted_router() sonucu — modül yüklenirken bir kez."""
        return build_sorted_router()

    @staticmethod
    @lru_cache(maxsize=1)
    def _fallback_router():
        """build_router() sonucu — modül yüklenirken bir kez."""
        return build_router()