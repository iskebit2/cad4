import math
import numpy as np
from typing import List, Dict, Tuple, Optional, Union, Any
# Geometrik yardımcılar
from structload.windcalc.geometry_utils import close_polygon, polygon_centroid, _make_local_sys, _project_3d_to_local_2d, _normalize_wind
from structload.windcalc.edge import Edge
from structload.data.wind_data import EPS, SurfaceType, WindRelation

class Surface:
    def __init__(self, polygon: Union[List, np.ndarray], name: str = "Test", tol: float = 1e-6):
        """3B Düzlemsel Poligon Nesnesi"""
        pts = np.asarray(polygon, dtype=float)

        if len(pts) > 1 and np.allclose(pts[0], pts[-1], atol=1e-8):
            pts = pts[:-1]

        if len(pts) < 3:
            raise ValueError("Poligon en az 3 nokta içermelidir.")

        self.name = name
        self.coords = pts # Açık 3B koordinatlar
        self.pts_3d: np.ndarray = close_polygon(pts) # Kapalı 3B polygon
        self.n_pts: int = len(pts)
        self.proj_info = _make_local_sys(self.pts_3d) # En uygun projeksiyon düzlemi
        self.pts_2d: np.ndarray = _project_3d_to_local_2d(self.pts_3d, self.proj_info) # 2B projeksiyon
        self.wind_vector = np.array([])
        
        self._wind_xy = np.array([])
        self._wind_to_2d = np.array([])

        self.tol = float(tol)

        # Geometrik özellikler
        self.normal, self.normal_unit = self._compute_normal()
        self.centroid = polygon_centroid(self.pts_3d)
        self.pitch: float = self._compute_pitch()
        self.angle = self._compute_angle()
        self.is_ccw = (self.polygon_direction_xy() == "CCW")

        self.surface_type: SurfaceType = (SurfaceType.ROOF if self.pitch <= 75.0 else SurfaceType.WALL)
        self.wind_relation = WindRelation.nodata
        self.roof_type = None

        self.edges = self._build_edges()
        self.exposed_edge_list = []
        self.leading_edge_list = []
        self.global_leading_edge_list = []
        self.global_leading = False
        self.any_shared = False
        self.zones = []

    def _compute_normal(self) -> Tuple[np.ndarray, np.ndarray]:
        normal = np.zeros(3)
        for i in range(self.n_pts):
            p_curr, p_next = self.pts_3d[i], self.pts_3d[(i + 1) % self.n_pts]
            normal[0] += (p_curr[1] - p_next[1]) * (p_curr[2] + p_next[2])
            normal[1] += (p_curr[2] - p_next[2]) * (p_curr[0] + p_next[0])
            normal[2] += (p_curr[0] - p_next[0]) * (p_curr[1] + p_next[1])

        norm_len = np.linalg.norm(normal)
        if norm_len < 1e-12:
            raise ValueError(f"Geçersiz/Çökmüş poligon düzlemi: {self.pts_3d}")
        return normal, normal / norm_len

    def _compute_angle(self) -> float:
        if self.pitch < 1e-10:
            return 0.0
        nx, ny, nz = self.normal_unit
        if self.pitch >= 90.0 - 1e-10:
            return float(np.degrees(np.arctan2(ny, nx)))
        horiz_len = np.hypot(nx, ny)
        if horiz_len < 1e-12:
            return 0.0
        sign = np.sign(ny) if abs(ny) > abs(nx) else np.sign(nx)
        return float(sign * self.pitch)

    def _compute_pitch(self) -> float:
        nz_ratio = abs(self.normal_unit[2])
        nz_ratio = np.clip(nz_ratio, -1.0, 1.0)
        return float(np.degrees(np.arccos(nz_ratio)))

    @property
    def properties(self) -> dict:
        """
        UI / raporlama için özet sözlük.
        Her erişimde güncel hesaplanır → çoklu güncelleme sorunu yok.

        Kullanım:
            data_dialog._add_branch_properties() → getattr(plane, "properties")
        """
        return {
            "name": self.name,
            "type": self.surface_type.value,
            "wind_relation": self.wind_relation.value,
            "roof_type": self.roof_type or "-",
            "pitch_deg": round(self.pitch, 3),
            "angle_deg": round(self.angle, 3),
            "is_ccw": self.is_ccw,
            "n_pts": self.n_pts,
            "centroid": tuple(round(float(v), 3) for v in self.centroid),
            "normal_unit": tuple(round(float(v), 4) for v in self.normal_unit),
            "n_edges": len(self.edges),
            "n_exposed": len(self.exposed_edge_list),
            "n_leading": len(self.leading_edge_list),
            "n_zones": len(self.zones),
            "has_global_leading": bool(self.global_leading),
            "any_shared": bool(self.any_shared),
        }

    def _get_best_projection_plane(self):
        abs_n = np.abs(self.normal_unit)
        max_idx = np.argmax(abs_n)
        if max_idx == 2:
            return 'XY', (0, 1), 2
        elif max_idx == 1:
            return 'XZ', (0, 2), 1
        else:
            return 'YZ', (1, 2), 0

    def polygon_direction_xy(self) -> str:
        """Poligonun XY düzlemindeki yönünü belirler."""
        polygon = np.asarray(self.pts_3d, dtype=float)
        if len(polygon) < 3:
            return "DEGENERATE"
        if np.allclose(polygon[0], polygon[-1]):
            polygon = polygon[:-1]
        if len(polygon) < 3:
            return "DEGENERATE"
        area2 = 0.0
        n = len(polygon)
        for i in range(n):
            x1, y1 = polygon[i][:2]
            x2, y2 = polygon[(i + 1) % n][:2]
            area2 += x1 * y2 - x2 * y1
        if area2 > EPS:
            return "CCW"
        elif area2 < -EPS:
            return "CW"
        else:
            return "DEGENERATE"

    def _build_edges(self) -> Dict[int, Edge]:
        edges = {}
        for i in range(self.n_pts):
            try:
                edges[i] = Edge.from_points(i, self)
            except ValueError:
                continue
        return edges

    def get_upslope_vector_xy(self) -> Optional[np.ndarray]:
        """
        Poligonun CCW/CW yapısından bağımsız olarak,
        Z yüksekliğinin arttığı (tırmanma) yönün XY projeksiyonunu döner.
        """
        nx, ny, nz = self.normal_unit

        # Tam dikey duvar veya dümdüz çatı
        if abs(nz) < 1e-4 or abs(nz) > 0.9999:
            return None

        # Z'nin artış gösterdiği XY gradyan yönü: (-nx/nz, -ny/nz)
        slope_xy = -np.array([nx / nz, ny / nz], dtype=float)
        norm = np.linalg.norm(slope_xy)

        return slope_xy / norm if norm > 1e-12 else None

    def analyze_wind_relation(self, w_vector: np.ndarray, angle_tol_deg: float = 5.0) -> WindRelation:
        self.wind_vector = w_vector
        # 1. Rüzgar yatay birim vektörü
        w_xy = np.array(w_vector[:2], dtype=float)
        w_norm = np.linalg.norm(w_xy)
        if w_norm < 1e-12:
            raise ValueError("Rüzgar vektörünün yatay bileşeni sıfır olamaz.")
        w_xy /= w_norm

        # 2. DUVAR HESABI
        if self.surface_type == SurfaceType.WALL:
            n_xy = np.array(self.normal_unit[:2], dtype=float)
            n_norm = np.linalg.norm(n_xy)
            if n_norm > 1e-12:
                n_xy /= n_norm
                # Dış normal ile rüzgar karşı karşıya geliyorsa (dot < 0) WINDWARD'dır
                dot = np.dot(n_xy, w_xy)
                tol_sin = np.sin(np.radians(angle_tol_deg))
                if dot < -tol_sin:
                    return WindRelation.WINDWARD
                elif dot > tol_sin:
                    return WindRelation.LEEWARD
            return WindRelation.PARALLEL

        # 3. ÇATI (ROOF) HESABI
        upslope_xy = self.get_upslope_vector_xy()
        if upslope_xy is None:
            return WindRelation.PARALLEL

        # Rüzgar yönü ile tırmanış yönünün iç çarpımı
        dot = np.dot(upslope_xy, w_xy)
        tol_cos = np.sin(np.radians(angle_tol_deg))

        if dot > tol_cos:
            return WindRelation.WINDWARD
        elif dot < -tol_cos:
            return WindRelation.LEEWARD
        else:
            return WindRelation.PARALLEL

    def _wind_to_local_2d(self, wind_vector: np.ndarray) -> np.ndarray:
        """Global 3B rüzgâr vektörünü Surface lokal 2B sistemine dönüştürür."""
        wind = np.array([
                            wind_vector[0],
                            wind_vector[1],
                            0.0
                        ])

        u_dir = self.proj_info["u_dir"]
        v_dir = self.proj_info["v_dir"]

        return np.array([
            np.dot(wind, u_dir),
            np.dot(wind, v_dir)
        ])
    
    def analyze(self, wind_vector: Optional[np.ndarray]) -> None:
        wind_to = _normalize_wind(wind_vector)
        if wind_to is None:
            return

        self.wind_relation = self.analyze_wind_relation(wind_vector)
        self._wind_xy = wind_to[:2]

        # BURADA global -> local dönüşüm yapılacak
        self._wind_to_2d = self._wind_to_local_2d(wind_to)

        # Analiz verilerini sıfırla
        for edge in self.edges.values():
            edge.reset_analysis()

        # 1. Metrikleri hesapla
        for edge in self.edges.values():
            self._compute_edge_metrics(edge)

        # 2. Hücum kenarlarını işaretle
        self._mark_leading()

        self.exposed_edge_list = [k for k, ed in self.edges.items() if ed.exposed]
        self.leading_edge_list = [k for k, ed in self.edges.items() if ed.leading]


    def _compute_edge_metrics(self, edge: Edge) -> None:
        if edge.direction_2d is None:
            pos1 = float(np.dot(edge.p1[:2], self._wind_to_2d))
            edge.pos_front = pos1
            edge.pos_back = pos1
            edge.angle = 90.0
            edge.exposed = False
            edge.vertical = True
            return

        p1 = edge.p1_2d
        p2 = edge.p2_2d

        s1 = float(np.dot(p1, self._wind_to_2d))
        s2 = float(np.dot(p2, self._wind_to_2d))

        edge.pos_front_pt = edge.p1_2d if s1 <= s2 else edge.p2_2d
        edge.pos_front = min(s1, s2)
        edge.pos_back = max(s1, s2)

        cos_a = float(np.clip(abs(np.dot(edge.direction_2d, self._wind_to_2d)), -1.0, 1.0))
        edge.angle = float(np.degrees(np.arccos(cos_a)))
        edge.exposed = self._is_exposed(edge)
        edge.vertical = False

    def _is_exposed(self, edge) -> bool:

        e = (
            np.asarray(edge.p2[:2], dtype=float)
            - np.asarray(edge.p1[:2], dtype=float)
        )

        w = self._wind_xy

        cross = (
            e[0] * w[1]
            - e[1] * w[0]
        )

        edge.wind_to_2d= self._wind_to_2d

        if self.is_ccw:
            return cross > self.tol

        return cross < -self.tol

    def _mark_leading(self):
        exposed = [
            e for e in self.edges.values()
            if e.exposed
        ]

        if not exposed:
            return

        leading = min(
            exposed,
            key=lambda e: (
                e.pos_back,
                -e.angle
            )
        )

        for e in exposed:
            e.leading = (
                abs(e.pos_back - leading.pos_back) <= self.tol
                and abs(e.angle - leading.angle) <= self.tol
            )
