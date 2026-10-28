# data/materials_catalog.py
"""
Malzeme kataloğu — mevcut mechanical.py verilerini MatType'a göre gruplar.
Panelin "Katalogdan Yükle" özelliği buradan beslenir.
"""
from data.enums import MatType
from structload.data.mechanical import (
    AHSAPUNITS,
    CONCRETEUNITS,
    OSBUNITS,
    STEELUNITS,
    ahsap_data,
    concrete_data,
    osb_data,
    steel_data,
)

# Her MatType için hangi katalog(lar) kullanılabilir
CATALOG_BY_MATTYPE = {
    MatType.CONCRETE: {
        "label": "Beton (TS 500 / EN 1992)",
        "items": list(concrete_data.keys()),
        "units": CONCRETEUNITS,
    },
    MatType.STEEL: {
        "label": "Yapısal Çelik (EN 10025-2)",
        "items": list(steel_data.keys()),
        "units": STEELUNITS,
    },
    MatType.TIMBER: {
        "label": "Ahşap (EN 338)",
        "items": list(ahsap_data.keys()),
        "units": AHSAPUNITS,
    },
    MatType.COLDFORMED: {
        "label": "OSB (EN 300)",
        "items": list(osb_data.keys()),
        "units": OSBUNITS,
    },
    MatType.MASONRY: {
        "label": "OSB (EN 300)",
        "items": list(osb_data.keys()),
        "units": OSBUNITS,
    },
}


def catalog_names_for(mat_type: MatType):
    """Verilen MatType için katalog isimleri listesi."""
    entry = CATALOG_BY_MATTYPE.get(mat_type)
    return entry["items"] if entry else []


def get_catalog_params(name: str, mat_type: MatType, thickness_mm: float = 16.0) -> dict:
    """
    Katalogdan parametreleri getir. MatType'a göre doğru sözlüğe bakar.

    Döndürdüğü dict: {"E": ..., "G": ..., "nu": ..., "density": ..., 
                       "fck": ..., "fy": ..., "param_name": değer, ...}
    Anahtarlar katalog tipine göre değişir.
    """
    if mat_type == MatType.CONCRETE:
        if name not in concrete_data:
            raise KeyError(f"Beton kataloğunda '{name}' yok")
        raw = concrete_data[name]
        # CONCRETEUNITS sırası: fck, fck_cube, fctk_0.05, fctm, Ecm, nu, rho
        return {
            "fck":        raw[0],
            "fck_cube":   raw[1],
            "fctk_0_05":  raw[2],
            "fctm":       raw[3],
            "Ecm":        raw[4],
            "nu":         raw[5],
            "density":    raw[6],
        }
    elif mat_type == MatType.STEEL:
        if name not in steel_data:
            raise KeyError(f"Çelik kataloğunda '{name}' yok")
        raw = steel_data[name]
        # STEELUNITS: fy, fu, E, G, nu, rho
        fy = raw[0]
        # EN 10025-2: kalınlığa göre fy azaltma
        if thickness_mm > 40:
            fy -= 20
        elif thickness_mm > 16:
            fy -= 10
        return {
            "fy":      fy,
            "fu":      raw[1],
            "E":       raw[2],
            "G":       raw[3],
            "nu":      raw[4],
            "density": raw[5],
        }
    elif mat_type == MatType.TIMBER:
        if name not in ahsap_data:
            raise KeyError(f"Ahşap kataloğunda '{name}' yok")
        raw = ahsap_data[name]
        # AHSAPUNITS: fm,k, ft,0,k, ft,90,k, fc,0,k, fc,90,k, fv,k,
        #             Em,o,ort, E0.05, Em,90,ort, Gor, ρ, ρort
        return {
            "fm_k":       raw[0],
            "ft_0_k":     raw[1],
            "ft_90_k":    raw[2],
            "fc_0_k":     raw[3],
            "fc_90_k":    raw[4],
            "fv_k":       raw[5],
            "Em_o_ort":   raw[6],
            "E_0_05":     raw[7],
            "Em_90_ort":  raw[8],
            "Gor":        raw[9],
            "density":    raw[11],  # ρort
        }
    elif mat_type in (MatType.COLDFORMED, MatType.MASONRY):
        # OSB — thickness ve direction varsayılan
        if name not in osb_data:
            raise KeyError(f"OSB kataloğunda '{name}' yok")
        if 10 <= thickness_mm <= 18:
            tkey = "10-18mm"
        elif 6 <= thickness_mm < 10:
            tkey = "6-10mm"
        else:
            tkey = "10-18mm"  # varsayılan
        raw = osb_data[name][tkey]["major"]
        # OSBUNITS: fm,k, ..., Em,o,ort, E0.05, Em,90,ort, Gor, ρ, ρort
        return {
            "fm_k":       raw[0],
            "ft_0_k":     raw[1],
            "ft_90_k":    raw[2],
            "fc_0_k":     raw[3],
            "fc_90_k":    raw[4],
            "fv_k":       raw[5],
            "Em_o_ort":   raw[6],
            "E_0_05":     raw[7],
            "Em_90_ort":  raw[8],
            "Gor":        raw[9],
            "density":    raw[11],
        }
    raise ValueError(f"MatType {mat_type} için katalog yok")

def apply_catalog_to_material(mat, name: str, thickness_mm: float = 16.0):
    """
    Katalogdan Material nesnesine değerleri yaz.
    MatType → hangi katalog olduğu belirler.
    """
    params = get_catalog_params(name, mat.mat_type, thickness_mm)

    # Material alanlarına eşle
    if "Ecm" in params:
        mat.E1 = mat.E2 = mat.E3 = params["Ecm"]
        # Betonda G = E / (2(1+nu))
        G = params["Ecm"] / (2 * (1 + params["nu"]))
        mat.G12 = mat.G13 = mat.G23 = G
        mat.nu12 = mat.nu13 = mat.nu23 = params["nu"]
        mat.density = params["density"]
    elif "E" in params:
        mat.E1 = mat.E2 = mat.E3 = params["E"]
        mat.G12 = mat.G13 = mat.G23 = params["G"]
        mat.nu12 = mat.nu13 = mat.nu23 = params["nu"]
        mat.density = params["density"]
    elif "Em_o_ort" in params:
        # kN/mm² → N/mm² (×1000)
        E = params["Em_o_ort"] * 1000.0
        mat.E1 = mat.E2 = mat.E3 = E
        G = params["Gor"] * 1000.0 if params["Gor"] < 100 else params["Gor"]
        mat.G12 = mat.G13 = mat.G23 = G
        mat.nu12 = mat.nu13 = mat.nu23 = 0.3   # ahşap için yaklaşık
        mat.density = params["density"]

    return params