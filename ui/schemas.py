# ui/schemas.py
"""Her element tipi için hazır şemalar."""
from ui.schema import FieldSpec, GroupSpec


def node_schema():
    return [
        GroupSpec("Genel", [
            FieldSpec("label",      "str",   "Label"),
            FieldSpec("is_visible", "bool",  "Görünür"),
            FieldSpec("color",      "color", "Renk (R,G,B)"),
        ]),
        GroupSpec("Konum", [
            FieldSpec("x", "float", "X", step=0.1, format="%.3f"),
            FieldSpec("y", "float", "Y", step=0.1, format="%.3f"),
            FieldSpec("z", "float", "Z", step=0.1, format="%.3f"),
        ]),
        GroupSpec("Restraint", [
            FieldSpec("restraint.ux", "bool", "UX"),
            FieldSpec("restraint.uy", "bool", "UY"),
            FieldSpec("restraint.uz", "bool", "UZ"),
            FieldSpec("restraint.rx", "bool", "RX"),
            FieldSpec("restraint.ry", "bool", "RY"),
            FieldSpec("restraint.rz", "bool", "RZ"),
        ], default_open=False),
    ]


# ui/schemas.py
def frame_schema():
    return [
        GroupSpec("Genel", [
            FieldSpec("label",      "str",   "Label"),
            FieldSpec("is_visible", "bool",  "Görünür"),
            FieldSpec("color",      "color", "Renk"),
        ]),
        GroupSpec("Geometri", [
            FieldSpec("rotation_deg", "float", "Rotation",
                      step=1.0, format="%.2f"),
        ]),
        GroupSpec("Kesit", [
            FieldSpec("section.profile_type", "enum", "Profil",
                      choices=["RECT", "CIRCLE", "I", "T", "TUBE", "PIPE"]),
            FieldSpec("section.profile_params.h", "float", "h",
                      step=1.0, format="%.1f"),
            FieldSpec("section.profile_params.b", "float", "b",
                      step=1.0, format="%.1f"),
        ]),
        GroupSpec("Yayılı Yük Setleri (Segment Bazlı)", [
            FieldSpec("dist_load_sets_list", "list_object",
                      "Pattern → Segment Seti",
                      item_schema=[
                          FieldSpec("pattern_name", "str",   "Pattern"),
                          FieldSpec("coord_sys",    "enum",  "CoordSys",
                                    choices=["Local", "Global"]),
                          FieldSpec("load_dir",     "enum",  "Yön",
                                    choices=["1","2","3","4","5","6",
                                             "7","8","9","10"]),
                          FieldSpec("mode",         "enum",  "Mode",
                                    choices=["REPLACE", "ADD"]),
                          FieldSpec("is_relative",  "bool",  "Relative"),
                          FieldSpec("segments_text", "str",  "Segmentler (x1,x2,q1,q2 | ...)"),
                      ]),
        ], default_open=True),
    ]


def area_schema():
    return [
        GroupSpec("Genel", [
            FieldSpec("label",      "str",   "Label"),
            FieldSpec("is_visible", "bool",  "Görünür"),
            FieldSpec("color",      "color", "Renk"),
        ]),
        GroupSpec("Geometri", [
            FieldSpec("thickness", "float", "Kalınlık",
                      step=0.01, format="%.3f"),
        ]),
    ]


def link_schema():
    return [
        GroupSpec("Genel", [
            FieldSpec("label",      "str",   "Label"),
            FieldSpec("is_visible", "bool",  "Görünür"),
            FieldSpec("color",      "color", "Renk"),
        ]),
        GroupSpec("Property", [
            FieldSpec("propname", "str", "Prop Adı"),
        ]),
    ]


def polygon_schema():
    return [
        GroupSpec("Genel", [
            FieldSpec("label",        "str",   "Label"),
            FieldSpec("is_visible",   "bool",  "Görünür"),
            FieldSpec("is_temporary", "bool",  "Geçici (Temp)"),
            FieldSpec("color",        "color", "Renk"),
        ]),
        GroupSpec("Poligon", [
            FieldSpec("poly_type", "enum", "Tip",
                      choices=["GENERIC", "SURFACE", "ZONE",
                               "SECTION_CUT", "LOAD_AREA"]),
        ]),
        GroupSpec("Yükler (Uniform to Frame)", [
            FieldSpec("uniform_to_frame_loads", "list_object", "Yük Tanımları",
                      item_schema=[
                          FieldSpec("pattern_name", "str", "Load Pattern"),
                          FieldSpec("value", "float", "Değer (kN/m²)"),
                          FieldSpec("direction", "enum", "Yön", 
                                    choices=["GX", "GY", "GZ", "1", "2", "3", "GRAV", "PX", "PY", "PZ"]),
                          FieldSpec("dist_type", "enum", "Dağıtım Tipi", 
                                    choices=["One way", "Two way"]),
                      ]),
        ]),
    ]


_SCHEMAS = {
    "Node":    node_schema,
    "Frame":   frame_schema,
    "Area":    area_schema,
    "Link":    link_schema,
    "Polygon": polygon_schema,
}


def schema_for(element_type: str):
    fn = _SCHEMAS.get(element_type)
    return fn() if fn else [GroupSpec("Genel", [])]

def multi_schema_for(elements):
    """
    Çoklu seçim için şema. Ortak alanları tek bir şemada topla.
    """
    if not elements:
        return []
    types = set(getattr(e, "element_type", "?") for e in elements)

    if len(types) == 1:
        # Tek tip → o tipin şeması
        et = next(iter(types))
        base = schema_for(et)
    else:
        # Karışık tipler → sadece ortak alanlar
        base = [
            GroupSpec("Genel", [
                FieldSpec("label",      "str",   "Label"),
                FieldSpec("is_visible", "bool",  "Görünür"),
                FieldSpec("color",      "color", "Renk (R,G,B)"),
            ]),
        ]

    # `is_visible` ve `label` zaten base'de var
    return base