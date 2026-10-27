# data/preset_loader.py
"""
Hazır Yük Kütüphanesi Yükleyici

- Düz yükler (G / Q): LoadDefinition'a çevrilir.
- Kiriş/duvar senaryoları: WallLoadEngine ile hesaplanır,
  sonuç bir LoadDefinition olarak döner (value = kN/m).
"""

import json
import os
from typing import Optional

from structload.loads.load_definition import LoadDefinition
from structload.loads.wall_load_engine import WallLoadEngine

KGF_TO_KN = 0.00980665


class PresetLibrary:
    def __init__(self, json_path: Optional[str] = None):
        if json_path is None:
            json_path = os.path.join(
                os.path.dirname(__file__),
                "load_maps.json"
            )
        self.json_path = json_path
        self.categories: dict = {}
        self.meta: dict = {}
        self._yukle()

    # ------------------------------------------------------------------
    def _yukle(self):
        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.meta = {
            "version": data.get("version", ""),
            "source": data.get("source", ""),
            "conversion": data.get("conversion", {}),
        }
        self.categories = data.get("categories", {})

    # ------------------------------------------------------------------
    @staticmethod
    def kgf_to_kn(kgf: float, rounding: int = 2) -> float:
        return round(kgf * KGF_TO_KN, rounding)

    # ------------------------------------------------------------------
    def kategori_listesi(self) -> list[tuple[str, str, str]]:
        return [
            (kid, cat.get("label", kid), cat.get("load_type", "G"))
            for kid, cat in self.categories.items()
        ]

    # ------------------------------------------------------------------
    def kategori_yukleri(self, kategori_id: str) -> list[dict]:
        cat = self.categories.get(kategori_id)
        if cat is None:
            return []

        if kategori_id == "hazir_kiris_senaryolari":
            return self._kiriş_senaryolari(kategori_id)

        rounding = self.meta.get("conversion", {}).get("rounding", 2)
        sonuc = []
        for item in cat.get("items", []):
            kgf = float(item["kgf"])
            sonuc.append({
                "name": item["name"],
                "kgf": kgf,
                "kn": self.kgf_to_kn(kgf, rounding),
            })
        return sonuc

    # ------------------------------------------------------------------
    def _kiriş_senaryolari(self, kategori_id: str) -> list[dict]:
        """
        Kiriş senaryolarını WallLoadEngine ile hesaplar ve
        her biri için name + line_load (kN/m) döner.
        """
        

        cat = self.categories[kategori_id]
        sonuc = []
        for item in cat.get("items", []):
            engine = WallLoadEngine(
                wall_name=item["name"],
                wall_height_m=item.get("wall_height_m", 2.80),
                beam_depth_m=item.get("beam_depth_m", 0.40),
            )
            for layer in item.get("layers", []):
                engine.add_layer(
                    mat_key=layer["mat"],
                    thickness_m=layer.get("thickness_m", 0.0),
                    custom_label=layer.get("label"),
                )
            sonuc.append({
                "name": item["name"],
                "kgf": None,                     # kgf cinsinden yok
                "kn": round(engine.line_load_kn_m(), 3),  # kN/m
                "unit": "kN/m",
                "wall_height_m": engine.wall_height,
                "beam_depth_m": engine.beam_depth,
                "net_height_m": engine.net_height,
                "area_load_kn_m2": round(engine.total_area_load(), 3),
                "layers": engine.layers,
                "_engine": engine,   # rapor için
            })
        return sonuc

    # ------------------------------------------------------------------
    def load_definition_olustur(
        self,
        kategori_id: str,
        item_index: int,
        load_id: str,
        load_type: Optional[str] = None,
        source_ek: str = "Hazır Kütüphane",
    ) -> LoadDefinition:
        cat = self.categories.get(kategori_id)
        if cat is None:
            raise KeyError(f"Kategori bulunamadı: {kategori_id}")

        items = self.kategori_yukleri(kategori_id)
        if not (0 <= item_index < len(items)):
            raise IndexError(f"Item index geçersiz: {item_index}")

        item = items[item_index]
        if load_type is None:
            load_type = cat.get("load_type", "G")

        # ---- KİRİŞ SENARYOSU ----
        if kategori_id == "hazir_kiris_senaryolari":
            return LoadDefinition(
                id=load_id,
                name=item["name"],
                load_type="G",
                value=item["kn"],       # kN/m
                unit="kN/m",
                source=f"{source_ek} | Kiriş Senaryosu",
                description=(
                    f"Kat: {item['wall_height_m']} m, "
                    f"Kiriş: {item['beam_depth_m']} m, "
                    f"Net: {item['net_height_m']:.2f} m, "
                    f"Yüzey: {item['area_load_kn_m2']} kN/m² → "
                    f"Çizgisel: {item['kn']} kN/m"
                ),
            )

        # ---- DÜZ YÜK ----
        return LoadDefinition(
            id=load_id,
            name=item["name"],
            load_type=load_type,
            value=item["kn"],
            unit="kN/m²",
            source=f"{source_ek} | TS 498 | {item['kgf']} kgf/m²",
            description=f"kgf/m²: {item['kgf']} → kN/m²: {item['kn']}",
        )