# tools/area_to_frame.py

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field

import numpy as np

from core.units import Dimension, UnitSystem, convert_value
from data.enums import DistType, LoadDirection, PolygonType
from domain.definition import AreaUniformLoad, LoadPattern
from domain.element import Frame, Node
from domain.math_model import PolygonAnalysisData
from domain.polygon import Polygon
from tools.polygon_load_transfer import build_polygon_frame_loads
from logging_config import CadLogger

logger = CadLogger.get(__name__)


# ============================================================================
# Sonuç nesneleri
# ============================================================================
@dataclass
class TransferResult:
    ok: bool
    status: str
    segment_count: int = 0
    touched_frames: list = field(default_factory=list)
    error: str | None = None

@dataclass
class AssocPreview:
    """Ana renderer'a geçici renk katmanı sağlar. Model datasına dokunmaz."""
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
    """Panel tarafından tutulan geçici assoc state'i."""
    polygon_id: int
    associated: set[int] = field(default_factory=set)
    excluded: set[int] = field(default_factory=set)
    dirty: bool = False

class _ZoneDictAdapter:
    """zone_children_by_direction dict'ini zone objesi gibi sunar."""
    def __init__(self, data: dict):
        self._data = data
        self.label = data.get("label", "")
        self.surface = data.get("surface", "")
        self.kind = data.get("kind", "")
        self.coords = data.get("coords", [])
        self.cpe10 = data.get("cpe10_override") or data.get("cpe10", (0.0, 0.0))
        self.cpe1 = data.get("cpe1_override") or data.get("cpe1", (0.0, 0.0))
        self.pitch = data.get("pitch", 0.0)
        self.table_type = data.get("table_type", "")

# ============================================================================
# Servis
# ============================================================================
class AreaToFrame:
    """UI'dan bağımsız polygon→frame iş mantığı."""

    def __init__(self, project):
        self.project = project

    # ----------------------------------------------------------------
    # Kısayollar
    # ----------------------------------------------------------------
    @property
    def math_model(self):
        return self.project.math_model if self.project else None

    def _analysis_data(self, polygon: Polygon) -> PolygonAnalysisData:
        return self.project.polygon_analysis_data(polygon)

    # ----------------------------------------------------------------
    # Listeleme (salt okunur)
    # ----------------------------------------------------------------
    def list_polygons(self) -> list[Polygon]:
        if not self.project or not self.project.scene:
            return []
        return sorted(
            self.project.math_model.polygons.values(),
            key=lambda p: (p.label or "", int(p.unique_id)),
        )

    def list_frames(self) -> dict[int, Frame]:
        if not self.math_model:
            return {}
        return self.math_model.frames

    def get_polygon(self, polygon_id: int | None) -> Polygon | None:
        if polygon_id is None or not self.project or not self.project.math_model:
            return None
        return self.project.math_model.polygons.get(int(polygon_id))

    def list_wind_zones(self, polygon: Polygon) -> list[tuple[str, int, object]]:
        """Polygon'a ait zone'lar. Tek kaynak: polygon.zone_children_by_direction."""
        zone_dict = polygon.zone_children_by_direction or {}
        entries = []
        for dir_key, zones in zone_dict.items():
            for idx, zone_dict_item in enumerate(zones):
                entries.append((str(dir_key), idx, _ZoneDictAdapter(zone_dict_item)))
        return entries

    def polygon_loads_summary(self, polygon: Polygon) -> dict:
        """UI göstermek için özet."""
        ad = self._analysis_data(polygon)
        transfers = self.project.loads.area_load_transfers_for_polygon(
            int(polygon.unique_id),
        )
        wind = [t for t in transfers if t.get("source_type") == "wind_zone"]
        transferred_ids = sorted({
            int(fid)
            for t in transfers
            for fid in t.get("transferred_frame_ids", ())
        })
        return {
            "assigned_loads": list(ad.assigned_loads),
            "wind_transfers": wind,
            "transferred_frame_ids": transferred_ids,
        }

    # ----------------------------------------------------------------
    # Birim
    # ----------------------------------------------------------------
    def area_load_unit(self) -> str:
        us = self.project.unit_system
        return f"{us.force_unit}/{us.length_unit}²"

    def length_unit(self) -> str:
        return self.project.unit_system.length_unit

    # ----------------------------------------------------------------
    # Grid config — project üzerinde saklanır
    # ----------------------------------------------------------------
    def get_grid_settings(self) -> tuple[float, int]:
        step = float(getattr(self.project, "transfer_grid_step", 0.0) or 0.0)
        bins = int(getattr(self.project, "transfer_grid_bins", 12) or 12)
        if step <= 0.0:
            step = float(convert_value(
                Dimension.LENGTH, 200.0, UnitSystem.N_MM,
                self.project.unit_system,
            ))
        return step, bins

    def set_grid_settings(self, step: float, n_bins: int) -> None:
        one_meter = convert_value(
            Dimension.LENGTH, 1.0, UnitSystem.N_M, self.project.unit_system,
        )
        step = max(0.05 * one_meter, min(2.0 * one_meter, float(step)))
        n_bins = max(3, min(50, int(n_bins)))
        self.project.transfer_grid_step = float(step)
        self.project.transfer_grid_bins = int(n_bins)

    # ----------------------------------------------------------------
    # Assoc draft
    # ----------------------------------------------------------------
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

    def auto_assoc(
        self, polygon: Polygon, draft: AssocDraft, *,
        keep_excluded: bool = True,
    ) -> dict:
        """
        Eşik değerlerine ve polygon tipine göre uygun frame'leri draft'a ekler.
        `keep_excluded=True`: draft.excluded korunur (kullanıcı elle çıkardıkları).
        `keep_excluded=False`: önce excluded temizlenir, sonra taranır.
        """
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
        return {
            "added": len(draft.associated),
            "excluded": len(draft.excluded),
        }

    def add_selected_frames(
        self, polygon: Polygon, draft: AssocDraft, frame_ids: list[int],
    ) -> dict:
        """Sahnede seçili frame'leri draft.associated'a ekler (hariçten çıkarır)."""
        for uid in frame_ids:
            uid = int(uid)
            draft.associated.add(uid)
            draft.excluded.discard(uid)
        draft.dirty = True
        return {"added": len(frame_ids), "total": len(draft.associated)}

    def apply(self, polygon: Polygon, draft: AssocDraft) -> dict:
        """Draft'ı polygon ve analysis_data'ya yazar."""
        polygon.associated = set(draft.associated)
        polygon.excluded = set(draft.excluded)
        polygon.association_revision += 1

        ad = self._analysis_data(polygon)
        ad.associated_frame_ids = sorted(draft.associated)

        self.math_model.mark_dirty()
        draft.dirty = False
        return {
            "associated": len(polygon.associated),
            "excluded": len(polygon.excluded),
        }

    def cancel(self, polygon: Polygon, draft: AssocDraft) -> None:
        draft.associated = set(polygon.associated)
        draft.excluded = set(polygon.excluded)
        draft.dirty = False

    # ----------------------------------------------------------------
    # Transfer: polygon alan yükü
    # ----------------------------------------------------------------
    def transfer_area_loads(self, polygon: Polygon) -> TransferResult:
        if not self.math_model:
            return TransferResult(False, "Math model yok.", error="no_model")
        ad = self._analysis_data(polygon)
        if not ad.assigned_loads:
            return TransferResult(False, "Bu polygon üzerinde atanmış yük yok.",
                                  error="no_loads")
        try:
            step, n_bins = self.get_grid_settings()
            generated = build_polygon_frame_loads(
                self.math_model, polygon,
                analysis_data=ad,
                step=step,
                n_bins=n_bins,
            )
            if not generated:
                return TransferResult(False, "Aktarım için segment üretilemedi.",
                                      error="no_segments")
            self._apply_frame_transfers(generated)
            self.math_model.mark_dirty()

            touched = [
                self.math_model.frames[fid]
                for fid in generated
                if fid in self.math_model.frames
            ]
            segment_count = sum(
                len(load_set.segments)
                for pattern_loads in generated.values()
                for load_set in pattern_loads.values()
            )
            msg = (
                f"{segment_count} yayılı yük segmenti "
                f"{len(generated)} frame'e aktarıldı."
            )
            logger.debug("[AreaToFrame] %s", msg)
            return TransferResult(
                True, msg, segment_count=segment_count, touched_frames=touched,
            )
        except (TypeError, ValueError) as e:
            logger.debug("[AreaToFrame] transfer: %s", e)
            return TransferResult(False, str(e), error=str(e))
        except Exception as e:
            logger.exception("[AreaToFrame] transfer başarısız")
            return TransferResult(
                False, "Aktarım sırasında hata oluştu; log'a bakın.",
                error=str(e),
            )

    # ----------------------------------------------------------------
    # Transfer: rüzgar zone
    # ----------------------------------------------------------------
    def transfer_wind_zone(
    self, surface: Polygon, direction_key: str, zone_index: int, zone,
    *, cpe_kind: str, cpi_pos: float, cpi_neg: float,
) -> TransferResult:
        """Zone'u (dict veya adapter) frame'lere aktar. Kaynak: polygon.zone_children_by_direction."""
        if not self.math_model:
            return TransferResult(False, "Math model yok.", error="no_model")

        surface_data = self._analysis_data(surface)
        if not surface_data.associated_frame_ids:
            return TransferResult(
                False, "Önce polygon için frame hedeflerini belirleyin.",
                error="no_assoc",
            )

        # ★ Basınç verisi wind_results'tan gelir (analiz önbelleği)
        pressure_result = self.project.loads.wind_results.get(direction_key)
        if pressure_result is None:
            return TransferResult(
                False, f"{direction_key} yönü için basınç sonucu yok.",
                error="no_pressure",
            )

        try:
            q_p = float(getattr(pressure_result, "q_p", 0.0))
            if q_p <= 0.0:
                return TransferResult(False, "Rüzgar tepe basıncı geçersiz.",
                                    error="bad_qp")

            wind_direction = getattr(
                pressure_result, "direction",
                getattr(pressure_result, "w_dir", (0.0, 0.0, 0.0)),
            )
            wind_direction = np.asarray(wind_direction, dtype=float)
            if wind_direction.shape != (3,) or not np.isfinite(wind_direction).all():
                return TransferResult(False, "Rüzgar yön vektörü geçersiz.",
                                    error="bad_direction")

            length_factor = convert_value(
                Dimension.LENGTH, 1.0, UnitSystem.N_M,
                self.project.unit_system,
            )

            # ★ zone artık _ZoneDictAdapter (dict) — attribute erişimi çalışır
            raw_coords = getattr(zone, "coords", None)
            if not raw_coords:
                return TransferResult(False, "Zone geometrisi boş.",
                                    error="bad_geometry")
            coords = np.asarray(raw_coords, dtype=float)
            if coords.ndim != 2 or coords.shape[0] < 3 or coords.shape[1] != 3:
                return TransferResult(False, "Rüzgar zone geometrisi geçersiz.",
                                    error="bad_geometry")

            # zone.coords ZATEN proje biriminde (store_zones/_assign_zones çevirdi)
            # ★ length_factor = 1.0 olmalı, tekrar çevirme!
            zone_nodes = [Node(*coords[i]) for i in range(len(coords))]
            zone_polygon = Polygon(
                nodes=zone_nodes,
                label=f"{zone.label} wind zone",
                poly_type=PolygonType.ZONE,
            )
            zone_ad = PolygonAnalysisData(
                associated_frame_ids=list(surface_data.associated_frame_ids),
                transfer_dist_type=surface_data.transfer_dist_type,
            )

            # ★ cpe_kind → cpe10 veya cpe1 (adapter'da override varsa onu kullanır)
            raw_coefs = getattr(zone, cpe_kind, (0.0, 0.0))
            if np.isscalar(raw_coefs):
                coefficients = (float(raw_coefs), float(raw_coefs))
            else:
                values = tuple(float(v) for v in raw_coefs)
                if not values:
                    return TransferResult(False, "Cpe katsayısı boş.",
                                        error="empty_cpe")
                coefficients = (
                    values[0],
                    values[1] if len(values) > 1 else values[0],
                )

            normal = np.asarray(Polygon.calculate_normal(zone_nodes), dtype=float)
            sign = -1.0 if float(np.dot(normal, wind_direction)) > 0.0 else 1.0

            kind_label = "CPE10" if cpe_kind == "cpe10" else "CPE1"
            loads: list[AreaUniformLoad] = []
            for cpe_lbl, cpe in zip(("MN", "MX"), coefficients):
                for cpi_lbl, cpi in (("P", cpi_pos), ("M", cpi_neg)):
                    pattern_name = (
                        f"WIND_{direction_key}_{kind_label}_{cpe_lbl}_{cpi_lbl}"
                    )
                    pressure = sign * q_p * (cpe - cpi)
                    value = convert_value(
                        Dimension.AREA_LOAD, pressure, UnitSystem.KN_M,
                        self.project.unit_system,
                    )
                    loads.append(AreaUniformLoad(
                        pattern_name=pattern_name,
                        direction=LoadDirection.LOCAL_2,
                        value=float(value),
                        source_name=f"{zone.label} {kind_label} {cpe_lbl}/{cpi_lbl}",
                    ))
                    existing = self.project.load_patterns.get(pattern_name)
                    if existing is None:
                        self.project.add_load_pattern(LoadPattern(
                            name=pattern_name,
                            design_type="Wind",
                            self_wt_mult=0.0,
                        ))
                    elif str(existing.design_type).lower() != "wind":
                        return TransferResult(
                            False,
                            f"'{pattern_name}' pattern tipi "
                            f"{existing.design_type!r}; Wind gerekli.",
                            error="pattern_type",
                        )

            source_key = f"wind:{direction_key}:{zone_index}"
            distribution = DistType.from_input(surface_data.transfer_dist_type)
            step, n_bins = self.get_grid_settings()
            generated = build_polygon_frame_loads(
                self.math_model,
                zone_polygon,
                loads,
                analysis_data=zone_ad,
                dist_type=distribution,
                step=step,
                n_bins=n_bins,
            )
            self._apply_frame_transfers(generated)
            transferred_ids = sorted(generated)

            self.project.loads.area_load_transfers.append({
                "polygon_id": int(surface.unique_id),
                "source_type": "wind_zone",
                "source_key": source_key,
                "direction_key": direction_key,
                "zone_label": str(zone.label),
                "cpe_kind": kind_label,
                "dist_type": distribution.value,
                "loads": loads,
                "transferred_frame_ids": transferred_ids,
            })
            self.project.loads.area_frame_transfers.append({
                "polygon_id": int(surface.unique_id),
                "source_key": source_key,
                "transferred_frame_ids": transferred_ids,
                "pattern_names": sorted({
                    p
                    for frame_loads in generated.values()
                    for p in frame_loads
                }),
            })
            self.math_model.mark_dirty()

            touched = [
                self.math_model.frames[fid]
                for fid in generated
                if fid in self.math_model.frames
            ]
            segment_count = sum(
                len(load_set.segments)
                for pattern_loads in generated.values()
                for load_set in pattern_loads.values()
            )
            msg = f"{zone.label}: {segment_count} rüzgar yük segmenti aktarıldı."
            logger.debug("[AreaToFrame] %s", msg)
            return TransferResult(
                True, msg, segment_count=segment_count, touched_frames=touched,
            )

        except (TypeError, ValueError, KeyError) as e:
            logger.debug("[AreaToFrame] wind zone: %s", e)
            return TransferResult(False, str(e), error=str(e))
        except Exception as e:
            logger.exception("[AreaToFrame] wind zone başarısız")
            return TransferResult(
                False, "Rüzgar zone aktarımı sırasında hata; log'a bakın.",
                error=str(e),
            )

    # ----------------------------------------------------------------
    # İç yardımcı
    # ----------------------------------------------------------------
    def _apply_frame_transfers(self, generated) -> None:
        frames = self.math_model.frames
        for frame_id, pattern_loads in generated.items():
            frame = frames.get(frame_id)
            if frame is None:
                continue
            for pattern_name, load_set in pattern_loads.items():
                frame.dist_load_sets[pattern_name] = deepcopy(load_set)
                frame.mark_dirty()