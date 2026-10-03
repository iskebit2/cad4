#snow_load.py

"""
Kar Yükü Motoru - TS EN 1991-1-3
"""

from typing import Dict, Any
from structload.utils.report_dataframe import ReportDataFrame
from structload.data.snow_data import SNOW_LOAD_TABLE, ALTITUDE_FACTORS, SNOW_REGIONS
from structload.utils.math_utils import interpolate_2d, calculate_snow_shape_coefficient, round_values


class SnowLoad:
    """
    Kar Yükü Hesaplama Sınıfı
    TS EN 1991-1-3 ve Türkiye Ulusal Eki
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: {
                "slope": 23.41,      # Çatı eğimi (derece)
                "snow_region": 2,    # Kar bölgesi (1-9)
                "altitude": 50,      # Rakım (m)
                "Ce": 1.0,           # Maruziyet katsayısı
                "Ct": 1.0            # Isıl katsayı
            }
        """
        self.config = config
        self.slope = config.get("slope", 0)
        self.region = config.get("snow_region", 2)
        self.altitude = config.get("altitude", 0)
        self.Ce = config.get("Ce", 1.0)
        self.Ct = config.get("Ct", 1.0)
        
        # Hesaplamalar
        self._calculate()
    
    def _calculate(self):
        """Tüm kar yükü hesaplamalarını yapar"""
        # 1. Temel kar yükü (sₖ)
        self.sk = self._calculate_sk()
        
        # 2. Şekil katsayısı (μ)
        self.mu = calculate_snow_shape_coefficient(self.slope)
        
        # 3. Nihai kar yükü (s)
        self.s = self.mu * self.Ce * self.Ct * self.sk
    
    def _calculate_sk(self) -> float:
        """Karakteristik kar yükünü hesaplar"""
        # Bölge kontrolü
        if not 1 <= self.region <= 9:
            raise ValueError(f"Geçersiz bölge: {self.region}. Bölge 1-9 arasında olmalı.")
        
        # 1000m üzeri kontrolü
        if self.altitude > 1000:
            sk_1000 = self._interpolate_sk(1000)
            if self.altitude <= 1500:
                return sk_1000 * 1.10
            else:
                return sk_1000 * 1.15
        
        # Interpolasyon
        return self._interpolate_sk(self.altitude)
    
    def _interpolate_sk(self, altitude: float) -> float:
        """Rakıma göre interpolasyon"""
        altitudes = [row[0] for row in SNOW_LOAD_TABLE]
        sk_values = [row[self.region] for row in SNOW_LOAD_TABLE]
        return interpolate_2d(altitude, altitudes, sk_values)
    
    def report(self) -> ReportDataFrame:
        """Kar yükü raporu"""
        data = {
            "Parametre": [
                "Kar Bölgesi",
                "Rakım",
                "Çatı Eğimi (α)",
                "Maruziyet Katsayısı (Cₑ)",
                "Isıl Katsayı (Cₜ)",
                "Şekil Katsayısı (μ)",
                "Temel Kar Yükü (sₖ)",
                "Kar Yükü (s)"
            ],
            "Değer": [
                f"Bölge {self.region}",
                f"{self.altitude} m",
                f"{self.slope}°",
                f"{self.Ce:.2f}",
                f"{self.Ct:.2f}",
                f"{self.mu:.3f}",
                f"{self.sk:.3f} kN/m²",
                f"{self.s:.3f} kN/m²"
            ]
        }
        
        desc = f"""
        Standart: TS EN 1991-1-3 ve Türkiye Ulusal Eki
        
        Çatı Şekil Katsayısı (μ):
        • 0° ≤ α ≤ 30°: μ = 0.8
        • 30° < α < 60°: μ = 0.8 × (60 - α) / 30
        • α ≥ 60°: μ = 0
        
        Kar Yükü Formülü: s = μ × Cₑ × Cₜ × sₖ
        """
        
        return ReportDataFrame(
            data,
            custom_title="Kar Yükü Analizi",
            custom_desc=desc
        )
    
    def get_load_patterns(self) -> Dict[str, float]:
        """SAP2000 yük kalıbı"""
        return {"SNOW": self.s}


if __name__ == "__main__":
    config = {
        "slope": 23.41,
        "snow_region": 2,
        "altitude": 50,
        "Ce": 1.0,
        "Ct": 1.0
    }
    snow = SnowLoad(config)
    print(snow.report())