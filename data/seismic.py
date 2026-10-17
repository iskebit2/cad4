# data/seismic.py
# ============================================================================
# TBDY 2018 DEPREM TABLOLARI VE KATSAYILARI (LOOKUP TABLES)
# ============================================================================
from typing import List, Tuple


TSC_2018_FS_TABLE = {
    "ZA": [(0.25, 0.8), (0.50, 0.8), (0.75, 0.8), (1.00, 0.8), (1.25, 0.8), (1.50, 0.8)],
    "ZB": [(0.25, 0.9), (0.50, 0.9), (0.75, 0.9), (1.00, 0.9), (1.25, 0.9), (1.50, 0.9)],
    "ZC": [(0.25, 1.3), (0.50, 1.3), (0.75, 1.2), (1.00, 1.2), (1.25, 1.2), (1.50, 1.2)],
    "ZD": [(0.25, 1.6), (0.50, 1.4), (0.75, 1.2), (1.00, 1.1), (1.25, 1.0), (1.50, 1.0)],
    "ZE": [(0.25, 2.4), (0.50, 1.7), (0.75, 1.3), (1.00, 1.1), (1.25, 0.9), (1.50, 0.8)],
}

TSC_2018_F1_TABLE = {
    "ZA": [(0.10, 0.8), (0.20, 0.8), (0.30, 0.8), (0.40, 0.8), (0.50, 0.8), (0.60, 0.8)],
    "ZB": [(0.10, 0.8), (0.20, 0.8), (0.30, 0.8), (0.40, 0.8), (0.50, 0.8), (0.60, 0.8)],
    "ZC": [(0.10, 1.5), (0.20, 1.5), (0.30, 1.5), (0.40, 1.4), (0.50, 1.3), (0.60, 1.2)],
    "ZD": [(0.10, 2.4), (0.20, 2.2), (0.30, 2.0), (0.40, 1.8), (0.50, 1.6), (0.60, 1.5)],
    "ZE": [(0.10, 4.2), (0.20, 3.3), (0.30, 2.8), (0.40, 2.4), (0.50, 2.2), (0.60, 2.0)],
}


def get_tsc2018_site_coefficients(ss: float, s1: float, site_class: str) -> Tuple[float, float]:
    """
    TBDY 2018 Tablo 2.1 ve 2.2'ye göre doğrusal interpolasyon ile Fs ve F1 katsayılarını hesaplar.
    ZF sınıfında sahaya özel zemin davranışı analizi gerektiğinden varsayılan 1.0 döner.
    """
    site_class = site_class.upper()
    if site_class not in TSC_2018_FS_TABLE or site_class == "ZF":
        return 1.0, 1.0

    def interpolate(val: float, points: List[Tuple[float, float]]) -> float:
        if val <= points[0][0]:
            return points[0][1]
        if val >= points[-1][0]:
            return points[-1][1]
        for i in range(len(points) - 1):
            x0, y0 = points[i]
            x1, y1 = points[i + 1]
            if x0 <= val <= x1:
                return y0 + (y1 - y0) * (val - x0) / (x1 - x0)
        return 1.0

    fs = interpolate(ss, TSC_2018_FS_TABLE[site_class])
    f1 = interpolate(s1, TSC_2018_F1_TABLE[site_class])
    return fs, f1