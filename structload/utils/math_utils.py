"""
Ortak Matematik ve Mühendislik Araçları
"""

import math
from typing import List, Dict, Any, Tuple
from collections.abc import Mapping

def interpolate_value(value: float, data: Mapping) -> Any:
    """
    Verilen sözlük veya Mapping nesnesinde lineer interpolasyon yapar.
    Hem standart dict hem de MappingProxyType (salt okunur) nesneleri destekler.
    """
    keys = sorted(data.keys())
    
    if value <= keys[0]:
        return data[keys[0]]
    if value >= keys[-1]:
        return data[keys[-1]]
    
    # Alt ve üst değerleri bul
    for i in range(len(keys) - 1):
        if keys[i] <= value <= keys[i + 1]:
            lower_key, upper_key = keys[i], keys[i + 1]
            lower_val = data[lower_key]
            upper_val = data[upper_key]
            
            # İnterpolasyon çarpanı
            t = (value - lower_key) / (upper_key - lower_key)
            
            # Durum 1: İç içe sözlük yapısı (Mapping veya dict) var ise (cpe verileri gibi)
            if isinstance(lower_val, Mapping):
                result = {}
                for k in lower_val.keys():
                    sub_lower = lower_val[k]
                    sub_upper = upper_val[k]
                    
                    # Eğer içerdeki değer de bir tuple/liste ise eleman bazlı interpolasyon yap (örn: (-1.7, 0.0))
                    if isinstance(sub_lower, (list, tuple)):
                        result[k] = [sub_lower[j] + t * (sub_upper[j] - sub_lower[j]) 
                                     for j in range(len(sub_lower))]
                    else:
                        result[k] = sub_lower + t * (sub_upper - sub_lower)
                return result
            
            # Durum 2: Doğrudan liste veya tuple ise
            elif isinstance(lower_val, (list, tuple)):
                return [lower_val[j] + t * (upper_val[j] - lower_val[j]) 
                        for j in range(len(lower_val))]
            
            # Durum 3: Düz sayısal değer ise
            else:
                return lower_val + t * (upper_val - lower_val)
                
    return data[keys[-1]]


def interpolate_2d(x: float, xp: List[float], yp: List[float]) -> float:
    """
    2D lineer interpolasyon.
    
    Args:
        x: Interpolasyon yapılacak x değeri
        xp: X ekseni değerleri (sıralı)
        yp: Y ekseni değerleri
    
    Returns:
        Interpolasyon sonucu
    """
    for i in range(len(xp) - 1):
        if xp[i] <= x <= xp[i + 1]:
            return yp[i] + (yp[i + 1] - yp[i]) * (x - xp[i]) / (xp[i + 1] - xp[i])
    return yp[-1]


def calculate_wind_velocity_pressure(v_b0: float, rho: float = 1.25) -> float:
    """
    Temel rüzgar hızı basıncını hesaplar.
    
    Args:
        v_b0: Temel rüzgar hızı (m/s)
        rho: Hava yoğunluğu (kg/m³)
    
    Returns:
        q_b (kN/m²)
    """
    return 0.5 * rho * v_b0**2 / 1000


def calculate_roughness_coefficient(z0: float, z: float, zmin: float) -> Tuple[float, float]:
    """
    Pürüzlülük katsayısını hesaplar.
    
    Args:
        z0: Pürüzlülük uzunluğu (m)
        z: Referans yükseklik (m)
        zmin: Minimum yükseklik (m)
    
    Returns:
        (kr, cr) - Pürüzlülük katsayıları
    """
    kr = 0.19 * (z0 / 0.05) ** 0.07
    z_eff = max(z, zmin)
    cr = kr * math.log(z_eff / z0)
    return kr, cr


def calculate_exposure_coefficient(cr: float, ct: float) -> float:
    """
    Maruziyet katsayısını hesaplar.
    
    Args:
        cr: Pürüzlülük katsayısı
        ct: Topografya katsayısı
    
    Returns:
        ce - Maruziyet katsayısı
    """
    return (cr * ct) ** 2


def calculate_turbulence_intensity(z0: float, z: float, zmin: float, kI: float = 1.0) -> float:
    """
    Türbülans şiddetini hesaplar.
    
    Args:
        z0: Pürüzlülük uzunluğu (m)
        z: Referans yükseklik (m)
        zmin: Minimum yükseklik (m)
        kI: Türbülans faktörü
    
    Returns:
        Iv - Türbülans şiddeti
    """
    z_eff = max(z, zmin)
    return kI / math.log(z_eff / z0)


def calculate_snow_shape_coefficient(alpha: float) -> float:
    """
    Kar şekil katsayısını hesaplar (beşik çatı).
    
    Args:
        alpha: Çatı eğimi (derece)
    
    Returns:
        μ - Şekil katsayısı
    """
    if alpha <= 30:
        return 0.8
    elif alpha < 60:
        return 0.8 * (60 - alpha) / 30
    else:
        return 0.0


def round_values(data: Dict[str, Any], decimals: int = 3) -> Dict[str, Any]:
    """
    Dictionary'deki tüm sayısal değerleri yuvarlar.
    
    Args:
        data: Dictionary
        decimals: Ondalık basamak sayısı
    
    Returns:
        Yuvarlanmış dictionary
    """
    result = {}
    for k, v in data.items():
        if isinstance(v, float):
            result[k] = round(v, decimals)
        elif isinstance(v, (list, tuple)):
            result[k] = [round(x, decimals) if isinstance(x, float) else x for x in v]
        else:
            result[k] = v
    return result