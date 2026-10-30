from types import SimpleNamespace

from data.serializer import _decode, _encode
from core.edit.edit_controller import EditController
from domain.element import Area, Frame, Link, Node, Polygon
from domain.plane import (
    INTERSECTING,
    ON_PLANE,
    OUTSIDE,
    WITHIN_DEPTH,
    Plane,
)
from domain.project import Project


def _bounded_plane(**kwargs):
    ignore_bounds = kwargs.pop("auto_assoc_ignore_bounds", False)
    plane = Plane(
        origin=(0.0, 0.0, 0.0),
        normal=(0.0, 0.0, 1.0),
        u=(1.0, 0.0, 0.0),
        v=(0.0, 1.0, 0.0),
        u_min=-1.0,
        u_max=1.0,
        v_min=-1.0,
        v_max=1.0,
        depth_minus=2.0,
        depth_plus=2.0,
        **kwargs,
    )
    plane.auto_assoc_ignore_bounds = ignore_bounds
    return plane


def _node(point):
    return Node(*point)


def test_point_and_segment_association_statuses_use_boundary_and_depth():
    plane = _bounded_plane()

    assert plane.classify_element(_node((0.5, 0.5, 0.0)), "node") == ON_PLANE
    assert plane.classify_element(_node((0.5, 0.5, 1.0)), "node") == WITHIN_DEPTH
    assert plane.classify_element(_node((2.0, 0.0, 0.0)), "node") == OUTSIDE
    assert plane.classify_element(_node((0.0, 0.0, 3.0)), "node") == OUTSIDE

    crossing_frame = Frame(
        _node((-3.0, 0.0, -1.0)),
        _node((3.0, 0.0, 1.0)),
        section=None,
    )
    crossing_outside = Link(
        _node((-3.0, 4.0, -1.0)),
        _node((3.0, 4.0, 1.0)),
    )
    coplanar_frame = Frame(
        _node((-3.0, 0.0, 0.0)),
        _node((3.0, 0.0, 0.0)),
        section=None,
    )

    assert plane.classify_element(crossing_frame, "frame") == INTERSECTING
    assert plane.classify_element(crossing_outside, "link") == OUTSIDE
    assert plane.classify_element(coplanar_frame, "frame") == ON_PLANE


def test_surface_association_uses_polygon_geometry_not_only_vertices():
    plane = _bounded_plane()
    enclosing_area = Area(
        [
            _node((-10.0, -10.0, 0.0)),
            _node((10.0, -10.0, 0.0)),
            _node((10.0, 10.0, 0.0)),
            _node((-10.0, 10.0, 0.0)),
        ],
        thickness=1.0,
    )
    crossing_polygon = Polygon(
        [
            _node((-2.0, -2.0, -1.0)),
            _node((2.0, -2.0, 1.0)),
            _node((2.0, 2.0, 1.0)),
            _node((-2.0, 2.0, -1.0)),
        ]
    )
    offset_polygon = Polygon(
        [
            _node((-10.0, -10.0, 1.0)),
            _node((10.0, -10.0, 1.0)),
            _node((10.0, 10.0, 1.0)),
            _node((-10.0, 10.0, 1.0)),
        ]
    )
    polygon_with_center_notch = Polygon(
        [
            _node((-4.0, -4.0, 1.0)),
            _node((4.0, -4.0, 1.0)),
            _node((4.0, 4.0, 1.0)),
            _node((2.0, 4.0, 1.0)),
            _node((2.0, -2.0, 1.0)),
            _node((-2.0, -2.0, 1.0)),
            _node((-2.0, 4.0, 1.0)),
            _node((-4.0, 4.0, 1.0)),
        ]
    )

    assert plane.classify_element(enclosing_area, "area") == ON_PLANE
    assert plane.classify_element(crossing_polygon, "poly") == INTERSECTING
    assert plane.classify_element(offset_polygon, "poly") == WITHIN_DEPTH
    assert plane.classify_element(polygon_with_center_notch, "poly") == OUTSIDE


def test_assoc_refresh_tracks_statuses_exclusions_and_model_changes():
    project = Project()
    plane = Plane(
        origin=(0.0, 0.0, 0.0),
        normal=(0.0, 0.0, 1.0),
        u_min=-1.0,
        u_max=1.0,
        v_min=-1.0,
        v_max=1.0,
        depth_minus=2.0,
        depth_plus=2.0,
        name="Work",
    )
    node = _node((0.0, 0.0, 0.0))
    project.scene.add_node(node)
    project.add_plane(plane)

    assert plane.associated["node"] == {node.unique_id}
    assert plane.association_of("node", node.unique_id) == ON_PLANE

    plane.remove_assoc("node", node.unique_id)
    project.scene.invalidate_plane_associations()
    project.scene.refresh_plane_associations()
    assert plane.association_of("node", node.unique_id) == ON_PLANE
    assert node.unique_id not in plane.associated["node"]

    edit = EditController(SimpleNamespace(
        scene=project.scene,
        renderer=SimpleNamespace(update_geo=lambda _scene: None),
    ))
    assert edit.update(node, {"z": 3.0}).ok
    assert project.scene._plane_associations_dirty
    project.scene.refresh_plane_associations()
    assert plane.association_of("node", node.unique_id) == OUTSIDE


def test_association_ignores_boundary_only_when_configured():
    plane = _bounded_plane(auto_assoc_ignore_bounds=True)

    assert plane.classify_element(_node((5.0, 0.0, 1.0)), "node") == WITHIN_DEPTH


def test_association_revision_changes_when_membership_changes():
    plane = _bounded_plane()
    revision = plane.association_revision

    plane.add_assoc("node", 7)
    assert plane.association_revision > revision

    revision = plane.association_revision
    plane.remove_assoc("node", 7)
    assert plane.association_revision > revision


def test_association_status_round_trips_with_plane_serialization():
    plane = _bounded_plane(name="Work")
    plane.association_status["node"][12] = ON_PLANE
    plane.association_status["frame"][13] = INTERSECTING

    revived = _decode(_encode(plane))

    assert revived.association_status["node"] == {12: ON_PLANE}
    assert revived.association_status["frame"] == {13: INTERSECTING}
    assert revived.association_counts() == {
        ON_PLANE: 1,
        INTERSECTING: 1,
        WITHIN_DEPTH: 0,
        OUTSIDE: 0,
    }


def test_scene_association_dirty_flag_is_not_persisted():
    encoded_scene = _encode(Project().scene)

    assert "_plane_associations_dirty" not in encoded_scene
