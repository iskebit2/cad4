import math

# Ahşap kereste verileri
ahsap_data = {
    "C14": [14, 7.2, 0.4, 16, 2, 3, 7, 4.7, 0.23, 0.44, 290, 350],
    "C16": [16, 8.5, 0.4, 17, 2.2, 3.2, 8, 5.4, 0.27, 0.5, 310, 370],
    "C18": [18, 10, 0.4, 18, 2.2, 3.4, 9, 6, 0.3, 0.56, 320, 380],
    "C20": [20, 11.5, 0.4, 19, 2.3, 3.6, 9.5, 6.4, 0.32, 0.59, 330, 400],
    "C22": [22, 13, 0.4, 20, 2.4, 3.8, 10, 6.7, 0.33, 0.63, 340, 410],
    "C24": [24, 14.5, 0.4, 21, 2.5, 4, 11, 7.4, 0.37, 0.69, 350, 420],
    "C27": [27, 16.5, 0.4, 22, 2.5, 4, 11.5, 7.7, 0.38, 0.72, 360, 430],
    "C30": [30, 19, 0.4, 24, 2.7, 4, 12, 8, 0.4, 0.75, 380, 460],
    "C35": [35, 22.5, 0.4, 25, 2.7, 4, 13, 8.7, 0.43, 0.81, 390, 470],
    "C40": [40, 26, 0.4, 27, 2.8, 4, 14, 9.4, 0.47, 0.88, 400, 480],
    "C45": [45, 30, 0.4, 29, 2.9, 4, 15, 10.1, 0.5, 0.94, 410, 490],
    "C50": [50, 33.5, 0.4, 30, 3, 4, 16, 10.7, 0.53, 1, 430, 520]
}

# OSB verileri: Kalınlığa ve yöne göre gruplandırıldı
osb_data = {
    "OSB/3": {
        "10-18mm": {
            "major": [16.4, 9.4, 6.8, 15.4, 10.0, 6.8, 4930, 0.85*4930, 1980, 50, 620, 620],
            "minor": [8.2, 7.0, 6.8, 12.7, 10.0, 6.8, 1980, 0.85*1980, 4930, 50, 620, 620]
        },
        "6-10mm": {
            "major": [18.0, 9.9, 6.8, 15.9, 10.0, 6.8, 4930, 0.85*4930, 1980, 50, 640, 640],
            "minor": [9.0, 7.2, 6.8, 12.9, 10.0, 6.8, 1980, 0.85*1980, 4930, 50, 640, 640]
        }
    }
}

# Beton verileri (TS 500 / EN 1992-1-1)
# Sırasıyla: fck, fck,cube, fctk_0.05, fctm, Ecm, nu, rho
concrete_data = {
    "C20/25": [20, 25, 1.5, 2.2, 30000, 0.2, 2500],
    "C25/30": [25, 30, 1.8, 2.6, 31000, 0.2, 2500],
    "C30/37": [30, 37, 2.0, 2.9, 33000, 0.2, 2500],
    "C35/45": [35, 45, 2.2, 3.2, 34000, 0.2, 2500],
    "C40/50": [40, 50, 2.5, 3.5, 35000, 0.2, 2500],
    "C45/55": [45, 55, 2.7, 3.8, 36000, 0.2, 2500],
    "C50/60": [50, 60, 2.9, 4.1, 37000, 0.2, 2500]
}

# Yapısal Çelik verileri (TS EN 10025-2, t <= 16mm için nominal değerler)
# Sırasıyla: fy, fu, E, G, nu, rho
steel_data = {
    "S235": [235, 360, 210000, 80769, 0.3, 7850],
    "S275": [275, 430, 210000, 80769, 0.3, 7850],
    "S355": [355, 510, 210000, 80769, 0.3, 7850],
    "S450": [450, 550, 210000, 80769, 0.3, 7850]
}

AHSAPUNITS= {
    'fm,k': 'N/mm²', 'ft,0,k': 'N/mm²', 'ft,90,k': 'N/mm²',
    'fc,0,k': 'N/mm²', 'fc,90,k': 'N/mm²', 'fv,k': 'N/mm²',
    'Em,o,ort': 'kN/mm²', 'E0.05': 'kN/mm²', 'Em,90,ort': 'kN/mm²',
    'Gor': 'kN/mm²', 'ρ': 'kg/m³', 'ρort': 'kg/m³'
}

OSBUNITS= {
    'fm,k': 'N/mm²', 'ft,0,k': 'N/mm²', 'ft,90,k': 'N/mm²',
    'fc,0,k': 'N/mm²', 'fc,90,k': 'N/mm²', 'fv,k': 'N/mm²',
    'Em,o,ort': 'N/mm²', 'E0.05': 'N/mm²', 'Em,90,ort': 'N/mm²',
    'Gor': 'N/mm²', 'ρ': 'kg/m³', 'ρort': 'kg/m³'
}

CONCRETEUNITS = {
    'fck': 'N/mm²', 'fck,cube': 'N/mm²', 'fctk,0.05': 'N/mm²',
    'fctm': 'N/mm²', 'Ecm': 'N/mm²', 'ν': '-', 'ρ': 'kg/m³'
}

STEELUNITS = {
    'fy': 'N/mm²', 'fu': 'N/mm²', 'E': 'N/mm²',
    'G': 'N/mm²', 'ν': '-', 'ρ': 'kg/m³'
}



class woodMaterial:
    def __init__(self, malzeme):
        self.material= malzeme
        self.results= ahsap_data[malzeme]
        self.units= AHSAPUNITS
        self.param= {}
        for i,k in enumerate(self.units):
            self.param[k]= self.results[i]
            

class osbMaterial:
    def __init__(self, malzeme, thickness_mm, direction="major"):
        if malzeme not in osb_data:
            raise ValueError(f"Desteklenmeyen OSB malzemesi: {malzeme}")

        # Kalınlık aralığına göre doğru veriyi seçme
        if 10 <= thickness_mm <= 18:
            thickness_key = "10-18mm"
        elif 6 <= thickness_mm < 10:
            thickness_key = "6-10mm"
        else:
            raise ValueError(f"Belirtilen kalınlık ({thickness_mm} mm) için veri bulunamadı.")

        if direction not in ["major", "minor"]:
            raise ValueError(f"Geçersiz yön: {direction}. 'major' veya 'minor' olmalı.")

        self.results = osb_data[malzeme][thickness_key][direction]
        self.param = {}
        self.units= OSBUNITS
        for i,k in enumerate(self.units):
            self.param[k]= self.results[i]

        self.material = f"{malzeme}, {thickness_mm}mm, {direction}"

class concreteMaterial:
    def __init__(self, malzeme):
        if malzeme not in concrete_data:
            raise ValueError(f"Desteklenmeyen beton sınıfı: {malzeme}")
        self.material = malzeme
        self.results = concrete_data[malzeme]
        self.units = CONCRETEUNITS
        self.param = {k: self.results[i] for i, k in enumerate(self.units)}


class steelMaterial:
    def __init__(self, malzeme, thickness_mm=16):
        if malzeme not in steel_data:
            raise ValueError(f"Desteklenmeyen çelik sınıfı: {malzeme}")
            
        self.material = malzeme
        self.results = steel_data[malzeme].copy()
        
        # Et kalınlığı arttıkça akma dayanımında düsüş (EN 10025-2 mantığı)
        if thickness_mm > 40:
            self.results[0] -= 20  # fy azaltması
        elif thickness_mm > 16:
            self.results[0] -= 10

        self.units = STEELUNITS
        self.param = {k: self.results[i] for i, k in enumerate(self.units)}