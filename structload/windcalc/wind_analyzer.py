from enum import Enum, auto

import numpy as np
from structload.data.wind_data import TOL, WindRelation
from structload.windcalc.geometry_utils import _clip_line_to_polygon_2d, _close_polygon, _create_edge_perp_2d, _split_by_line_2d, _unproject_local_2d_to_3d, _valid_polygon
from structload.windcalc.surface import Surface
from structload.windcalc.windengine import WindEngine
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

class WindAnalyzer:

    def __init__(
        self,
        points,
        polygons,
        w_dir,
        **engine_kwargs,
    ):
        self.points = points
        self.polygons = polygons
        self.w_dir = np.asarray(w_dir, dtype=float)

        self.engine = WindEngine(
            points=points,
            polygons=polygons,
            w_dir=self.w_dir,
            **engine_kwargs,
        )

        self.e = self.engine.e
        self.all_surfaces = {}
        self.zones = []

    def analyze(self):

        self._create_surfaces()
        self._analyze_shared_edges()
        self._analysis_global_edges()
        self._classify_surfaces()
        self._generate_zones()

        return self.zones

    def _create_surfaces(self):

        for poly_name, pt_names in self.polygons.items():

            pts = np.array(
                [self.points[pt] for pt in pt_names],
                dtype=float,
            )

            surf = Surface(
                pts,
                name=poly_name,
            )

            surf.analyze(self.w_dir)

            self.all_surfaces[poly_name] = surf

    def _get_neighbors(self, surf):

        neighbors = {}

        for edge in surf.edges.values():

            for shared in edge.shared:

                if shared["is_coplanar_shared"]:
                    continue

                name = shared["surface"]
                neighbors[name] = self.all_surfaces[name]

        return list(neighbors.values())

    def _has_global_leading_neighbor(self, surf, neighbors):

        for neighbor in neighbors:

            if (
                neighbor.global_leading
                and neighbor.wind_relation == surf.wind_relation
            ):
                return True

        return False

    def _classify_surface(self, surf):

        neighbors = self._get_neighbors(surf)

        relations = {
            n.wind_relation
            for n in neighbors
        }

        if surf.wind_relation == WindRelation.WINDWARD:

            if WindRelation.PARALLEL in relations:
                return "HIPPED"

            if relations and relations <= {WindRelation.LEEWARD}:
                return "DUOPITCH"

            return "MONOPITCH"

        if surf.wind_relation == WindRelation.LEEWARD:

            if WindRelation.PARALLEL in relations:
                return "HIPPED"

            if relations and relations <= {WindRelation.WINDWARD}:
                return "DUOPITCH"

            return "MONOPITCH"

        if surf.wind_relation == WindRelation.PARALLEL:

            if not neighbors:
                return "MONOPITCH"

            if all(
                np.isclose(
                    n.angle,
                    surf.angle,
                    atol=1e-6,
                )
                for n in neighbors
            ):
                return "MONOPITCH"

            if self._has_global_leading_neighbor(
                surf,
                neighbors,
            ):
                return "DUOPITCH"

            return "HIPPED"

        return None

    def _classify_surfaces(self):

        for surface in self.all_surfaces.values():

            if surface.surface_type.value != "ROOF":
                continue

            surface.roof_type = self._classify_surface(surface)
    
    def _analysis_global_edges(self):

        global_leading = []

        for surface in self.all_surfaces.values():

            if surface.surface_type.value != "ROOF":
                continue

            surface.global_leading = False

            for edge in surface.edges.values():

                edge._global = False

                if not edge.leading:
                    continue

                if not edge.shared:
                    edge._global = True
                    surface.global_leading = True
                    global_leading.append(edge)
                    continue

                is_global = True

                for shared in edge.shared:
                    if shared.get("same_edge", False):
                        is_global = False
                        break

                if is_global:
                    edge._global = True
                    surface.global_leading = True
                    global_leading.append(edge)

        return global_leading

    @staticmethod
    def _are_edges_overlapping(e1, e2, tol=1e-4):

        p1a, p1b = np.asarray(e1.p1), np.asarray(e1.p2)
        p2a, p2b = np.asarray(e2.p1), np.asarray(e2.p2)

        same_dir = (
            np.linalg.norm(p1a - p2a) < tol
            and np.linalg.norm(p1b - p2b) < tol
        )

        opp_dir = (
            np.linalg.norm(p1a - p2b) < tol
            and np.linalg.norm(p1b - p2a) < tol
        )

        return same_dir or opp_dir

    def _analyze_shared_edges(self, tol=1e-3):

        surfaces = list(self.all_surfaces.values())

        plane_data = []

        for surface in surfaces:

            if surface.surface_type.value != "ROOF":
                continue

            normal = surface.normal_unit

            if normal is None or not surface.edges:
                continue

            first_edge = next(
                iter(surface.edges.values()),
                None,
            )

            if first_edge is None:
                continue

            d_const = -float(
                np.dot(normal, first_edge.p1)
            )

            plane_data.append(
                {
                    "surface": surface,
                    "normal": normal,
                    "d": d_const,
                }
            )

        n = len(plane_data)

        for i in range(n):

            surf_i = plane_data[i]["surface"]
            ni = plane_data[i]["normal"]
            di = plane_data[i]["d"]

            for j in range(i + 1, n):

                surf_j = plane_data[j]["surface"]
                nj = plane_data[j]["normal"]
                dj = plane_data[j]["d"]

                normal_dot = abs(
                    float(np.dot(ni, nj))
                )

                is_coplanar = (
                    abs(normal_dot - 1.0) < TOL
                    and abs(abs(di) - abs(dj)) < TOL
                )

                for ei in surf_i.edges.values():

                    for ej in surf_j.edges.values():

                        if not self._are_edges_overlapping(
                            ei,
                            ej,
                            TOL,
                        ):
                            continue

                        ei.shared.append(
                            {
                                "surface": surf_j.name,
                                "surface_edge": ej.index,
                                "same_edge": True,
                                "is_coplanar_shared": is_coplanar,
                            }
                        )

                        ej.shared.append(
                            {
                                "surface": surf_i.name,
                                "surface_edge": ei.index,
                                "same_edge": True,
                                "is_coplanar_shared": is_coplanar,
                            }
                        )

                        ei.is_coplanar_shared = is_coplanar
                        ej.is_coplanar_shared = is_coplanar

        roof_surfaces = [
            s
            for s in self.all_surfaces.values()
            if s.surface_type.value == "ROOF"
        ]

        for surface in roof_surfaces:

            surface.global_leading = any(
                getattr(edge, "_global", False)
                for edge in surface.edges.values()
            )

            surface.any_shared = any(
                getattr(edge, "is_shared", False)
                for edge in surface.edges.values()
            )

            surface.exposed_edge_list = [
                k
                for k, edge in surface.edges.items()
                if edge.exposed
            ]

            surface.leading_edge_list = [
                k
                for k, edge in surface.edges.items()
                if edge.leading
            ]

    # ------------------------------------------------------------------
    # ZONE GENERATION
    # ------------------------------------------------------------------

    def _generate_zones(self):
        """
        Tüm yüzeyler için rüzgar bölgelerini üretir.

        WALL  -> _get_wall_zones()
        ROOF  -> _get_roof_zones()

        Sonuç:
            self.zones : List[Zone]
        """

        zones = []

        for surface in self.all_surfaces.values():

            if surface.surface_type.value == "WALL":
                surface_zones = self._get_wall_zones(surface)

            elif surface.surface_type.value == "ROOF":
                surface_zones = self._get_roof_zones(surface)

            else:
                surface.zones = []
                continue

            zones.extend(surface_zones)

        self.zones = zones
        return self.zones

    # ------------------------------------------------------------------
    # WALL ZONES
    # ------------------------------------------------------------------

    def _get_wall_zones(self, surface):
        """
        Duvar yüzeyi için TS EN 1991-1-4 bölge geometrilerini üretir.
        """

        if surface.surface_type.value != "WALL":
            surface.zones = []
            return surface.zones

        relation = surface.wind_relation.value

        # --------------------------------------------------------------
        # WINDWARD / LEEWARD
        # --------------------------------------------------------------

        if relation in ("WINDWARD", "LEEWARD"):

            surface.zones = [
                _make_zone(
                    surface,
                    surface.pts_3d,
                    ZoneKind.ORDINARY,
                    table_type="WALL",
                )
            ]

            return surface.zones

        # --------------------------------------------------------------
        # PARALLEL
        # --------------------------------------------------------------

        if relation != "PARALLEL":
            surface.zones = []
            return surface.zones

        pts_2d = np.asarray(surface.pts_2d, dtype=float)
        pts_2d_closed = _close_polygon(pts_2d)

        u_dir = np.asarray(
            surface.proj_info["u_dir"],
            dtype=float,
        )
        v_dir = np.asarray(
            surface.proj_info["v_dir"],
            dtype=float,
        )

        wind_3d = np.asarray(
            surface.wind_vector,
            dtype=float,
        )

        # --------------------------------------------------------------
        # Wind vector -> local 2D
        # --------------------------------------------------------------

        w_plane = np.array(
            [
                np.dot(wind_3d, u_dir),
                np.dot(wind_3d, v_dir),
            ],
            dtype=float,
        )

        w_norm = np.linalg.norm(w_plane)

        # Rüzgar yüzey düzleminde tanımsızsa
        if w_norm < 1e-12:

            surface.zones = [
                _make_zone(
                    surface,
                    surface.pts_3d,
                    ZoneKind.TURBULENCE,
                    table_type="WALL",
                )
            ]

            return surface.zones

        w_dir_2d = w_plane / w_norm

        perp_2d = np.array(
            [
                -w_dir_2d[1],
                w_dir_2d[0],
            ]
        )

        # --------------------------------------------------------------
        # Yüzey boyutu
        # --------------------------------------------------------------

        proj_vals = (
            pts_2d_closed[:-1] @ w_dir_2d
        )

        min_p = float(proj_vals.min())
        max_p = float(proj_vals.max())

        d_len = max_p - min_p

        if d_len < 1e-6:

            surface.zones = [
                _make_zone(
                    surface,
                    surface.pts_3d,
                    ZoneKind.TURBULENCE,
                    table_type="WALL",
                )
            ]

            return surface.zones

        # --------------------------------------------------------------
        # e
        # --------------------------------------------------------------

        e = self.e

        if e <= 0:
            e = d_len

        a_len = e / 5.0
        b_len = 4.0 * e / 5.0

        splits = [
            a_len,
            a_len + b_len,
        ]

        zone_kinds = [
            ZoneKind.TURBULENCE,
            ZoneKind.ORDINARY,
            ZoneKind.WEAK,
        ]

        # --------------------------------------------------------------
        # e yüzey boyundan büyükse
        # --------------------------------------------------------------

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

        # --------------------------------------------------------------
        # Bölme
        # --------------------------------------------------------------

        zones = []
        current_poly_2d = pts_2d_closed

        for idx, offset in enumerate(splits):

            if offset >= d_len - 1e-5:
                break

            split_p = min_p + offset

            ref_pt = w_dir_2d * split_p

            p1 = (
                ref_pt
                - perp_2d * 10000.0
            )

            p2 = (
                ref_pt
                + perp_2d * 10000.0
            )

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
                current_poly_2d = _close_polygon(
                    part2_2d
                )
            else:
                zone_2d = part2_2d
                current_poly_2d = _close_polygon(
                    part1_2d
                )

            zone_3d = _unproject_local_2d_to_3d(
                zone_2d,
                surface.proj_info,
            )

            zones.append(
                _make_zone(
                    surface,
                    zone_3d,
                    zone_kinds[idx],
                    table_type="WALL",
                    pitch=0.0,
                )
            )

        # --------------------------------------------------------------
        # Kalan bölge
        # --------------------------------------------------------------

        if len(zones) < len(zone_kinds):
            remaining_kind = zone_kinds[len(zones)]
        else:
            remaining_kind = ZoneKind.WEAK

        remaining_3d = _unproject_local_2d_to_3d(
            current_poly_2d,
            surface.proj_info,
        )

        zones.append(
            _make_zone(
                surface,
                remaining_3d,
                remaining_kind,
                table_type="WALL",
                pitch=0.0,
            )
        )

        surface.zones = zones

        return surface.zones

    # ------------------------------------------------------------------
    # ROOF ZONES
    # ------------------------------------------------------------------

    def _get_roof_zones(self, surface):
        """
        Çatı yüzeyi için bölge geometrilerini üretir.
        """

        table_type = surface.roof_type
        relation = surface.wind_relation.value

        edges = surface.edges
        pts_2d = np.asarray(
            surface.pts_2d,
            dtype=float,
        )

        is_ccw = surface.is_ccw

        # --------------------------------------------------------------
        # Hedef kenarlar
        #
        # Leading edges önce,
        # exposed fakat leading olmayanlar sonra.
        # --------------------------------------------------------------

        target_edges = (
            list(surface.leading_edge_list)
            + [
                k
                for k in surface.exposed_edge_list
                if k not in surface.leading_edge_list
            ]
        )

        # --------------------------------------------------------------
        # Wind -> local 2D
        # --------------------------------------------------------------

        wind_3d = np.asarray(
            surface.wind_vector,
            dtype=float,
        )

        u_dir = np.asarray(
            surface.proj_info["u_dir"],
            dtype=float,
        )

        v_dir = np.asarray(
            surface.proj_info["v_dir"],
            dtype=float,
        )

        w_plane = np.array(
            [
                np.dot(wind_3d, u_dir),
                np.dot(wind_3d, v_dir),
            ],
            dtype=float,
        )

        w_norm = np.linalg.norm(w_plane)

        if w_norm > 1e-12:
            w_plane /= w_norm
        else:
            w_plane = np.array(
                [1.0, 0.0],
                dtype=float,
            )

        # --------------------------------------------------------------
        # Bölge deposu
        # --------------------------------------------------------------

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

        # --------------------------------------------------------------
        # Windward turbulence corner
        # --------------------------------------------------------------

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
                self.e / 4.0,
            )

            if res is None:
                return

            result_L, result_R = res

            if result_L is None or result_R is None:
                return

            corner1, turbulence_other = (
                _split_by_line_2d(
                    turbulence,
                    *result_L,
                )
            )

            if not (
                _valid_polygon(corner1)
                and _valid_polygon(turbulence_other)
            ):
                return

            turbulence_remain, corner2 = (
                _split_by_line_2d(
                    turbulence_other,
                    *result_R,
                )
            )

            if not (
                _valid_polygon(turbulence_remain)
                and _valid_polygon(corner2)
            ):
                return

            f1_3d = (
                _unproject_local_2d_to_3d(
                    corner1,
                    surface.proj_info,
                )
            )

            f2_3d = (
                _unproject_local_2d_to_3d(
                    corner2,
                    surface.proj_info,
                )
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

        # --------------------------------------------------------------
        # Parallel ordinary / weak
        # --------------------------------------------------------------

        def split_parallel_ordinary_weak(
            parallel_ordinary,
            remain_poly,
        ):

            if not surface.leading_edge_list:

                add_zone(
                    parallel_ordinary,
                    ZoneKind.ORDINARY,
                )

                return

            edge_idx = surface.leading_edge_list[0]

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
                + w_plane * (self.e / 2.0)
            )

            w_perp = np.array(
                [
                    -w_plane[1],
                    w_plane[0],
                ]
            )

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

        # ==============================================================
        # Ana kenar döngüsü
        # ==============================================================

        counter = 0
        remain_ = pts_2d.copy()

        for edge_idx in target_edges:

            edge = edges.get(edge_idx)

            if edge is None:
                continue

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

            left_normal = np.array(
                [
                    -edge_dir[1],
                    edge_dir[0],
                ]
            )

            inward = (
                left_normal
                if is_ccw
                else -left_normal
            )

            offset = inward * (self.e / 10.0)

            clipped = _clip_line_to_polygon_2d(
                p1 + offset,
                p2 + offset,
                remain_,
            )

            if clipped is None:
                continue

            ordinary, turbulence = (
                _split_by_line_2d(
                    remain_,
                    *clipped,
                )
            )

            if not (
                _valid_polygon(ordinary)
                and _valid_polygon(turbulence)
            ):
                continue

            # ----------------------------------------------------------
            # Global leading edge
            # ----------------------------------------------------------

            if getattr(edge, "_global", False):

                split_windward_turbulence_corners(
                    turbulence,
                    edge,
                )

            # ----------------------------------------------------------
            # Normal leading / exposed edge
            # ----------------------------------------------------------

            else:

                if (
                    edge.leading
                    and relation == "LEEWARD"
                    and len(surface.leading_edge_list) == 1
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

        # ==============================================================
        # Kalan bölge
        # ==============================================================

        if relation == "PARALLEL":

            split_parallel_ordinary_weak(
                remain_,
                remain_,
            )

        else:

            add_zone(
                remain_,
                ZoneKind.ORDINARY,
            )

        # ==============================================================
        # 2D -> 3D ve Zone nesneleri
        # ==============================================================

        zones = []

        for poly_2d, kind, index in regions_2d:

            if not _valid_polygon(poly_2d):
                continue

            poly_3d = (
                _unproject_local_2d_to_3d(
                    poly_2d,
                    surface.proj_info,
                )
            )

            zones.append(
                _make_zone(
                    surface,
                    poly_3d,
                    kind,
                    index=index,
                    table_type=table_type,
                    pitch=surface.pitch,
                )
            )

        surface.zones = zones

        return surface.zones

