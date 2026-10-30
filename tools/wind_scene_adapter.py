from __future__ import annotations

from typing import Any

import numpy as np

from core.units import Dimension, UnitSystem, convert_value
from data.enums import PolygonType
from domain.definition import WindDirectionResult, WindResult
from structload.windcalc.wind_analyzer import WindAnalyzer


class WindSceneAdapter:
    """Translate CAD geometry to the wind calculator and persist its zones."""

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
    def build_inputs(scene, project) -> tuple[dict[str, list[float]], dict[str, list[str]], dict[str, Any]]:
        unit_system = project.unit_system
        if not isinstance(unit_system, UnitSystem):
            unit_system = UnitSystem.from_sap(unit_system)
        to_meters = convert_value(Dimension.LENGTH, 1.0, unit_system, UnitSystem.N_M)

        points: dict[str, list[float]] = {}
        polygons: dict[str, list[str]] = {}

        def add_surface(name: str, nodes) -> None:
            if len(nodes) < 3:
                return
            point_names = []
            for node in nodes:
                point_name = f"N{node.unique_id}"
                points.setdefault(
                    point_name,
                    [
                        float(node.x) * to_meters,
                        float(node.y) * to_meters,
                        float(node.z) * to_meters,
                    ],
                )
                point_names.append(point_name)
            polygons[name] = point_names

        for area in scene.areas.values():
            add_surface(f"AREA_{area.unique_id}", area.nodes)

        explicit_surfaces = {
            PolygonType.SURFACE_ONEWAY,
            PolygonType.SURFACE_TWOWAY,
        }
        for polygon in scene.polygons.values():
            if polygon.poly_type in explicit_surfaces:
                add_surface(f"POLYGON_{polygon.unique_id}", polygon.nodes)

        if not polygons:
            for polygon in scene.polygons.values():
                if polygon.poly_type not in {
                    PolygonType.ZONE,
                    PolygonType.SECTION_CUT,
                    PolygonType.LOAD_AREA,
                }:
                    add_surface(f"POLYGON_{polygon.unique_id}", polygon.nodes)

        if not polygons:
            raise ValueError("Rüzgar analizi için sahnede geçerli Area veya yüzey poligonu bulunamadı.")

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
        if not hasattr(project.loads, "wind_zones"):
            project.loads.wind_zones = {}
        project.loads.wind_zones[direction_key] = list(zones)
        if engine_data is None:
            return

        zone_data = [
            {
                "label": zone.label,
                "surface": zone.surface,
                "table_type": zone.table_type,
                "pitch": float(zone.pitch),
                "coords": np.asarray(zone.coords, dtype=float).tolist(),
                "cpe": list(WindSceneAdapter._coefficient_pair(zone.cpe10)),
            }
            for zone in zones
        ]
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
                    "cpe": list(
                        WindSceneAdapter._coefficient_pair(source.cpe1)
                    ),
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
