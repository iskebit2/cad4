# utils/meta_tables.py

from structload.utils.report_dataframe import ReportDataFrame
from structload.data.mechanical import woodMaterial


import pandas as pd
from structload.data.material_data import (
MATERIAL_LIBRARY,
WALL_PRESETS,
DEAD_LOAD_PRESETS,
LIVE_LOADS

)



# ============================================================
# KATMAN HESABI — TEK KAYNAK
# ============================================================

def katman_yuku(layer: dict) -> tuple[float, str, float | None]:
    """
    Bir katmanın alansal yükünü ve meta bilgisini döner.
    
    Returns:
        (yuk_kN_m2, kaynak_aciklama, kalinlik)
    
    Katman şeması (esnek):
        {"mat": "şap", "thickness_m": 0.04, "label": "..."}      # kütüphaneden
        {"custom_weight": 0.10, "unit": "area", "label": "..."}   # elle
        {"mat": "özel", "weight": 7.8, "thickness_m": 0.02}       # override
    """
    kalinlik = layer.get("thickness_m")

    # 1) Kütüphaneden çek (mat varsa)
    mat_key = layer.get("mat")
    if mat_key and mat_key in MATERIAL_LIBRARY:
        mat = MATERIAL_LIBRARY[mat_key]
        weight = layer.get("weight", mat["weight"])
        unit = mat.get("unit", "volumetric")

        if unit == "volumetric":
            if kalinlik is None or kalinlik <= 0:
                raise ValueError(
                    f"'{mat_key}' hacimsel malzeme, thickness_m zorunlu."
                )
            return weight * kalinlik, f"{mat['name']} × {kalinlik*1000:.0f} mm", kalinlik
        else:  # area
            return weight, f"{mat['name']} (alansal)", None

    # 2) custom_weight varsa
    if "custom_weight" in layer:
        weight = layer["custom_weight"]
        unit = layer.get("unit", "area")
        if unit == "volumetric":
            if kalinlik is None or kalinlik <= 0:
                raise ValueError("Hacimsel custom_weight için thickness_m zorunlu.")
            return weight * kalinlik, f"Özel × {kalinlik*1000:.0f} mm", kalinlik
        return weight, "Özel (alansal)", None

    # 3) Ne mat ne custom_weight → hata
    raise KeyError(
        f"Katman tanımsız: {layer.get('label', '?')} — "
        f"'mat' veya 'custom_weight' gerekli."
    )


# ============================================================
# TEK KATMANLIK RAPOR
# ============================================================

def katman_raporu_df(
    layers: list[dict],
    title: str,
    desc: str = "",
) -> ReportDataFrame:
    """Katman listesini tek ReportDataFrame'e çevirir."""
    rows = []
    toplam = 0.0

    for i, layer in enumerate(layers, 1):
        try:
            yuk, aciklama, kalinlik = katman_yuku(layer)
            toplam += yuk
            rows.append({
                "No": i,
                "Katman": layer.get("label") or aciklama,
                "Açıklama": aciklama,
                "Kalınlık": kalinlik if kalinlik is not None else "-",
                "Yük": round(yuk, 4),
            })
        except Exception as e:
            rows.append({
                "No": i,
                "Katman": layer.get("label", "?"),
                "Açıklama": f"HATA: {e}",
                "Kalınlık": "-",
                "Yük": 0.0,
            })

    # Toplam satırı
    rows.append({
        "No": "",
        "Katman": "TOPLAM",
        "Açıklama": "",
        "Kalınlık": "",
        "Yük": round(toplam, 4),
    })

    return ReportDataFrame(
        rows,
        custom_title=title,
        custom_desc=desc,
        column_units={
            "Kalınlık": "m",
            "Yük": "kN/m²",
        },
        column_descriptions={
            "No": "Sıra",
            "Katman": "Katman adı",
            "Açıklama": "Malzeme ve hesap açıklaması",
            "Kalınlık": "Katman kalınlığı",
            "Yük": "Hesaplanan ölü yük",
        },
        column_formats={
            "Kalınlık": ".3f",
            "Yük": ".3f",
        },
    )

def duvar_alansal_yuk(layers: list[dict]) -> float:
    """Duvar katmanlarının toplam alansal yükü (kN/m²)."""
    return sum(katman_yuku(l)[0] for l in layers)


def calculate_wall_line_load(
    layers: list[dict],
    wall_height_m: float,
    beam_depth_m: float = 0.0,
    opening_ratio: float = 0.0,
) -> dict:
    """
    Kiriş üstü duvar çizgi yükü (kN/m).
    """
    # --- Validasyon ---
    if wall_height_m < 0:
        raise ValueError(f"wall_height_m negatif: {wall_height_m}")
    if beam_depth_m < 0:
        raise ValueError(f"beam_depth_m negatif: {beam_depth_m}")
    if not 0.0 <= opening_ratio <= 1.0:
        raise ValueError(f"opening_ratio 0-1 arası olmalı: {opening_ratio}")

    net_height = max(0.0, wall_height_m - beam_depth_m)
    unit_area = duvar_alansal_yuk(layers)
    raw = unit_area * net_height
    effective = raw * (1.0 - opening_ratio)

    return {
        "unit_area_load_kn_m2":     round(unit_area, 4),
        "wall_height_m":            wall_height_m,
        "beam_depth_m":             beam_depth_m,
        "net_height_m":             round(net_height, 3),
        "opening_ratio":            opening_ratio,
        "opening_ratio_pct":        round(opening_ratio * 100, 1),
        "raw_line_load_kn_m":       round(raw, 4),
        "effective_line_load_kn_m": round(effective, 4),
        "warning": (
            "Kiriş duvarı tamamen kaplıyor (net = 0)"
            if net_height == 0.0 else None
        ),
    }


# ============================================================
# RAPOR
# ============================================================

def duvar_cizgi_yuk_raporu(
    layers: list[dict],
    wall_height_m: float,
    beam_depth_m: float = 0.0,
    opening_ratio: float = 0.0,
    title: str = "Kiriş Üstü Duvar Çizgi Yükü",
    desc: str = "",
) -> ReportDataFrame:
    """3 bölümlü duvar çizgi yükü raporu."""
    h = calculate_wall_line_load(
        layers, wall_height_m, beam_depth_m, opening_ratio
    )

    # --- KATMAN bölümü ---
    satirlar = []
    for i, layer in enumerate(layers, 1):
        try:
            yuk, aciklama, kalinlik = katman_yuku(layer)
            satirlar.append({
                "Bölüm": "KATMAN", "No": i,
                "Açıklama": layer.get("label") or aciklama,
                "Kalınlık": kalinlik if kalinlik is not None else "-",
                "Değer": round(yuk, 4),
                "Birim": "kN/m²",
            })
        except Exception as e:
            satirlar.append({
                "Bölüm": "KATMAN", "No": i,
                "Açıklama": f"HATA: {e}",
                "Kalınlık": "-", "Değer": 0.0, "Birim": "kN/m²",
            })
    satirlar.append({
        "Bölüm": "KATMAN", "No": "",
        "Açıklama": "Toplam Alansal Yük",
        "Kalınlık": "", "Değer": h["unit_area_load_kn_m2"],
        "Birim": "kN/m²",
    })

    # --- HESAP bölümü ---
    satirlar.extend([
        {"Bölüm": "HESAP", "No": "a", "Açıklama": "Duvar yüksekliği",
         "Kalınlık": "-", "Değer": h["wall_height_m"], "Birim": "m"},
        {"Bölüm": "HESAP", "No": "b", "Açıklama": "Kiriş yüksekliği (düşülen)",
         "Kalınlık": "-", "Değer": h["beam_depth_m"], "Birim": "m"},
        {"Bölüm": "HESAP", "No": "c", "Açıklama": "Net duvar yüksekliği (a-b)",
         "Kalınlık": "-", "Değer": h["net_height_m"], "Birim": "m"},
        {"Bölüm": "HESAP", "No": "d", "Açıklama": "Alansal yük",
         "Kalınlık": "-", "Değer": h["unit_area_load_kn_m2"], "Birim": "kN/m²"},
        {"Bölüm": "HESAP", "No": "e", "Açıklama": "Ham çizgi yük (c×d)",
         "Kalınlık": "-", "Değer": h["raw_line_load_kn_m"], "Birim": "kN/m"},
        {"Bölüm": "HESAP", "No": "f",
         "Açıklama": f"Boşluk düşülüyor (%{h['opening_ratio_pct']})",
         "Kalınlık": "-",
         "Değer": h["effective_line_load_kn_m"], "Birim": "kN/m"},
    ])

    # --- ÖZET ---
    satirlar.append({
        "Bölüm": "ÖZET", "No": "",
        "Açıklama": "NET ÇİZGİ YÜKÜ",
        "Kalınlık": "",
        "Değer": h["effective_line_load_kn_m"],
        "Birim": "kN/m",
    })

    aciklama = desc or (
        f"H={wall_height_m:.2f} m, h_kiriş={beam_depth_m:.2f} m, "
        f"boşluk=%{h['opening_ratio_pct']:.0f}"
    )

    return ReportDataFrame(
        satirlar,
        custom_title=title,
        custom_desc=aciklama,
        column_units={"Kalınlık": "m", "Değer": "karışık"},
        column_descriptions={
            "Bölüm": "KATMAN / HESAP / ÖZET",
            "No": "Sıra",
            "Açıklama": "Katman veya hesap adımı",
            "Kalınlık": "Kalınlık",
            "Değer": "Değer",
            "Birim": "Birim",
        },
        column_formats={"Kalınlık": ".3f", "Değer": ".4f"},
    )

# data/parse.py
"""
proje_data → toplu rapor tabloları.
Tüm yük motorlarını (döşeme, duvar, kar, rüzgar, deprem) birleştirir.
"""


# ============================================================
# ANA TOPLAYICI
# ============================================================

def parse_project_loads(proje_data: dict) -> dict[str, ReportDataFrame]:
    """
    proje_data'dan tüm rapor tablolarını üretir.
    
    Returns:
        {
            "dead_summary":         ReportDataFrame,
            "dead_detail_<key>":    ReportDataFrame,   # her ölü yük için
            "live_summary":         ReportDataFrame,
            "wall_summary":         ReportDataFrame,   # duvar özet
            "wall_<id>":            ReportDataFrame,   # her duvar için detay
        }
    """
    reports: dict[str, ReportDataFrame] = {}

    # ==========================================
    # 1. ÖLÜ YÜKLER (döşeme/kaplama)
    # ==========================================
    dead_summary_rows = []

    for item in proje_data.get("dead_loads", []):
        # --- item normalize ---
        if isinstance(item, str):
            if item not in DEAD_LOAD_PRESETS:
                dead_summary_rows.append({
                    "Yük": item,
                    "Açıklama": f"⚠️ Bilinmeyen preset: {item}",
                    "Toplam (kN/m²)": 0.0,
                    "kgf/m²": 0.0,
                })
                continue
            preset = DEAD_LOAD_PRESETS[item]
            key_name = item
            title_name = preset["name"]
            layers = preset["details"]
        elif isinstance(item, dict) and len(item) == 1:
            key_name, layers = next(iter(item.items()))
            title_name = f"Kullanıcı Tanımlı ({key_name})"
        else:
            continue

        # --- Detay raporu ---
        df = katman_raporu_df(
            layers,
            title=f"Yük Analizi: {title_name}",
            desc=f"Preset: {key_name}  |  {len(layers)} katman",
        )
        reports[f"dead_detail_{key_name}"] = df

        # --- Özet ---
        try:
            toplam = sum(katman_yuku(l)[0] for l in layers)
        except Exception:
            toplam = 0.0
        dead_summary_rows.append({
            "Yük": key_name,
            "Açıklama": title_name,
            "Toplam (kN/m²)": round(toplam, 3),
            "kgf/m²": round(toplam / 0.00980665, 1),
        })

    if dead_summary_rows:
        reports["dead_summary"] = ReportDataFrame(
            dead_summary_rows,
            custom_title="PROJE ÖLÜ YÜK ÖZETİ",
            custom_desc="Detay tablolarından otomatik hesaplanmıştır.",
            column_units={"Toplam (kN/m²)": "kN/m²", "kgf/m²": "kgf/m²"},
            column_formats={"Toplam (kN/m²)": ".3f", "kgf/m²": ".1f"},
        )

    # ==========================================
    # 2. HAREKETLİ YÜKLER
    # ==========================================
    live_rows = []
    for item in proje_data.get("live_loads", []):
        if isinstance(item, str) and item in LIVE_LOADS:
            ll = LIVE_LOADS[item]
            live_rows.append({
                "Anahtar": item,
                "Açıklama": ll["name"],
                "Kategori": ll.get("cat", "-"),
                "Q (kN/m²)": ll["value"],
            })

    if live_rows:
        reports["live_summary"] = ReportDataFrame(
            live_rows,
            custom_title="PROJE HAREKETLİ YÜK ÖZETİ",
            custom_desc="TS 498 / TS EN 1991-1-1.",
            column_units={"Q (kN/m²)": "kN/m²"},
            column_formats={"Q (kN/m²)": ".2f"},
        )

    # ==========================================
    # 3. DUVAR YÜKLERİ ← YENİ
    # ==========================================
    wall_summary_rows = []

    for duvar in proje_data.get("duvarlar", []):
        duvar_id = duvar.get("id", "?")
        preset_key = duvar.get("preset")

        # --- Preset kontrol ---
        if preset_key not in WALL_PRESETS:
            wall_summary_rows.append({
                "ID": duvar_id,
                "Preset": preset_key or "-",
                "Açıklama": f"⚠️ Bilinmeyen preset: {preset_key}",
                "Alan (kN/m²)": 0.0,
                "Net H (m)": 0.0,
                "Çizgi (kN/m)": 0.0,
            })
            continue

        preset = WALL_PRESETS[preset_key]

        # --- Detay raporu ---
        try:
            df = duvar_cizgi_yuk_raporu(
                layers=preset["details"],
                wall_height_m=duvar.get("wall_height_m", 3.0),
                beam_depth_m=duvar.get("beam_depth_m", 0.0),
                opening_ratio=duvar.get("opening_ratio", 0.0),
                title=f"Duvar {duvar_id} — {preset['name']}",
                desc=duvar.get("aciklama", ""),
            )
            reports[f"wall_{duvar_id}"] = df

            # --- Özet satırı ---
            h = calculate_wall_line_load_safe(
                preset["details"],
                duvar.get("wall_height_m", 3.0),
                duvar.get("beam_depth_m", 0.0),
                duvar.get("opening_ratio", 0.0),
            )
            wall_summary_rows.append({
                "ID": duvar_id,
                "Preset": preset_key,
                "Açıklama": duvar.get("aciklama", preset["name"]),
                "Alan (kN/m²)": h["unit_area_load_kn_m2"],
                "Net H (m)": h["net_height_m"],
                "Boşluk %": h["opening_ratio_pct"],
                "Çizgi (kN/m)": h["effective_line_load_kn_m"],
            })
        except Exception as e:
            wall_summary_rows.append({
                "ID": duvar_id,
                "Preset": preset_key,
                "Açıklama": f"HATA: {e}",
                "Alan (kN/m²)": 0.0, "Net H (m)": 0.0,
                "Boşluk %": 0.0, "Çizgi (kN/m)": 0.0,
            })

    if wall_summary_rows:
        reports["wall_summary"] = ReportDataFrame(
            wall_summary_rows,
            custom_title="PROJE DUVAR ÇİZGİ YÜK ÖZETİ",
            custom_desc="Kiriş üstü duvarlar — net çizgi yükleri (kN/m).",
            column_units={
                "Alan (kN/m²)": "kN/m²",
                "Net H (m)":    "m",
                "Boşluk %":     "%",
                "Çizgi (kN/m)": "kN/m",
            },
            column_formats={
                "Alan (kN/m²)": ".3f",
                "Net H (m)":    ".2f",
                "Boşluk %":     ".1f",
                "Çizgi (kN/m)": ".3f",
            },
        )
    return reports


# ============================================================
# YARDIMCI
# ============================================================

def calculate_wall_line_load_safe(layers, h, hk, op) -> dict:
    """Validasyon hatası olursa boş dict döner."""
    try:
        return calculate_wall_line_load(layers, h, hk, op)
    except Exception:
        return {
            "unit_area_load_kn_m2": 0.0,
            "net_height_m": 0.0,
            "opening_ratio_pct": 0.0,
            "effective_line_load_kn_m": 0.0,
        }

def _guze_etiket(k: str) -> str:
    """snake_case → 'Snake Case' (başlık için)."""
    return k.replace("_", " ").strip().capitalize()


# ============================================================
# 1. PROJE BİLGİLERİ
# ============================================================

def tablo_proje_bilgileri(pdata: dict) -> ReportDataFrame:
    info = pdata["proje_bilgileri"]
    return ReportDataFrame(
        {
            "Parametre": [
                "Proje Adı",
                "Ada / Parsel",
                "Mühendis",
                "Tarih",
                "Revizyon",
            ],
            "Değer": [
                info.get("proje_adi", " "),
                info.get("ada_parsel", "-"),
                info.get("muhendis", "-"),
                info.get("tarih", "-"),
                info.get("revizyon", "-"),
            ],
        },
        custom_title="1. Proje Bilgileri",
        custom_desc="Projenin kimlik ve künye bilgileri.",
    )


# ============================================================
# 2. YÖNETMELİKLER
# ============================================================

def tablo_yonetmelikler() -> ReportDataFrame:
    return ReportDataFrame(
        {
            "Yönetmelik ve Standart": [
                "AHŞAP BİNALARIN TASARIM, HESAP VE YAPIM ESASLARINA DAİR YÖNETMELİK (2025)",
                "Tasarım Örnekleri Kılavuzu",
                "TS EN 1995-1-1: Eurocode 5",
                "TS EN 1990",
                "TS EN 1991",
                "TBDY 2018",
                "TS EN 338",
                "TS 498",
            ],
            "Açıklama": [
                "Ana tasarım ve hesap esaslarını belirleyen yönetmelik.",
                "Yönetmelik eki tasarımcı kılavuzu.",
                "Yapı Tasarımı İçin Esaslar — Ahşap Yapılar.",
                "Eurocode — Yapıların Tasarımı için Esaslar.",
                "Eurocode 1 — Yapı Üzerindeki Etkiler (Kar, Rüzgar, Hareketli).",
                "Türkiye Bina Deprem Yönetmeliği.",
                "Yapısal Ahşap — Dayanım Sınıfları.",
                "Yapı Elemanlarının Boyutlandırılmasında Alınacak Yükler.",
            ],
        },
        custom_title="2. Yönetmelik ve Standartlar",
        custom_desc="Hesaplarda kullanılan ulusal ve uluslararası yönetmelikler.",
    )


# ============================================================
# 3. SAHA VE DEPREM
# ============================================================

def tablo_saha_ve_deprem(pdata: dict) -> ReportDataFrame:
    s = pdata["saha_ve_deprem"]
    # Anahtar → (görünen ad, birim)
    alanlar = [
        ("zemin_sinifi",                       "Zemin Sınıfı",                    "-"),
        ("ks_yatak_katsayisi_kN_m3",           "Yatak Katsayısı (ks)",            "kN/m³"),
        ("q_em_kpa",                           "İzin Verilen Taşıma Gücü (qem)",  "kPa"),
        ("S_DS",                               "Kısa Periyot Tasarım Spektrumu (SDS)", "g"),
        ("S_D1",                               "1 sn Tasarım Spektrumu (SD1)",    "g"),
        ("bina_kullanim_sinifi_BKS",           "Bina Kullanım Sınıfı (BKS)",      "-"),
        ("deprem_tasarim_sinifi_DTS",          "Deprem Tasarım Sınıfı (DTS)",     "-"),
        ("I_bina_onem_katsayisi",              "Bina Önem Katsayısı (I)",         "-"),
        ("R_davranim_katsayisi_X",             "Davranış Katsayısı (Rx)",         "-"),
        ("R_davranim_katsayisi_Y",             "Davranış Katsayısı (Ry)",         "-"),
        ("D_dayanim_fazlaligi_X",              "Dayanım Fazlalığı (Dx)",          "-"),
        ("D_dayanim_fazlaligi_Y",              "Dayanım Fazlalığı (Dy)",          "-"),
    ]

    rows = []
    for key, label, unit in alanlar:
        val = s.get(key, None)
        if val:
            rows.append({"Parametre": label, "Değer": val, "Birim": unit})

    return ReportDataFrame(
        rows,
        custom_title="3. Saha ve Deprem Parametreleri",
        custom_desc="TBDY 2018'e göre zemin, spektrum ve deprem parametreleri.",
    )


# ============================================================
# 4. MALZEME SINIFLARI
# ============================================================

def tablo_malzeme_siniflari(pdata: dict) -> ReportDataFrame:
    malz = pdata["malzemeler"]
    etiketler = {
        "beton":         "Beton",
        "donati":        "Donatı Çeliği",
        "yapisal_celik": "Yapısal Çelik",
        "ahsap":         "Ahşap",
        "panel":         "Panel",
    }
    rows = [
        {"Eleman Grubu": etiketler.get(k, _guze_etiket(k)), "Malzeme Sınıfı": v}
        for k, v in malz.items()
    ]
    return ReportDataFrame(
        rows,
        custom_title="4. Malzeme Sınıfları",
        custom_desc="Yapıda kullanılan malzeme sınıfları ve standartları.",
    )


# ============================================================
# 5. AHŞAP MALZEME MEKANİK ÖZELLİKLERİ
# ============================================================

def tablo_ahsap_mekanik(pdata: dict) -> ReportDataFrame:
    """woodMaterial(config) → param ve units sözlüklerini tabloya çevirir."""
    ahsap_sinifi = pdata["malzemeler"].get("ahsap", "C24")
    wood = woodMaterial(ahsap_sinifi)

    # wood.param ve wood.units — sizin data/mechanical.py'de
    # Eğer farklıysa uyarlarız (aşağıda not var)
    rows = []
    for k, v in wood.param.items():
        rows.append({
            "Parametre": k,
            "Değer": v,
            "Birim": wood.units.get(k, "-"),
        })

    return ReportDataFrame(
        rows,
        custom_title=f"5. Ahşap Malzeme Özellikleri — {ahsap_sinifi}",
        custom_desc="TS EN 338'e göre yapısal dayanım parametreleri.",
    )


# ============================================================
# HEPSİNİ TOPLA
# ============================================================

def create_meta_tables(pdata: dict) -> list:
    """
    Meta tablolar + tüm yük detayları (ölü, hareketli, duvar).
    """
    tables = []

    # --- 1-5: Meta tablolar ---
    tables.append(tablo_proje_bilgileri(pdata))
    tables.append(tablo_yonetmelikler())
    tables.append(tablo_saha_ve_deprem(pdata))
    tables.append(tablo_malzeme_siniflari(pdata))

    try:
        tables.append(tablo_ahsap_mekanik(pdata))
    except Exception as e:
        print(f"⚠️  Ahşap mekanik: {e}")

    # --- 6-8: Yük tabloları (özet + detay) ---
    reports = parse_project_loads(pdata)

    # Sıralı ekle: önce özetler, sonra detaylar
    sirali_anahtarlar = (
        "dead_summary",
        "live_summary",
        "wall_summary",
    )
    for key in sirali_anahtarlar:
        if key in reports:
            tables.append(reports[key])

    # Detaylar
    detay_anahtarlar = sorted(
        k for k in reports
        if k.startswith(("dead_detail_", "wall_"))
        and not k.endswith("_summary")
    )
    for key in detay_anahtarlar:
        tables.append(reports[key])

    return tables