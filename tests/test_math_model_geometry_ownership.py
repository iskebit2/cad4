import json
import logging
import zipfile

from data.serializer import load_project_file, save_project_file
from domain.element import Area, Frame, Link, Node
from domain.definition import ConstraintDefinition
from domain.line import Line
from domain.polygon import Polygon
from domain.project import Project
from domain.vertex import Vertex
from geometry.geometry_processor import GeometryProcessor


def _project_with_six_elements():
    project = Project()
    model = project.math_model
    nodes = [Node(0, 0, 0), Node(10, 0, 0), Node(10, 10, 0)]
    for node in nodes:
        model.add_node(node)

    model.add_frame(Frame(node_i=nodes[0], node_j=nodes[1]))
    area = Area(nodes=nodes)
    area.thickness = 1.0
    model.add_area(area)
    model.add_link(Link(node_i=nodes[1], node_j=nodes[2]))
    project.add_polygon(Polygon(nodes))
    project.add_line(Line(v1=Vertex(20, 0, 0), v2=Vertex(30, 0, 0)))
    project.add_constraint_definition(ConstraintDefinition(name="C1"))
    return project


def test_six_geometry_types_share_math_model_ownership_and_bounds():
    project = _project_with_six_elements()
    model = project.math_model

    assert len(model.all_elements) == 8
    assert set(model.polygons) == {
        element.unique_id for element in model.all_elements.values()
        if isinstance(element, Polygon)
    }
    assert set(model.lines) == {
        element.unique_id for element in model.all_elements.values()
        if isinstance(element, Line)
    }
    assert not hasattr(project.scene, "polygons")
    assert not hasattr(project.scene, "lines")
    assert model.bounds.min[0] == 0
    assert model.bounds.max[0] == 30


def test_geometry_processor_prepares_polygon_and_line_from_math_model():
    project = _project_with_six_elements()
    logger = logging.getLogger("cad.geometry.geometry_processor")
    was_disabled = logger.disabled
    logger.disabled = True
    try:
        geometry = GeometryProcessor.process(
            project.scene, math_model=project.math_model,
        )
    finally:
        logger.disabled = was_disabled

    assert geometry.polygons == list(project.math_model.polygons.values())
    assert geometry.lines == list(project.math_model.lines.values())


def test_serializer_stores_geometry_in_math_model_and_reads_legacy_scene_fields(
    tmp_path,
):
    project = _project_with_six_elements()
    path = tmp_path / "geometry.cd4"
    save_project_file(project, path)

    loaded = load_project_file(path)
    assert len(loaded.math_model.nodes) == 3
    assert len(loaded.math_model.frames) == 1
    assert len(loaded.math_model.areas) == 1
    assert len(loaded.math_model.links) == 1
    assert len(loaded.math_model.polygons) == 1
    assert len(loaded.math_model.lines) == 1
    assert set(loaded.constraint_definitions) == {"C1"}
    loaded_frame = next(iter(loaded.math_model.frames.values()))
    assert loaded_frame.node_i is loaded.math_model.nodes[loaded_frame.node_i.unique_id]
    assert loaded_frame.node_j is loaded.math_model.nodes[loaded_frame.node_j.unique_id]

    with zipfile.ZipFile(path, "r") as source:
        payload = json.loads(source.read("project.json"))

    def as_version_8(value):
        if isinstance(value, list):
            return [as_version_8(item) for item in value]
        if not isinstance(value, dict):
            return value
        converted = {key: as_version_8(item) for key, item in value.items()}
        object_type = converted.pop("__object__", None)
        if object_type in {"Node", "Frame", "Area", "Link"}:
            converted["__dataclass__"] = object_type
        return converted

    version_8_payload = as_version_8(payload)
    version_8_payload["version"] = 8
    version_8_path = tmp_path / "version_8.cd4"
    with zipfile.ZipFile(version_8_path, "w", zipfile.ZIP_DEFLATED) as target:
        target.writestr("project.json", json.dumps(version_8_payload))

    version_8_loaded = load_project_file(version_8_path)
    assert len(version_8_loaded.math_model.nodes) == 3
    assert len(version_8_loaded.math_model.frames) == 1

    payload["scene"]["polygons"] = payload["math_model"].pop("polygons")
    payload["scene"]["lines"] = payload["math_model"].pop("lines")
    legacy_path = tmp_path / "legacy.cd4"
    with zipfile.ZipFile(legacy_path, "w", zipfile.ZIP_DEFLATED) as target:
        target.writestr("project.json", json.dumps(payload))

    legacy_loaded = load_project_file(legacy_path)
    assert len(legacy_loaded.math_model.polygons) == 1
    assert len(legacy_loaded.math_model.lines) == 1
