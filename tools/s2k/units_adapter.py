# tools/s2k/units_adapter.py
"""
Birim dönüşümü TEK kaynaktan: core.units.
Bu modül sadece S2K handler'larına kısayol sağlar.
"""
from core.units import (
    UnitConverter,
    UnitSystem,
    UnitRegistry,
    validate_section_properties,
    G_MM_S2,
)

__all__ = [
    "UnitConverter", "UnitSystem", "UnitRegistry",
    "validate_section_properties", "G_MM_S2",
]