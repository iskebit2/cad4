# data/csi_catalog.py
"""
CSi XML kataloglarından Section/Material üretme köprüsü.
tools/csi_section_library.py'nin üstünde ince bir katman.
"""
from typing import Optional, Dict, List
from tools.csi_section_library import CSiSectionLibrary, CSiMaterialLibrary
from domain.definition import Section, Material
from data.enums import SectionType, MatType

from logging_config import CadLogger
logger = CadLogger.get(__name__)


# CSi kesit tipi → bizim SectionType
CSI_TO_SECTIONTYPE = {
    "STEEL_I_SECTION":          SectionType.I,
    "STEEL_CHANNEL_SECTION":    SectionType.CHANNEL,
    "STEEL_ANGLE_SECTION":      SectionType.L,
    "STEEL_T_SECTION":          SectionType.T,
    "STEEL_DBLANGLE_SECTION":   SectionType.L,       # yaklaşık
    "STEEL_PIPE_SECTION":       SectionType.PIPE,
    "STEEL_RECTANGULAR_SECTION": SectionType.RECT,
    "CONCRETE_RECTANGULAR_SECTION": SectionType.RECT,
    "CONCRETE_CIRCULAR_SECTION": SectionType.CIRCLE,
}

# CSi alan adı → bizim profile_params anahtarı
CSI_TO_PROFILE_PARAMS = {
    "D":  "h",
    "BF": "b",
    "TF": "tf",
    "TW": "tw",
    "OD": "d",     # pipe
    "T":  "t",     # pipe
    "DIST": "dist",  # double angle
}

# CSi'da hazır gelen hesaplanmış özellikler (analiz için)
CSI_CATALOG_PROPS = (
    "A", "I33", "I22", "J", "Z33", "Z22", "R33", "R22",
    "AS2", "AS3", "S33POS", "S33NEG", "S22POS", "S22NEG",
)


def section_from_csi(csi_lib: CSiSectionLibrary, label: str,
                     material: Optional[Material] = None) -> Optional[Section]:
    """
    CSiSectionLibrary'den bir Section üret.
    Arama: label doğrudan varsa kullan.
    """
    data = csi_lib.get_section(label)
    if not data:
        return None

    csi_type = data.get("type", "")
    section_type = CSI_TO_SECTIONTYPE.get(csi_type, SectionType.RECT)

    # profile_params: geometrik değerler
    params: Dict[str, float] = {}
    for csi_key, our_key in CSI_TO_PROFILE_PARAMS.items():
        if csi_key in data:
            try:
                params[our_key] = float(data[csi_key])
            except (ValueError, TypeError):
                pass

    # catalog_props: hesaplanmış özellikler
    catalog_props: Dict[str, float] = {}
    for prop in CSI_CATALOG_PROPS:
        if prop in data:
            try:
                catalog_props[prop] = float(data[prop])
            except (ValueError, TypeError):
                pass

    return Section(
        name=label,
        profile_type=section_type,
        profile_params=params,
        material=material,
        catalog_props=catalog_props,
        catalog_source="CSi Euro",
    )


def material_from_csi(csi_lib: CSiMaterialLibrary, name: str) -> Optional[Material]:
    """CSiMaterialLibrary'den Material üret."""
    data = csi_lib.get_material(name)
    if not data:
        return None

    mat_type_raw = data.get("type", "").lower()
    mat_type = {
        "concrete": MatType.CONCRETE,
        "steel":    MatType.STEEL,
        "rebar":    MatType.REBAR,
        "tendon":   MatType.TENDON,
    }.get(mat_type_raw, MatType.NODESIGN)

    def _f(key, default=0.0):
        try:
            return float(data.get(key, default))
        except (ValueError, TypeError):
            return default

    E = _f("modulusOfElasticity")
    nu = _f("poissonsRatio", 0.3)
    # CSi yoğunluğu kg/m³ olarak verir mi? SAP'ta "weightDensity" genelde kN/m³
    # ama SAP2000 25'te "massDensity" kg/m³ veya kg·s²/mm⁴
    # Şimdilik weightDensity'yi kg/m³ kabul edelim, kullanıcı kontrol eder
    density = _f("weightDensity", 7850 if mat_type == MatType.STEEL else 2500)

    G = E / (2 * (1 + nu))

    mat = Material(
        name=name,
        mat_type=mat_type,
        E1=E, E2=E, E3=E,
        G12=G, G13=G, G23=G,
        nu12=nu, nu13=nu, nu23=nu,
        density=density,
    )
    # fck, fy vb. değerleri params'a koy
    if mat_type == MatType.CONCRETE and "compressiveStrength" in data:
        mat.params = {"fck": _f("compressiveStrength")}
    elif mat_type in (MatType.STEEL, MatType.REBAR):
        if "minimumYieldStress" in data:
            mat.params = {
                "fy": _f("minimumYieldStress"),
                "fu": _f("minimumTensileStress"),
            }
    return mat