from io import BytesIO
import numpy as np
import pandas as pd
from PIL import Image as PILImage, ImageDraw, ImageFont

from structload.data.wind_data import CPI_NEGATIVE, CPI_POSITIVE
from structload.utils.report_dataframe import ReportDataFrame

def show_zones(zones, building, size=800):
    zone_records = []
    cpe10_values = []

    for zone_obj in zones:
        coords = np.asarray(zone_obj.coords, dtype=float)
        cpe = zone_obj.cpe10
        current_cpe = float(cpe[0] if isinstance(cpe, (tuple, list, np.ndarray)) else cpe)
        
        zone_records.append((coords, zone_obj.label, current_cpe))
        cpe10_values.append(current_cpe)

    if not zone_records:
        raise ValueError("all_wind_zones boş!")

    b_coords = np.asarray(list(building.points.values()), dtype=float)
    min_b = b_coords.min(axis=0)
    max_b = b_coords.max(axis=0)
    mid_b = (min_b + max_b) / 2.0

    all_coords = np.vstack([r[0] for r in zone_records])
    mins = all_coords.min(axis=0)
    maxs = all_coords.max(axis=0)
    
    ranges = maxs - mins
    max_range = max(float(ranges.max()), 1.0)
    mid = (mins + maxs) / 2.0

    def project(p):
        x, y, z = p - mid
        sx = x - y
        sy = z - (x + y) * 0.5
        return sx, sy

    projected = [(np.array([project(p) for p in coords]), label, cpe) for coords, label, cpe in zone_records]

    all_2d = np.vstack([p for p, _, _ in projected])
    min_x, min_y = all_2d.min(axis=0)
    max_x, max_y = all_2d.max(axis=0)

    range_x = max(max_x - min_x, 1e-9)
    range_y = max(max_y - min_y, 1e-9)

    margin = 80
    scale = min((size - 2 * margin) / range_x, (size - 2 * margin) / range_y)

    def screen(p):
        sx = margin + (p[0] - min_x) * scale
        sy = size - margin - (p[1] - min_y) * scale
        return int(sx), int(sy)

    image = PILImage.new("RGBA", (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)

    neg = [v for v in cpe10_values if v < 0]
    pos = [v for v in cpe10_values if v > 0]
    max_neg = max([abs(v) for v in neg], default=1.0)
    max_pos = max(pos, default=1.0)

    def zone_color(cpe):
        if cpe < 0:
            t = min(abs(cpe) / max_neg, 1.0)
            return int(220 - 180 * t), int(235 - 150 * t), int(250 - 40 * t), 180
        if cpe > 0:
            t = min(cpe / max_pos, 1.0)
            return 255, int(225 - 180 * t), int(225 - 180 * t), 180
        return 220, 220, 220, 180

    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()

    for pts, label, cpe in projected:
        polygon = [screen(p) for p in pts]
        fill = zone_color(cpe)

        draw.polygon(polygon, fill=fill)
        draw.line(polygon + [polygon[0]], fill=(40, 40, 40, 255), width=2)

        centroid = pts.mean(axis=0)
        cx, cy = screen(centroid)

        text = f"{label} ({cpe:.2f})"
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pad = 5

        draw.rounded_rectangle(
            (cx - tw // 2 - pad, cy - th // 2 - pad, cx + tw // 2 + pad, cy + th // 2 + pad),
            radius=5,
            fill=(255, 255, 255, 180),
            outline=(100, 100, 100, 180),
            width=1,
        )

        draw.text((cx - tw // 2, cy - th // 2), text, font=font, fill=(0, 0, 0, 255))

    wind_vector = np.asarray(building.w_dir, dtype=float)
    norm = np.linalg.norm(wind_vector)
    wind_dir = wind_vector / norm if norm >= 1e-9 else np.array([1.0, 0.0, 0.0])

    arrow_length = max_range / 3.0
    start = mid_b.copy()

    dominant_axis = int(np.argmax(np.abs(wind_dir)))
    sign = np.sign(wind_dir[dominant_axis])
    b_size = max_b - min_b

    start[dominant_axis] = mid_b[dominant_axis] - sign * b_size[dominant_axis] / 2.0 - sign * arrow_length * 0.5
    end = start + wind_dir * arrow_length

    p1 = screen(project(start))
    p2 = screen(project(end))

    draw.line([p1, p2], fill=(220, 30, 30, 255), width=6)

    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    length = np.hypot(dx, dy)

    if length > 1e-9:
        ux, uy = dx / length, dy / length
        size_arrow = 25
        left = (p2[0] - ux * size_arrow - uy * size_arrow * 0.5, p2[1] - uy * size_arrow + ux * size_arrow * 0.5)
        right = (p2[0] - ux * size_arrow + uy * size_arrow * 0.5, p2[1] - uy * size_arrow - ux * size_arrow * 0.5)
        draw.polygon([p2, left, right], fill=(220, 30, 30, 255))
    
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def get_parameters_report(building) -> ReportDataFrame:
    h = building.geometry.get("h", 1)
    z_ref = max(h, building.zmin)

    params = [
        ("Bina Yüksekliği (h)", f"{h:.2f} m"),
        ("Arazi Kategorisi", building.terrain),
        ("Pürüzlülük Uzunluğu (z₀)", f"{building.z0:.3f} m"),
        ("Minimum Yükseklik (z_min)", f"{building.zmin:.1f} m"),
        ("Referans Yükseklik (z_ref)", f"{z_ref:.3f} m"),
        ("Temel Rüzgar Hızı (v_b0)", f"{building.v_b0:.1f} m/s"),
        ("Hava Yoğunluğu (ρ)", f"{building.rho:.2f} kg/m³"),
        ("Temel Hız Basıncı (q_b)", f"{building.q_b:.3f} kN/m²"),
        ("Pürüzlülük Katsayısı (k_r)", f"{building.kr:.3f}"),
        ("Arazi Faktörü (c_r)", f"{building.cr:.3f}"),
        ("Türbülans Şiddeti (I_v)", f"{building.Iv:.3f}"),
        ("Maruziyet Katsayısı (c_e)", f"{building.ce:.3f}"),
        ("Pik Hız Basıncı (q_p)", f"{building.q_p:.3f} kN/m²"),
        ("İç Basınç (+)", f"{CPI_POSITIVE:.2f}"),
        ("İç Basınç (-)", f"{CPI_NEGATIVE:.2f}"),
    ]

    df = pd.DataFrame(params, columns=["Parametre", "Değer"])

    desc = f"""
    Rüzgar Yükü Analizi - TS EN 1991-1-4

    Arazi Kategorisi: {building.terrain}

    Hesaplama Formülleri:
    q_b = 0.5 × ρ × v_b0² = {building.q_b:.3f} kN/m²
    k_r = 0.19 × (z₀/0.05)^0.07 = {building.kr:.3f}
    c_r = k_r × ln(z/z₀) = {building.cr:.3f}
    I_v = k_I / ln(z/z₀) = {building.Iv:.3f}
    c_e = c_r² × (1 + 7·I_v) = {building.ce:.3f}
    q_p = c_e × q_b = {building.q_p:.3f} kN/m²

    Not: Referans yükseklik olarak mahya seviyesi (z₂) kullanılmıştır.
    """
    return ReportDataFrame(
                            df,
                            custom_title="Rüzgar Yükü Parametreleri",
                            custom_desc=desc,
                            column_descriptions={"Parametre": "Hesap Parametresi", "Değer": "Hesaplanan Değer"},
                            column_units={"Parametre": "-", "Değer": "-"}
                        )


def _first(v):
    return v[0] if isinstance(v, (tuple, list, np.ndarray)) else v


def _second(v):
    return v[1] if isinstance(v, (tuple, list, np.ndarray)) and len(v) > 1 else 0.0


def _iter_zones(results):
    for bund in results:
        all_surfaces = getattr(bund, "all_surfaces", None) or {}
        for surf in all_surfaces.values():
            for zone in getattr(surf, "zones", None) or []:
                yield zone


def _as_3d(vec) -> np.ndarray:
    v = np.asarray(vec, dtype=float).ravel()
    if v.size == 2:
        return np.array([v[0], v[1], 0.0])
    if v.size >= 3:
        return v[:3].copy()
    return np.array([1.0, 0.0, 0.0])


_TYPE_ABBR = {
    "WALL": "W",
    "MONOPITCH": "M",
    "DUOPITCH": "D",
    "HIPPED": "H",
}


def create_cpe_summary_df(zones, engine) -> ReportDataFrame:
    rows = []
    for zone in zones:
        rows.append({
            "Bölge": zone.label,
            "Yüzey": zone.surface,
            "Tablo": zone.table_type,
            "Yön": zone.table_type_dir,
            "Eğim": zone.pitch,
            "Cpe,10 min": float(_first(zone.cpe10)),
            "Cpe,10 max": float(_second(zone.cpe10)),
            "Cpe,1 min": float(_first(zone.cpe1)),
            "Cpe,1 max": float(_second(zone.cpe1)),
        })

    df = pd.DataFrame(rows).sort_values("Bölge").reset_index(drop=True)

    desc = f"""
    Dış ve Net Basınç Katsayıları Özeti (TS EN 1991-1-4)

    Semboller ve Tanımlar:
    • CPE10 / CPE10m : 10 m² yüzey alanı için min (basınç/emme) ve max dış basınç katsayıları (c_pe,10).
    • CPE1 / CPE1m   : 1 m² yüzey alanı için min ve max dış basınç katsayıları (c_pe,1).
    • c_pi           : İç basınç katsayısı (Pozitif: {CPI_POSITIVE:+.2f}, Negatif: {CPI_NEGATIVE:+.2f}).

    Kombinasyon Kodları ve Formüller:
    • Cp10TPMn : c_pe,10(min) - c_pi(+)  [10 m² - Min Dış, Pozitif İç Basınç]
    • Cp10TNMn : c_pe,10(min) - c_pi(-)  [10 m² - Min Dış, Negatif İç Basınç]
    • Cp10TPMx : c_pe,10(max) - c_pi(+)  [10 m² - Max Dış, Pozitif İç Basınç]
    • Cp10TNMx : c_pe,10(max) - c_pi(-)  [10 m² - Max Dış, Negatif İç Basınç]
    • Cp1TPMn  : c_pe,1(min)  - c_pi(+)  [1 m²  - Min Dış, Pozitif İç Basınç]
    • Cp1TNMn  : c_pe,1(min)  - c_pi(-)  [1 m²  - Min Dış, Negatif İç Basınç]
    • Cp1TPMx  : c_pe,1(max)  - c_pi(+)  [1 m²  - Max Dış, Pozitif İç Basınç]
    • Cp1TNMx  : c_pe,1(max)  - c_pi(-)  [1 m²  - Max Dış, Negatif İç Basınç]

    Not: Net katsayılar w = q_p × (c_pe - c_pi) bağıntısına esas oluşturmak üzere hesaplanmıştır.
    """

    graphic = show_zones(zones, engine)
    
    report = ReportDataFrame(
        df,
        custom_title="Dış ve Net Basınç Katsayıları (Cpe & Cp,net)",
        custom_desc=desc,
        graphics=[{
            "image": graphic,
            "title": "Rüzgar Bölgesi Grafiği",
            "description": "Tablo ile ilişkili örnek grafik."
        }]
    )

    return report


def create_wind_force_df(zones, engine) -> ReportDataFrame:
    q_p = engine.q_p

    def _f(cpe, cpi):
        return round(q_p * (cpe - cpi), 3)

    rows = []
    for zone in zones:
        cpe10_min = float(_first(zone.cpe10))
        cpe10_max = float(_second(zone.cpe10))
        cpe1_min = float(_first(zone.cpe1))
        cpe1_max = float(_second(zone.cpe1))

        rows.append({
            "Bölge": zone.label,
            "Type": _TYPE_ABBR.get(zone.table_type, zone.table_type),
            "Pitch": round(float(zone.pitch), 3),
            "F10PMn (kN/m²)": _f(cpe10_min, CPI_POSITIVE),
            "F10NMn (kN/m²)": _f(cpe10_min, CPI_NEGATIVE),
            "F10PMx (kN/m²)": _f(cpe10_max, CPI_POSITIVE),
            "F10NMx (kN/m²)": _f(cpe10_max, CPI_NEGATIVE),
            "F1PMn (kN/m²)": _f(cpe1_min, CPI_POSITIVE),
            "F1NMn (kN/m²)": _f(cpe1_min, CPI_NEGATIVE),
            "F1PMx (kN/m²)": _f(cpe1_max, CPI_POSITIVE),
            "F1NMx (kN/m²)": _f(cpe1_max, CPI_NEGATIVE),
        })

    df = pd.DataFrame(rows).sort_values("Bölge").reset_index(drop=True)

    desc = f"""
    Rüzgar Yükü ve Tasarım Basınçları (TS EN 1991-1-4)

    Hesap Parametreleri:
    • Pik Hız Basıncı (q_p) : {q_p:.3f} kN/m²
    • İç Basınç Katsayıları : c_pi(+) = {CPI_POSITIVE:+.2f}, c_pi(-) = {CPI_NEGATIVE:+.2f}

    Sütun Sembolleri ve Formüller:
    • w = q_p × (c_pe - c_pi)

    Kombinasyon İsimlendirmeleri:
    • F10PMn : q_p × [c_pe,10(min) - c_pi(+)]  (Ana Taşıyıcı Sistem - En Olumsuz Emme / Basınç)
    • F10NMn : q_p × [c_pe,10(min) - c_pi(-)]  (Ana Taşıyıcı Sistem - Negatif İç Basınçlı)
    • F10PMx : q_p × [c_pe,10(max) - c_pi(+)]  (Ana Taşıyıcı Sistem - Maksimum Dış Basınçlı)
    • F10NMx : q_p × [c_pe,10(max) - c_pi(-)]  (Ana Taşıyıcı Sistem - Kombine Max Basınç)
    • F1PMn  : q_p × [c_pe,1(min)  - c_pi(+)]  (Eleman/Kaplama Hesabı - En Olumsuz Emme)
    • F1TNMn : q_p × [c_pe,1(min)  - c_pi(-)]  (Eleman/Kaplama Hesabı - Negatif İç Basınçlı)
    • F1PMx  : q_p × [c_pe,1(max)  - c_pi(+)]  (Eleman/Kaplama Hesabı - Maksimum Dış Basınçlı)
    • F1NMx  : q_p × [c_pe,1(max)  - c_pi(-)]  (Eleman/Kaplama Hesabı - Kombine Max Basınç)

    Not: Pozitif (+) değerler yüzeye doğru basıncı (itme), negatif (-) değerler yüzeyden dışarı doğru basıncı (emme/çekme) ifade eder.
    """

    return ReportDataFrame(
        df,
        custom_title="Tasarım Rüzgar Yükleri (kN/m²)",
        custom_desc=desc
    )