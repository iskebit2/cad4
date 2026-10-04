# tools/s2k/units.py
"""SAP2000 birim dönüştürücü."""


class UnitConverter:
    """SAP2000 birim sistemi → yerel (N, mm, °C)."""
    
    LENGTH_FACTORS = {'MM': 1.0, 'CM': 10.0, 'M': 1000.0, 'IN': 25.4, 'FT': 304.8}
    FORCE_FACTORS = {
        'N': 1.0, 'KN': 1000.0, 'KG': 9.80665, 'KGF': 9.80665,
        'TON': 9806.65, 'KIP': 4448.22, 'LB': 4.44822,
    }
    
    def __init__(self, currunits_str: str = "N, mm, C"):
        self.length_scale = 1.0
        self.force_scale = 1.0
        self.temp_unit = "C"
        self.raw_string = currunits_str
        self.parse_units(currunits_str)
    
    def parse_units(self, currunits_str: str):
        self.raw_string = currunits_str.strip()
        parts = [p.strip().upper() for p in currunits_str.split(',')]
        if len(parts) >= 2:
            self.force_scale = self.FORCE_FACTORS.get(parts[0], 1.0)
            self.length_scale = self.LENGTH_FACTORS.get(parts[1], 1.0)
        if len(parts) >= 3:
            self.temp_unit = parts[2]
    
    # Dönüşüm metodları
    def L(self, v): return v * self.length_scale
    def F(self, v): return v * self.force_scale
    def M(self, v): return v * self.force_scale * self.length_scale
    def E(self, v): return v * self.force_scale / (self.length_scale ** 2)
    def w(self, v): return v * self.force_scale / self.length_scale
    def area_w(self, v): return v * self.force_scale / (self.length_scale ** 2)
    def acc(self, v): return v * self.length_scale
    
    def temp(self, v):
        """Sıcaklık farkı °C cinsine."""
        if self.temp_unit == "F":
            return v * (5.0 / 9.0)
        return v
    
    def temp_grad(self, v):
        """Sıcaklık gradyanı °C/mm."""
        return self.temp(v) / self.length_scale

    def __str__(self) -> str:
        """İnsan-okunabilir birim string'i."""
        return self.raw_string