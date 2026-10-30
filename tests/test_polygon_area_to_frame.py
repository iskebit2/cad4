import pytest
import numpy as np

from core.units import Dimension, UnitSystem, convert_value
from data.enums import DistType, LoadDirection
from domain.definition import (
    AreaUniformLoad,
    FrameDistributedLoad,
    LoadSegment,
    WindResult,
)
from domain.element import Frame, Node, Polygon
from domain.project import Project
from domain.polygon_load_transfer import (
    build_polygon_frame_loads,
    transfer_polygon_loads_to_frames,
)
from inspector.window import InspectorWindow
from ui.area_to_frame_panel import AreaToFramePanel
from ui.adapters import polygon_to_values
from structload.windcalc.zone import Zone


def _polygon():
    return Polygon(
        [
            Node(0, 0, 0),
            Node(10, 0, 0),
            Node(10, 4, 0),
            Node(0, 4, 0),
        ],
        label="Slab",
    )


def _frame(y, *, x1=0, x2=10):
    return Frame(
        Node(x1, y, 0),
        Node(x2, y, 0),
        section=None,
        label=f"Beam {y}",
    )


def _configured_project():
    project = Project()
    polygon = _polygon()
    first = _frame(1)
    second = _frame(3)
    unrelated = _frame(2, x1=20, x2=30)
    for frame in (first, second, unrelated):
        project.scene.add_frame(frame)
    project.scene.add_polygon(polygon)
    polygon.associated_frame_ids = [first.unique_id, second.unique_id]
    project.loads.add_area_load_transfer(
        polygon,
        AreaUniformLoad(
            pattern_name="DEAD",
            direction=LoadDirection.GRAVITY,
            value=2.0,
            source_name="Roof load",
        ),
    )
    return project, polygon, first, second, unrelated


def test_one_way_transfer_uses_only_associated_frames_and_conserves_load():
    project, polygon, first, second, unrelated = _configured_project()
    polygon.transfer_dist_type = DistType.ONE_WAY_U1

    generated = build_polygon_frame_loads(project.scene, polygon)

    assert set(generated) == {first.unique_id, second.unique_id}
    assert unrelated.dist_load_sets == {}
    total_frame_force = sum(
        load.segments[0].q1 * 10.0
        for pattern_loads in generated.values()
        for load in pattern_loads.values()
    )
    assert total_frame_force == pytest.approx(80.0)
    assert generated[first.unique_id]["DEAD"].segments[0].q1 == pytest.approx(4.0)
    assert generated[second.unique_id]["DEAD"].segments[0].q1 == pytest.approx(4.0)


def test_two_way_transfer_conserves_load_and_records_frame_contributions():
    project, polygon, first, second, _ = _configured_project()
    polygon.transfer_dist_type = DistType.TWO_WAY

    generated = transfer_polygon_loads_to_frames(project.scene, polygon)

    assert set(generated) == {first.unique_id, second.unique_id}
    assert first.dist_load_sets["DEAD"].segments[0].q1 == pytest.approx(4.0)
    assert second.dist_load_sets["DEAD"].segments[0].q1 == pytest.approx(4.0)
    assert len(project.loads.area_frame_transfers) == 2
    assert all(
        item["polygon_id"] == polygon.unique_id
        for item in project.loads.area_frame_transfers
    )
    assert all(
        item["transferred_frame_ids"] == [first.unique_id, second.unique_id]
        for item in project.loads.area_load_transfers_for_polygon(
            polygon.unique_id,
        )
    )


def test_reapplying_transfer_does_not_duplicate_segments_and_restores_removed_target():
    project, polygon, first, second, _ = _configured_project()
    first.dist_load_sets["DEAD"] = FrameDistributedLoad(
        pattern_name="DEAD",
        segments=[LoadSegment(x1=0.0, x2=1.0, q1=1.0, q2=1.0)],
    )

    transfer_polygon_loads_to_frames(project.scene, polygon)
    transfer_polygon_loads_to_frames(project.scene, polygon)

    assert len(first.dist_load_sets["DEAD"].segments) == 2
    assert first.dist_load_sets["DEAD"].segments[0].q1 == pytest.approx(1.0)
    assert len(second.dist_load_sets["DEAD"].segments) == 1

    polygon.associated_frame_ids = [first.unique_id]
    transfer_polygon_loads_to_frames(project.scene, polygon)

    assert len(first.dist_load_sets["DEAD"].segments) == 2
    assert second.unique_id not in {
        item["frame_id"] for item in project.loads.area_frame_transfers
    }


def test_transfer_requires_user_associated_frames():
    project = Project()
    polygon = _polygon()
    polygon.assigned_loads.append(AreaUniformLoad(pattern_name="DEAD", value=1))
    project.scene.add_polygon(polygon)

    with pytest.raises(ValueError, match="frame'leri seçin"):
        build_polygon_frame_loads(project.scene, polygon)


def test_load_manager_preserves_one_way_u2_distribution_choice():
    project = Project()
    polygon = _polygon()
    project.loads.add_area_load_transfer(
        polygon,
        AreaUniformLoad(pattern_name="LIVE", value=1),
        dist_type=DistType.ONE_WAY_U2,
    )

    assert polygon.transfer_dist_type == DistType.ONE_WAY_U2.value
    assert project.loads.area_load_transfers[0]["dist_type"] == (
        DistType.ONE_WAY_U2.value
    )


@pytest.mark.parametrize(
    ("unit_system", "expected_value"),
    [
        (UnitSystem.KN_M, 1.4),
        (UnitSystem.N_MM, 0.0014),
        (
            UnitSystem.TONF_M,
            convert_value(
                Dimension.AREA_LOAD, 1.4, UnitSystem.KN_M,
                UnitSystem.TONF_M,
            ),
        ),
    ],
)
def test_preset_area_load_is_stored_in_current_project_units(
    unit_system, expected_value,
):
    from ui.load_assign_panel import LoadAssignPanel

    project = Project()
    project.unit_system = unit_system
    polygon = _polygon()
    panel = LoadAssignPanel()
    panel.set_context({
        "project": project,
        "selection_polygons": [polygon],
    })
    panel.open()
    for category_id, _, _, items in panel._categories:
        for index, item in enumerate(items):
            if item["name"] == "Marley Kaplama":
                panel._selected_presets.add((category_id, index))
    panel._apply_selected_presets()

    assert polygon.assigned_loads[0].value == pytest.approx(expected_value)


def test_boundary_associated_frame_receives_full_tributary_load():
    project = Project()
    polygon = _polygon()
    edge_frame = _frame(0)
    project.scene.add_polygon(polygon)
    project.scene.add_frame(edge_frame)
    polygon.associated_frame_ids = [edge_frame.unique_id]
    polygon.assigned_loads = [
        AreaUniformLoad(pattern_name="LIVE", value=2.0),
    ]

    generated = build_polygon_frame_loads(project.scene, polygon)

    load = generated[edge_frame.unique_id]["LIVE"]
    assert load.segments[0].q1 == pytest.approx(8.0)
    assert (load.segments[0].x1, load.segments[0].x2) == pytest.approx((0, 1))


def test_transfer_rejects_non_planar_polygons():
    project, polygon, *_ = _configured_project()
    polygon.nodes[2].z = 1.0

    with pytest.raises(ValueError, match="düzlemsel olmayan"):
        build_polygon_frame_loads(project.scene, polygon)


@pytest.mark.parametrize(
    "unit_system",
    [UnitSystem.KN_M, UnitSystem.N_MM, UnitSystem.TONF_M],
)
def test_wind_zone_transfer_converts_from_kn_m_and_uses_associated_frames(
    unit_system,
):
    project, surface, first, second, unrelated = _configured_project()
    project.unit_system = unit_system
    length_factor = convert_value(
        Dimension.LENGTH, 1.0, UnitSystem.N_M, unit_system,
    )
    for node in surface.nodes + [
        first.node_i, first.node_j, second.node_i, second.node_j,
        unrelated.node_i, unrelated.node_j,
    ]:
        node._x *= length_factor
        node._y *= length_factor
        node._z *= length_factor
    surface.associated_frame_ids = [first.unique_id, second.unique_id]
    project.loads.wind_results["01"] = WindResult(
        direction=(1.0, 0.0, 0.0),
        q_p=0.8,
    )
    zone = Zone(
        label="D",
        coords=np.asarray([
            [0.0, 0.0, 0.0],
            [10.0, 0.0, 0.0],
            [10.0, 4.0, 0.0],
            [0.0, 4.0, 0.0],
        ]),
        surface=f"POLYGON_{surface.unique_id}",
        table_type="WALL",
        table_type_dir=0,
        pitch=0.0,
    )
    zone._interpolate = lambda _: (-0.8, 0.7)
    project.loads.wind_zones["01"] = [zone]
    panel = AreaToFramePanel()
    panel.set_context({
        "project": project,
        "scene": project.scene,
        "selection_polygons": [surface],
    })

    segments = panel._transfer_wind_zone(surface, "01", 0, zone)
    panel._transfer_wind_zone(surface, "01", 0, zone)

    assert segments == 8
    assert unrelated.dist_load_sets == {}
    assert set(first.dist_load_sets) == {
        "WIND_01_CPE10_MN_P", "WIND_01_CPE10_MN_M",
        "WIND_01_CPE10_MX_P", "WIND_01_CPE10_MX_M",
    }
    assert all(
        load_set.coord_sys == "Local" and load_set.load_dir == "2"
        for frame in (first, second)
        for load_set in frame.dist_load_sets.values()
    )
    assert all(
        len(load_set.segments) == 1
        for frame in (first, second)
        for load_set in frame.dist_load_sets.values()
    )
    expected_area_pressure = convert_value(
        Dimension.AREA_LOAD, -0.8, UnitSystem.KN_M, unit_system,
    )
    assert first.dist_load_sets[
        "WIND_01_CPE10_MN_P"
    ].segments[0].q1 == pytest.approx(
        expected_area_pressure * 2.0 * length_factor,
    )
    transfer = next(
        item for item in project.loads.area_load_transfers
        if item["source_type"] == "wind_zone"
    )
    assert transfer["zone_label"] == "D"
    assert transfer["direction_key"] == "01"


def test_panel_registration_inspector_and_load_manager_round_trip(tmp_path):
    from app.panel_registry import PANEL_SPECS
    from data.serializer import load_project_file, save_project_file

    project, polygon, first, *_ = _configured_project()
    panel = AreaToFramePanel()
    panel.set_context({
        "project": project,
        "scene": project.scene,
        "selection_polygons": [polygon],
    })
    panel._transfer(polygon)

    assert any(item["name"] == "area_to_frame" for item in PANEL_SPECS)
    assert polygon_to_values(polygon)["assigned_loads_summary"] == [
        "Roof load | DEAD | 2 (GRAV)"
    ]
    inspector = InspectorWindow(scene=project.scene)
    inspector.set_context({"project": project})
    inspector.controller.set_selection([polygon])
    assert inspector._values_for_selection()["area_load_transfer_summary"]

    project.loads.wind_results["01"] = WindResult(
        direction=(1.0, 0.0, 0.0),
        q_p=0.8,
        zones_cpe10=[{"label": "D", "cpe": [-0.8, 0.7]}],
    )
    filepath = tmp_path / "area-frame.cd4"
    save_project_file(project, str(filepath))
    restored = load_project_file(str(filepath))

    assert restored.scene.frames[first.unique_id].dist_load_sets["DEAD"]
    assert len(restored.loads.area_frame_transfers) == 2
    assert restored.loads.wind_results["01"].q_p == pytest.approx(0.8)
