# ui/schemas.py
"""Her element tipi için hazır şemalar."""
from data.enums import PolygonType
from ui.schema import FieldSpec, GroupSpec


# ============================================================================
# NODE
# ============================================================================
def node_schema():
    return [
        GroupSpec("Genel", [
            FieldSpec("label",      "str",   "Label"),
            FieldSpec("is_visible", "bool",  "Görünür"),
            FieldSpec("color",      "color", "Renk (R,G,B)"),
        ]),
        GroupSpec("Konum", [
            FieldSpec("x", "float", "X", step=0.1, format="%.3f", unit="(L)"),
            FieldSpec("y", "float", "Y", step=0.1, format="%.3f", unit="(L)"),
            FieldSpec("z", "float", "Z", step=0.1, format="%.3f", unit="(L)"),
            FieldSpec("coord_sys",  "str", "Koordinat Sistemi"),
            FieldSpec("coord_type", "str", "Tip"),
            FieldSpec("special_jt", "bool", "Özel Düğüm"),
        ]),
        GroupSpec("Mesnet", [
            FieldSpec("restraint.ux", "bool", "UX"),
            FieldSpec("restraint.uy", "bool", "UY"),
            FieldSpec("restraint.uz", "bool", "UZ"),
            FieldSpec("restraint.rx", "bool", "RX"),
            FieldSpec("restraint.ry", "bool", "RY"),
            FieldSpec("restraint.rz", "bool", "RZ"),
        ], default_open=False),
        GroupSpec("Kütle", [
            FieldSpec("mass_1", "float", "M1", step=0.1, format="%.3f", unit="(M)"),
            FieldSpec("mass_2", "float", "M2", step=0.1, format="%.3f", unit="(M)"),
            FieldSpec("mass_3", "float", "M3", step=0.1, format="%.3f", unit="(M)"),
            FieldSpec("mmi_1",  "float", "MMI1", step=0.1, format="%.3f", unit="(M·L²)"),
            FieldSpec("mmi_2",  "float", "MMI2", step=0.1, format="%.3f", unit="(M·L²)"),
            FieldSpec("mmi_3",  "float", "MMI3", step=0.1, format="%.3f", unit="(M·L²)"),
        ], default_open=False),
        GroupSpec("Ek Kütle", [
            FieldSpec("added_mass_1", "float", "ΔM1", step=0.1, format="%.3f", unit="(M)"),
            FieldSpec("added_mass_2", "float", "ΔM2", step=0.1, format="%.3f", unit="(M)"),
            FieldSpec("added_mass_3", "float", "ΔM3", step=0.1, format="%.3f", unit="(M)"),
            FieldSpec("added_mmi_1",  "float", "ΔMMI1", step=0.1, format="%.3f", unit="(M·L²)"),
            FieldSpec("added_mmi_2",  "float", "ΔMMI2", step=0.1, format="%.3f", unit="(M·L²)"),
            FieldSpec("added_mmi_3",  "float", "ΔMMI3", step=0.1, format="%.3f", unit="(M·L²)"),
            FieldSpec("mass_coord_sys", "str", "Kütle CS"),
        ], default_open=False),
        GroupSpec("Bağlantı", [
            FieldSpec("constraint_name", "str", "Constraint"),
        ], default_open=False),
        GroupSpec("Yay (Spring)", [
            FieldSpec("spring_u1", "float", "U1", step=1.0, format="%.3f", unit="(F/L)"),
            FieldSpec("spring_u2", "float", "U2", step=1.0, format="%.3f", unit="(F/L)"),
            FieldSpec("spring_u3", "float", "U3", step=1.0, format="%.3f", unit="(F/L)"),
            FieldSpec("spring_r1", "float", "R1", step=1.0, format="%.3f", unit="(M/rad)"),
            FieldSpec("spring_r2", "float", "R2", step=1.0, format="%.3f", unit="(M/rad)"),
            FieldSpec("spring_r3", "float", "R3", step=1.0, format="%.3f", unit="(M/rad)"),
        ], default_open=False),
    ]


# ============================================================================
# FRAME
# ============================================================================
def frame_schema():
    return [
        GroupSpec("Genel", [
            FieldSpec("label",      "str",   "Label"),
            FieldSpec("is_visible", "bool",  "Görünür"),
            FieldSpec("color",      "color", "Renk"),
        ]),
        GroupSpec("Kesit", [
            FieldSpec("section", "section_ref", "Kesit"),
            FieldSpec("section_info", "info", "Kesit Özeti"),
        ]),
        GroupSpec("Geometri", [
            FieldSpec("rotation_deg", "float", "Rotation (°)",
                      step=1.0, format="%.2f"),
        ]),
        GroupSpec("Insertion Point", [
            FieldSpec("cardinal_pt",         "str",  "Kardinal Nokta"),
            FieldSpec("mirror2",             "bool", "Mirror 2"),
            FieldSpec("mirror3",             "bool", "Mirror 3"),
            FieldSpec("transform",           "bool", "Transform"),
            FieldSpec("insertion_coord_sys", "str",  "CS"),
            FieldSpec("jt_offset_i", "str", "I Offset (x,y,z)"),
            FieldSpec("jt_offset_j", "str", "J Offset (x,y,z)"),
        ], default_open=False),
        GroupSpec("End Offset", [
            FieldSpec("offset_type",     "enum",  "Tip",
                      choices=["User", "Automatic"]),
            FieldSpec("offset_length_i", "float", "I Uzunluğu", step=1.0, format="%.3f"),
            FieldSpec("offset_length_j", "float", "J Uzunluğu", step=1.0, format="%.3f"),
            FieldSpec("rigid_factor",    "float", "Rigid Factor", step=0.1, format="%.3f"),
        ], default_open=False),
        GroupSpec("Output Stations", [
            FieldSpec("station_type", "enum", "Tip",
                      choices=["MinNumSta", "MaxStaSpcg", "User"]),
            FieldSpec("min_num_sta",    "int",   "Min Adet"),
            FieldSpec("add_at_elm_int", "bool",  "Eleman İçi"),
            FieldSpec("add_at_pt_load", "bool",  "Noktasal Yükte"),
            FieldSpec("max_sta_spcg",   "float", "Max Aralık", step=1.0, format="%.3f"),
        ], default_open=False),
        GroupSpec("Auto Mesh", [
            FieldSpec("auto_mesh",         "bool",  "Aktif"),
            FieldSpec("mesh_at_joints",    "bool",  "Düğümlerde"),
            FieldSpec("mesh_at_frames",    "bool",  "Çubuklarda"),
            FieldSpec("mesh_num_segments", "int",   "Segment Sayısı"),
            FieldSpec("mesh_max_length",   "float", "Max Uzunluk", step=1.0, format="%.3f"),
            FieldSpec("mesh_max_degrees",  "float", "Max Açı", step=1.0, format="%.2f"),
        ], default_open=False),
        GroupSpec("Local Axes", [
            FieldSpec("mirror_abt2", "bool", "Mirror 2"),
            FieldSpec("mirror_abt3", "bool", "Mirror 3"),
        ], default_open=False),
        GroupSpec("Design", [
            FieldSpec("design_proc",   "str",  "Design Prosedürü"),
            FieldSpec("load_transfer", "bool", "Load Transfer"),
        ], default_open=False),
        GroupSpec("Yayılı Yük Setleri", [
            FieldSpec("dist_load_sets_list", "list_object",
                      "Pattern → Segment Seti",
                      item_schema=[
                          FieldSpec("pattern_name", "str", "Pattern"),
                          FieldSpec("coord_sys",    "enum", "CoordSys",
                                    choices=["Local", "Global"]),
                          FieldSpec("load_dir",     "enum", "Yön",
                                    choices=["1","2","3","4","5","6",
                                             "7","8","9","10"]),
                          FieldSpec("mode",         "enum", "Mode",
                                    choices=["REPLACE", "ADD"]),
                          FieldSpec("is_relative",  "bool", "Relative"),
                          FieldSpec("segments_text", "str", "Segmentler"),
                      ]),
        ], default_open=True),
    ]


# ============================================================================
# AREA
# ============================================================================
def area_schema():
    return [
        GroupSpec("Genel", [
            FieldSpec("label",      "str",   "Label"),
            FieldSpec("is_visible", "bool",  "Görünür"),
            FieldSpec("color",      "color", "Renk"),
        ]),
        GroupSpec("Kabuk", [
            FieldSpec("thickness",    "float", "Kalınlık",
                      step=0.1, format="%.3f", unit="(L)"),
            FieldSpec("material",     "material_ref", "Malzeme"),
            FieldSpec("section_name", "string_select", "Kesit Adı"),
            FieldSpec("material_info", "info", "Malzeme Özeti"),
        ]),
        GroupSpec("Override", [
            FieldSpec("thick_over",  "float", "Kalınlık Override",
                      step=0.1, format="%.3f", unit="(L)"),
            FieldSpec("offset_over", "float", "Offset Override",
                      step=0.1, format="%.3f", unit="(L)"),
            FieldSpec("mat_prop",    "str", "MatProp"),
        ], default_open=False),
        GroupSpec("Alan Kesiti", [
            FieldSpec("area_section", "info", "AreaSection"),
        ], default_open=False),
    ]


# ============================================================================
# LINK
# ============================================================================
def link_schema():
    return [
        GroupSpec("Genel", [
            FieldSpec("label",      "str",   "Label"),
            FieldSpec("is_visible", "bool",  "Görünür"),
            FieldSpec("color",      "color", "Renk"),
        ]),
        GroupSpec("Link", [
            FieldSpec("propname", "link_prop_ref", "Prop"),
        ]),
    ]


# ============================================================================
# POLYGON
# ============================================================================
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
                    choices=[t.name for t in PolygonType]),
        ]),
        GroupSpec("İlişkili Frame'ler", [
            FieldSpec("associated_frame_ids", "list", "İlişkili Frame ID'leri"),
        ], default_open=False),
        GroupSpec("Alan Yükleri (Load Manager)", [
            FieldSpec(
                "assigned_loads_summary", "list",
                "Atanmış yükler (kaydedilmiş)",
            ),
            FieldSpec(
                "area_load_transfer_summary", "list",
                "Load Manager aktarım kayıtları",
            ),
            FieldSpec("transfer_target", "str", "Aktarım hedefi"),
            FieldSpec("transfer_dist_type", "str", "Tributary tipi"),
            FieldSpec("is_load_area", "bool", "Yük alanı etkin"),
        ], default_open=True),
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
    if not elements:
        return []
    types = set(getattr(e, "element_type", "?") for e in elements)
    if len(types) == 1:
        return schema_for(next(iter(types)))
    return [
        GroupSpec("Genel", [
            FieldSpec("label",      "str",   "Label"),
            FieldSpec("is_visible", "bool",  "Görünür"),
            FieldSpec("color",      "color", "Renk (R,G,B)"),
        ]),
    ]