from enum import Enum, auto
from typing import List
import numpy as np

from structload.windcalc.geometry_utils import _clip_line_to_polygon_2d, _close_polygon, _create_edge_perp_2d, _split_by_line_2d, _unproject_local_2d_to_3d, _valid_polygon
from structload.windcalc.surface import Surface
from structload.windcalc.zone import Zone


class ZoneKind(Enum):
    ORDINARY = auto()
    WEAK = auto()

    TURBULENCE = auto()
    TURBULENCE_CORNER_HIGH = auto()
    TURBULENCE_CORNER_LOW = auto()
    TURBULENCE_REMAIN = auto()

    TURBULENCE_STRA = auto()
    TURBULENCE_SLOP = auto()


# ------------------------------------------------------------
# CPE tablo etiketleri
# ------------------------------------------------------------

ZONE_LABELS = {

    # ---------------- WALL ----------------
    ("WALL", "WINDWARD", ZoneKind.ORDINARY): "D",
    ("WALL", "LEEWARD",  ZoneKind.ORDINARY): "E",

    ("WALL", "PARALLEL", ZoneKind.TURBULENCE): "A",
    ("WALL", "PARALLEL", ZoneKind.ORDINARY): "B",
    ("WALL", "PARALLEL", ZoneKind.WEAK): "C",

    # ---------------- MONOPITCH ----------------
    ("MONOPITCH", "WINDWARD", ZoneKind.TURBULENCE_CORNER_HIGH): "F",
    ("MONOPITCH", "WINDWARD", ZoneKind.TURBULENCE_CORNER_LOW):  "F",
    ("MONOPITCH", "WINDWARD", ZoneKind.TURBULENCE_REMAIN):       "G",
    ("MONOPITCH", "WINDWARD", ZoneKind.ORDINARY):               "H",

    ("MONOPITCH", "LEEWARD", ZoneKind.TURBULENCE_CORNER_HIGH): "F",
    ("MONOPITCH", "LEEWARD", ZoneKind.TURBULENCE_CORNER_LOW):  "F",
    ("MONOPITCH", "LEEWARD", ZoneKind.TURBULENCE_REMAIN):       "G",
    ("MONOPITCH", "LEEWARD", ZoneKind.ORDINARY):               "H",

    ("MONOPITCH", "PARALLEL", ZoneKind.TURBULENCE_CORNER_HIGH): "Fu",
    ("MONOPITCH", "PARALLEL", ZoneKind.TURBULENCE_CORNER_LOW):  "Fl",
    ("MONOPITCH", "PARALLEL", ZoneKind.TURBULENCE_REMAIN):      "G",
    ("MONOPITCH", "PARALLEL", ZoneKind.ORDINARY):               "H",
    ("MONOPITCH", "PARALLEL", ZoneKind.WEAK):                   "I",

    # ---------------- DUOPITCH ----------------
    ("DUOPITCH", "WINDWARD", ZoneKind.TURBULENCE_CORNER_HIGH): "F",
    ("DUOPITCH", "WINDWARD", ZoneKind.TURBULENCE_CORNER_LOW):  "F",
    ("DUOPITCH", "WINDWARD", ZoneKind.TURBULENCE_REMAIN):      "G",
    ("DUOPITCH", "WINDWARD", ZoneKind.ORDINARY):               "H",

    ("DUOPITCH", "LEEWARD", ZoneKind.TURBULENCE_STRA): "J",
    ("DUOPITCH", "LEEWARD", ZoneKind.TURBULENCE_SLOP): "J",
    ("DUOPITCH", "LEEWARD", ZoneKind.ORDINARY):         "I",

    ("DUOPITCH", "PARALLEL", ZoneKind.TURBULENCE_CORNER_HIGH): "G",
    ("DUOPITCH", "PARALLEL", ZoneKind.TURBULENCE_CORNER_LOW):  "F",
    ("DUOPITCH", "PARALLEL", ZoneKind.TURBULENCE_REMAIN):      "G",
    ("DUOPITCH", "PARALLEL", ZoneKind.ORDINARY):               "H",
    ("DUOPITCH", "PARALLEL", ZoneKind.WEAK):                   "I",

    # ---------------- HIPPED ----------------
    ("HIPPED", "WINDWARD", ZoneKind.TURBULENCE_CORNER_HIGH): "F",
    ("HIPPED", "WINDWARD", ZoneKind.TURBULENCE_CORNER_LOW):  "F",
    ("HIPPED", "WINDWARD", ZoneKind.TURBULENCE_REMAIN):      "G",
    ("HIPPED", "WINDWARD", ZoneKind.ORDINARY):               "H",

    ("HIPPED", "LEEWARD", ZoneKind.TURBULENCE_STRA): "K",
    ("HIPPED", "LEEWARD", ZoneKind.TURBULENCE_SLOP): "J",
    ("HIPPED", "LEEWARD", ZoneKind.ORDINARY):         "I",

    ("HIPPED", "PARALLEL", ZoneKind.TURBULENCE_SLOP): "L",
    ("HIPPED", "PARALLEL", ZoneKind.ORDINARY):        "M",
    ("HIPPED", "PARALLEL", ZoneKind.WEAK):            "N",
}


TABLE_ANGLE = {
    "MONOPITCH": {
        "WINDWARD": 0,
        "LEEWARD": 180,
        "PARALLEL": 90,
    },

    "DUOPITCH": {
        "WINDWARD": 0,
        "LEEWARD": 0,
        "PARALLEL": 90,
    },

    "HIPPED": {
        "WINDWARD": 0,
        "LEEWARD": 0,
        "PARALLEL": 0,
    },

    "WALL": {
        "WINDWARD": 0,
        "LEEWARD": 0,
        "PARALLEL": 0,
    },
}


def _zone_label(table_type, wind_relation, kind):
    """
    Zone'un geometrik anlamından CPE tablo etiketini üretir.
    """
    key = (table_type, wind_relation, kind)
    return ZONE_LABELS.get(key, "UNDEFINED")
    

def _make_zone(
    plane1,
    coords,
    kind,
    *,
    index=None,
    table_type=None,
    pitch=0.0,
):
    """
    Geometrik zone bilgisinden gerçek Zone domain nesnesini oluşturur.
    """

    if table_type is None:
        table_type = plane1.roof_type

    relation = plane1.wind_relation.value

    label = _zone_label(
        table_type,
        relation,
        kind,
    )

    table_type_dir = TABLE_ANGLE[table_type][relation]

    zone = Zone(
        label=label,
        coords=_close_polygon(coords),
        surface=plane1.name,
        table_type=table_type,
        table_type_dir=table_type_dir,
        pitch=pitch,
    )

    # Slop bölgelerini birbirinden ayırmak gerekirse
    # Zone içinde kullanılabilir.
    zone.kind = kind
    zone.index = index

    return zone

def _get_wall_zones(plane1: Surface, e: float) -> List[Zone]:

    if plane1.surface_type.value != "WALL":
        return []

    relation = plane1.wind_relation.value

    # --------------------------------------------------------
    # WINDWARD
    # --------------------------------------------------------

    if relation == "WINDWARD":
        plane1.zones = [
            _make_zone(
                plane1,
                plane1.pts_3d,
                ZoneKind.ORDINARY,
                table_type="WALL",
            )
        ]
        return plane1.zones

    # --------------------------------------------------------
    # LEEWARD
    # --------------------------------------------------------

    if relation == "LEEWARD":
        plane1.zones = [
            _make_zone(
                plane1,
                plane1.pts_3d,
                ZoneKind.ORDINARY,
                table_type="WALL",
            )
        ]
        return plane1.zones

    # --------------------------------------------------------
    # PARALLEL
    # --------------------------------------------------------

    pts_2d = np.asarray(plane1.pts_2d, dtype=float)

    u_dir = np.asarray(
        plane1.proj_info["u_dir"],
        dtype=float,
    )

    v_dir = np.asarray(
        plane1.proj_info["v_dir"],
        dtype=float,
    )

    pts_2d_closed = _close_polygon(pts_2d)

    wind_3d = np.asarray(
        plane1.wind_vector,
        dtype=float,
    )

    w_plane = np.array([
        np.dot(wind_3d, u_dir),
        np.dot(wind_3d, v_dir),
    ])

    w_norm = np.linalg.norm(w_plane)

    # Rüzgar yüzeye paralel değilse
    # normal yönde bir izdüşüm vardır.
    if w_norm < 1e-12:
        plane1.zones = [
            _make_zone(
                plane1,
                plane1.pts_3d,
                ZoneKind.TURBULENCE,
                table_type="WALL",
            )
        ]
        return plane1.zones

    w_dir_2d = w_plane / w_norm

    perp_2d = np.array([
        -w_dir_2d[1],
        w_dir_2d[0],
    ])

    # --------------------------------------------------------
    # Duvarın rüzgar doğrultusundaki boyutu
    # --------------------------------------------------------

    proj_vals = pts_2d_closed[:-1] @ w_dir_2d

    min_p = float(proj_vals.min())
    max_p = float(proj_vals.max())

    d_len = max_p - min_p

    if d_len < 1e-6:
        plane1.zones = [
            _make_zone(
                plane1,
                plane1.pts_3d,
                ZoneKind.TURBULENCE,
                table_type="WALL",
            )
        ]
        return plane1.zones

    if e <= 0:
        e = d_len

    # --------------------------------------------------------
    # A = e/5
    # B = 4e/5
    # --------------------------------------------------------

    a_len = e / 5.0
    b_len = 4.0 * e / 5.0

    splits = [
        a_len,
        a_len + b_len,
    ]

    # --------------------------------------------------------
    # Geometriyi böl
    # --------------------------------------------------------

    zones_list = []
    current_poly_2d = pts_2d_closed

    zone_kinds = [
        ZoneKind.TURBULENCE,
        ZoneKind.ORDINARY,
        ZoneKind.WEAK,
    ]

    if a_len + b_len >= d_len - 1e-5:

        splits = (
            [a_len]
            if a_len < d_len - 1e-5
            else []
        )

        zone_kinds = [
            ZoneKind.TURBULENCE,
            ZoneKind.ORDINARY,
        ]

    for idx, offset in enumerate(splits):

        if offset >= d_len - 1e-5:
            break

        split_p = min_p + offset

        ref_pt = w_dir_2d * split_p

        p1 = ref_pt - perp_2d * 10000.0
        p2 = ref_pt + perp_2d * 10000.0

        part1_2d, part2_2d = _split_by_line_2d(
            current_poly_2d,
            p1,
            p2,
        )

        if not (
            _valid_polygon(part1_2d)
            and _valid_polygon(part2_2d)
        ):
            break

        center1 = (
            np.mean(part1_2d[:-1], axis=0)
            @ w_dir_2d
        )

        center2 = (
            np.mean(part2_2d[:-1], axis=0)
            @ w_dir_2d
        )

        if center1 < center2:
            zone_2d = part1_2d
            current_poly_2d = _close_polygon(part2_2d)
        else:
            zone_2d = part2_2d
            current_poly_2d = _close_polygon(part1_2d)

        zone_3d = _unproject_local_2d_to_3d(
            zone_2d,
            plane1.proj_info,
        )

        zones_list.append(
            _make_zone(
                plane1,
                zone_3d,
                zone_kinds[idx],
                table_type="WALL",
                pitch=0.0,
            )
        )

    # --------------------------------------------------------
    # Kalan bölge
    # --------------------------------------------------------

    if len(zones_list) < len(zone_kinds):
        remaining_kind = zone_kinds[len(zones_list)]
    else:
        remaining_kind = ZoneKind.WEAK

    remaining_3d = _unproject_local_2d_to_3d(
        current_poly_2d,
        plane1.proj_info,
    )

    zones_list.append(
        _make_zone(
            plane1,
            remaining_3d,
            remaining_kind,
            table_type="WALL",
            pitch=0.0,
        )
    )

    plane1.zones = zones_list

    return plane1.zones

def _get_roof_zones(plane1: Surface, e: float) -> List[Zone]:

    table_type = plane1.roof_type
    relation = plane1.wind_relation.value

    edges = plane1.edges
    pts_2d = np.asarray(
        plane1.pts_2d,
        dtype=float,
    )

    is_ccw = plane1.is_ccw

    target_edges = (
        plane1.leading_edge_list
        + [
            k
            for k in plane1.exposed_edge_list
            if k not in plane1.leading_edge_list
        ]
    )

    wind_3d = np.asarray(
        plane1.wind_vector,
        dtype=float,
    )

    u_dir = np.asarray(
        plane1.proj_info["u_dir"],
        dtype=float,
    )

    v_dir = np.asarray(
        plane1.proj_info["v_dir"],
        dtype=float,
    )

    w_plane = np.array([
        np.dot(wind_3d, u_dir),
        np.dot(wind_3d, v_dir),
    ])

    w_norm = np.linalg.norm(w_plane)

    if w_norm > 1e-12:
        w_plane /= w_norm
    else:
        w_plane = np.array([1.0, 0.0])

    # Artık dict değil.
    # Aynı tipten birden fazla zone kaybolmaz.
    regions_2d = []

    def add_zone(poly, kind, index=None):

        if not _valid_polygon(poly):
            return

        regions_2d.append(
            (
                poly,
                kind,
                index,
            )
        )

    # --------------------------------------------------------
    # WINDWARD turbulance corner
    # --------------------------------------------------------

    def split_windward_turbulence_corners(
        turbulence,
        edge,
        twin=True,
    ):

        if edge.wind_to_2d is None:
            edge.wind_to_2d = w_plane

        res = _create_edge_perp_2d(
            pts_2d,
            edge.p1_2d,
            edge.p2_2d,
            edge.wind_to_2d,
            e / 4.0,
        )

        if res is None:
            return

        result_L, result_R = res

        if result_L is None or result_R is None:
            return

        corner1, turbulence_other = _split_by_line_2d(
            turbulence,
            *result_L,
        )

        if not (
            _valid_polygon(corner1)
            and _valid_polygon(turbulence_other)
        ):
            return

        turbulence_remain, corner2 = _split_by_line_2d(
            turbulence_other,
            *result_R,
        )

        if not (
            _valid_polygon(turbulence_remain)
            and _valid_polygon(corner2)
        ):
            return

        f1_3d = _unproject_local_2d_to_3d(
            corner1,
            plane1.proj_info,
        )

        f2_3d = _unproject_local_2d_to_3d(
            corner2,
            plane1.proj_info,
        )

        z1 = (
            float(np.mean(f1_3d[:, 2]))
            if len(f1_3d)
            else 0.0
        )

        z2 = (
            float(np.mean(f2_3d[:, 2]))
            if len(f2_3d)
            else 0.0
        )

        if z1 >= z2:

            add_zone(
                corner1,
                ZoneKind.TURBULENCE_CORNER_HIGH,
            )

            if twin:
                add_zone(
                    corner2,
                    ZoneKind.TURBULENCE_CORNER_LOW,
                )

        else:

            add_zone(
                corner2,
                ZoneKind.TURBULENCE_CORNER_HIGH,
            )

            if twin:
                add_zone(
                    corner1,
                    ZoneKind.TURBULENCE_CORNER_LOW,
                )

        if twin:
            add_zone(
                turbulence_remain,
                ZoneKind.TURBULENCE_REMAIN,
            )
        else:
            add_zone(
                turbulence_other,
                ZoneKind.TURBULENCE_REMAIN,
            )

    # --------------------------------------------------------
    # PARALLEL ordinary / weak
    # --------------------------------------------------------

    def split_parallel_ordinary_weak(
        parallel_ordinary, remain_poly
    ):

        if not plane1.leading_edge_list:
            add_zone(
                parallel_ordinary,
                ZoneKind.ORDINARY,
            )
            return

        edge_idx = plane1.leading_edge_list[0]

        if edge_idx not in edges:
            add_zone(
                parallel_ordinary,
                ZoneKind.ORDINARY,
            )
            return

        edge = edges[edge_idx]

        if edge.pos_front_pt is None:
            edge.pos_front_pt = edge.p1_2d

        p0e = (
            np.asarray(
                edge.pos_front_pt,
                dtype=float,
            )
            + w_plane * (e / 2.0)
        )

        w_perp = np.array([
            -w_plane[1],
            w_plane[0],
        ])

        ptp_val = (
            max(
                np.ptp(pts_2d[:, 0]),
                np.ptp(pts_2d[:, 1]),
            )
            if len(pts_2d)
            else 100.0
        )

        L = 10.0 * ptp_val

        cut = _clip_line_to_polygon_2d(
            p0e - w_perp * L,
            p0e + w_perp * L,
            remain_poly,
        )

        if cut is None:
            add_zone(
                parallel_ordinary,
                ZoneKind.ORDINARY,
            )
            return

        ordinary, weak = _split_by_line_2d(
            parallel_ordinary,
            *cut,
        )

        if not (
            _valid_polygon(ordinary)
            and _valid_polygon(weak)
        ):
            add_zone(
                parallel_ordinary,
                ZoneKind.ORDINARY,
            )
            return

        add_zone(
            ordinary,
            ZoneKind.ORDINARY,
        )

        add_zone(
            weak,
            ZoneKind.WEAK,
        )

    # --------------------------------------------------------
    # Ana döngü
    # --------------------------------------------------------

    counter = 0
    remain_ = pts_2d.copy()

    for idx_ in target_edges:

        if idx_ not in edges:
            continue

        edge = edges[idx_]

        p1 = np.asarray(
            edge.p1_2d,
            dtype=float,
        )

        p2 = np.asarray(
            edge.p2_2d,
            dtype=float,
        )

        edge_vec = p2 - p1
        edge_len = np.linalg.norm(edge_vec)

        if edge_len < 1e-10:
            continue

        edge_dir = edge_vec / edge_len

        left_normal = np.array([
            -edge_dir[1],
            edge_dir[0],
        ])

        inward = (
            left_normal
            if is_ccw
            else -left_normal
        )

        offset = inward * (e / 10.0)

        clipped = _clip_line_to_polygon_2d(
            p1 + offset,
            p2 + offset,
            remain_,
        )

        if clipped is None:
            continue

        ordinary, turbulence = _split_by_line_2d(
            remain_,
            *clipped,
        )

        if not (
            _valid_polygon(ordinary)
            and _valid_polygon(turbulence)
        ):
            continue

        # ----------------------------------------------------
        # Global leading edge
        # ----------------------------------------------------

        if getattr(edge, "_global", False):

            split_windward_turbulence_corners(
                turbulence,
                edge,
            )

        # ----------------------------------------------------
        # Normal leading / exposed edge
        # ----------------------------------------------------

        else:

            if (
                edge.leading
                and relation == "LEEWARD"
                and len(plane1.leading_edge_list) == 1
            ):

                add_zone(
                    turbulence,
                    ZoneKind.TURBULENCE_STRA,
                )

            else:

                counter += 1

                add_zone(
                    turbulence,
                    ZoneKind.TURBULENCE_SLOP,
                    counter,
                )

        remain_ = ordinary

    # --------------------------------------------------------
    # Kalan bölge
    # --------------------------------------------------------

    if relation == "PARALLEL":

        split_parallel_ordinary_weak(remain_, remain_)

    else:

        add_zone(
            remain_,
            ZoneKind.ORDINARY,
        )

    # --------------------------------------------------------
    # 2D → 3D → Zone
    # --------------------------------------------------------

    zones = []

    for poly_2d, kind, index in regions_2d:

        if not _valid_polygon(poly_2d):
            continue

        poly_3d = _unproject_local_2d_to_3d(
            poly_2d,
            plane1.proj_info,
        )

        zones.append(
            _make_zone(
                plane1,
                poly_3d,
                kind,
                index=index,
                table_type=table_type,
                pitch=plane1.pitch,
            )
        )

    plane1.zones = zones

    return plane1.zones

def _analysis_all_zones(all_surfaces, e):

    for s_name, surf in all_surfaces.items():

        if surf.surface_type.value == "WALL":
            surf_zones = _get_wall_zones(surf, e)
        else:
            surf_zones = _get_roof_zones(surf, e)

        zone_names = [
            z.label
            for z in surf_zones
        ]

        # print(
        #     f"{surf.name} "
        #     f"{surf.surface_type.value} "
        #     f"wind_relation={surf.wind_relation.value} "
        #     f"roof_type={surf.roof_type} "
        #     f"Zones={zone_names}"
        # )