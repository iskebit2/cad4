# core/analysis/mass_source.py

from dataclasses import dataclass, field
from typing import Dict

import numpy as np

from domain.scene import Scene
from domain.definition import LoadDirection


G_MM_S2 = 9810.0


VERTICAL_DIRECTIONS = {
    LoadDirection.GRAVITY,
    LoadDirection.GLOBAL_Z,
    LoadDirection.PROJECTED_Z,
    LoadDirection.LOCAL_3,
}


# ============================================================
# YARDIMCILAR
# ============================================================

def is_vertical(direction) -> bool:
    return direction in VERTICAL_DIRECTIONS


def get_pattern_kind(design_type: str) -> str:
    text = str(design_type).upper().strip()

    if "DEAD" in text:
        return "dead"

    if "LIVE" in text:
        return "live"

    return "other"


def _pattern_factors(scene: Scene, n: float):
    factors = {}

    for name, pattern in scene.def_mgr.load_patterns.items():
        kind = get_pattern_kind(pattern.design_type)

        if kind == "dead":
            factors[name] = 1.0

        elif kind == "live":
            factors[name] = n

        else:
            factors[name] = 0.0

    return factors


def _node_key_map(scene):
    """
    unique_id ile scene.nodes anahtarını eşleştirir.
    """
    result = {}

    for key, node in scene.nodes.items():
        result[key] = key

        unique_id = getattr(node, "unique_id", None)

        if unique_id is not None:
            result[unique_id] = key

    return result


# ============================================================
# GEOMETRİ KÜTLELERİ
# ============================================================

def polygon_area_3d(nodes) -> float:
    """
    3B düzlemsel poligon alanı.
    Sonuç: mm²
    """
    if len(nodes) < 3:
        return 0.0

    points = np.array(
        [[node.x, node.y, node.z] for node in nodes],
        dtype=float
    )

    normal = np.zeros(3)

    for i in range(len(points)):
        p1 = points[i]
        p2 = points[(i + 1) % len(points)]

        normal[0] += (
            (p1[1] - p2[1]) *
            (p1[2] + p2[2])
        )

        normal[1] += (
            (p1[2] - p2[2]) *
            (p1[0] + p2[0])
        )

        normal[2] += (
            (p1[0] - p2[0]) *
            (p1[1] + p2[1])
        )

    return float(np.linalg.norm(normal) / 2.0)


def frame_mass(frame) -> float:
    """
    Frame öz kütlesi.

    Birim:
        ton
    """
    section = getattr(frame, "section", None)

    if section is None:
        return 0.0

    material = getattr(section, "material", None)

    if material is None:
        return 0.0

    area = section.profile_params.get("Area", 0.0)

    if area <= 0.0:
        return 0.0

    length = frame.get_length()

    if length <= 0.0:
        return 0.0

    density = material.density

    return area * length * density


def area_mass(area) -> float:
    """
    Area öz kütlesi.

    Birim:
        ton
    """
    material = getattr(area, "material", None)

    if material is None:
        return 0.0

    thickness = getattr(area, "thickness", 0.0)

    if thickness <= 0.0:
        return 0.0

    geometry_area = polygon_area_3d(area.nodes)

    if geometry_area <= 0.0:
        return 0.0

    return (
        geometry_area *
        thickness *
        material.density
    )


# ============================================================
# SONUÇ
# ============================================================

@dataclass
class MassBreakdown:

    self_weight: float = 0.0

    dead_loads: float = 0.0
    live_loads: float = 0.0

    n: float = 0.3

    dead_patterns: Dict[str, float] = field(
        default_factory=dict
    )

    live_patterns: Dict[str, float] = field(
        default_factory=dict
    )

    @property
    def G(self):
        return self.self_weight + self.dead_loads

    @property
    def Q(self):
        return self.live_loads

    @property
    def nQ(self):
        return self.n * self.Q

    @property
    def total(self):
        return self.G + self.nQ

    @property
    def total_kg(self):
        return self.total * 1000.0

    @property
    def total_weight_kn(self):
        return self.total * G_MM_S2 / 1000.0

    def __inspector_tree__(self):

        return {
            "G — Sabit Kütle": {
                "Öz Kütle": f"{self.self_weight:.3f} ton",
                "Sabit Yükler": f"{self.dead_loads:.3f} ton",
                "G": f"{self.G:.3f} ton",
            },

            "Q — Hareketli Kütle": {
                "Hareketli Yükler": f"{self.live_loads:.3f} ton",
                "Q": f"{self.Q:.3f} ton",
                "n": f"{self.n:.3f}",
                "n · Q": f"{self.nQ:.3f} ton",
            },

            "Deprem Kütlesi": {
                "m = G + n·Q": f"{self.total:.3f} ton",
                "Kütle": f"{self.total_kg:.1f} kg",
                "Ağırlık": f"{self.total_weight_kn:.3f} kN",
            },

            "Yük Desenleri": {
                "Dead": self.dead_patterns,
                "Live": self.live_patterns,
            },
        }


# ============================================================
# KÜTLE HESABI
# ============================================================

def build_mass_data(scene: Scene, num_dofs: int, n: float = 0.3):
    """
    Tek ve merkezi kütle hesabı.

    Döndürür:
        M_global
        MassBreakdown
        node_masses
    """

    node_key_map = _node_key_map(scene)

    node_masses = {
        key: 0.0
        for key in scene.nodes
    }

    breakdown = MassBreakdown(n=n)

    factors = _pattern_factors(scene, n)

    # --------------------------------------------------------
    # 1. FRAME ÖZ KÜTLELERİ
    # --------------------------------------------------------

    for frame in scene.frames.values():

        mass = frame_mass(frame)

        if mass <= 0.0:
            continue

        breakdown.self_weight += mass

        key_i = node_key_map.get(
            getattr(frame.node_i, "unique_id", None),
            None
        )

        key_j = node_key_map.get(
            getattr(frame.node_j, "unique_id", None),
            None
        )

        if key_i is not None:
            node_masses[key_i] += mass / 2.0

        if key_j is not None:
            node_masses[key_j] += mass / 2.0

    # --------------------------------------------------------
    # 2. FRAME YÜKLERİ
    # --------------------------------------------------------

    for frame in scene.frames.values():

        length = frame.get_length()

        if length <= 0.0:
            continue

        key_i = node_key_map.get(
            getattr(frame.node_i, "unique_id", None)
        )

        key_j = node_key_map.get(
            getattr(frame.node_j, "unique_id", None)
        )

        for load in getattr(frame, "dist_loads", []):

            if not is_vertical(load.direction):
                continue

            factor = factors.get(
                load.pattern_name,
                0.0
            )

            if factor <= 0.0:
                continue

            p_avg = (
                load.p1 +
                load.p2
            ) / 2.0

            force = p_avg * length
            mass = force / G_MM_S2

            contribution = mass * factor

            kind = get_pattern_kind(
                scene.def_mgr
                .load_patterns[
                    load.pattern_name
                ].design_type
            )

            if kind == "dead":

                breakdown.dead_loads += mass

                breakdown.dead_patterns[
                    load.pattern_name
                ] = (
                    breakdown.dead_patterns.get(
                        load.pattern_name,
                        0.0
                    ) + mass
                )

            elif kind == "live":

                breakdown.live_loads += mass

                breakdown.live_patterns[
                    load.pattern_name
                ] = (
                    breakdown.live_patterns.get(
                        load.pattern_name,
                        0.0
                    ) + mass
                )

            if key_i is not None:
                node_masses[key_i] += (
                    contribution / 2.0
                )

            if key_j is not None:
                node_masses[key_j] += (
                    contribution / 2.0
                )

        # ----------------------------------------------------
        # FRAME GRAVITY LOADS
        # ----------------------------------------------------

        for load in getattr(
            frame,
            "gravity_loads",
            []
        ):

            factor = factors.get(
                load.pattern_name,
                0.0
            )

            if factor <= 0.0:
                continue

            mass = (
                frame_mass(frame) *
                load.multiplier_z
            )

            if mass <= 0.0:
                continue

            contribution = mass * factor

            pattern = scene.def_mgr.load_patterns.get(
                load.pattern_name
            )

            if pattern is None:
                continue

            kind = get_pattern_kind(
                pattern.design_type
            )

            if kind == "dead":

                breakdown.dead_loads += mass

                breakdown.dead_patterns[
                    load.pattern_name
                ] = (
                    breakdown.dead_patterns.get(
                        load.pattern_name,
                        0.0
                    ) + mass
                )

            elif kind == "live":

                breakdown.live_loads += mass

                breakdown.live_patterns[
                    load.pattern_name
                ] = (
                    breakdown.live_patterns.get(
                        load.pattern_name,
                        0.0
                    ) + mass
                )

            if key_i is not None:
                node_masses[key_i] += (
                    contribution / 2.0
                )

            if key_j is not None:
                node_masses[key_j] += (
                    contribution / 2.0
                )

    # --------------------------------------------------------
    # 3. AREA YÜKLERİ
    # --------------------------------------------------------

    for area in scene.areas.values():

        nodes = area.nodes

        if len(nodes) < 3:
            continue

        geometry_area = polygon_area_3d(nodes)

        if geometry_area <= 0.0:
            continue

        # ----------------------------------------------------
        # AREA SELF WEIGHT
        # ----------------------------------------------------

        mass = area_mass(area)

        if mass > 0.0:

            breakdown.self_weight += mass

            contribution = (
                mass / len(nodes)
            )

            for node in nodes:

                key = node_key_map.get(
                    getattr(node, "unique_id", None)
                )

                if key is not None:
                    node_masses[key] += contribution

        # ----------------------------------------------------
        # UNIFORM LOAD
        # ----------------------------------------------------

        for load in getattr(
            area,
            "uniform_loads",
            []
        ):

            if not is_vertical(load.direction):
                continue

            factor = factors.get(
                load.pattern_name,
                0.0
            )

            if factor <= 0.0:
                continue

            force = (
                load.value *
                geometry_area
            )

            mass = force / G_MM_S2
            contribution = mass * factor

            pattern = scene.def_mgr.load_patterns.get(
                load.pattern_name
            )

            if pattern is None:
                continue

            kind = get_pattern_kind(
                pattern.design_type
            )

            if kind == "dead":

                breakdown.dead_loads += mass

                breakdown.dead_patterns[
                    load.pattern_name
                ] = (
                    breakdown.dead_patterns.get(
                        load.pattern_name,
                        0.0
                    ) + mass
                )

            elif kind == "live":

                breakdown.live_loads += mass

                breakdown.live_patterns[
                    load.pattern_name
                ] = (
                    breakdown.live_patterns.get(
                        load.pattern_name,
                        0.0
                    ) + mass
                )

            node_mass = contribution / len(nodes)

            for node in nodes:

                key = node_key_map.get(
                    getattr(node, "unique_id", None)
                )

                if key is not None:
                    node_masses[key] += node_mass

        # ----------------------------------------------------
        # UNIFORM TO FRAME
        # ----------------------------------------------------

        for load in getattr(
            area,
            "uniform_to_frame_loads",
            []
        ):

            if not is_vertical(load.direction):
                continue

            factor = factors.get(
                load.pattern_name,
                0.0
            )

            if factor <= 0.0:
                continue

            force = (
                load.value *
                geometry_area
            )

            mass = force / G_MM_S2
            contribution = mass * factor

            pattern = scene.def_mgr.load_patterns.get(
                load.pattern_name
            )

            if pattern is None:
                continue

            kind = get_pattern_kind(
                pattern.design_type
            )

            if kind == "dead":

                breakdown.dead_loads += mass

                breakdown.dead_patterns[
                    load.pattern_name
                ] = (
                    breakdown.dead_patterns.get(
                        load.pattern_name,
                        0.0
                    ) + mass
                )

            elif kind == "live":

                breakdown.live_loads += mass

                breakdown.live_patterns[
                    load.pattern_name
                ] = (
                    breakdown.live_patterns.get(
                        load.pattern_name,
                        0.0
                    ) + mass
                )

            node_mass = contribution / len(nodes)

            for node in nodes:

                key = node_key_map.get(
                    getattr(node, "unique_id", None)
                )

                if key is not None:
                    node_masses[key] += node_mass

    # --------------------------------------------------------
    # 4. NODE LOADS
    # --------------------------------------------------------

    for key, node in scene.nodes.items():

        for load in getattr(node, "loads", []):

            factor = factors.get(
                load.pattern_name,
                0.0
            )

            if factor <= 0.0:
                continue

            fz = abs(
                getattr(load, "fz", 0.0)
            )

            if fz <= 0.0:
                continue

            mass = fz / G_MM_S2
            contribution = mass * factor

            pattern = scene.def_mgr.load_patterns.get(
                load.pattern_name
            )

            if pattern is None:
                continue

            kind = get_pattern_kind(
                pattern.design_type
            )

            if kind == "dead":

                breakdown.dead_loads += mass

                breakdown.dead_patterns[
                    load.pattern_name
                ] = (
                    breakdown.dead_patterns.get(
                        load.pattern_name,
                        0.0
                    ) + mass
                )

            elif kind == "live":

                breakdown.live_loads += mass

                breakdown.live_patterns[
                    load.pattern_name
                ] = (
                    breakdown.live_patterns.get(
                        load.pattern_name,
                        0.0
                    ) + mass
                )

            node_masses[key] += contribution

    # --------------------------------------------------------
    # 5. GLOBAL MASS MATRIX
    # --------------------------------------------------------

    M_global = np.zeros(
        (num_dofs, num_dofs),
        dtype=float
    )

    for key, node in scene.nodes.items():

        mass = node_masses.get(key, 0.0)

        if mass <= 0.0:
            continue

        dofs = getattr(
            node,
            "dof_indices",
            None
        )

        if not dofs:
            continue

        for offset in (0, 1, 2):

            if offset >= len(dofs):
                continue

            dof = dofs[offset]

            if 0 <= dof < num_dofs:
                M_global[dof, dof] = mass

    return M_global, breakdown, node_masses


# ============================================================
# GERİYE DÖNÜK KOLAYLIK
# ============================================================

def compute_seismic_mass(
    scene: Scene,
    n: float = 0.3
) -> MassBreakdown:

    num_dofs = len(scene.nodes) * 6

    for i, node in enumerate(scene.nodes.values()):
        node.dof_indices = list(
            range(i * 6, i * 6 + 6)
        )

    _, breakdown, _ = build_mass_data(
        scene,
        num_dofs,
        n
    )

    return breakdown


def get_seismic_mass(
    scene: Scene,
    n: float = 0.3
) -> float:

    return compute_seismic_mass(
        scene,
        n
    ).total