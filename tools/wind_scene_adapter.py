from __future__ import annotations

from typing import Any

import numpy as np

from core.units import Dimension, UnitSystem, convert_value
from data.enums import PolygonType
from domain.definition import WindDirectionResult, WindResult
from structload.windcalc.wind_analyzer import WindAnalyzer


class WindSceneAdapter:
    """Translate CAD geometry (Project Polygons / Vertices) to the wind calculator."""

    @staticmethod
    def _coefficient_pair(value: Any) -> tuple[float, float]:
        if np.isscalar(value):
            number = float(value)
            return number, number
        values = tuple(float(item) for item in value)
        if not values:
            return 0.0, 0.0
        return values[0], values[1] if len(values) > 1 else values[0]

    @staticmethod
    def build_inputs(project) -> tuple[dict[str, list[float]], dict[str, list[str]], dict[str, Any]]:
        unit_system = project.unit_system
        if not isinstance(unit_system, UnitSystem):
            unit_system = UnitSystem.from_sap(unit_system)
        to_meters = convert_value(Dimension.LENGTH, 1.0, unit_system, UnitSystem.N_M)

        points: dict[str, list[float]] = {}
        polygons: dict[str, list[str]] = {}

        explicit_surfaces = {
                PolygonType.SURFACE,
                PolygonType.LOAD_AREA,
            }

        target_polygons = [
            p for p in project.polygons.values()
            if p.poly_type in explicit_surfaces or not getattr(p, "is_temporary", False)
        ]

        if not target_polygons:
            target_polygons = list(project.polygons.values())

        for polygon in target_polygons:
            if polygon.poly_type in {PolygonType.ZONE, PolygonType.SECTION_CUT}:
                continue

            vertices = getattr(polygon, "vertices", None) or getattr(polygon, "nodes", None)
            if not vertices or len(vertices) < 3:
                continue

            poly_name = polygon.label or f"POLYGON_{polygon.unique_id}"
            point_names = []

            for idx, v in enumerate(vertices):
                if hasattr(v, "x") and hasattr(v, "y") and hasattr(v, "z"):
                    vx, vy, vz = float(v.x), float(v.y), float(v.z)
                    v_id = getattr(v, "unique_id", f"{polygon.unique_id}_{idx}")
                elif isinstance(v, (list, tuple)) and len(v) >= 3:
                    vx, vy, vz = float(v[0]), float(v[1]), float(v[2])
                    v_id = f"{polygon.unique_id}_{idx}"
                else:
                    continue

                point_name = f"V_{v_id}"
                points.setdefault(
                    point_name,
                    [
                        vx * to_meters,
                        vy * to_meters,
                        vz * to_meters,
                    ],
                )
                point_names.append(point_name)

            if len(point_names) >= 3:
                polygons[poly_name] = point_names

        cfg = project.config.wind
        terrain = str(getattr(cfg, "terrain_category", "III")).strip()
        if not terrain.lower().startswith("kategori"):
            terrain = f"Kategori {terrain}"
        wind_config = {
            "v_b0": float(getattr(cfg, "vb0", 28.0)),
            "terrain": terrain,
            "rho": float(getattr(cfg, "rho", 1.25)),
            "ct": float(getattr(cfg, "ct", 1.0)),
            "kI": float(getattr(cfg, "kI", 1.0)),
        }
        return points, polygons, wind_config

    @staticmethod
    def analyze(
        points: dict[str, list[float]],
        polygons: dict[str, list[str]],
        wind_config: dict[str, Any],
        w_dir: tuple[float, float, float],
    ) -> tuple[list[Any], dict[str, Any]]:
        direction = np.asarray(w_dir, dtype=float)
        if direction.shape != (3,) or not np.isfinite(direction).all():
            raise ValueError("Rüzgar yönü üç sonlu koordinat içermelidir.")
        if np.linalg.norm(direction[:2]) < 1e-12:
            raise ValueError("Rüzgar yönünün yatay bileşeni sıfır olamaz.")

        analyzer = WindAnalyzer(points, polygons, direction, **wind_config)
        zones = analyzer.analyze()
        engine = analyzer.engine
        return zones, {
            "q_p": float(engine.q_p),
            "q_b": float(engine.q_b),
            "z_ref": float(engine.z_ref),
            "e": float(engine.e or 0.0),
            "geometry": dict(engine.geometry),
        }

    @staticmethod
    def store_zones(
        project,
        direction_key: str,
        zones: list[Any],
        engine_data: dict[str, Any] | None = None,
        direction: tuple[float, float, float] | None = None,
    ) -> None:
        """Analiz önbelleği: project.loads.wind_zones + wind_results.

        ★ polygon.zone_children_by_direction YAZMAZ — onu wind_analysis_panel
        (_assign_zones_to_polygons) yapar. Böylece tek doğruluk kaynağı kalır.
        """
        if not hasattr(project.loads, "wind_zones"):
            project.loads.wind_zones = {}
        project.loads.wind_zones[direction_key] = list(zones)

        if engine_data is None:
            return

        unit_system = project.unit_system
        if not isinstance(unit_system, UnitSystem):
            unit_system = UnitSystem.from_sap(unit_system)

        # Proje birimine çevir
        meters_to_project = convert_value(
            Dimension.LENGTH, 1.0, UnitSystem.N_M, unit_system,
        )

        zone_data = []
        for zone in zones:
            coords = np.asarray(zone.coords, dtype=float)
            # WindAnalyzer'dan gelen coords METRE cinsinden → proje birimine
            coords_project = (coords * meters_to_project).tolist()
            zone_data.append({
                "label": zone.label,
                "surface": zone.surface,
                "table_type": zone.table_type,
                "table_type_dir": zone.table_type_dir,
                "pitch": float(zone.pitch),
                "coords": coords_project,
                "cpe10": list(WindSceneAdapter._coefficient_pair(zone.cpe10)),
                "cpe1": list(WindSceneAdapter._coefficient_pair(zone.cpe1)),
            })

        project.loads.wind_results[direction_key] = WindResult(
            direction=tuple(direction or (0.0, 0.0, 0.0)),
            q_p=float(engine_data["q_p"]),
            q_b=float(engine_data["q_b"]),
            z_ref=float(engine_data["z_ref"]),
            e=float(engine_data["e"]),
            zones_cpe10=zone_data,
            zones_cpe1=[
                {
                    **zone,
                    "cpe": list(WindSceneAdapter._coefficient_pair(source.cpe1)),
                }
                for zone, source in zip(zone_data, zones)
            ],
        )

    @staticmethod
    def update_direction_result(
        result: WindDirectionResult,
        zones: list[Any],
        engine_data: dict[str, Any],
    ) -> None:
        result.q_p = engine_data["q_p"]
        result.q_b = engine_data["q_b"]
        result.z_ref = engine_data["z_ref"]
        result.e = engine_data["e"]
        result.geometry = engine_data["geometry"]
        result.zones_data = [
            {
                "label": zone.label,
                "surface": zone.surface,
                "table_type": zone.table_type,
                "table_type_dir": zone.table_type_dir,
                "pitch": float(zone.pitch),
                "coords": np.asarray(zone.coords, dtype=float).tolist(),
                "cpe10": list(WindSceneAdapter._coefficient_pair(zone.cpe10)),
                "cpe1": list(WindSceneAdapter._coefficient_pair(zone.cpe1)),
            }
            for zone in zones
        ]

    @staticmethod
    def build_inputs_for_polygons(project, polygons):
        """Seçili polygon'lardan structload input."""
        if not polygons:
            raise ValueError("Polygon listesi boş")

        unit_system = project.unit_system
        if not isinstance(unit_system, UnitSystem):
            unit_system = UnitSystem.from_sap(unit_system)
        to_meters = convert_value(Dimension.LENGTH, 1.0, unit_system, UnitSystem.N_M)

        points: dict[str, list[float]] = {}
        polygons_dict: dict[str, list[str]] = {}

        for p in polygons:
            vertices = getattr(p, "vertices", None) or getattr(p, "nodes", None)
            if not vertices or len(vertices) < 3:
                continue

            poly_name = p.label or f"Polygon_{p.unique_id}"
            point_names = []

            for idx, v in enumerate(vertices):
                if hasattr(v, "x") and hasattr(v, "y") and hasattr(v, "z"):
                    vx, vy, vz = float(v.x), float(v.y), float(v.z)
                    v_id = getattr(v, "unique_id", f"{p.unique_id}_{idx}")
                elif isinstance(v, (list, tuple)) and len(v) >= 3:
                    vx, vy, vz = float(v[0]), float(v[1]), float(v[2])
                    v_id = f"{p.unique_id}_{idx}"
                else:
                    continue

                point_name = f"V_{v_id}"
                points.setdefault(
                    point_name,
                    [
                        vx * to_meters,
                        vy * to_meters,
                        vz * to_meters,
                    ],
                )
                point_names.append(point_name)

            if len(point_names) >= 3:
                polygons_dict[poly_name] = point_names

        _, _, wind_config = WindSceneAdapter.build_inputs(project)
        return points, polygons_dict, wind_config