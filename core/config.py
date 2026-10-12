from dataclasses import dataclass, field


@dataclass
class WindConfig:
    # TS EN 1991-1-4
    vb0: float = 28.0
    terrain_category: str = "III"
    z0: float = 0.0
    z1: float = 5.27
    z2: float = 6.92
    cpi_positive: float = 0.2
    cpi_negative: float = -0.3


@dataclass
class SnowConfig:
    # TS EN 1991-1-3
    sk: float = 0.75
    exposure_coefficient: float = 1.0
    thermal_coefficient: float = 1.0
    shape_coefficient: float = 0.8


@dataclass
class SeismicConfig:
    # TBDY 2018
    ss: float = 0.0
    s1: float = 0.0
    soil_class: str = "ZD"
    importance_factor: float = 1.0
    building_height_class: str = ""
    behavior_factor: float = 8.0
    overstrength_factor: float = 3.0


@dataclass
class ProjectConfig:
    wind: WindConfig = field(default_factory=WindConfig)
    snow: SnowConfig = field(default_factory=SnowConfig)
    seismic: SeismicConfig = field(default_factory=SeismicConfig)
