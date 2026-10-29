import pytest
from pathlib import Path
from core.units import UnitSystem
from tools.s2k import S2KParser, S2KLoader


S2K_V10 = Path("tests/fixtures/s2k_v10.s2k")
S2K_V25 = Path("tests/fixtures/s2k_v25.s2k")


@pytest.mark.skipif(not S2K_V10.exists(), reason="fixture yok")
def test_import_v10_project_unit():
    loader = S2KLoader(str(S2K_V10))
    project, meta = loader.load_with_metadata()
    assert meta.curr_units_raw == "Ton. m. C"
    assert meta.unit_system == UnitSystem.TONF_M
    assert project.unit_system == UnitSystem.TONF_M, "import sonrası project birimi S2K birimi olmalı"


@pytest.mark.skipif(not S2K_V25.exists(), reason="fixture yok")
def test_import_v25_project_unit():
    loader = S2KLoader(str(S2K_V25))
    project, meta = loader.load_with_metadata()
    assert meta.curr_units_raw == "Tonf, m, C"
    assert meta.unit_system == UnitSystem.TONF_M
    assert project.unit_system == UnitSystem.TONF_M


@pytest.mark.skipif(not S2K_V25.exists(), reason="fixture yok")
def test_import_values_unchanged():
    """Import sırasında değerler dokunulmamış — snapshot karşılaştır."""
    loader = S2KLoader(str(S2K_V25))
    project, _ = loader.load_with_metadata()

    # S2K v25'te Joint 1: X=-2.7477, Y=-2.3566, Z=0
    n1 = next(iter(project.scene.nodes.values()))
    assert n1.x == pytest.approx(-2.7477, rel=1e-4)


@pytest.mark.skipif(not S2K_V25.exists(), reason="fixture yok")
def test_import_then_convert_to_nmm():
    loader = S2KLoader(str(S2K_V25))
    project, _ = loader.load_with_metadata()
    from core.units import convert_project_units
    convert_project_units(project, UnitSystem.N_MM)
    # X artık mm
    n1 = next(iter(project.scene.nodes.values()))
    assert n1.x == pytest.approx(-2747.7, rel=1e-4)