import pytest

from core.units import UnitSystem
from domain.definition import (
    AreaUniformLoad,
    DistType,
    LoadDirection,
    LoadPattern,
)
from domain.element import Node, Polygon
from domain.project import Project
from ui.load_assign_panel import LoadAssignPanel


def _polygon(label, offset=0.0):
    return Polygon(
        [
            Node(offset, 0.0, 0.0),
            Node(offset + 1000.0, 0.0, 0.0),
            Node(offset + 1000.0, 1000.0, 0.0),
            Node(offset, 1000.0, 0.0),
        ],
        label=label,
    )


def _panel_for(project, polygons):
    panel = LoadAssignPanel()
    panel.set_context({
        "project": project,
        "selection_polygons": polygons,
    })
    panel.open()
    return panel


def _preset_key(panel, preset_name):
    for category_id, _label, _load_type, items in panel._categories:
        for index, item in enumerate(items):
            if item["name"] == preset_name:
                return category_id, index
    raise AssertionError(f"Preset not found: {preset_name}")


def test_assigning_prepared_dead_load_to_polygon_converts_project_units():
    project = Project()
    polygon = _polygon("Slab")
    panel = _panel_for(project, [polygon])
    panel._selected_presets.add(_preset_key(panel, "Marley Kaplama"))

    assigned_count = panel._apply_selected_presets()

    assert assigned_count == 1
    assert len(polygon.assigned_loads) == 1
    load = polygon.assigned_loads[0]
    assert isinstance(load, AreaUniformLoad)
    assert load.pattern_name == "DEAD"
    assert load.direction is LoadDirection.GRAVITY
    assert load.source_name == "Marley Kaplama"
    assert load.value == pytest.approx(0.0014)  # kN/m² -> N/mm²
    assert project.load_patterns["DEAD"] == LoadPattern(
        name="DEAD", design_type="Dead",
    )
    transfers = project.loads.area_load_transfers_for_polygon(
        polygon.unique_id,
    )
    assert len(transfers) == 1
    assert transfers[0]["source_type"] == "uniform"
    assert transfers[0]["transfer_target"] == "frames"
    assert transfers[0]["dist_type"] == DistType.ONE_WAY_U1.value
    assert transfers[0]["load"].source_name == "Marley Kaplama"


def test_assigning_multiple_prepared_loads_targets_all_selected_polygons():
    project = Project()
    project.unit_system = UnitSystem.KN_M
    first = _polygon("Slab A")
    second = _polygon("Slab B", offset=2000.0)
    panel = _panel_for(project, [first, second])
    panel._selected_presets.update({
        _preset_key(panel, "Marley Kaplama"),
        _preset_key(panel, "Konut, teras, oda ve koridorlar"),
    })
    panel._distribution_type_index = 2

    assigned_count = panel._apply_selected_presets()

    assert assigned_count == 4
    for polygon in (first, second):
        assert len(polygon.assigned_loads) == 2
        by_pattern = {
            load.pattern_name: load.value for load in polygon.assigned_loads
        }
        assert by_pattern["DEAD"] == pytest.approx(1.4)
        assert by_pattern["LIVE"] == pytest.approx(1.96)
    assert project.load_patterns["DEAD"].design_type == "Dead"
    assert project.load_patterns["LIVE"].design_type == "Live"
    assert all(
        transfer["dist_type"] == DistType.TWO_WAY.value
        for polygon in (first, second)
        for transfer in project.loads.area_load_transfers_for_polygon(
            polygon.unique_id,
        )
    )


def test_prepared_polygon_load_assignments_survive_project_round_trip(tmp_path):
    project = Project()
    polygon = _polygon("Slab")
    project.scene.add_polygon(polygon)
    panel = _panel_for(project, [polygon])
    panel._selected_presets.add(_preset_key(panel, "Marley Kaplama"))
    panel._apply_selected_presets()

    filepath = tmp_path / "polygon-loads.cd4"
    project.save(str(filepath))
    restored = Project.load(str(filepath))
    restored_polygon = next(iter(restored.scene.polygons.values()))

    assert len(restored_polygon.assigned_loads) == 1
    assert restored_polygon.assigned_loads[0].pattern_name == "DEAD"
    assert restored_polygon.assigned_loads[0].source_name == "Marley Kaplama"
    assert restored_polygon.assigned_loads[0].value == pytest.approx(0.0014)
    transfers = restored.loads.area_load_transfers_for_polygon(
        restored_polygon.unique_id,
    )
    assert len(transfers) == 1
    assert transfers[0]["load"].source_name == "Marley Kaplama"
    assert transfers[0]["transfer_target"] == "frames"
