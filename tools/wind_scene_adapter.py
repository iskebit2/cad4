# tools/wind_scene_adapter.py
from __future__ import annotations

from typing import Any

import numpy as np

from core.units import Dimension, UnitSystem, convert_value
from data.enums import PolygonType
from domain.definition import WindDirectionResult, WindResult
from structload.windcalc.wind_analyzer import WindAnalyzer


class WindSceneAdapter:
    WIND_UNIT_SYSTEM = UnitSystem.KN_M

    @staticmethod
    def _project_unit_system(project) -> UnitSystem:
        unit_system = project.unit_system
        if not isinstance(unit_system, UnitSystem):
            return UnitSystem.from_sap(unit_system)
        return unit_system

    @staticmethod
    def _length_scale(from_sys: UnitSystem, to_sys: UnitSystem) -> float:
        return float(convert_value(Dimension.LENGTH, 1.0, from_sys, to_sys))

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
    def _extract_points_and_polygons(
        project,
        target_polygons: list[Any],
        to_wind_length: float,
    ) -> tuple[dict[str, list[float]], dict[str, list[str]]]:
        points: dict[str, list[float]] = {}
        polygons: dict[str, list[str]] = {}

        for polygon in target_polygons:
            if polygon.poly_type in {PolygonType.ZONE, PolygonType.SECTION_CUT}:
                continue

            vertices = getattr(polygon, "vertices", None) or getattr(polygon, "nodes", None)
            if not vertices or len(vertices) < 3:
                continue

            poly_name = polygon.label or f"POLYGON_{polygon.unique_id}"
            point_names: list[str] = []

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
                        vx * to_wind_length,
                        vy * to_wind_length,
                        vz * to_wind_length,
                    ],
                )
                point_names.append(point_name)

            if len(point_names) >= 3:
                polygons[poly_name] = point_names

        return points, polygons

    @staticmethod
    def _build_wind_config(project, proj_unit: UnitSystem) -> dict[str, Any]:
        cfg = project.config.wind
        terrain = str(getattr(cfg, "terrain_category", "III")).strip()
        if not terrain.lower().startswith("kategori"):
            terrain = f"Kategori {terrain}"
        return {
            "v_b0": float(getattr(cfg, "vb0", 28.0)),
            "terrain": terrain,
            "rho": float(getattr(cfg, "rho", 1.25)),
            "ct": float(getattr(cfg, "ct", 1.0)),
            "kI": float(getattr(cfg, "kI", 1.0)),
        }

    @staticmethod
    def build_inputs(project) -> tuple[dict[str, list[float]], dict[str, list[str]], dict[str, Any]]:
        proj_unit = WindSceneAdapter._project_unit_system(project)
        to_wind_length = WindSceneAdapter._length_scale(proj_unit, WindSceneAdapter.WIND_UNIT_SYSTEM)

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

        points, polygons = WindSceneAdapter._extract_points_and_polygons(
            project, target_polygons, to_wind_length,
        )
        wind_config = WindSceneAdapter._build_wind_config(project, proj_unit)
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
        if not hasattr(project.loads, "wind_zones"):
            project.loads.wind_zones = {}
        project.loads.wind_zones[direction_key] = list(zones)

        if engine_data is None:
            return

        proj_unit = WindSceneAdapter._project_unit_system(project)
        wind_to_project = WindSceneAdapter._length_scale(WindSceneAdapter.WIND_UNIT_SYSTEM, proj_unit)

        zone_data = []
        for zone in zones:
            coords = np.asarray(zone.coords, dtype=float)
            coords_project = (coords * wind_to_project).tolist()
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
        if not polygons:
            raise ValueError("Polygon listesi boş")

        proj_unit = WindSceneAdapter._project_unit_system(project)
        to_wind_length = WindSceneAdapter._length_scale(proj_unit, WindSceneAdapter.WIND_UNIT_SYSTEM)

        points, polygons_dict = WindSceneAdapter._extract_points_and_polygons(
            project, list(polygons), to_wind_length,
        )
        wind_config = WindSceneAdapter._build_wind_config(project, proj_unit)
        
        return points, polygons_dict, wind_config