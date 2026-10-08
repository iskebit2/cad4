# tools/wind_service.py

from typing import Dict, List, Tuple, Any
import numpy as np

from domain.scene import Scene
from domain.element import Node, Polygon, PolygonType
from structload.windcalc.wind_analyzer import WindAnalyzer


def get_cpe_color(cpe_val: float, min_cpe: float = -1.5, max_cpe: float = 0.8, alpha: float = 0.6) -> List[float]:
    if isinstance(cpe_val, (list, tuple, np.ndarray)):
        cpe_val = float(np.mean(cpe_val))
    else:
        cpe_val = float(cpe_val)

    norm = (cpe_val - min_cpe) / (max_cpe - min_cpe)
    norm = max(0.0, min(1.0, norm))

    r = max(0.0, min(1.0, 1.5 - abs(norm - 0.75) * 4.0))
    g = max(0.0, min(1.0, 1.5 - abs(norm - 0.50) * 4.0))
    b = max(0.0, min(1.0, 1.5 - abs(norm - 0.25) * 4.0))

    return [round(r, 3), round(g, 3), round(b, 3), round(alpha, 3)]


class WindSceneAdapter:

    @classmethod
    def extract_wind_data_from_scene(cls, scene: Scene) -> Tuple[Dict[str, List[float]], Dict[str, List[str]]]:
        """
        Sahnedeki TÜM düğüm ve poligonları WindEngine/WindAnalyzer'ın beklediği 
        points ve polygons formatına getirir.
        """
        points: Dict[str, List[float]] = {}
        polygons: Dict[str, List[str]] = {}

        if hasattr(scene, 'nodes') and scene.nodes:
            for nid, n in scene.nodes.items():
                points[f"N_{n.unique_id}"] = [float(n.x), float(n.y), float(n.z)]

        surface_polys = [
            p for p in scene.polygons.values() 
            if getattr(p, "poly_type", None) == PolygonType.SURFACE
        ] if hasattr(scene, 'polygons') else []

        target_polys = surface_polys if surface_polys else (list(scene.polygons.values()) if hasattr(scene, 'polygons') else [])

        for poly in target_polys:
            p_key = f"POLY_{poly.unique_id}"
            node_keys = [f"N_{n.unique_id}" for n in poly.nodes]
            polygons[p_key] = node_keys

        return points, polygons

    @classmethod
    def run_wind_analysis_and_update_scene(
        cls, 
        scene: Scene, 
        w_dir: Tuple[float, float, float] = (1.0, 0.0, 0.0),
        engine_kwargs: Dict[str, Any] = None
    ) -> List[Polygon]:
        """
        Sizin yazdığınız WindAnalyzer sınıfını doğrudan çalıştırır.
        """
        # Eski ZONE poligonlarını temizle
        old_zone_ids = [
            pid for pid, poly in scene.polygons.items() 
            if getattr(poly, "poly_type", None) == PolygonType.ZONE or poly.label.startswith("ZONE_")
        ]
        for pid in old_zone_ids:
            poly = scene.polygons.pop(pid, None)
            if poly:
                for node in poly.nodes:
                    if node.label.startswith("W_NODE_") and node.unique_id in scene.nodes:
                        scene.nodes.pop(node.unique_id, None)

        points, polygons = cls.extract_wind_data_from_scene(scene)

        if not engine_kwargs:
            engine_kwargs = {"v_b0": 28.0, "terrain": "Kategori III"}

        # DOĞRUDAN SİZİN WindAnalyzer MOTORUNUZU ÇALIŞTIRIR
        analyzer = WindAnalyzer(
            points=points,
            polygons=polygons,
            w_dir=list(w_dir),
            **engine_kwargs
        )

        zones = analyzer.analyze()

        created_polygons: List[Polygon] = []

        for idx, zone in enumerate(zones):
            zone_nodes: List[Node] = []
            for coord in zone.coords:
                node = Node(x=float(coord[0]), y=float(coord[1]), z=float(coord[2]), label=f"W_NODE_{idx}")
                scene.add_node(node)
                zone_nodes.append(node)

            if len(zone_nodes) >= 3:
                poly = Polygon(
                    nodes=zone_nodes, 
                    label=f"ZONE_{zone.label}_{zone.surface}", 
                    poly_type=PolygonType.ZONE
                )
                
                cpe10 = getattr(zone, 'cpe10', None)
                poly.color = get_cpe_color(cpe10) if cpe10 is not None else [0.8, 0.3, 0.8, 0.5]

                poly.windplane = {
                    "label": zone.label,
                    "surface": zone.surface,
                    "table_type": zone.table_type,
                    "table_type_dir": zone.table_type_dir,
                    "pitch": zone.pitch,
                    "cpe10": cpe10,
                    "cpe1": getattr(zone, 'cpe1', None),
                    "kind": str(getattr(zone, "kind", "")),
                }

                scene.add_polygon(poly)
                created_polygons.append(poly)

        return created_polygons