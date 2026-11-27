# tools/area_to_frame.py
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np

from core.units import Dimension, UnitSystem, convert_value
from data.enums import DistType, LoadDirection
from domain.definition import AreaUniformLoad, FrameDistributedLoad, LoadPattern
from domain.math_model import PolygonAnalysisData
from domain.polygon import Polygon
from tools.polygon_load_transfer import (
    build_polygon_frame_loads,
    merge_frame_distributed_loads,
)
from functools import cached_property

@dataclass
class TransferBatch:
    polygon_id: int
    source_label: str
    staged_loads: dict[int, dict[str, FrameDistributedLoad]] = field(default_factory=dict)
    mode: str = "replace"

    @property
    def frame_count(self) -> int:
        return len(self.staged_loads)

    @cached_property
    def segment_count(self) -> int:
        return sum(
            len(ls.segments)
            for pats in self.staged_loads.values()
            for ls in pats.values()
        )

    @property
    def pattern_names(self) -> list[str]:
        return sorted({p for pats in self.staged_loads.values() for p in pats})


@dataclass
class AssocPreview:
    polygon_id: int | None = None
    associated: set[int] = field(default_factory=set)
    excluded: set[int] = field(default_factory=set)
    active: bool = False

    def clear(self) -> None:
        self.polygon_id = None
        self.associated.clear()
        self.excluded.clear()
        self.active = False


@dataclass
class AssocDraft:
    polygon_id: int
    associated: set[int] = field(default_factory=set)
    excluded: set[int] = field(default_factory=set)
    dirty: bool = False


class AreaToFrame:
    def __init__(self, project):
        self.project = project

    @property
    def math_model(self):
        return self.project.math_model if self.project else None

    def analysis_data(self, polygon: Polygon) -> PolygonAnalysisData:
        return self.project.polygon_analysis_data(polygon)

    def area_load_unit(self) -> str:
        us = self.project.unit_system
        return f"{us.force_unit}/{us.length_unit}²"

    def line_load_unit(self) -> str:
        us = self.project.unit_system
        return f"{us.force_unit}/{us.length_unit}"

    def length_unit(self) -> str:
        return self.project.unit_system.length_unit

    def get_grid_settings(self) -> tuple[float, int]:
        step = float(getattr(self.project, "transfer_grid_step", 0.0) or 0.0)
        bins = int(getattr(self.project, "transfer_grid_bins", 12) or 12)
        if step <= 0.0:
            step = float(
                convert_value(Dimension.LENGTH, 200.0, UnitSystem.N_MM, self.project.unit_system)
            )
        return step, bins

    def set_grid_settings(self, step: float, n_bins: int) -> None:
        one_meter = convert_value(Dimension.LENGTH, 1.0, UnitSystem.N_M, self.project.unit_system)
        self.project.transfer_grid_step = max(0.05 * one_meter, min(2.0 * one_meter, float(step)))
        self.project.transfer_grid_bins = max(3, min(50, int(n_bins)))

    def new_draft(self, polygon: Polygon) -> AssocDraft:
        return AssocDraft(
            polygon_id=int(polygon.unique_id),
            associated=set(polygon.associated),
            excluded=set(polygon.excluded),
        )

    def toggle(self, draft: AssocDraft, uid: int, on: bool) -> None:
        uid = int(uid)
        if on:
            draft.associated.add(uid)
            draft.excluded.discard(uid)
        else:
            draft.associated.discard(uid)
            draft.excluded.add(uid)
        draft.dirty = True

    def clear_draft(self, draft: AssocDraft) -> None:
        draft.associated.clear()
        draft.excluded.clear()
        draft.dirty = True

    def auto_assoc(self, polygon: Polygon, draft: AssocDraft, *, keep_excluded: bool = True) -> None:
        if not keep_excluded:
            draft.excluded.clear()
        result = polygon.refresh_assoc(
            self.math_model,
            force=True,
            write=False,
            excluded_override=draft.excluded,
        )
        draft.associated = set(result)
        draft.dirty = True

    def add_selected_frames(self, draft: AssocDraft, frame_ids: list[int]) -> None:
        for uid in frame_ids:
            uid = int(uid)
            draft.associated.add(uid)
            draft.excluded.discard(uid)
        draft.dirty = True

    def apply_assoc(self, polygon: Polygon, draft: AssocDraft) -> None:
        polygon.associated = set(draft.associated)
        polygon.excluded = set(draft.excluded)
        polygon.association_revision += 1
        ad = self.analysis_data(polygon)
        ad.associated_frame_ids = sorted(draft.associated)
        self.math_model.mark_dirty()
        draft.dirty = False

    def cancel_assoc(self, polygon: Polygon, draft: AssocDraft) -> None:
        draft.associated = set(polygon.associated)
        draft.excluded = set(polygon.excluded)
        draft.dirty = False

    def build_wind_zone_fields(
        self,
        surface: Polygon,
        direction_key: str,
        *,
        cpe_kind: str,
        cpi_pos: float,
        cpi_neg: float,
    ) -> list[tuple[list[tuple[float, float, float]], AreaUniformLoad]]:
        pressure_result = self.project.loads.wind_results.get(direction_key)
        if pressure_result is None:
            raise ValueError(f"{direction_key} yönü için basınç sonucu yok.")

        q_p = float(getattr(pressure_result, "q_p", 0.0))
        if q_p <= 0.0:
            raise ValueError("Rüzgar tepe basıncı geçersiz.")

        wind_direction = np.asarray(
            getattr(pressure_result, "direction", getattr(pressure_result, "w_dir", (0.0, 0.0, 0.0))),
            dtype=float,
        )
        if wind_direction.shape != (3,) or not np.isfinite(wind_direction).all():
            raise ValueError("Rüzgar yön vektörü geçersiz.")

        zones = (surface.zone_children_by_direction or {}).get(direction_key, [])
        if not zones:
            raise ValueError(f"{direction_key} yönü için zone listesi boş.")

        surface_normal = np.asarray(Polygon.calculate_normal(list(surface.nodes)), dtype=float)
        sign = -1.0 if float(np.dot(surface_normal, wind_direction)) > 0.0 else 1.0
        kind_label = "CPE10" if cpe_kind == "cpe10" else "CPE1"
        override_key = "cpe10_override" if cpe_kind == "cpe10" else "cpe1_override"

        zone_fields: list[tuple[list[tuple[float, float, float]], AreaUniformLoad]] = []
        for z_dict in zones:
            raw_coords = z_dict.get("coords")
            if not raw_coords or len(raw_coords) < 3:
                continue
            coords = [(float(c[0]), float(c[1]), float(c[2])) for c in raw_coords]
            raw_coefs = z_dict.get(override_key) or z_dict.get(cpe_kind, (0.0, 0.0))
            if np.isscalar(raw_coefs):
                coefficients = (float(raw_coefs), float(raw_coefs))
            else:
                vals = tuple(float(v) for v in raw_coefs)
                coefficients = (vals[0], vals[1] if len(vals) > 1 else vals[0])

            for cpe_lbl, cpe in zip(("MN", "MX"), coefficients):
                for cpi_lbl, cpi in (("P", cpi_pos), ("M", cpi_neg)):
                    pattern_name = f"WIND_{direction_key}_{kind_label}_{cpe_lbl}_{cpi_lbl}"
                    pressure = sign * q_p * (cpe - cpi)
                    value = float(
                        convert_value(
                            Dimension.AREA_LOAD,
                            pressure,
                            UnitSystem.KN_M,
                            self.project.unit_system,
                        )
                    )
                    existing = self.project.load_patterns.get(pattern_name)
                    if existing is None:
                        self.project.add_load_pattern(
                            LoadPattern(name=pattern_name, design_type="Wind", self_wt_mult=0.0)
                        )
                    zone_fields.append(
                        (
                            coords,
                            AreaUniformLoad(
                                pattern_name=pattern_name,
                                direction=LoadDirection.LOCAL_3,
                                value=value,
                                source_name=f"{z_dict.get('label', '')} {kind_label} {cpe_lbl}/{cpi_lbl}",
                            ),
                        )
                    )
        return zone_fields

    def compute_polygon_frame_loads(
        self,
        polygon: Polygon,
        *,
        include_area_loads: bool = True,
        wind_direction_key: str | None = None,
        cpe_kind: str = "cpe10",
        cpi_pos: float = 0.2,
        cpi_neg: float = -0.3,
    ) -> dict[int, dict[str, FrameDistributedLoad]]:
        ad = self.analysis_data(polygon)
        loads = list(ad.assigned_loads) if include_area_loads else []
        zone_fields = None
        if wind_direction_key:
            zone_fields = self.build_wind_zone_fields(
                polygon,
                wind_direction_key,
                cpe_kind=cpe_kind,
                cpi_pos=cpi_pos,
                cpi_neg=cpi_neg,
            )
        if not loads and not zone_fields:
            return {}
        step, n_bins = self.get_grid_settings()
        return build_polygon_frame_loads(
            self.math_model,
            polygon,
            loads=loads,
            analysis_data=ad,
            dist_type=DistType.from_input(ad.transfer_dist_type),
            step=step,
            n_bins=n_bins,
            zone_fields=zone_fields,
        )

    def stage_area_loads(self, polygon: Polygon) -> TransferBatch:
        staged = self.compute_polygon_frame_loads(polygon, include_area_loads=True)
        return TransferBatch(
            polygon_id=int(polygon.unique_id),
            source_label=f"{polygon.label or 'Polygon'} (Alan Yükleri)",
            staged_loads=staged,
        )

    def stage_wind_direction(
        self,
        surface: Polygon,
        direction_key: str,
        *,
        cpe_kind: str,
        cpi_pos: float,
        cpi_neg: float,
    ) -> TransferBatch:
        kind_label = "CPE10" if cpe_kind == "cpe10" else "CPE1"
        staged = self.compute_polygon_frame_loads(
            surface,
            include_area_loads=False,
            wind_direction_key=direction_key,
            cpe_kind=cpe_kind,
            cpi_pos=cpi_pos,
            cpi_neg=cpi_neg,
        )
        return TransferBatch(
            polygon_id=int(surface.unique_id),
            source_label=f"{surface.label or 'Polygon'} — Rüzgar ({direction_key}, {kind_label})",
            staged_loads=staged,
        )

    def commit_batch(self, batch: TransferBatch) -> list[int]:
        touched = merge_frame_distributed_loads(
            self.math_model,
            batch.staged_loads,
            batch.mode,
        )
        self.math_model.mark_dirty()
        return touched