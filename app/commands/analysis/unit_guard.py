# core/analysis/unit_guard.py
from core.units import UnitSystem, convert_project_units


def ensure_nmm(project) -> None:
    """Solver öncesi project'i N_MM'ye çevir."""
    if project.unit_system != UnitSystem.N_MM:
        convert_project_units(project, UnitSystem.N_MM, reason="solver")