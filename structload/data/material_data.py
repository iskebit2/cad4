# data/material_data.py
"""
Yük ve Malzeme Veritabanı (TS 498 / TS EN 1991-1-1 Uyumlu)

Birim Standartları:
- Volumetric : kN/m³ (Kalınlık 'm' ile çarpılarak alansal yüke çevrilir)
- Area       : kN/m² (Doğrudan alansal yük olarak eklenir)
- Live Loads : kN/m² (Doğrudan yönetmelik standart değerleri)
"""
# ============================================================================
# 1. ÖLÜ YÜKLER (TS 498 / TS EN 1991-1-1) - NET YÖNETMELİK DEĞERLERİ
# ============================================================================

# data/material_data.py

DEAD_LOAD_PRESETS = {
    "mese_parke": {
        "name": "Sert Ahşap Meşe Parke Kaplama Döşeme Yükü",
        "details": [
            {"label": "18 mm Meşe Parke",     "mat": "ahşap_meşe",     "thickness_m": 0.018},
            {"label": "Parke Altı Şilte",     "custom_weight": 0.01,   "unit": "area"},
            {"label": "4 cm Tesviye Şapı",    "mat": "şap",            "thickness_m": 0.04},
            {"label": "1.5 cm Tavan Sıvası",  "mat": "sıva_alçı",      "thickness_m": 0.015},
        ],
    },
    "marley": {
        "name": "Marley Kaplama Döşeme Yükü",
        "details": [
            {"label": "2 cm Çimento Harcı",   "mat": "çimento_harcı",  "thickness_m": 0.02},
            {"label": "3 cm Tesviye Şapı",    "mat": "şap",            "thickness_m": 0.03},
            {"label": "1.5 cm Tavan Sıvası",  "mat": "sıva_alçı",      "thickness_m": 0.015},
            {"label": "Marley Kaplama",       "custom_weight": 0.05,   "unit": "area"},
        ],
    },
    "fayans": {
        "name": "Fayans / Seramik Kaplama Döşeme Yükü",
        "details": [
            {"label": "1 cm Seramik",         "mat": "seramik_kaplama", "custom_weight": 0.25, "unit": "area"},
            {"label": "2.5 cm Yapıştırma Harcı", "mat": "çimento_harcı", "thickness_m": 0.025},
            {"label": "4 cm Tesviye Şapı",    "mat": "şap",            "thickness_m": 0.04},
            {"label": "1.5 cm Tavan Sıvası",  "mat": "sıva_alçı",      "thickness_m": 0.015},
        ],
    },
    "merdiven": {
        "name": "Merdiven Kaplama ve Basamak Yükü",
        "details": [
            {"label": "3 cm Mermer",          "mat": "mermer",         "thickness_m": 0.03},
            {"label": "3 cm Harç",            "mat": "çimento_harcı",  "thickness_m": 0.03},
            {"label": "2 cm Alt Sıva",        "mat": "sıva_alçı",      "thickness_m": 0.02},
        ],
    },
}

# ============================================================================
# 2. HAREKETLİ YÜKLER (TS 498 / TS EN 1991-1-1) - NET YÖNETMELİK DEĞERLERİ
# ============================================================================

LIVE_LOADS = {
    "kullanici_tanimli": {
        "name": "Kullanıcı Tanımlı",
        "value": 2.0,
        "cat": "A",
        "desc": "Özel yük tanımı"
    },
    "konut": {
        "name": "Konut, teras, oda ve koridorlar",
        "value": 2.0,
        "cat": "A",
        "desc": "Ev, otel odaları, hastane koğuşları"
    },
    "konut_dukkan": {
        "name": "Konutlarda 50 m²'ye kadar dükkanlar / hastane odaları",
        "value": 2.0,
        "cat": "A",
        "desc": "Küçük ölçekli ticari veya sağlık alanları"
    },
    "ofis": {
        "name": "Büro ve genel çalışma alanları",
        "value": 3.5,
        "cat": "B",
        "desc": "Ofisler, bürolar, doktor muayenehaneleri"
    },
    "hastane_servis": {
        "name": "Hastane mutfakları, ameliyathane ve poliklinikler",
        "value": 3.5,
        "cat": "B",
        "desc": "Yoğun donanımlı sağlık birimleri"
    },
    "sinif": {
        "name": "Sınıflar, amfiler, yatakhaneler ve okul koridorları",
        "value": 3.5,
        "cat": "C1",
        "desc": "Eğitim yapıları"
    },
    "konut_merdiveni": {
        "name": "Konut merdivenleri ve sahanlıklar",
        "value": 3.5,
        "cat": "A",
        "desc": "Bina içi düşey sirkülasyon"
    },
    "toplanti_sabit": {
        "name": "Tiyatrolar, sinemalar, sabit koltuklu salonlar",
        "value": 5.0,
        "cat": "C2",
        "desc": "Sabit oturma düzenli toplanma alanları"
    },
    "toplanti_serbest": {
        "name": "Camiler, lokantalar, bekleme ve dans salonları",
        "value": 5.0,
        "cat": "C3",
        "desc": "Serbest hareketli toplanma alanları"
    },
    "magaza": {
        "name": "Mağazalar, teşhir salonları ve fırınlar",
        "value": 5.0,
        "cat": "D1",
        "desc": "Perakende alışveriş alanları"
    },
    "spor_sergi": {
        "name": "Spor, dans, sergi salonları ve pazar yerleri",
        "value": 5.0,
        "cat": "C5",
        "desc": "Fiziksel aktivite ve kalabalık alanları"
    },
    "kutuphane_arsiv": {
        "name": "Kütüphaneler, arşivler ve evrak depoları",
        "value": 5.0,
        "cat": "E",
        "desc": "Ağır istifleme yapılan alanlar"
    },
    "buyuk_mutfak": {
        "name": "Büyük mutfaklar, kantinler ve mezbahalar",
        "value": 5.0,
        "cat": "C3",
        "desc": "Endüstriyel servis alanları"
    },
    "merdiven_umumi": {
        "name": "Umumi yapılarda merdivenler ve girişler",
        "value": 5.0,
        "cat": "C3",
        "desc": "Yoğun yaya trafiği olan merdivenler"
    },
    "balkon": {
        "name": "Balkonlar (10 m²'ye kadar)",
        "value": 5.0,
        "cat": "A",
        "desc": "Konsol ve açık alanlar"
    },
    "tribun_hareketli": {
        "name": "Tribünler (oturma yeri sabit olmayan)",
        "value": 7.5,
        "cat": "C4",
        "desc": "Dinamik kalabalık yükleri"
    },
    "garaj_hafif": {
        "name": "Garajlar (toplam ağırlığı <= 2.5 ton araçlar)",
        "value": 5.0,
        "cat": "F",
        "desc": "Binek araç otoparkları"
    },
}


# ============================================================================
# 3. MALZEME KÜTÜPHANESİ (Hacimsel: kN/m³ | Alansal: kN/m²)
# ============================================================================

MATERIAL_LIBRARY = {
    # --- AHŞAP MALZEMELER (kN/m³) ---
    "ahşap_çam":        {"weight": 5.0,  "unit": "volumetric", "name": "Çam Ahşap"},
    "ahşap_meşe":       {"weight": 7.0,  "unit": "volumetric", "name": "Meşe Ahşap"},
    "ahşap_kayın":      {"weight": 7.0,  "unit": "volumetric", "name": "Kayın Ahşap"},
    "ahşap_ladin":      {"weight": 4.5,  "unit": "volumetric", "name": "Ladin Ahşap"},
    "ahşap_osb":        {"weight": 6.5,  "unit": "volumetric", "name": "OSB Levha"},
    "ahşap_clt":        {"weight": 5.0,  "unit": "volumetric", "name": "CLT Panel"},
    "ahşap_kontrplak":  {"weight": 6.0,  "unit": "volumetric", "name": "Kontrplak"},
    "ahşap_glulam":     {"weight": 5.0,  "unit": "volumetric", "name": "Glulam"},
    "ahşap_mdf":        {"weight": 7.5,  "unit": "volumetric", "name": "MDF Levha"},
    "ahşap_sunta":      {"weight": 7.0,  "unit": "volumetric", "name": "Sunta"},

    # --- BETON & DUVAR & HARÇLAR (kN/m³) ---
    "betonarme":        {"weight": 25.0, "unit": "volumetric", "name": "Betonarme"},
    "beton_hafif":      {"weight": 18.0, "unit": "volumetric", "name": "Hafif Beton"},
    "gazbeton":         {"weight": 6.0,  "unit": "volumetric", "name": "Gazbeton / Ytong"},
    "bims":             {"weight": 10.0, "unit": "volumetric", "name": "Bims Blok"},
    "tuğla_dolu":       {"weight": 18.0, "unit": "volumetric", "name": "Dolu Harman Tuğlası"},
    "tuğla_delikli":    {"weight": 12.0, "unit": "volumetric", "name": "Düşey Delikli Tuğla"},
    "kireçtaşı":        {"weight": 23.0, "unit": "volumetric", "name": "Kireçtaşı / Kalker"},
    "bazalt":           {"weight": 29.0, "unit": "volumetric", "name": "Bazalt"},
    "granit":           {"weight": 28.0, "unit": "volumetric", "name": "Granit"},
    "mermer":           {"weight": 27.0, "unit": "volumetric", "name": "Mermer"},
    "traverten":        {"weight": 24.0, "unit": "volumetric", "name": "Traverten"},
    "çimento_harcı":    {"weight": 22.0, "unit": "volumetric", "name": "Çimento Harcı / Seramik Yapıştırıcı"},
    "şap":              {"weight": 22.0, "unit": "volumetric", "name": "Çimento Esaslı Şap"},
    "şap_anhidrit":     {"weight": 20.0, "unit": "volumetric", "name": "Anhidrit Şap"},
    "sıva_kireç":       {"weight": 18.0, "unit": "volumetric", "name": "Kireç Harçlı Sıva"},
    "sıva_çimento":     {"weight": 21.0, "unit": "volumetric", "name": "Çimento Harçlı Sıva"},
    "sıva_alçı":        {"weight": 12.0, "unit": "volumetric", "name": "Alçı Sıva"},
    "dolgu_kum":        {"weight": 17.0, "unit": "volumetric", "name": "Kum Dolgu"},
    "dolgu_toprak":     {"weight": 18.0, "unit": "volumetric", "name": "Bitkisel Toprak Dolgu"},

    # --- ISITMA & YALITIM MALZEMELERİ (Düzeltildi: Hacimsel Yoğunluk kN/m³) ---
    "izolasyon_xps":    {"weight": 0.4,  "unit": "volumetric", "name": "XPS Isı Yalıtımı"},
    "izolasyon_eps":    {"weight": 0.3,  "unit": "volumetric", "name": "EPS Isı Yalıtımı"},
    "izolasyon_taş":    {"weight": 1.2,  "unit": "volumetric", "name": "Taş Yünü Yalıtım"},

    # --- KAPLAMA & BİTİŞ YÜZEYLERİ (Alansal: kN/m²) ---
    "seramik_kaplama":   {"weight": 0.25, "unit": "area", "name": "Seramik / Karo Kaplama (Harçlı)"},
    "parke_laminat":     {"weight": 0.10, "unit": "area", "name": "Laminat Parke + Şilte"},
    "parke_masif":       {"weight": 0.20, "unit": "area", "name": "Masif Ahşap Parke"},
    "halı":              {"weight": 0.05, "unit": "area", "name": "Halı / Linolyum"},
    "yükseltilmiş_panel": {"weight": 0.25, "unit": "area", "name": "Yükseltilmiş Döşeme Paneli"},
    "çatı_kiremidi":     {"weight": 0.45, "unit": "area", "name": "Kiremit Çatı Kaplaması"},
    "çatı_sac":          {"weight": 0.12, "unit": "area", "name": "Trapez Sac Kaplama"},
    "çatı_güneş_paneli": {"weight": 0.20, "unit": "area", "name": "Güneş Paneli Sistemi"},
    "asma_tavan_alçıpan":{"weight": 0.15, "unit": "area", "name": "Alçıpan Asma Tavan"},
    "asma_tavan_metal":  {"weight": 0.10, "unit": "area", "name": "Metal / Modüler Asma Tavan"},
    "bölme_alçıpan":     {"weight": 0.30, "unit": "area", "name": "Alçıpan Bölme Duvar"},
    "su_yalıtımı_membran":{"weight": 0.08, "unit": "area", "name": "Bitümlü Su Yalıtım Membranı"},
    "cephe_taş_mekanik": {"weight": 0.80, "unit": "area", "name": "Mekanik Askılı Taş Cephe"},
    "cephe_kompozit":    {"weight": 0.15, "unit": "area", "name": "Alüminyum Kompozit Cephe"},
    "cephe_cam":         {"weight": 0.45, "unit": "area", "name": "Giydirme Cam Cephe"},
}

# ============================================================================
# 4. DUVAR YÜKLERİ
# ============================================================================

WALL_PRESETS = {
    # --- İç duvarlar ---
    "ic_duvar_alcipan": {
        "name": "Alçıpan İç Duvar (75 mm)",
        "details": [
            {"label": "Alçıpan (çift yüz)", "custom_weight": 0.30, "unit": "area"},
            {"label": "Metal Profil",       "custom_weight": 0.05, "unit": "area"},
            {"label": "Taş Yünü Dolgu",     "mat": "izolasyon_taş", "thickness_m": 0.075},
        ],
    },
    "ic_duvar_tugla": {
        "name": "Delikli Tuğla İç Duvar (13.5 cm)",
        "details": [
            {"label": "Delikli Tuğla", "mat": "tuğla_delikli", "thickness_m": 0.135},
            {"label": "İki Yüz Sıva",  "mat": "sıva_alçı",      "thickness_m": 0.03},
        ],
    },

    # --- Dış duvarlar ---
    "dis_duvar_yarim_tugla": {
        "name": "Yarım Tuğla Dış Duvar + Yalıtım",
        "details": [
            {"label": "Tuğla Duvar",     "mat": "tuğla_delikli",  "thickness_m": 0.135},
            {"label": "Taş Yünü Yalıtım", "mat": "izolasyon_taş",  "thickness_m": 0.08},
            {"label": "İç Sıva",         "mat": "sıva_çimento",   "thickness_m": 0.02},
            {"label": "Dış Sıva",        "mat": "sıva_çimento",   "thickness_m": 0.015},
        ],
    },
    "dis_duvar_beton": {
        "name": "Betonarme Dış Duvar (20 cm)",
        "details": [
            {"label": "Betonarme",       "mat": "betonarme",      "thickness_m": 0.20},
            {"label": "İç Sıva",         "mat": "sıva_çimento",   "thickness_m": 0.02},
            {"label": "Dış Sıva",        "mat": "sıva_çimento",   "thickness_m": 0.015},
        ],
    },
    "dis_duvar_gazbeton": {
        "name": "Gazbeton Dış Duvar (25 cm)",
        "details": [
            {"label": "Gazbeton Blok",   "mat": "gazbeton",       "thickness_m": 0.25},
            {"label": "İç Sıva",         "mat": "sıva_alçı",      "thickness_m": 0.02},
            {"label": "Dış Sıva",        "mat": "sıva_çimento",   "thickness_m": 0.015},
        ],
    },
}

# ============================================================================
# 5. GERİYE UYUMLULUK VE YARDIMCI METOTLAR
# ============================================================================

MATERIAL_WEIGHTS = {key: mat["weight"] for key, mat in MATERIAL_LIBRARY.items()}

def get_material_info(key: str) -> dict:
    if key not in MATERIAL_LIBRARY:
        raise KeyError(f"Tanımsız malzeme anahtarı: '{key}'")
    return MATERIAL_LIBRARY[key]

def get_live_load_info(key: str) -> dict:
    if key not in LIVE_LOADS:
        raise KeyError(f"Tanımsız hareketli yük anahtarı: '{key}'")
    item = LIVE_LOADS[key]
    return {'name': key, 'value':round(item["value"], 2), 'cat': item["cat"],'desc':item["name"]}
    
