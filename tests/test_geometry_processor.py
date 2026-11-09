import numpy as np

from domain.grid import Axis
from domain.element import Frame, Node
from domain.line import Line
from domain.polygon import Polygon
from domain.vertex import Vertex
from geometry.geometry_processor import GeometryProcessor
from plane.plane import Plane
from plane.plane_policy import SectionFilterMode


def _clip_plane(mode=SectionFilterMode.CLIP):
    return Plane.from_axis_offset(
        "z",
        0.0,
        u_min=-1.0,
        u_max=1.0,
        v_min=-1.0,
        v_max=1.0,
        depth_minus=1.0,
        depth_plus=1.0,
        filter_mode=mode,
    )


def _coords(point):
    return np.asarray(point.coords, dtype=float)


def test_clip_line_returns_clipped_copy_without_mutating_source():
    line = Line(v1=Vertex(-2.0, 0.0, 0.0), v2=Vertex(2.0, 0.0, 0.0))

    result = GeometryProcessor.process_lines([line], _clip_plane())

    assert len(result) == 1
    assert result[0] is not line
    assert np.allclose(_coords(result[0].v1), (-1.0, 0.0, 0.0))
    assert np.allclose(_coords(result[0].v2), (1.0, 0.0, 0.0))
    assert np.allclose(_coords(line.v1), (-2.0, 0.0, 0.0))
    assert np.allclose(_coords(line.v2), (2.0, 0.0, 0.0))


def test_clip_frame_crops_structural_endpoints_without_mutating_source():
    frame = Frame(
        node_i=Node(-2.0, 0.0, 0.0),
        node_j=Node(2.0, 0.0, 0.0),
        section=None,
    )

    result = GeometryProcessor.process_lines([frame], _clip_plane())

    assert len(result) == 1
    assert result[0] is not frame
    assert np.allclose(_coords(result[0].node_i), (-1.0, 0.0, 0.0))
    assert np.allclose(_coords(result[0].node_j), (1.0, 0.0, 0.0))
    assert np.allclose(_coords(frame.node_i), (-2.0, 0.0, 0.0))
    assert np.allclose(_coords(frame.node_j), (2.0, 0.0, 0.0))


def test_clip_polygon_crops_bounds_and_preserves_source():
    polygon = Polygon(nodes=[
        Vertex(-2.0, -2.0, 0.0),
        Vertex(2.0, -2.0, 0.0),
        Vertex(2.0, 2.0, 0.0),
        Vertex(-2.0, 2.0, 0.0),
    ])

    result = GeometryProcessor.process_polygons([polygon], _clip_plane())

    assert len(result) == 1
    assert result[0] is not polygon
    clipped_coords = np.asarray([_coords(node) for node in result[0].nodes])
    expected_coords = np.asarray([
        (-1.0, -1.0, 0.0), (1.0, -1.0, 0.0),
        (1.0, 1.0, 0.0), (-1.0, 1.0, 0.0),
    ])
    assert np.allclose(
        clipped_coords[np.lexsort(clipped_coords.T[::-1])],
        expected_coords[np.lexsort(expected_coords.T[::-1])],
    )
    assert np.allclose(
        np.asarray([_coords(node) for node in polygon.nodes]),
        ((-2.0, -2.0, 0.0), (2.0, -2.0, 0.0),
         (2.0, 2.0, 0.0), (-2.0, 2.0, 0.0)),
    )


def test_intersect_polygon_filter_accepts_numpy_backed_coordinates():
    polygon = Polygon(nodes=[
        Vertex(-0.5, -0.5, 0.0),
        Vertex(0.5, -0.5, 0.0),
        Vertex(0.5, 0.5, 0.0),
        Vertex(-0.5, 0.5, 0.0),
    ])
    plane = _clip_plane(SectionFilterMode.INTERSECT)

    assert GeometryProcessor.process_polygons([polygon], plane) == [polygon]


def test_clip_grid_axis_updates_segment_without_mutating_axis():
    axis = Axis(
        origin=(0.0, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
        length=2.0,
    )

    result = GeometryProcessor.process_grid_axes(
        type("GridData", (), {"axes": [axis]})(), _clip_plane(),
    )

    assert len(result) == 1
    assert result[0] is not axis
    assert np.allclose(result[0].start_point(), (-1.0, 0.0, 0.0))
    assert np.allclose(result[0].end_point(), (1.0, 0.0, 0.0))
    assert axis.length == 2.0


def test_strict_mode_requires_whole_segment_inside_plane():
    line = Line(v1=Vertex(-2.0, 0.0, 0.0), v2=Vertex(0.0, 0.0, 0.0))

    assert GeometryProcessor.process_lines(
        [line], _clip_plane(SectionFilterMode.STRICT),
    ) == []
