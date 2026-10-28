import queue
import time

import numpy as np

from app.cad_app import CadApp
from data.serializer import _decode, _encode
from domain.definition import WindDirectionResult
from domain.element import Area, Node
from domain.project import Project
from structload.windcalc.zone import Zone
from tools.wind_scene_adapter import WindSceneAdapter
from ui.zones_panel import ZonesPanel


def _project_with_roof():
    project = Project()
    nodes = [
        Node(0, 0, 5000, label="N1"),
        Node(5000, 0, 5000, label="N2"),
        Node(5000, 5000, 5000, label="N3"),
        Node(0, 5000, 5000, label="N4"),
    ]
    for node in nodes:
        project.scene.add_node(node)
    project.scene.add_area(Area(nodes, thickness=100, label="Roof"))
    return project


def test_build_inputs_converts_scene_lengths_to_meters():
    project = _project_with_roof()

    points, polygons, wind_config = WindSceneAdapter.build_inputs(
        project.scene, project
    )

    assert next(iter(points.values())) == [0.0, 0.0, 5.0]
    assert len(polygons) == 1
    assert wind_config["terrain"] == "Kategori III"
    assert wind_config["v_b0"] == project.config.wind.vb0


def test_wind_analysis_zones_are_stored_without_mutating_scene(tmp_path):
    project = _project_with_roof()
    points, polygons, wind_config = WindSceneAdapter.build_inputs(
        project.scene, project
    )
    zones, engine_data = WindSceneAdapter.analyze(
        points, polygons, wind_config, (1.0, 0.0, 0.0)
    )

    assert zones
    original_nodes = set(project.scene.nodes)
    original_polygons = set(project.scene.polygons)
    WindSceneAdapter.store_zones(project, "01", zones)

    assert set(project.scene.nodes) == original_nodes
    assert set(project.scene.polygons) == original_polygons
    assert project.loads.wind_zones["01"] == zones

    restored_loads = _decode(_encode(project.loads))
    restored_zone = restored_loads.wind_zones["01"][0]
    assert isinstance(restored_zone, Zone)
    assert np.array_equal(restored_zone.coords, zones[0].coords)

    project_path = tmp_path / "wind.cd4"
    project.save(str(project_path))
    loaded_project = Project.load(str(project_path))
    assert isinstance(loaded_project.loads.wind_zones["01"][0], Zone)
    assert np.array_equal(
        loaded_project.loads.wind_zones["01"][0].coords, zones[0].coords
    )

def test_wall_zone_scalar_coefficients_are_saved_as_pairs():
    project = Project()
    nodes = [
        Node(0, 0, 0),
        Node(0, 5000, 0),
        Node(0, 5000, 5000),
        Node(0, 0, 5000),
    ]
    for node in nodes:
        project.scene.add_node(node)
    project.scene.add_area(Area(nodes, thickness=100, label="Wall"))
    points, polygons, wind_config = WindSceneAdapter.build_inputs(
        project.scene, project
    )
    zones, engine_data = WindSceneAdapter.analyze(
        points, polygons, wind_config, (1.0, 0.0, 0.0)
    )

    assert zones
    WindSceneAdapter.store_zones(project, "01", zones)
    WindSceneAdapter.update_direction_result(
        WindDirectionResult(w_dir=(1.0, 0.0, 0.0)), zones, engine_data
    )

    assert isinstance(WindSceneAdapter._coefficient_pair(zones[0].cpe10), tuple)
    assert len(WindSceneAdapter._coefficient_pair(zones[0].cpe10)) == 2


def test_wind_panel_callbacks_are_wired_without_frame_distribution():
    app = CadApp.__new__(CadApp)
    panel = ZonesPanel()
    app.panels = {"wind": {"instance": panel}}

    app._wire_panel_hooks()

    assert panel.on_run_analysis.__self__ is app
    assert panel.on_select_direction.__self__ is app
    assert panel.on_distribute is None


def test_run_callback_analyzes_and_saves_zones_to_project_loads(tmp_path):
    app = CadApp.__new__(CadApp)
    app.current_project = _project_with_roof()
    app.engine = None
    app._wind_queue = queue.Queue()
    app._wind_analysis_generation = 0
    app._wind_analysis_status = ""
    panel = ZonesPanel()
    app.panels = {"wind": {"instance": panel}}
    app._wire_panel_hooks()

    panel.on_run_analysis()
    deadline = time.monotonic() + 10
    while app._wind_queue.empty() and time.monotonic() < deadline:
        time.sleep(0.01)

    assert not app._wind_queue.empty()
    before_nodes = set(app.current_project.scene.nodes)
    before_polygons = set(app.current_project.scene.polygons)
    app._process_wind_queue()
    assert app.current_project.loads.wind_zones["01"]
    assert "bölgesi hesaplandı" in app._wind_analysis_status
    assert set(app.current_project.scene.nodes) == before_nodes
    assert set(app.current_project.scene.polygons) == before_polygons

    project_path = tmp_path / "wind.cd4"
    app.current_project.save(str(project_path))
    loaded_project = Project.load(str(project_path))
    assert isinstance(
        loaded_project.analysis.wind["directions"]["01"], WindDirectionResult
    )


def test_wind_analysis_state_contains_a_default_direction():
    app = CadApp.__new__(CadApp)
    app.current_project = Project()

    state = app._wind_analysis_state()

    assert state["active_direction"] == (1.0, 0.0, 0.0)
    assert isinstance(state["directions"]["01"], WindDirectionResult)


def test_zones_panel_reads_active_zone_objects_from_project_loads():
    project = _project_with_roof()
    points, polygons, wind_config = WindSceneAdapter.build_inputs(
        project.scene, project
    )
    zones, engine_data = WindSceneAdapter.analyze(
        points, polygons, wind_config, (1.0, 0.0, 0.0)
    )
    WindSceneAdapter.store_zones(project, "01", zones)
    panel = ZonesPanel()
    panel.project = project
    panel.wind_analysis_ref = {
        "directions": {"01": WindDirectionResult(w_dir=(1.0, 0.0, 0.0))},
        "active_direction": (1.0, 0.0, 0.0),
    }

    assert panel._collect_zones() == zones
    assert not project.scene.polygons
