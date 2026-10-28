import pytest

from structload.windcalc.wind_analyzer import (
    ZONE_LABELS as ANALYZER_ZONE_LABELS,
    ZoneKind as AnalyzerZoneKind,
)
from structload.windcalc.zone_generator import (
    ZONE_LABELS as GENERATOR_ZONE_LABELS,
    ZoneKind as GeneratorZoneKind,
)


@pytest.mark.parametrize("table_type", ["MONOPITCH", "DUOPITCH", "HIPPED"])
def test_windward_non_corner_turbulence_strip_is_zone_g(table_type):
    assert GENERATOR_ZONE_LABELS[
        (table_type, "WINDWARD", GeneratorZoneKind.TURBULENCE_SLOP)
    ] == "G"
    assert ANALYZER_ZONE_LABELS[
        (table_type, "WINDWARD", AnalyzerZoneKind.TURBULENCE_SLOP)
    ] == "G"
