# tools/report_builders.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from core.report.report_dataframe import ReportDataFrame
from core.report.report_tree import (
    MATERIAL_MODULE_ORDER,
    ReportSection,
    ReportTree,
    ReportTreeBuilder,
    SectionBuilder,
    SectionStatus,
    collect_active_material_types,
)
from data.seismic import get_tsc2018_site_coefficients
from data.enums import MatType
from structload.loads.snow_load import SnowLoad
from structload.loads.spectrum import Spectrum
from structload.utils.meta_tables import parse_project_loads
from structload.windcalc.report import (
    create_cpe_summary_df,
    create_wind_force_df,
    get_parameters_report,
)
from structload.windcalc.wind_analyzer import WindAnalyzer
from structload.windcalc.windengine import WindEngine
from tools.wind_scene_adapter import WindSceneAdapter


@dataclass
class ReportBuildResult:
    produced: list[ReportDataFrame] = field(default_factory=list)
    sections: list[ReportSection] = field(default_factory=list)
    tree: ReportTree = field(default_factory=ReportTree)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return bool(self.skipped or self.failed)


def _overview_identity(project: Any) -> ReportDataFrame:
    unit = project.unit_system
    rows = [
        ("Birim Sistemi", unit.value),
        ("Malzeme", len(project.materials)),
        ("Kesit", len(project.sections)),
        ("Alan Kesiti", len(project.area_sections)),
        ("Yük Paterni", len(project.load_patterns)),
        ("Yük Durumu", len(project.load_cases)),
        ("Kombinasyon", len(project.combinations)),
    ]
    name = getattr(getattr(project, "info", None), "name", None)
    if name:
        rows.insert(0, ("Proje Adı", str(name)))
    df = ReportDataFrame(rows, columns=["Alan", "Değer"])
    df.custom_title = "Proje Künyesi"
    df.custom_desc = "Projenin kimlik ve içerik özeti."
    return df


def _overview_units(project: Any) -> ReportDataFrame:
    unit = project.unit_system
    rows = [
        ("Kuvvet", unit.force_unit),
        ("Uzunluk", unit.length_unit),
        ("Sıcaklık", unit.temp_unit),
    ]
    df = ReportDataFrame(rows, columns=["Büyüklük", "Birim"])
    df.custom_title = "Birim Sistemi"
    df.custom_desc = f"Proje birim sistemi: {unit.value}"
    return df


def _overview_grid(project: Any) -> ReportDataFrame | None:
    grid = project.grid
    xs = sorted(set(grid.x_coords))
    ys = sorted(set(grid.y_coords))
    zs = sorted(set(grid.z_coords))
    if not xs and not ys and not zs:
        return None
    rows: list[tuple[str, str, str, str]] = []
    for i, v in enumerate(xs):
        label = grid.x_labels[i] if i < len(grid.x_labels) else ""
        rows.append(("X", label, f"{v:g}", ""))
    for i, v in enumerate(ys):
        label = grid.y_labels[i] if i < len(grid.y_labels) else ""
        rows.append(("Y", label, f"{v:g}", ""))
    for i, v in enumerate(zs):
        label = grid.z_labels[i] if i < len(grid.z_labels) else ""
        rows.append(("Z", label, f"{v:g}", ""))
    df = ReportDataFrame(rows, columns=["Eksen", "İsim", "Koordinat", "Not"])
    df.custom_title = "Grid Özeti"
    df.custom_desc = f"X: {len(xs)} · Y: {len(ys)} · Z: {len(zs)} eksen"
    return df


class OverviewSectionBuilder:
    section_id = "overview"
    title = "Proje Özeti"

    def is_applicable(self, project: Any, context: Any) -> bool:
        return project is not None

    def build(self, project: Any, context: Any) -> ReportSection:
        frames: list[ReportDataFrame] = [
            _overview_identity(project),
            _overview_units(project),
        ]
        grid_df = _overview_grid(project)
        if grid_df is not None:
            frames.append(grid_df)
        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=SectionStatus.READY,
            frames=frames,
        )


class WindSectionBuilder:
    section_id = "wind"
    title = "Rüzgar Yükleri"

    def is_applicable(self, project: Any, context: Any) -> bool:
        return project is not None

    def build(self, project: Any, context: Any) -> ReportSection:
        points, polygons, _config = WindSceneAdapter.build_inputs(project)
        if not points or not polygons:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=["düğüm veya poligon yok"],
            )

        engine = WindEngine(points=points, polygons=polygons)
        param_rep = get_parameters_report(engine)
        param_rep.custom_title = "Rüzgar Yükü Parametreleri (Genel)"
        frames: list[ReportDataFrame] = [param_rep]
        notes: list[str] = []

        for w_key, w_dir in (
            ("X+ (Yön 1)", np.array([1.0, 0.0, 0.0])),
            ("Y+ (Yön 2)", np.array([0.0, 1.0, 0.0])),
        ):
            analyzer = WindAnalyzer(points, polygons, w_dir)
            zones = analyzer.analyze()
            if not zones:
                notes.append(f"{w_key}: bölge yok")
                continue
            cpe_rep = create_cpe_summary_df(zones, analyzer.engine)
            cpe_rep.custom_title = f"Dış Basınç Katsayıları - {w_key}"
            frames.append(cpe_rep)

            force_rep = create_wind_force_df(zones, analyzer.engine)
            force_rep.custom_title = f"Tasarım Rüzgar Yükleri - {w_key}"
            frames.append(force_rep)

        status = SectionStatus.READY if len(frames) > 1 else SectionStatus.MISSING_DATA
        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=status,
            frames=frames,
            notes=notes,
        )


class SnowSectionBuilder:
    section_id = "snow"
    title = "Kar Yükü"

    def is_applicable(self, project: Any, context: Any) -> bool:
        return project is not None

    def build(self, project: Any, context: Any) -> ReportSection:
        snow_cfg = getattr(getattr(project, "config", None), "snow", None)
        if snow_cfg is None:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=["config.snow tanımsız"],
            )

        required = ("slope", "snow_region", "altitude", "exposure_coefficient", "thermal_coefficient")
        missing = [name for name in required if not hasattr(snow_cfg, name)]
        if missing:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=[f"eksik alanlar: {', '.join(missing)}"],
            )

        payload = {
            "slope": snow_cfg.slope,
            "snow_region": snow_cfg.snow_region,
            "altitude": snow_cfg.altitude,
            "Ce": snow_cfg.exposure_coefficient,
            "Ct": snow_cfg.thermal_coefficient,
        }
        snow_rep = SnowLoad(payload).report()
        frames = [snow_rep] if snow_rep is not None else []
        status = SectionStatus.READY if frames else SectionStatus.MISSING_DATA
        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=status,
            frames=frames,
        )


class LoadsSectionBuilder:
    section_id = "loads"
    title = "Yük Tanımları"

    def is_applicable(self, project: Any, context: Any) -> bool:
        return project is not None

    def build(self, project: Any, context: Any) -> ReportSection:
        payload = {
            "dead_loads": list(getattr(project.loads, "definitions", {}).keys()) or ["konut_dosemesi"],
            "live_loads": list(getattr(project.loads, "live_definitions", {}).keys()) or ["konut"],
            "duvarlar": list(getattr(project.loads, "wall_definitions", {}).keys()),
        }
        produced = parse_project_loads(payload)
        frames = list(produced.values())
        status = SectionStatus.READY if frames else SectionStatus.MISSING_DATA
        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=status,
            frames=frames,
        )


class SeismicSectionBuilder:
    section_id = "seismic"
    title = "Deprem Spektrumu"

    def is_applicable(self, project: Any, context: Any) -> bool:
        return project is not None

    def build(self, project: Any, context: Any) -> ReportSection:
        seismic_cfg = getattr(getattr(project, "config", None), "seismic", None)
        if seismic_cfg is None:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=["config.seismic tanımsız"],
            )

        required = ("ss", "s1", "soil_class")
        missing = [name for name in required if not hasattr(seismic_cfg, name)]
        if missing:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=[f"eksik alanlar: {', '.join(missing)}"],
            )

        fs, f1 = get_tsc2018_site_coefficients(
            seismic_cfg.ss, seismic_cfg.s1, seismic_cfg.soil_class,
        )
        sds, sd1 = seismic_cfg.ss * fs, seismic_cfg.s1 * f1
        eq = Spectrum({
            "dd2": {"Sds": sds, "Sd1": sd1},
            "dd3": {"Sds": sds * 0.5, "Sd1": sd1 * 0.5},
            "zemin_sinifi": seismic_cfg.soil_class,
            "Hn": 10.0,
            "structure_type": "concrete_frame",
        })
        eq.run()
        frames: list[ReportDataFrame] = []
        if eq.table_parameters is not None and not eq.table_parameters.empty:
            frames.append(eq.table_parameters)
        if eq.table_spectrum is not None and not eq.table_spectrum.empty:
            frames.append(eq.table_spectrum)

        status = SectionStatus.READY if frames else SectionStatus.NOT_RUN
        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=status,
            frames=frames,
        )


class MaterialModuleSectionBuilder:
    def __init__(self, section_id: str, title: str, mat_type: MatType) -> None:
        self.section_id = section_id
        self.title = title
        self.mat_type = mat_type

    def is_applicable(self, project: Any, context: Any) -> bool:
        active_types = context.get("active_material_types") if isinstance(context, dict) else None
        if active_types is None:
            active_types = collect_active_material_types(project)
        return self.mat_type in active_types

    def build(self, project: Any, context: Any) -> ReportSection:
        math_model = getattr(project, "math_model", None)
        frame_count = 0
        area_count = 0
        if math_model is not None:
            for frame in getattr(math_model, "frames", {}).values():
                sec = getattr(frame, "section", None)
                mat = getattr(sec, "material", None) if sec is not None else None
                mtype = getattr(mat, "mat_type", None)
                if isinstance(mtype, MatType) and mtype == self.mat_type:
                    frame_count += 1
            for area in getattr(math_model, "areas", {}).values():
                mat = getattr(area, "material", None)
                if mat is None:
                    area_sec = getattr(area, "area_section", None)
                    mat = getattr(area_sec, "material", None) if area_sec is not None else None
                mtype = getattr(mat, "mat_type", None)
                if isinstance(mtype, MatType) and mtype == self.mat_type:
                    area_count += 1

        df = ReportDataFrame(
            [
                ("Malzeme Türü", self.mat_type.sap_label),
                ("Aktif Frame Eleman", frame_count),
                ("Aktif Area Eleman", area_count),
            ],
            columns=["Özellik", "Değer"],
        )
        df.custom_title = f"{self.title} Özeti"
        df.custom_desc = "Modeldeki aktif taşıyıcı eleman dağılımı."
        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=SectionStatus.READY,
            frames=[df],
        )


def default_section_builders() -> list[SectionBuilder]:
    builders: list[SectionBuilder] = [
        OverviewSectionBuilder(),
        WindSectionBuilder(),
        SnowSectionBuilder(),
        LoadsSectionBuilder(),
        SeismicSectionBuilder(),
    ]
    for sec_id, sec_title, mat_type in MATERIAL_MODULE_ORDER:
        builders.append(MaterialModuleSectionBuilder(sec_id, sec_title, mat_type))
    return builders


def build_project_report_tree(project: Any) -> ReportBuildResult:
    result = ReportBuildResult()
    context = {"active_material_types": collect_active_material_types(project)}
    tree_builder = ReportTreeBuilder(default_section_builders())
    sections, tree = tree_builder.build_sections(project, context)
    result.sections = sections
    result.tree = tree

    for sec in sections:
        if sec.status == SectionStatus.MISSING_DATA:
            reason = "; ".join(sec.notes) if sec.notes else "eksik veri"
            result.skipped.append((sec.section_id, reason))
        for frame in sec.frames:
            result.produced.append(frame)

    return result


def build_project_report(project: Any) -> ReportBuildResult:
    return build_project_report_tree(project)