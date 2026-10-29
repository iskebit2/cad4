from unittest.mock import MagicMock
from core.units import UnitSystem


def test_cad_app_set_unit_system(make_project):
    """cad_app.set_unit_system gerçekten dönüştürüyor mu?"""
    from app.cad_app import CadApp
    p = make_project(UnitSystem.N_MM)
    app = MagicMock()
    app.current_project = p
    app.engine = None

    CadApp.set_unit_system(app, UnitSystem.TONF_M)
    assert p.unit_system == UnitSystem.TONF_M