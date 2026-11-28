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
from structload.windcalc.report import (
    create_cpe_summary_df,
    create_wind_force_df,
    get_parameters_report,
)
from structload.windcalc.wind_analyzer import WindAnalyzer
from structload.windcalc.windengine import WindEngine
from tools.wind_scene_adapter import WindSceneAdapter
from core.design.steel_check import build_steel_frame_check_frames
from core.design.timber_check import build_timber_floor_frames, build_timber_frame_check_frames

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
        patterns = getattr(project, "load_patterns", {}) or {}
        assignments = _collect_load_assignments(project)
        frames: list[ReportDataFrame] = []
        notes: list[str] = []

        for category, title in (
            ("dead", "Ölü Yükler"),
            ("live", "Hareketli Yükler"),
        ):
            category_patterns = {
                name: pattern
                for name, pattern in patterns.items()
                if _load_pattern_category(pattern) == category
            }
            if not category_patterns:
                continue

            pattern_rows = []
            category_assignments = []
            for name in sorted(category_patterns):
                pattern = category_patterns[name]
                matching = assignments.get(name, [])
                pattern_rows.append({
                    "Yük Paterni": name,
                    "Öz Ağırlık Çarpanı": getattr(pattern, "self_wt_mult", 0.0),
                    "Atama Sayısı": len(matching),
                })
                category_assignments.extend(matching)

            pattern_frame = ReportDataFrame(
                pattern_rows,
                columns=["Yük Paterni", "Öz Ağırlık Çarpanı", "Atama Sayısı"],
                custom_title=f"{title} - Yük Paternleri",
                custom_desc=(
                    "Projedeki yük paternleri ve elemanlara atanmış "
                    "yük kayıtlarının sayısı."
                ),
                column_formats={"Öz Ağırlık Çarpanı": ".3f"},
            )
            frames.append(pattern_frame)

            if category_assignments:
                detail_frame = ReportDataFrame(
                    category_assignments,
                    columns=["Eleman", "Yük Paterni", "Yük Türü", "Yük Değeri"],
                    custom_title=f"{title} - Atamalar",
                    custom_desc="Elemanlara atanmış değerler; birimler proje birim sistemindedir.",
                )
                frames.append(detail_frame)

        unknown_patterns = sorted(
            name for name in assignments if name not in patterns
        )
        if unknown_patterns:
            notes.append(
                "Atama yapılmış ancak projede tanımı bulunmayan yük paternleri: "
                + ", ".join(unknown_patterns)
            )

        if not frames:
            notes.append("Projede ölü veya hareketli yük paterni tanımlanmamış.")

        status = SectionStatus.READY if frames else SectionStatus.MISSING_DATA
        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=status,
            frames=frames,
            notes=notes,
        )


def _load_pattern_category(pattern: Any) -> str | None:
    design_type = str(getattr(pattern, "design_type", "")).strip().casefold()
    if design_type.startswith(("dead", "super dead")) or design_type == "ölü":
        return "dead"
    if design_type.startswith("live") or design_type in {"hareketli", "canlı"}:
        return "live"
    return None


def _material_type(material: Any) -> MatType | None:
    raw_type = getattr(material, "mat_type", None)
    if raw_type is None:
        return None
    return MatType.from_sap(raw_type)


def _collect_load_assignments(project: Any) -> dict[str, list[dict[str, str]]]:
    model = getattr(project, "math_model", None)
    if model is None:
        return {}

    force_unit = project.unit_system.force_unit
    length_unit = project.unit_system.length_unit
    line_load_unit = f"{force_unit}/{length_unit}"
    area_load_unit = f"{force_unit}/{length_unit}²"
    result: dict[str, list[dict[str, str]]] = {}

    def add(pattern_name: Any, element: str, load_type: str, value: str) -> None:
        name = str(pattern_name or "").strip()
        if not name:
            return
        result.setdefault(name, []).append({
            "Eleman": element,
            "Yük Paterni": name,
            "Yük Türü": load_type,
            "Yük Değeri": value,
        })

    def element_label(kind: str, item: Any) -> str:
        label = str(getattr(item, "label", "") or "").strip()
        unique_id = getattr(item, "unique_id", "?")
        return f"{kind} {label or unique_id}"

    for node in getattr(model, "nodes", {}).values():
        element = element_label("Düğüm", node)
        for load in getattr(node, "loads", []) or []:
            force = ", ".join(f"{axis}={getattr(load, axis, 0.0):g}" for axis in ("fx", "fy", "fz"))
            moment = ", ".join(f"{axis}={getattr(load, axis, 0.0):g}" for axis in ("mx", "my", "mz"))
            add(
                getattr(load, "pattern_name", ""),
                element,
                "Noktasal yük",
                f"F: {force} {force_unit}; M: {moment} {force_unit}·{length_unit}",
            )

    for frame in getattr(model, "frames", {}).values():
        element = element_label("Çubuk", frame)
        for load in (getattr(frame, "dist_load_sets", {}) or {}).values():
            segments = getattr(load, "segments", []) or []
            details = "; ".join(
                f"x={segment.x1:g}..{segment.x2:g}: "
                f"q={segment.q1:g}..{segment.q2:g} {line_load_unit}"
                for segment in segments
            )
            if details:
                add(
                    getattr(load, "pattern_name", ""),
                    element,
                    "Dağıtılmış yük",
                    details,
                )
        for load in getattr(frame, "point_loads", []) or []:
            force = ", ".join(
                f"{axis}={getattr(load, axis, 0.0):g}"
                for axis in ("fx", "fy", "fz")
            )
            moment = ", ".join(
                f"{axis}={getattr(load, axis, 0.0):g}"
                for axis in ("mx", "my", "mz")
            )
            add(
                getattr(load, "pattern_name", ""),
                element,
                "Çubuk noktasal yükü",
                f"F: {force} {force_unit}; M: {moment} {force_unit}·{length_unit}",
            )
        for load in getattr(frame, "gravity_loads", []) or []:
            add(
                getattr(load, "pattern_name", ""),
                element,
                "Yerçekimi yük çarpanı",
                f"X={load.multiplier_x:g}, Y={load.multiplier_y:g}, Z={load.multiplier_z:g}",
            )

    for area in getattr(model, "areas", {}).values():
        element = element_label("Alan", area)
        for load in getattr(area, "uniform_loads", []) or []:
            direction = getattr(load, "direction", "")
            direction = getattr(direction, "value", direction)
            add(
                getattr(load, "pattern_name", ""),
                element,
                "Düzgün alan yükü",
                f"{load.value:g} {area_load_unit}, yön={direction}",
            )
        for load in getattr(area, "uniform_to_frame_loads", []) or []:
            direction = getattr(load, "direction", "")
            direction = getattr(direction, "value", direction)
            add(
                getattr(load, "pattern_name", ""),
                element,
                "Düzgün yük aktarımı",
                f"{load.value:g} {area_load_unit}, yön={direction}",
            )
        for load in getattr(area, "surface_pressures", []) or []:
            add(
                getattr(load, "pattern_name", ""),
                element,
                "Yüzey basıncı",
                f"{load.pressure:g} {area_load_unit}, yüz={load.face}",
            )
        for load in getattr(area, "gravity_loads", []) or []:
            add(
                getattr(load, "pattern_name", ""),
                element,
                "Yerçekimi yük çarpanı",
                f"X={load.multiplier_x:g}, Y={load.multiplier_y:g}, Z={load.multiplier_z:g}",
            )

    for polygon_id, analysis in (getattr(model, "polygon_analysis", {}) or {}).items():
        polygon = getattr(model, "polygons", {}).get(polygon_id)
        element = element_label("Poligon", polygon) if polygon is not None else f"Poligon {polygon_id}"
        for load in getattr(analysis, "assigned_loads", []) or []:
            direction = getattr(load, "direction", "")
            direction = getattr(direction, "value", direction)
            add(
                getattr(load, "pattern_name", ""),
                element,
                "Poligon alan yükü",
                f"{load.value:g} {area_load_unit}, yön={direction}",
            )

    return result


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
        if self.mat_type == MatType.TIMBER and bool(getattr(project, "timber_floors", None)):
            return True
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
                if isinstance(sec, str):
                    sec = getattr(project, "sections", {}).get(sec)
                mat = getattr(sec, "material", None) if sec is not None else None
                if _material_type(mat) == self.mat_type:
                    frame_count += 1
            for area in getattr(math_model, "areas", {}).values():
                mat = getattr(area, "material", None)
                if mat is None:
                    area_sec = getattr(area, "area_section", None)
                    mat = getattr(area_sec, "material", None) if area_sec is not None else None
                if _material_type(mat) == self.mat_type:
                    area_count += 1

        summary_df = ReportDataFrame(
            [
                ("Malzeme Türü", self.mat_type.sap_label),
                ("Aktif Frame Eleman", frame_count),
                ("Aktif Area Eleman", area_count),
            ],
            columns=["Özellik", "Değer"],
        )
        summary_df.custom_title = f"{self.title} Özeti"
        summary_df.custom_desc = "Modeldeki aktif taşıyıcı eleman dağılımı."

        frames: list[ReportDataFrame] = [summary_df]
        notes: list[str] = []

        if self.mat_type == MatType.TIMBER:
            frame_check_dfs, timber_notes = build_timber_frame_check_frames(project)
            frames.extend(frame_check_dfs)
            notes.extend(timber_notes)
            floor_dfs = build_timber_floor_frames(project)
            frames.extend(floor_dfs)
            
        if self.mat_type == MatType.STEEL:
            steel_dfs, steel_notes = build_steel_frame_check_frames(project)
            frames.extend(steel_dfs)
            notes.extend(steel_notes)

        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=SectionStatus.READY,
            frames=frames,
            notes=notes,
        )

class MaterialsSectionBuilder:
    section_id = "materials"
    title = "Malzemeler"

    def is_applicable(self, project: Any, context: Any) -> bool:
        return bool(getattr(project, "materials", None))

    def build(self, project: Any, context: Any) -> ReportSection:
        rows = []
        for name, mat in project.materials.items():
            mat_type = _material_type(mat)
            rows.append({
                "Ad": name,
                "Tür": mat_type.sap_label if mat_type is not None else "",
                "Sınıf": mat.grade,
                "E": mat.E1,
                "G": mat.G12,
                "ν": mat.nu12,
                "fy": mat.fy,
                "fu": mat.fu,
                "Yoğunluk": mat.density,
            })
        df = ReportDataFrame(
            rows,
            columns=["Ad", "Tür", "Sınıf", "E", "G", "ν", "fy", "fu", "Yoğunluk"],
            custom_title="Malzeme Listesi",
            custom_desc="Projede tanımlı malzemeler ve mekanik parametreleri.",
            column_units={
                "E": "MPa", "G": "MPa", "ν": "-",
                "fy": "MPa", "fu": "MPa", "Yoğunluk": "kg/m³",
            },
            column_formats={
                "E": ".1f", "G": ".1f", "ν": ".3f",
                "fy": ".1f", "fu": ".1f", "Yoğunluk": ".1f",
            },
        )
        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=SectionStatus.READY,
            frames=[df],
        )


class SectionsSectionBuilder:
    section_id = "sections"
    title = "Kesitler"

    def is_applicable(self, project: Any, context: Any) -> bool:
        return bool(getattr(project, "sections", None))

    def build(self, project: Any, context: Any) -> ReportSection:
        rows = []
        for name, sec in project.sections.items():
            p = sec.profile_params
            rows.append({
                "Ad": name,
                "Tip": sec.profile_type.value,
                "Malzeme": sec.material.name if sec.material else "",
                "A": p.get("Area", 0.0),
                "I33": p.get("I33", 0.0),
                "I22": p.get("I22", 0.0),
                "J": p.get("J", 0.0),
                "h": p.get("h", 0.0),
                "b": p.get("b", 0.0),
            })
        df = ReportDataFrame(
            rows,
            columns=["Ad", "Tip", "Malzeme", "A", "I33", "I22", "J", "h", "b"],
            custom_title="Kesit Listesi",
            custom_desc="Projede tanımlı çerçeve kesitleri ve geometrik özellikleri.",
            column_units={
                "A": "mm²", "I33": "mm⁴", "I22": "mm⁴", "J": "mm⁴",
                "h": "mm", "b": "mm",
            },
            column_formats={"A": ".1f", "I33": ".0f", "I22": ".0f", "J": ".0f", "h": ".1f", "b": ".1f"},
        )
        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=SectionStatus.READY,
            frames=[df],
        )

class ModalSectionBuilder:
    section_id = "modal"
    title = "Modal Analiz"

    def is_applicable(self, project: Any, context: Any) -> bool:
        return project is not None

    def build(self, project: Any, context: Any) -> ReportSection:
        results = getattr(project, "analysis_results", None)
        modal = getattr(results, "modal", None)
        if modal is None or modal.n_modes == 0:
            warning = getattr(project, "analysis_results_warning", None)
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.NOT_RUN,
                notes=[
                    warning or "Modal analiz henüz çalıştırılmadı."
                ],
            )

        periods_df = ReportDataFrame(
            [
                {
                    "Mod": i + 1,
                    "T (s)": float(modal.periods[i]),
                    "f (Hz)": float(modal.frequencies[i]),
                    "Modal Kütle (kg)": float(modal.modal_mass[i]),
                }
                for i in range(modal.n_modes)
            ],
            columns=["Mod", "T (s)", "f (Hz)", "Modal Kütle (kg)"],
            custom_title="Modal Periyotlar ve Frekanslar",
            custom_desc="Kütlesel katılım oranları ile birlikte mod özellikleri.",
            column_units={"T (s)": "s", "f (Hz)": "Hz", "Modal Kütle (kg)": "kg"},
            column_formats={"T (s)": ".4f", "f (Hz)": ".3f", "Modal Kütle (kg)": ".2f"},
        )

        total_mass = modal.total_mass_x or 1.0
        cum_x = np.cumsum(modal.effective_mass_x) / total_mass * 100.0
        cum_y = np.cumsum(modal.effective_mass_y) / (modal.total_mass_y or 1.0) * 100.0
        cum_z = np.cumsum(modal.effective_mass_z) / (modal.total_mass_z or 1.0) * 100.0

        mass_df = ReportDataFrame(
            [
                {
                    "Mod": i + 1,
                    "T (s)": float(modal.periods[i]),
                    "ΣMx (%)": float(cum_x[i]),
                    "ΣMy (%)": float(cum_y[i]),
                    "ΣMz (%)": float(cum_z[i]),
                }
                for i in range(modal.n_modes)
            ],
            columns=["Mod", "T (s)", "ΣMx (%)", "ΣMy (%)", "ΣMz (%)"],
            custom_title="Kümülatif Kütle Katılım Oranları",
            custom_desc="TBDY 2018 4.5.6 — her iki yatay yönde en az %90 kütle katılımı sağlanmalıdır.",
            column_units={"T (s)": "s", "ΣMx (%)": "%", "ΣMy (%)": "%", "ΣMz (%)": "%"},
            column_formats={"T (s)": ".4f", "ΣMx (%)": ".1f", "ΣMy (%)": ".1f", "ΣMz (%)": ".1f"},
        )

        notes = []
        if cum_x[-1] < 90.0 or cum_y[-1] < 90.0:
            notes.append(
                f"Kütle katılımı %90 altında: X=%{cum_x[-1]:.1f}, Y=%{cum_y[-1]:.1f}"
            )

        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=SectionStatus.READY,
            frames=[periods_df, mass_df],
            notes=notes,
        )

class BaseReactSectionBuilder:
    section_id = "base_react"
    title = "Taban Reaksiyonları"

    def is_applicable(self, project: Any, context: Any) -> bool:
        res = getattr(project, "analysis_results", None)
        return res is not None and bool(getattr(res, "static_results", None))

    def build(self, project: Any, context: Any) -> ReportSection:
        res = project.analysis_results
        rows = []
        for cname, sres in res.static_results.items():
            rows.append({
                "Yük Durumu": cname,
                "Fx (kN)": sres.sum_F[0] * 1e-3,
                "Fy (kN)": sres.sum_F[1] * 1e-3,
                "Fz (kN)": sres.sum_F[2] * 1e-3,
                "Mx (kN·m)": sres.sum_F[3] * 1e-6,
                "My (kN·m)": sres.sum_F[4] * 1e-6,
                "Mz (kN·m)": sres.sum_F[5] * 1e-6,
            })
        df = ReportDataFrame(
            rows,
            columns=["Yük Durumu", "Fx (kN)", "Fy (kN)", "Fz (kN)",
                     "Mx (kN·m)", "My (kN·m)", "Mz (kN·m)"],
            custom_title="Taban Reaksiyonları",
            custom_desc="Her yük durumu için toplam taban kesme kuvvetleri ve momentleri.",
            column_units={
                "Fx (kN)": "kN", "Fy (kN)": "kN", "Fz (kN)": "kN",
                "Mx (kN·m)": "kN·m", "My (kN·m)": "kN·m", "Mz (kN·m)": "kN·m",
            },
            column_formats={
                "Fx (kN)": ".1f", "Fy (kN)": ".1f", "Fz (kN)": ".1f",
                "Mx (kN·m)": ".1f", "My (kN·m)": ".1f", "Mz (kN·m)": ".1f",
            },
        )

        reac_rows = []
        for cname, sres in res.static_results.items():
            reac_rows.append({
                "Yük Durumu": cname,
                "ΣRx (kN)": sres.sum_R[0] * 1e-3,
                "ΣRy (kN)": sres.sum_R[1] * 1e-3,
                "ΣRz (kN)": sres.sum_R[2] * 1e-3,
                "ΣRMx (kN·m)": sres.sum_R[3] * 1e-6,
                "ΣRMy (kN·m)": sres.sum_R[4] * 1e-6,
                "ΣRMz (kN·m)": sres.sum_R[5] * 1e-6,
            })
        reac_df = ReportDataFrame(
            reac_rows,
            columns=["Yük Durumu", "ΣRx (kN)", "ΣRy (kN)", "ΣRz (kN)",
                     "ΣRMx (kN·m)", "ΣRMy (kN·m)", "ΣRMz (kN·m)"],
            custom_title="Mesnet Reaksiyonları Toplamı",
            custom_desc="Denge kontrolü: ΣF ve ΣR toplamları sıfıra yakın olmalıdır.",
            column_units={
                "ΣRx (kN)": "kN", "ΣRy (kN)": "kN", "ΣRz (kN)": "kN",
                "ΣRMx (kN·m)": "kN·m", "ΣRMy (kN·m)": "kN·m", "ΣRMz (kN·m)": "kN·m",
            },
            column_formats={
                "ΣRx (kN)": ".2f", "ΣRy (kN)": ".2f", "ΣRz (kN)": ".2f",
                "ΣRMx (kN·m)": ".2f", "ΣRMy (kN·m)": ".2f", "ΣRMz (kN·m)": ".2f",
            },
        )

        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=SectionStatus.READY,
            frames=[df, reac_df],
        )

class BetaSectionBuilder:
    section_id = "beta"
    title = "Beta Büyütme Katsayıları"

    def is_applicable(self, project: Any, context: Any) -> bool:
        res = getattr(project, "analysis_results", None)
        if res is None or not getattr(res, "static_results", None):
            return False
        cfg = getattr(getattr(project, "config", None), "seismic", None)
        if cfg is None:
            return False
        return all(c in res.static_results for c in ("EQX", "EQY", "QUAKEX", "QUAKEY"))

    def build(self, project: Any, context: Any) -> ReportSection:
        res = project.analysis_results
        cfg = project.config.seismic
        sr = res.static_results

        vt_x = abs(sr["EQX"].sum_F[0]) * 1e-3
        vt_y = abs(sr["EQY"].sum_F[1]) * 1e-3
        vte_x = abs(sr["QUAKEX"].sum_F[0]) * 1e-3
        vte_y = abs(sr["QUAKEY"].sum_F[1]) * 1e-3

        gamma_e = cfg.gamma_E
        beta_x = max(gamma_e * vte_x / vt_x, 1.0) if vt_x > 0 else 1.0
        beta_y = max(gamma_e * vte_y / vt_y, 1.0) if vt_y > 0 else 1.0

        df = ReportDataFrame(
            [
                {
                    "Yön": "X",
                    "Vt (Modal) (kN)": vt_x,
                    "Vte (Eşdeğer) (kN)": vte_x,
                    "γᴇ": gamma_e,
                    "β": beta_x,
                },
                {
                    "Yön": "Y",
                    "Vt (Modal) (kN)": vt_y,
                    "Vte (Eşdeğer) (kN)": vte_y,
                    "γᴇ": gamma_e,
                    "β": beta_y,
                },
            ],
            columns=["Yön", "Vt (Modal) (kN)", "Vte (Eşdeğer) (kN)", "γᴇ", "β"],
            custom_title="Beta Büyütme Katsayıları",
            custom_desc=(
                "TBDY 2018 4.8.4 — Denk.(4.31): β = (γᴇ · Vte) / Vt ≥ 1.0. "
                f"Düzensizlik: {'var (γᴇ=0.90)' if cfg.has_irregularity else 'yok (γᴇ=0.80)'}"
            ),
            column_units={
                "Vt (Modal) (kN)": "kN", "Vte (Eşdeğer) (kN)": "kN",
                "γᴇ": "-", "β": "-",
            },
            column_formats={
                "Vt (Modal) (kN)": ".1f", "Vte (Eşdeğer) (kN)": ".1f",
                "γᴇ": ".2f", "β": ".3f",
            },
        )

        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=SectionStatus.READY,
            frames=[df],
        )

class DriftSectionBuilder:
    section_id = "drift"
    title = "Göreli Kat Ötelemeleri"

    def is_applicable(self, project: Any, context: Any) -> bool:
        res = getattr(project, "analysis_results", None)
        if res is None or not getattr(res, "static_results", None):
            return False
        cfg = getattr(getattr(project, "config", None), "seismic", None)
        return cfg is not None

    def _ensure_drift_results(self, project: Any) -> list[str]:
        from app.analysis.seismic_combos import ensure_seismic_cases_and_combos
        from app.analysis.structuralanalysis import _evaluate_combinations

        res = project.analysis_results
        cfg = project.config.seismic
        if not all(c in res.static_results for c in cfg.drift_combo_names):
            ensure_seismic_cases_and_combos(project, include_design_combos=False)
            _evaluate_combinations(project, res.static_results)
        return [c for c in cfg.drift_combo_names if c in res.static_results]

    def build(self, project: Any, context: Any) -> ReportSection:
        res = project.analysis_results
        cfg = project.config.seismic
        available_combos = self._ensure_drift_results(project)
        if not available_combos:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=[
                    f"Göreli öteleme yük durumları bulunamadı ({', '.join(cfg.drift_combo_names)}). "
                    "Analiz Yöneticisi üzerinden deprem kombinasyonlarını oluşturup analizi çalıştırın."
                ],
            )

        mesh = res.mesh
        if mesh is None:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=["SolverMesh yok"],
            )

        stories = self._collect_stories(mesh)
        if len(stories) < 2:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=["Kat sayısı < 2"],
            )

        lambda_val = self._calc_lambda(project)
        if lambda_val is None:
            return ReportSection(
                section_id=self.section_id,
                title=self.title,
                status=SectionStatus.MISSING_DATA,
                notes=["T1 veya spektrum yok — λ hesaplanamadı"],
            )

        limit = cfg.limit_raw * cfg.kappa
        rows = []
        for cname in available_combos:
            sres = res.static_results[cname]
            prev_ux = 0.0
            prev_uy = 0.0
            for z, node_keys, h in stories:
                ux_vals = [sres.node_displacements[k][0] for k in node_keys
                           if k in sres.node_displacements]
                uy_vals = [sres.node_displacements[k][1] for k in node_keys
                           if k in sres.node_displacements]
                if not ux_vals:
                    continue
                ux_max = max(ux_vals)
                uy_max = max(uy_vals)
                delta_x = ux_max - prev_ux
                delta_y = uy_max - prev_uy
                delta_i = max(abs(delta_x), abs(delta_y))
                delta_eff = (cfg.R / cfg.I) * delta_i
                ratio = lambda_val * delta_eff / h if h > 0 else 0.0
                rows.append({
                    "Yük Durumu": cname,
                    "Kat": int(round(z)),
                    "h (mm)": h,
                    "Δi (mm)": delta_i,
                    "δi (mm)": delta_eff,
                    "λ·δi/h": ratio,
                    "Limit": limit,
                    "Durum": "✓" if ratio <= limit else "✗",
                })
                prev_ux = ux_max
                prev_uy = uy_max

        df = ReportDataFrame(
            rows,
            columns=["Yük Durumu", "Kat", "h (mm)", "Δi (mm)", "δi (mm)",
                     "λ·δi/h", "Limit", "Durum"],
            custom_title="Göreli Kat Ötelemeleri",
            custom_desc=(
                "TBDY 2018 4.9.1 — Denk.(4.32): Δi=ui−ui-1, Denk.(4.33): δi=(R/I)·Δi, "
                f"Denk.(4.34b): λ·δi,max/hi ≤ {cfg.limit_raw:.4f}·κ. "
                f"λ={lambda_val:.3f}, κ={cfg.kappa}"
            ),
            column_units={
                "h (mm)": "mm", "Δi (mm)": "mm", "δi (mm)": "mm",
                "λ·δi/h": "-", "Limit": "-",
            },
            column_formats={
                "h (mm)": ".1f", "Δi (mm)": ".4f", "δi (mm)": ".4f",
                "λ·δi/h": ".5f", "Limit": ".5f",
            },
        )

        fails = [r for r in rows if r["Durum"] == "✗"]
        notes = [f"{len(fails)} adet sınır aşımı"] if fails else []

        return ReportSection(
            section_id=self.section_id,
            title=self.title,
            status=SectionStatus.READY,
            frames=[df],
            notes=notes,
        )

    @staticmethod
    def _collect_stories(mesh: Any, project: Any = None) -> list[tuple[float, list[str], float]]:
        internal_keys = getattr(mesh, "internal_node_keys", set()) or set()
        nodes = getattr(mesh, "nodes", {})

        story_defs = project.ordered_stories() if project is not None and hasattr(project, "ordered_stories") else []
        active_defs = [s for s in story_defs if not s.is_mezzanine]
        if active_defs:
            stories: list[tuple[float, list[str], float]] = []
            for idx, st in enumerate(active_defs):
                z_top = float(st.elevation)
                h = float(st.height) if st.height > 0.0 else (
                    z_top - float(active_defs[idx - 1].elevation) if idx > 0 else 0.0
                )
                nkeys = [
                    k for k, n in nodes.items()
                    if k not in internal_keys and abs(float(n.z) - z_top) <= 1.0
                ]
                stories.append((z_top, nkeys, h))
            return stories

        groups: dict[float, list[str]] = {}
        for n_key, node in nodes.items():
            if n_key in internal_keys:
                continue
            z = round(float(node.z), 0)
            groups.setdefault(z, []).append(n_key)
        levels = sorted(groups.keys())
        stories = []
        for i, z in enumerate(levels):
            h = z - levels[i - 1] if i > 0 else 0.0
            stories.append((z, groups[z], h))
        return stories[1:]

    @staticmethod
    def _calc_lambda(project) -> float | None:
        res = getattr(project, "analysis_results", None)
        if res is None or res.modal is None or res.modal.n_modes == 0:
            return None
        cfg = project.config.seismic
        t1 = float(res.modal.periods[0])
        sae_dd2 = DriftSectionBuilder._sae(t1, cfg.dd2)
        sae_dd3 = DriftSectionBuilder._sae(t1, cfg.dd3)
        if sae_dd2 <= 0:
            return None
        return sae_dd3 / sae_dd2

    @staticmethod
    def _sae(T: float, dd: dict) -> float:
        sds = dd.get("Sds", 0.0)
        sd1 = dd.get("Sd1", 0.0)
        if sds <= 0 or sd1 <= 0:
            return 0.0
        ta = 0.2 * sd1 / sds
        tb = sd1 / sds
        tl = 6.0
        if 0 <= T <= ta:
            return (0.4 + 0.6 * T / ta) * sds
        if ta < T <= tb:
            return sds
        if tb < T <= tl:
            return sd1 / T
        return sd1 * tl / (T ** 2)


# class TorsionSectionBuilder:
#     section_id = "torsion"
#     title = "A1 Burulma Düzensizliği"

#     def is_applicable(self, project: Any, context: Any) -> bool:
#         res = getattr(project, "analysis_results", None)
#         if res is None or not getattr(res, "static_results", None):
#             return False
#         cfg = getattr(getattr(project, "config", None), "seismic", None)
#         return cfg is not None

#     def build(self, project: Any, context: Any) -> ReportSection:
#         from app.analysis.seismic_combos import ensure_seismic_cases_and_combos
#         from app.analysis.structuralanalysis import _evaluate_combinations

#         res = project.analysis_results
#         cfg = project.config.seismic
#         if not all(c in res.static_results for c in cfg.drift_combo_names):
#             ensure_seismic_cases_and_combos(project, include_design_combos=False)
#             _evaluate_combinations(project, res.static_results)

#         available_combos = [c for c in cfg.drift_combo_names if c in res.static_results]
#         if not available_combos:
#             return ReportSection(
#                 section_id=self.section_id,
#                 title=self.title,
#                 status=SectionStatus.MISSING_DATA,
#                 notes=[
#                     f"Burulma kontrolü için yük durumları bulunamadı ({', '.join(cfg.drift_combo_names)})."
#                 ],
#             )

#         mesh = res.mesh
#         if mesh is None:
#             return ReportSection(
#                 section_id=self.section_id,
#                 title=self.title,
#                 status=SectionStatus.MISSING_DATA,
#                 notes=["SolverMesh yok"],
#             )

#         stories = DriftSectionBuilder._collect_stories(mesh)
#         if not stories:
#             return ReportSection(
#                 section_id=self.section_id,
#                 title=self.title,
#                 status=SectionStatus.MISSING_DATA,
#                 notes=["Kat yok"],
#             )

#         rows = []
#         for cname in available_combos:
#             sres = res.static_results[cname]
#             direction = "X" if "X" in cname.upper() else "Y"
#             axis = 0 if direction == "X" else 1
#             for z, node_keys, _h in stories:
#                 vals = [abs(sres.node_displacements[k][axis]) for k in node_keys
#                         if k in sres.node_displacements]
#                 if len(vals) < 2:
#                     continue
#                 d_max = max(vals)
#                 d_avg = sum(vals) / len(vals)
#                 eta = d_max / d_avg if d_avg > 0 else 1.0
#                 dbi = (eta / 1.2) ** 2 if eta > 1.2 else 1.0
#                 rows.append({
#                     "Yük Durumu": cname,
#                     "Yön": direction,
#                     "Kat": int(round(z)),
#                     "Δmax (mm)": d_max,
#                     "Δort (mm)": d_avg,
#                     "ηbi": eta,
#                     "A1": "Var" if eta > 1.2 else "Yok",
#                     "Dbi": dbi,
#                 })

#         df = ReportDataFrame(
#             rows,
#             columns=["Yük Durumu", "Yön", "Kat", "Δmax (mm)", "Δort (mm)",
#                      "ηbi", "A1", "Dbi"],
#             custom_title="A1 Burulma Düzensizliği",
#             custom_desc=(
#                 "TBDY 2018 3.6.2.1 — ηbi = (Δi)max / (Δi)ort > 1.2 ise A1 düzensizliği var. "
#                 "Denk.(4.29): Dbi = (ηbi/1.2)² — 1.2 < ηbi ≤ 2.0 aralığında ±%5 ek dışmerkezlik Dbi ile büyütülür."
#             ),
#             column_units={
#                 "Δmax (mm)": "mm", "Δort (mm)": "mm",
#                 "ηbi": "-", "Dbi": "-",
#             },
#             column_formats={
#                 "Δmax (mm)": ".4f", "Δort (mm)": ".4f",
#                 "ηbi": ".3f", "Dbi": ".3f",
#             },
#         )

#         a1_count = sum(1 for r in rows if r["A1"] == "Var")
#         notes = [f"{a1_count} katta A1 düzensizliği tespit edildi"] if a1_count else []

#         return ReportSection(
#             section_id=self.section_id,
#             title=self.title,
#             status=SectionStatus.READY,
#             frames=[df],
#             notes=notes,
#         )

from tools.report_irregularities import IrregularitiesSectionBuilder


def default_section_builders() -> list[SectionBuilder]:
    builders: list[SectionBuilder] = [
        OverviewSectionBuilder(),
        MaterialsSectionBuilder(),
        SectionsSectionBuilder(),
        WindSectionBuilder(),
        SnowSectionBuilder(),
        LoadsSectionBuilder(),
        SeismicSectionBuilder(),
        ModalSectionBuilder(),
        BaseReactSectionBuilder(),
        BetaSectionBuilder(),
        DriftSectionBuilder(),
        IrregularitiesSectionBuilder(),
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
        for child in sec.children:
            if child.status == SectionStatus.MISSING_DATA:
                reason = "; ".join(child.notes) if child.notes else "eksik veri"
                result.skipped.append((f"{sec.section_id}.{child.section_id}", reason))
            for frame in child.frames:
                result.produced.append(frame)

    return result


def build_project_report(project: Any) -> ReportBuildResult:
    return build_project_report_tree(project)
