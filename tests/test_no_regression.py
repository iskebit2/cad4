import pytest
from pathlib import Path
from core.units import UnitSystem, convert_project_units
from tools.s2k.loader import S2KLoader


FIXTURES = {
    "v10": Path("tests/fixtures/s2k_v10.s2k"),
    "v25": Path("tests/fixtures/s2k_v25.s2k"),
}


@pytest.mark.parametrize("label,path", FIXTURES.items())
def test_full_import_analysis_roundtrip(label, path):
    if not path.exists():
        pytest.skip(f"{label} fixture yok")
    loader = S2KLoader(str(path))
    p, meta = loader.load_with_metadata()
    orig_sys = p.unit_system
    orig_snapshot = _snapshot(p)

    # N_MM'ye çevir (solver)
    convert_project_units(p, UnitSystem.N_MM, reason="solver")
    # Geri dön
    convert_project_units(p, orig_sys, reason="restore")

    # Tüm değerler korunmuş mu?
    for k, v in _snapshot(p).items():
        assert v == pytest.approx(orig_snapshot[k], rel=1e-9), f"{label}:{k}"


def _snapshot(p):
    """S2K projesi için minimal snapshot."""
    n = next(iter(p.scene.nodes.values()))
    f = next(iter(p.scene.frames.values())) if p.scene.frames else None
    m = next(iter(p.materials.values())) if p.materials else None
    return {
        "node_x": n.x, "node_y": n.y, "node_z": n.z,
        "E1": m.E1 if m else 0,
        "frame_len": f.get_length() if f else 0,
    }