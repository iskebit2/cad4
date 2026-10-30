from types import SimpleNamespace

from core.plane_draw_manager import PlaneCreationTool
from domain.element import Node
from domain.plane import Plane
from domain.project import Project


def test_three_point_tool_registers_completed_plane_with_manager():
    project = Project()
    project.add_plane(
        Plane(origin=(0.0, 0.0, 0.0), normal=(0.0, 0.0, 1.0), name="Plane_1")
    )
    tool = PlaneCreationTool.__new__(PlaneCreationTool)
    tool.engine = SimpleNamespace(scene=project.scene)
    tool.p0 = Node(0.0, 0.0, 0.0)
    tool.p1 = Node(20.0, 0.0, 0.0)
    tool.p2 = Node(0.0, 30.0, 0.0)
    for node in (tool.p0, tool.p1, tool.p2):
        project.scene.add_node(node)
    tool.depth_plus = 500.0
    tool.depth_minus = 500.0
    tool.completed_plane = None
    tool.is_active = True
    tool.hover_node = None
    tool._last_mouse_y = None

    tool._confirm()

    plane = tool.completed_plane
    assert plane is not None
    assert plane.name == "Plane_2"
    assert project.plane_mgr.get(plane.name) is plane
    assert len(plane.associated["node"]) == 3
    assert not tool.is_active
