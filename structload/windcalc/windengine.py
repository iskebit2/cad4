# structload/windcalc/windengine.py

from dataclasses import dataclass, field
import math
import numpy as np
from typing import List, Dict, Tuple, Optional, Any

from structload.data.wind_data import ARAZI_KATEGORILERI

@dataclass
class WindEngine:
    points: Dict[str, Tuple[float, float, float]]
    polygons: Dict[str, List[str]]
    v_b0: float = 28.0
    terrain: str = "Kategori III"
    w_dir: Any = field(default_factory=lambda: np.array([1.0, 0.0, 0.0], dtype=float))
    scale_factor: float = 1000.0
    rho: float = 1.25
    ct: float = 1.0
    kI: float = 1.0

    # Calculated fields
    z0: float = field(init=False)
    zmin: float = field(init=False)
    geometry: Dict[str, Any] = field(init=False, default_factory=dict)
    surfaces: Dict[str, Dict[str, Any]] = field(init=False, default_factory=dict)
    e: Optional[float] = field(init=False, default=None)
    q_b: float = field(init=False, default=0.0)
    z_ref: float = field(init=False, default=0.0)
    kr: float = field(init=False, default=0.0)
    cr: float = field(init=False, default=0.0)
    Iv: float = field(init=False, default=0.0)
    ce: float = field(init=False, default=0.0)
    q_p: float = field(init=False, default=0.0)
    obb: Dict[str, Any] = field(init=False, default_factory=dict)

    def __post_init__(self):
        # Ensure numpy array type
        self.w_dir = np.asarray(self.w_dir, dtype=float)

        if self.terrain not in ARAZI_KATEGORILERI:
            raise ValueError(f"Geçersiz arazi kategorisi: {self.terrain}")

        self.z0 = ARAZI_KATEGORILERI[self.terrain]["z0"]
        self.zmin = ARAZI_KATEGORILERI[self.terrain]["zmin"]

        # Complete unified geometry calculations
        self.update_geometry()
        self._calculate_wind_parameters()

    def update_geometry(self) -> None:
        """
        Bina geometrisini ve yönlendirilmiş sınır kutusunu (OBB) rüzgar yönüne göre
        tek bir ortak işlemde hesaplar ve sınıf özniteliklerini günceller.
        """
        if self.w_dir is None:
            return

        # 1. Rüzgar doğrultusunu ve dikini yerel 2B sisteme projekte etmek için baz vektörler
        w_xy = self.w_dir[:2] / np.linalg.norm(self.w_dir[:2])
        v_vec = np.array([-w_xy[1], w_xy[0]], dtype=float)

        pts_matrix = np.array(list(self.points.values()))

        # 2. Bina noktalarını bu rüzgar tabanlı eksenlere projekte etme
        u_vals = pts_matrix[:, :2] @ w_xy
        v_vals = pts_matrix[:, :2] @ v_vec
        z_vals = pts_matrix[:, 2]

        u_min, u_max = float(u_vals.min()), float(u_vals.max())
        v_min, v_max = float(v_vals.min()), float(v_vals.max())
        z_min, z_max = float(z_vals.min()), float(z_vals.max())

        # 3. Temel skaler boyutlar (Genişlik, Derinlik, Yükseklik)
        b = v_max - v_min   # Rüzgara dik cephe genişliği
        d = u_max - u_min   # Rüzgar yönündeki bina derinliği
        h = z_max - z_min   # Bina toplam yüksekliği
        e = min(b, 2.0 * h) # Kritik e uzunluğu

        # 4. Yönlendirilmiş sınır kutusu (OBB) köşe koordinatlarının 3D uzayda üretilmesi
        ref_point = np.array([0.0, 0.0, 0.0], dtype=float)

        def get_3d_coord(u: float, v: float) -> List[float]:
            return [
                ref_point[0] + w_xy[0] * u + v_vec[0] * v,
                ref_point[1] + w_xy[1] * u + v_vec[1] * v,
                0.0
            ]

        c1 = get_3d_coord(u_min, v_min)
        c2 = get_3d_coord(u_max, v_min)
        c3 = get_3d_coord(u_max, v_max)
        c4 = get_3d_coord(u_min, v_max)

        # 5. Rüzgarın çarptığı yüzeyin tam orta noktası (Impact Point)
        # Rüzgar yönü 'u' eksenidir. Çarpma noktası rüzgarın ilk çarptığı sınırda (u_min)
        # ve rüzgara dik cephenin tam ortasında (v'lerin ortalaması: v_mid) olmalıdır.
        v_mid = (v_min + v_max) / 2.0
        impact_point = get_3d_coord(u_min, v_mid)

        # Sınıf değişkenlerini güncelle
        self.e = e
        self.geometry = {
            "b": b,
            "d": d,
            "h": h,
            "z_ground": z_min,
            "z_ridge": z_max,
            "e": e
        }

        self.obb = {
            "obb_corners": [c1, c2, c3, c4],
            "impact_point": impact_point,
            "wind_dir": [w_xy[0], w_xy[1], 0.0],
            "parallel_dir": [v_vec[0], v_vec[1], 0.0]
        }

    def _calculate_wind_parameters(self) -> None:
        self.q_b = 0.5 * self.rho * (self.v_b0 ** 2) / 1000.0
        self.z_ref = max(self.geometry["z_ridge"], self.zmin)

        self.kr = 0.19 * ((self.z0 / 0.05) ** 0.07)
        self.cr = self.kr * math.log(self.z_ref / self.z0)
        self.Iv = self.kI / math.log(self.z_ref / self.z0)

        self.ce = (self.cr * self.ct) ** 2 * (1.0 + 7.0 * self.Iv)
        self.q_p = self.ce * self.q_b

    def report(self):
        report_= {
            "Geometri": dict(self.geometry),
            "Rüzgar": {
            "v_b0": self.v_b0,
            "terrain": self.terrain,
            "q_p": self.q_p,
            "z_ref": self.z_ref,
            "z0": self.z0,
            "zmin": self.zmin,
            }
        }
        return f'Rüzgar hesabı\n\n{report_}'
