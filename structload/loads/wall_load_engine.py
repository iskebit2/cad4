# loads/wall_load_engine.py
"""
Duvar / Kiriş Çizgisel Yük Hesap Motoru

Bir duvarın katmanlarını (sıva, beden, kaplama, yalıtım, cephe) toplayıp
kirişe etkiyen çizgisel yükü (kN/m) hesaplar.

MATERIAL_LIBRARY birimlerini dikkate alır:
- 'volumetric' → kalınlıkla çarpılır
- 'area'       → doğrudan eklenir
"""

from structload.data.material_data import MATERIAL_LIBRARY


class WallLoadEngine:
    def __init__(
        self,
        wall_name: str,
        wall_height_m: float = 2.80,
        beam_depth_m: float = 0.50,
    ):
        self.wall_name = wall_name
        self.wall_height = wall_height_m
        self.beam_depth = beam_depth_m
        self.net_height = max(0.0, wall_height_m - beam_depth_m)
        self.layers = []

    def add_layer(
        self,
        mat_key: str,
        thickness_m: float = 0.0,
        custom_label: str = None,
    ):
        if mat_key not in MATERIAL_LIBRARY:
            raise KeyError(f"❌ '{mat_key}' malzemesi kütüphanede bulunamadı!")

        mat = MATERIAL_LIBRARY[mat_key]
        label = custom_label or mat["name"]

        if mat["unit"] == "volumetric":
            if thickness_m <= 0:
                raise ValueError(
                    f"❌ [{label}] hacimsel bir malzeme (kN/m³). "
                    f"Kalınlık (m) 0'dan büyük girmelisiniz!"
                )
            area_load = thickness_m * mat["weight"]
            unit_fmt = f"{mat['weight']:.1f} kN/m³"
            thick_fmt = f"{thickness_m * 100:.1f} cm"

        elif mat["unit"] == "area":
            area_load = mat["weight"]
            unit_fmt = f"{mat['weight']:.2f} kN/m²"
            thick_fmt = "-"

        else:
            raise ValueError(f"Bilinmeyen birim: {mat['unit']}")

        self.layers.append({
            "label": label,
            "unit_fmt": unit_fmt,
            "thickness": thick_fmt,
            "area_load": area_load,
        })
        return self

    def total_area_load(self) -> float:
        return sum(l["area_load"] for l in self.layers)

    def line_load_kn_m(self) -> float:
        return self.total_area_load() * self.net_height

    def print_report(self):
        total_kn_m2 = self.total_area_load()
        line_load_kn_m = self.line_load_kn_m()
        line_load_t_m = line_load_kn_m / 9.81

        print("=" * 70)
        print(f" DUVAR HESAP RAPORU: {self.wall_name}")
        print("=" * 70)
        print(f" Kat Yüksekliği   : {self.wall_height:.2f} m")
        print(f" Kiriş Yüksekliği : {self.beam_depth:.2f} m")
        print(f" Net Duvar Yük.   : {self.net_height:.2f} m")
        print("-" * 70)
        print(f"{'Katman Adı':<30} | {'Kalınlık':<10} | {'Birim Yük':<12} | {'Yüzey Yükü'}")
        print("-" * 70)

        for l in self.layers:
            print(
                f"{l['label']:<30} | {l['thickness']:<10} | "
                f"{l['unit_fmt']:<12} | {l['area_load']:.3f} kN/m²"
            )

        print("-" * 70)
        print(f" TOPLAM YÜZEY YÜKÜ (g_duvar) : {total_kn_m2:.3f} kN/m²")
        print(f" KİRİŞ ÇİZGİSEL YÜKÜ (q_kiriş): {line_load_kn_m:.3f} kN/m  ({line_load_t_m:.3f} t/m)")
        print("=" * 70 + "\n")