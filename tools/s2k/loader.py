# tools/s2k/loader.py
"""S2K dosya parser'ı + yüksek seviye loader."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from dataclasses import dataclass, field

import pandas as pd

from core.units import UnitSystem
from domain.project import Project
from geometry.project_builder import ProjectBuilder
from logging_config import CadLogger
from tools.s2k.context import LoadContext
from tools.s2k.handlers import build_router, build_sorted_router
from tools.s2k.scene_builder import (
    assign_joint_loads,
    assign_loads,
    create_areas,
    create_frames,
    create_links,
    create_nodes,
)

logger = CadLogger.get(__name__)

@dataclass
class S2KMetadata:
    program_name: str = ""
    version: str = ""
    curr_units_raw: str = ""
    curr_units_normalized: str = ""
    unit_system: UnitSystem = UnitSystem.N_MM
    num_tables: int = 0
    warnings: list[str] = field(default_factory=list)

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

    def __init__(self, file_path: str | None = None):
        self.file_path = file_path
        self.tables: dict[str, pd.DataFrame] = {}
        self.curr_units: str | None = None
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
            if not rows:
                continue

            new_df = pd.DataFrame(rows)

            if name in self.tables:
                # Aynı isimli tablo → SectionName/Name bazlı birleştir
                old_df = self.tables[name]
                key = next(
                    (c for c in ("SectionName", "Name", "Joint", "Frame", "Area", "Link")
                     if c in old_df.columns and c in new_df.columns),
                    None,
                )
                if key is None:
                    # Anahtar yok → concat
                    self.tables[name] = pd.concat(
                        [old_df, new_df], ignore_index=True,
                    )
                else:
                    # Satır bazlı merge: aynı key → sütunları birleştir
                    merged = old_df.copy()
                    for _, new_row in new_df.iterrows():
                        k_val = new_row.get(key)
                        match = merged[merged[key] == k_val]
                        if match.empty:
                            merged = pd.concat([merged, new_row.to_frame().T],
                                               ignore_index=True)
                        else:
                            idx = match.index[0]
                            for col, val in new_row.items():
                                if pd.notna(val):
                                    merged.at[idx, col] = val
                    self.tables[name] = merged
            else:
                self.tables[name] = new_df

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

    def get_all_tables(self) -> dict[str, pd.DataFrame]:
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

    def __init__(self, file_path: str | None = None):
        self.file_path = file_path
        self.parser = S2KParser(file_path) if file_path else None
        self.units: UnitSystem | None = None

    # ------------------------------------------------------------------
    # PUBLIC
    # ------------------------------------------------------------------
    def load(self, project: Project | None = None) -> Project:
        """Dosyayı parse et + handler'ları çalıştır + project üret."""
        project, _ = self.load_with_metadata(project)
        return project

    def load_with_metadata(self, project=None, *, ctx=None) -> tuple[Project, S2KMetadata]:
        if project is None:
            project = Project()
        if ctx is None:
            if self.parser is None:
                return project, S2KMetadata()
            ctx = self._run_handlers()
        meta = self._build_metadata(ctx)
        project = self.load_from_context(ctx, project)
        return project, meta

    def load_from_context(
        self, ctx: LoadContext, project: Project | None = None,
    ) -> Project:
        """Hazır LoadContext → Project. Değerler S2K biriminde KALIR."""
        if project is None:
            project = Project()

        s2k_sys = UnitSystem.from_sap(ctx.units_source_string)
        self.units = s2k_sys
        logger.info("[Loader] S2K CurrUnits = %s", s2k_sys.value)

        # Project birimini S2K'nın birimine ayarla — DEĞER DEĞİŞMEZ
        project.unit_system = s2k_sys

        builder = ProjectBuilder(project, s2k_sys)
        self._apply_ctx_to_builder(ctx, builder)
        self._build_scene_into_builder(ctx, builder)

        # finalize_and_convert / _migrate_materials ÇAĞRILMAZ

        logger.info("[Loader] Bitti — unit_system = %s", project.unit_system.value)
        return project

    def _build_metadata(self, ctx: LoadContext) -> S2KMetadata:
        meta = S2KMetadata()
        pc = self.parser.get_table("PROGRAM CONTROL") if self.parser else None
        if pc is not None and not pc.empty:
            r = pc.iloc[0]
            meta.program_name = str(r.get("ProgramName", "")).strip()
            meta.version = str(r.get("Version", "")).strip()
            meta.curr_units_raw = str(r.get("CurrUnits", "")).strip()
        meta.curr_units_normalized = ctx.units_source_string
        meta.unit_system = UnitSystem.from_sap(ctx.units_source_string)
        meta.num_tables = len(self.parser.get_all_tables()) if self.parser else 0
        meta.warnings = list(ctx.warnings)
        return meta

    # ------------------------------------------------------------------
    # HANDLERS
    # ------------------------------------------------------------------
    def _run_handlers(self) -> LoadContext:
        """Sıralı + kalan router ile tüm tabloları ctx'ye uygula."""
        ctx = LoadContext()
        tables = self.parser.get_all_tables()

        if not tables:
            logger.debug("[Loader] Tablo yok")
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
        """ctx'teki tüm tanımları builder'a aktar.

        Sıra önemli: material → section → area_section → SD → patterns/cases/combos.
        """
        self._apply_materials(ctx, builder)
        self._apply_sections(ctx, builder)
        self._apply_area_sections(ctx, builder)
        self._apply_load_patterns(ctx, builder)
        self._apply_load_cases(ctx, builder)
        self._apply_combinations(ctx, builder)
        self._apply_constraint_definitions(ctx, builder)
        self._apply_grid(ctx, builder)


    # ------------------------------------------------------------------
    # MATERIALS
    # ------------------------------------------------------------------
    def _apply_materials(self, ctx: LoadContext, builder: ProjectBuilder) -> None:
        for mat in ctx.materials.values():
            builder.add_material(
                mat.name,
                mat_type=mat.mat_type,
                E1=mat.E1, G12=mat.G12, density=mat.density,
                fy=getattr(mat, "fy", 235.0),
                fu=getattr(mat, "fu", 360.0),
                nu12=mat.nu12,
            )


    # ------------------------------------------------------------------
    # SECTIONS
    # ------------------------------------------------------------------
    def _apply_sections(self, ctx, builder):
        from data.enums import SectionType
        from domain.definition import Section as DomSection

        # 1) SD-only section'lar
        for name, sd in ctx.sd_sections.items():
            if name not in ctx.sections:
                ctx.sections[name] = DomSection(
                    name=name,
                    profile_type=SectionType.SD,
                    sd_section=sd,
                )

        # 2) Tüm section'ları işle
        for sec in ctx.sections.values():
            sd = ctx.sd_sections.get(sec.name)
            if sd is not None:
                sec.sd_section = sd

                # SD varsa profile_params'ı türet/zenginleştir (h/b/I33/I22 vs.)
                derived = _derive_params_from_sd(sd)
                if derived:
                    merged = dict(sec.profile_params or {})
                    for k, v in derived.items():
                        # 0 veya None değerleri ezme
                        if merged.get(k) in (None, 0.0):
                            merged[k] = v
                    sec.profile_params = merged

            # material
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
            builder.project.sections[sec.name] = sec


    # ------------------------------------------------------------------
    # AREA SECTIONS
    # ------------------------------------------------------------------
    def _apply_area_sections(self, ctx: LoadContext, builder: ProjectBuilder) -> None:
        for sec in ctx.area_section_objects.values():
            builder.project.add_area_section(sec)


    # ------------------------------------------------------------------
    # LOAD PATTERNS
    # ------------------------------------------------------------------
    def _apply_load_patterns(self, ctx: LoadContext, builder: ProjectBuilder) -> None:
        for lp in ctx.load_patterns.values():
            builder.add_load_pattern(
                lp.name,
                design_type=lp.design_type,
                self_wt_mult=lp.self_wt_mult,
            )


    # ------------------------------------------------------------------
    # LOAD CASES
    # ------------------------------------------------------------------
    def _apply_load_cases(self, ctx: LoadContext, builder: ProjectBuilder) -> None:
        for lc in ctx.load_cases.values():
            builder.add_load_case(
                lc.name,
                case_type=lc.case_type,
                initial_cond=lc.initial_cond,
                design_type=lc.design_type,
                auto_type=lc.auto_type,
                run_case=lc.run_case,
            )


    # ------------------------------------------------------------------
    # COMBINATIONS
    # ------------------------------------------------------------------
    def _apply_combinations(self, ctx: LoadContext, builder: ProjectBuilder) -> None:
        for combo in ctx.load_combos.values():
            builder.add_combination(
                combo.name,
                combo_type=combo.combo_type,
                auto_design=combo.auto_design,
            )


    # ------------------------------------------------------------------
    # CONSTRAINT DEFINITIONS
    # ------------------------------------------------------------------
    def _apply_constraint_definitions(self, ctx: LoadContext, builder: ProjectBuilder) -> None:
        for cd in ctx.constraint_definitions.values():
            builder.project.add_constraint_definition(cd)


    # ------------------------------------------------------------------
    # GRID / CONSTRAINTS
    # ------------------------------------------------------------------
    def _apply_grid(self, ctx: LoadContext, builder: ProjectBuilder) -> None:
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

def _derive_params_from_sd(sd) -> dict:
    """SD polygon(lar)dan bbox + analitik özellik türet."""
    from math import isfinite

    all_pts = []
    for shape in sd.shapes:
        for pt in shape.points:
            all_pts.append((pt.x, pt.y))

    if not all_pts:
        return {}

    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    h = max(ys) - min(ys)
    b = max(xs) - min(xs)

    total_area = 0.0
    for shape in sd.shapes:
        pts = [(p.x, p.y) for p in shape.points]
        if len(pts) < 3:
            continue
        a = 0.0
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            a += x0 * y1 - x1 * y0
        a *= 0.5
        if isfinite(a):
            total_area += abs(a)

    I33 = b * h**3 / 12.0 if h > 0 and b > 0 else 0.0
    I22 = h * b**3 / 12.0 if h > 0 and b > 0 else 0.0

    return {
        "h": h, "b": b,
        "Area": total_area,
        "I33": I33, "I22": I22, "J": I33 + I22,
        "AS2": total_area / 2.0, "AS3": total_area / 2.0,
    }