# windcalc/analysis.py
"""
Rüzgar analizi katmanı — SADECE veri üretir, çizim yapmaz.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any
import numpy as np

from structload.windcalc.surface import Surface
from structload.windcalc.surface_analyzer import (
    _analysis_classify_all_surface,
    _analysis_global_edges,
    _analyze_shared_edges,
)
from structload.windcalc.windengine import WindEngine


# ---------------------------------------------------------------------------
# Sonuç konteyneri
# ---------------------------------------------------------------------------
@dataclass
class ZoneResult:
    """Tek bir rüzgar yönü için analiz sonucu."""
    w_key: str
    w_dir: Tuple[float, float, float]
    engine: WindEngine
    all_surfaces: Dict[str, Surface]
    # Çizim için hazır edge bilgileri (opsiyonel, cache)
    legend_entries: Dict[str, Any] = field(default_factory=dict)

    def iter_zones(self):
        """Tüm yüzeylerdeki Zone nesnelerini tek düz listede döner."""
        for surf in self.all_surfaces.values():
            for zone in getattr(surf, "zones", []) or []:
                yield surf, zone

    def iter_edges(self):
        """(surface, edge) çiftlerini döner."""
        for surf in self.all_surfaces.values():
            for edge in surf.edges.values():
                yield surf, edge


@dataclass
class ZoneBundle:
    points: Dict[str, Tuple[float, float, float]]
    polygons: Dict[str, List[str]]
    e: float
    results: List[ZoneResult] = field(default_factory=list)

    def __iter__(self):
        return iter(self.results)

    # =========================================================
    # UI UYUMLULUK KATMANI (yukarıdaki property'ler)
    # =========================================================
    @property
    def wind_planes(self) -> Dict[str, Any]:
        if not self.results:
            return {}
        return dict(self.results[0].all_surfaces)

    @property
    def surfaces_items(self) -> Dict[str, Any]:
        return self.wind_planes

    @property
    def raw_points(self):
        return self.points

    def get_summary(self) -> Dict[str, Any]:
        """BuildingWindEngine.get_summary() benzeri özet."""
        if not self.results:
            return {}

        engine = self.results[0].engine
        return {
            "Geometri": dict(engine.geometry),
            "Rüzgar": {
                "v_b0": engine.v_b0,
                "terrain": engine.terrain,
                "q_p": engine.q_p,
                "z_ref": engine.z_ref,
                "z0": engine.z0,
                "zmin": engine.zmin,
            },
            "Yönler": [r.w_key for r in self.results],
            "Yüzey Sayısı": len(self.wind_planes),
        }

    def analysis_all_roof_wind(self, w_dir=None):
        """
        Eski API uyumluluğu.

        w_dir verilirse ilgili ZoneResult'ın surfaces'ini döner.
        Verilmezse ilk yönü döner.
        """
        if w_dir is None:
            return self.wind_planes

        w_arr = np.asarray(w_dir, dtype=float)
        norm = np.linalg.norm(w_arr)
        if norm < 1e-12:
            return self.wind_planes
        w_arr = w_arr / norm

        for r in self.results:
            r_arr = np.asarray(r.w_dir, dtype=float)
            r_norm = np.linalg.norm(r_arr)
            if r_norm < 1e-12:
                continue
            r_arr = r_arr / r_norm
            if np.allclose(r_arr, w_arr, atol=1e-6):
                return r.all_surfaces

        return self.wind_planes


# ---------------------------------------------------------------------------
# Ana analiz fonksiyonu
# ---------------------------------------------------------------------------
W_LIST = {
    "x+": np.array([1.0, 0.0, 0.0]),
    "y+": np.array([0.0, 1.0, 0.0]),
    "x-": np.array([-1.0, 0.0, 0.0]),
    "y-": np.array([0.0, -1.0, 0.0]),
}


def analyze(
    points,
    polygons,
    verbose: bool = False,
    **engine_kwargs,
) -> ZoneBundle:

    w_list = W_LIST

    results: List[ZoneResult] = []
    last_e = 0.0

    for w_key, w_dir in w_list.items():

        w_dir = np.asarray(w_dir, dtype=float)

        if verbose:
            print(f"\n{'=' * 40}\nWIND: {w_key}\n{'=' * 40}")

        engine = WindEngine(
                        points=points,
                        polygons=polygons,
                        w_dir=w_dir,
                        **engine_kwargs,
                    )

        last_e = engine.e

        all_surfaces: Dict[str, Surface] = {}

        for poly_name, pt_names in polygons.items():
            pts = np.array([points[pt] for pt in pt_names])

            surf = Surface(pts, name=poly_name)
            surf.analyze(w_dir)

            all_surfaces[poly_name] = surf

            if verbose:
                _debug_surface(surf)

        _analyze_shared_edges(all_surfaces, w_dir, tol=1e-3)
        _analysis_global_edges(all_surfaces)
        _analysis_classify_all_surface(all_surfaces)
        _generate_zones(all_surfaces, engine.e)

        results.append(
            ZoneResult(
                w_key=w_key,
                w_dir=tuple(w_dir),
                engine=engine,
                all_surfaces=all_surfaces,
            )
        )

    return ZoneBundle(
        points=dict(points),
        polygons=dict(polygons),
        e=last_e,
        results=results,
    )


def _generate_zones(all_surfaces: Dict[str, Surface], e: float) -> None:
    """Zone'ları surface üzerinde üretir (3D coords + label)."""
    from structload.windcalc.zone_generator import _get_roof_zones, _get_wall_zones

    for surf in all_surfaces.values():
        if surf.surface_type.value == "WALL":
            surf.zones = _get_wall_zones(surf, e)
        else:
            surf.zones = _get_roof_zones(surf, e)


def _debug_surface(surf: Surface) -> None:
    print(f"\nSurface: {surf.name}")
    print(f"  wind_vector: {surf.wind_vector}")
    print(f"  type       : {surf.surface_type.value}")
    print(f"  relation   : {surf.wind_relation.value}")
    print(f"  is_ccw     : {surf.is_ccw}")
    print("  Exposed edges:")
    for edge in surf.edges.values():
        if not edge.exposed:
            continue
        print(
            f"    Edge {edge.index}: "
            f"p1 {edge.p1}, p2 {edge.p2}, "
            f"wind_to_2d={edge.wind_to_2d}, "
            f"pos_front={edge.pos_front:8.3f}, "
            f"pos_back={edge.pos_back:8.3f}, "
            f"angle={edge.angle:7.3f}, "
            f"leading={edge.leading}"
        )
    print(
        "  >>> SELECTED LEADING:",
        [e.index for e in surf.edges.values() if e.leading],
    )