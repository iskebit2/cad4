# ui/schemas.py
"""Her element tipi için hazır şemalar."""
from data.enums import PolygonType
from ui.schema import Field, Group


# ============================================================================
# NODE
# ============================================================================
def node_schema():
    return [
        Group("Genel", [
            Field("label",      "str",   "Label"),
            Field("is_visible", "bool",  "Görünür"),
            Field("color",      "color", "Renk (R,G,B)"),
        ]),
        Group("Konum", [
            Field("x", "float", "X", step=0.1, format="%.3f", unit="(L)"),
            Field("y", "float", "Y", step=0.1, format="%.3f", unit="(L)"),
            Field("z", "float", "Z", step=0.1, format="%.3f", unit="(L)"),
            Field("coord_sys",  "str", "Koordinat Sistemi"),
            Field("coord_type", "str", "Tip"),
            Field("special_jt", "bool", "Özel Düğüm"),
        ]),
        Group("Mesnet", [
            Field("restraint.ux", "bool", "UX"),
            Field("restraint.uy", "bool", "UY"),
            Field("restraint.uz", "bool", "UZ"),
            Field("restraint.rx", "bool", "RX"),
            Field("restraint.ry", "bool", "RY"),
            Field("restraint.rz", "bool", "RZ"),
        ], default_open=False),
        Group("Kütle", [
            Field("mass_1", "float", "M1", step=0.1, format="%.3f", unit="(M)"),
            Field("mass_2", "float", "M2", step=0.1, format="%.3f", unit="(M)"),
            Field("mass_3", "float", "M3", step=0.1, format="%.3f", unit="(M)"),
            Field("mmi_1",  "float", "MMI1", step=0.1, format="%.3f", unit="(M·L²)"),
            Field("mmi_2",  "float", "MMI2", step=0.1, format="%.3f", unit="(M·L²)"),
            Field("mmi_3",  "float", "MMI3", step=0.1, format="%.3f", unit="(M·L²)"),
        ], default_open=False),
        Group("Ek Kütle", [
            Field("added_mass_1", "float", "ΔM1", step=0.1, format="%.3f", unit="(M)"),
            Field("added_mass_2", "float", "ΔM2", step=0.1, format="%.3f", unit="(M)"),
            Field("added_mass_3", "float", "ΔM3", step=0.1, format="%.3f", unit="(M)"),
            Field("added_mmi_1",  "float", "ΔMMI1", step=0.1, format="%.3f", unit="(M·L²)"),
            Field("added_mmi_2",  "float", "ΔMMI2", step=0.1, format="%.3f", unit="(M·L²)"),
            Field("added_mmi_3",  "float", "ΔMMI3", step=0.1, format="%.3f", unit="(M·L²)"),
            Field("mass_coord_sys", "str", "Kütle CS"),
        ], default_open=False),
        Group("Bağlantı", [
            Field("constraint_name", "str", "Constraint"),
        ], default_open=False),
        Group("Yay (Spring)", [
            Field("spring_u1", "float", "U1", step=1.0, format="%.3f", unit="(F/L)"),
            Field("spring_u2", "float", "U2", step=1.0, format="%.3f", unit="(F/L)"),
            Field("spring_u3", "float", "U3", step=1.0, format="%.3f", unit="(F/L)"),
            Field("spring_r1", "float", "R1", step=1.0, format="%.3f", unit="(M/rad)"),
            Field("spring_r2", "float", "R2", step=1.0, format="%.3f", unit="(M/rad)"),
            Field("spring_r3", "float", "R3", step=1.0, format="%.3f", unit="(M/rad)"),
        ], default_open=False),
    ]


# ============================================================================
# FRAME
# ============================================================================
def frame_schema():
    return [
        Group("Genel", [
            Field("label",      "str",   "Label"),
            Field("is_visible", "bool",  "Görünür"),
            Field("color",      "color", "Renk"),
        ]),
        Group("Kesit", [
            Field("section", "section_ref", "Kesit"),
            Field("section_info", "info", "Kesit Özeti"),
        ]),
        Group("Geometri", [
            Field("rotation_deg", "float", "Rotation (°)",
                      step=1.0, format="%.2f"),
        ]),
        Group("Insertion Point", [
            Field("cardinal_pt",         "str",  "Kardinal Nokta"),
            Field("mirror2",             "bool", "Mirror 2"),
            Field("mirror3",             "bool", "Mirror 3"),
            Field("transform",           "bool", "Transform"),
            Field("insertion_coord_sys", "str",  "CS"),
            Field("jt_offset_i", "str", "I Offset (x,y,z)"),
            Field("jt_offset_j", "str", "J Offset (x,y,z)"),
        ], default_open=False),
        Group("End Offset", [
            Field("offset_type",     "enum",  "Tip",
                      choices=["User", "Automatic"]),
            Field("offset_length_i", "float", "I Uzunluğu", step=1.0, format="%.3f"),
            Field("offset_length_j", "float", "J Uzunluğu", step=1.0, format="%.3f"),
            Field("rigid_factor",    "float", "Rigid Factor", step=0.1, format="%.3f"),
        ], default_open=False),
        Group("Output Stations", [
            Field("station_type", "enum", "Tip",
                      choices=["MinNumSta", "MaxStaSpcg", "User"]),
            Field("min_num_sta",    "int",   "Min Adet"),
            Field("add_at_elm_int", "bool",  "Eleman İçi"),
            Field("add_at_pt_load", "bool",  "Noktasal Yükte"),
            Field("max_sta_spcg",   "float", "Max Aralık", step=1.0, format="%.3f"),
        ], default_open=False),
        Group("Auto Mesh", [
            Field("auto_mesh",         "bool",  "Aktif"),
            Field("mesh_at_joints",    "bool",  "Düğümlerde"),
            Field("mesh_at_frames",    "bool",  "Çubuklarda"),
            Field("mesh_num_segments", "int",   "Segment Sayısı"),
            Field("mesh_max_length",   "float", "Max Uzunluk", step=1.0, format="%.3f"),
            Field("mesh_max_degrees",  "float", "Max Açı", step=1.0, format="%.2f"),
        ], default_open=False),
        Group("Local Axes", [
            Field("mirror_abt2", "bool", "Mirror 2"),
            Field("mirror_abt3", "bool", "Mirror 3"),
        ], default_open=False),
        Group("Design", [
            Field("design_proc",   "str",  "Design Prosedürü"),
            Field("load_transfer", "bool", "Load Transfer"),
        ], default_open=False),
        Group("Yayılı Yük Setleri", [
            Field("dist_load_sets_list", "list_object",
                      "Pattern → Segment Seti",
                      item_schema=[
                          Field("pattern_name", "str", "Pattern"),
                          Field("coord_sys",    "enum", "CoordSys",
                                    choices=["Local", "Global"]),
                          Field("load_dir",     "enum", "Yön",
                                    choices=["1","2","3","4","5","6",
                                             "7","8","9","10"]),
                          Field("mode",         "enum", "Mode",
                                    choices=["REPLACE", "ADD"]),
                          Field("is_relative",  "bool", "Relative"),
                          Field("segments_text", "str", "Segmentler"),
                      ]),
        ], default_open=True),
    ]


# ============================================================================
# AREA
# ============================================================================
def area_schema():
    return [
        Group("Genel", [
            Field("label",      "str",   "Label"),
            Field("is_visible", "bool",  "Görünür"),
            Field("color",      "color", "Renk"),
        ]),
        Group("Kabuk", [
            Field("thickness",    "float", "Kalınlık",
                      step=0.1, format="%.3f", unit="(L)"),
            Field("material",     "material_ref", "Malzeme"),
            Field("section_name", "string_select", "Kesit Adı"),
            Field("material_info", "info", "Malzeme Özeti"),
        ]),
        Group("Override", [
            Field("thick_over",  "float", "Kalınlık Override",
                      step=0.1, format="%.3f", unit="(L)"),
            Field("offset_over", "float", "Offset Override",
                      step=0.1, format="%.3f", unit="(L)"),
            Field("mat_prop",    "str", "MatProp"),
        ], default_open=False),
        Group("Alan Kesiti", [
            Field("area_section", "info", "AreaSection"),
        ], default_open=False),
    ]


# ============================================================================
# LINK
# ============================================================================
def link_schema():
    return [
        Group("Genel", [
            Field("label",      "str",   "Label"),
            Field("is_visible", "bool",  "Görünür"),
            Field("color",      "color", "Renk"),
        ]),
        Group("Link", [
            Field("propname", "link_prop_ref", "Prop"),
        ]),
    ]


# ============================================================================
# POLYGON
# ============================================================================
# ui/schemas.py — append (mevcut Group, Field, schema_for korunur)

def polygon_schema():
    return [
        Group("Genel", [
            Field("label", "Etiket", "string"),
            Field("poly_type", "Tip", "enum",
                  choices=("GENERIC", "SURFACE_ONEWAY", "SURFACE_TWOWAY",
                           "ZONE", "SECTION_CUT", "LOAD_AREA")),
            Field("color", "Renk", "color"),
            Field("is_visible", "Görünür", "bool"),
            Field("transfer_dist_type", "Dağıtım", "enum",
                  choices=("one_way_u1", "one_way_u2", "two_way")),
            Field("is_load_area", "Yük Alanı", "bool"),
        ]),
        Group("Zone", [
            Field("show_zones_direction", "Göster", "string"),
            Field("zone_count", "Zone Sayısı", "info"),
        ]),
        Group("Bilgi", [
            Field("vertex_count", "Köşe", "info"),
            Field("assoc_count", "Assoc", "info"),
            Field("assigned_loads_summary", "Yükler", "list"),
        ]),
        Group("Frame Assoc", [
            Field("associated_frame_ids", "Frame ID'leri", "list"),
        ]),
    ]


def line_schema():
    return [
        Group("Genel", [
            Field("label", "Etiket", "string"),
            Field("color", "Renk", "color"),
            Field("width", "Kalınlık", "float"),
            Field("style", "Stil", "enum",
                  choices=("solid", "dashed", "dash_dot")),
            Field("visible", "Görünür", "bool"),
            Field("is_column", "Kolon", "bool"),
        ]),
        Group("Geometri", [
            Field("v1x", "Başlangıç X", "float"),
            Field("v1y", "Başlangıç Y", "float"),
            Field("v1z", "Başlangıç Z", "float"),
            Field("v2x", "Bitiş X", "float"),
            Field("v2y", "Bitiş Y", "float"),
            Field("v2z", "Bitiş Z", "float"),
            Field("length", "Uzunluk", "info"),
        ]),
    ]


def grid_schema():
    return [
        Group("Koordinatlar", [
            Field("x_coords", "X", "string"),
            Field("y_coords", "Y", "string"),
            Field("z_coords", "Z", "string"),
        ]),
        Group("Etiketler", [
            Field("x_labels", "X", "string"),
            Field("y_labels", "Y", "string"),
            Field("z_labels", "Z", "string"),
        ]),
        Group("Görsel", [
            Field("show_labels", "Etiket Göster", "bool"),
            Field("label_position", "Konum", "enum",
                  choices=("end", "both_ends", "middle")),
            Field("label_overflow", "Taşma", "float"),
        ]),
    ]


def plane_schema():
    return [
        Group("Genel", [
            Field("name", "Ad", "string"),
            Field("depth_minus", "Derinlik -", "float"),
            Field("depth_plus", "Derinlik +", "float"),
        ]),
    ]


_SCHEMAS = {
    "Node":    node_schema,
    "Frame":   frame_schema,
    "Area":    area_schema,
    "Link":    link_schema,
    "Polygon": polygon_schema,
    "Line": line_schema,
    "Plane": plane_schema,
    "Grid": grid_schema,
}


def schema_for(element_type: str):
    fn = _SCHEMAS.get(element_type)
    return fn() if fn else [Group("Genel", [])]


def multi_schema_for(elements):
    if not elements:
        return []
    types = set(getattr(e, "element_type", "?") for e in elements)
    if len(types) == 1:
        return schema_for(next(iter(types)))
    return [
        Group("Genel", [
            Field("label",      "str",   "Label"),
            Field("is_visible", "bool",  "Görünür"),
            Field("color",      "color", "Renk (R,G,B)"),
        ]),
    ]