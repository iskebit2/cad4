from app.commands import project_commands as PC
from app.commands.registry import get_registry
from app.services.project_service import ProjectService
from domain.definition import (
    AreaSection,
    AreaUniformLoad,
    LinkPropLinear,
    LoadCase,
    LoadPattern,
    Material,
    PointLoad,
    Restraint,
    Section,
    StaticLoadAssignment,
)
from data.enums import LinkPropType, LoadDirection, MatType, PropAreaType, SectionType


class HeadlessContext:
    def __init__(self):
        self.engine = None
        self.ui = None
        self.edit_controller = None
        self.project_service = ProjectService(self)
        self.command_registry = get_registry()

    @property
    def current_project(self):
        return self.project_service.project


def build_structure(app=None):
    ctx = app if app is not None else HeadlessContext()
    project = ctx.current_project
    registry = ctx.command_registry

    def dispatch(command):
        result = registry.dispatch(ctx, command)
        if not result.handled:
            raise RuntimeError(result.message or f"Komut çalıştırılamadı: {command!r}")

    steel = Material(
        name="S235",
        mat_type=MatType.STEEL,
        E1=2.1e5,
        G12=8.1e4,
        nu12=0.3,
        fy=235.0,
        fu=360.0,
    )
    concrete = Material(
        name="C30",
        mat_type=MatType.CONCRETE,
        E1=3.2e4,
        G12=1.33e4,
        nu12=0.2,
        fc=30.0,
    )
    frame_section = Section(
        name="IPE300",
        material=steel,
        profile_type=SectionType.I,
        profile_params={
            "Area": 5380.0,
            "I33": 8.36e7,
            "I22": 6.04e6,
            "J": 2.01e5,
            "h": 300.0,
            "b": 150.0,
        },
    )
    area_section = AreaSection(
        name="SLAB150",
        prop_type=PropAreaType.Shell,
        area_type="Shell-Thin",
        material=concrete,
        thickness=150.0,
    )
    link_prop = LinkPropLinear(
        name="LINK1",
        prop_type=LinkPropType.LINEAR,
        Ke={
            "U1": 5.0e4,
            "U2": 1.0e3,
            "U3": 1.0e3,
            "R1": 0.0,
            "R2": 0.0,
            "R3": 0.0,
        },
    )
    dead_pattern = LoadPattern(name="DEAD", design_type="Dead", self_wt_mult=1.0)
    live_pattern = LoadPattern(name="LIVE", design_type="Live", self_wt_mult=0.0)
    dead_case = LoadCase(
        name="DEAD",
        case_type="LinStatic",
        design_type="Dead",
        static_assignments=[
            StaticLoadAssignment(load_type="Load pattern", load_name="DEAD", load_sf=1.0)
        ],
    )
    live_case = LoadCase(
        name="LIVE",
        case_type="LinStatic",
        design_type="Live",
        static_assignments=[
            StaticLoadAssignment(load_type="Load pattern", load_name="LIVE", load_sf=1.0)
        ],
    )

    for container_attr, item in (
        ("materials", steel),
        ("materials", concrete),
        ("sections", frame_section),
        ("area_sections", area_section),
        ("link_props", link_prop),
        ("load_patterns", dead_pattern),
        ("load_patterns", live_pattern),
        ("load_cases", dead_case),
        ("load_cases", live_case),
    ):
        dispatch(PC.AddDefinition(container_attr=container_attr, name=item.name, obj=item))

    model = project.math_model
    existing_node_ids = set(model.nodes)
    fixed_base = Restraint(ux=True, uy=True, uz=True, rx=True, ry=True, rz=True)

    for x, y, z, label, restraint in (
        (0.0, 0.0, 0.0, "node1", fixed_base),
        (5000.0, 0.0, 0.0, "node2", fixed_base),
        (0.0, 0.0, 3000.0, "node3", None),
        (5000.0, 0.0, 3000.0, "node4", None),
        (0.0, 4000.0, 0.0, "node5", fixed_base),
        (5000.0, 4000.0, 0.0, "node6", fixed_base),
        (0.0, 4000.0, 3000.0, "node7", None),
        (5000.0, 4000.0, 3000.0, "node8", None),
    ):
        dispatch(PC.AddNode(x=x, y=y, z=z, label=label, restraint=restraint))

    nodes = {
        node.label: node
        for uid, node in model.nodes.items()
        if uid not in existing_node_ids
    }

    frame_edges = (
        ("node1", "node2"), ("node2", "node6"),
        ("node6", "node5"), ("node5", "node1"),
        ("node3", "node4"), ("node4", "node8"),
        ("node8", "node7"), ("node7", "node3"),
        ("node1", "node3"), ("node2", "node4"),
        ("node5", "node7"), ("node6", "node8"),
    )
    for index, (node_i, node_j) in enumerate(frame_edges, start=1):
        dispatch(PC.AddFrame(
            node_i_uid=nodes[node_i].unique_id,
            node_j_uid=nodes[node_j].unique_id,
            section_name="IPE300",
            label=f"frame{index}",
        ))

    dispatch(PC.AddArea(
        node_uids=[nodes[name].unique_id for name in ("node3", "node4", "node8", "node7")],
        thickness=150.0,
        label="roof",
    ))
    roof_area = next(a for a in model.areas.values() if a.label == "roof")
    roof_area.area_section = area_section
    roof_area.section_name = area_section.name
    roof_area.material = concrete
    roof_area.mat_prop = concrete.name
    roof_area.uniform_loads.append(
        AreaUniformLoad(
            pattern_name="LIVE",
            direction=LoadDirection.GLOBAL_Z,
            value=-0.005,
            coordinate_system="GLOBAL",
            source_name="roof_live",
        )
    )

    dispatch(PC.AddLink(
        node_i_uid=nodes["node1"].unique_id,
        node_j_uid=nodes["node8"].unique_id,
        prop_name="LINK1",
        label="brace1",
    ))

    for top_label in ("node3", "node4", "node7", "node8"):
        nodes[top_label].loads.append(
            PointLoad(pattern_name="LIVE", fx=2500.0, fz=-10000.0)
        )

    model.mark_dirty()
    model.refresh_bounds()
    if ctx.engine is not None:
        ctx.engine.update_geo(project)
        ctx.engine.fit_view()

    return project

proj= build_structure()
print(proj)

from app.commands.analysis.solve_static import run_static_analysis
results = run_static_analysis(proj)

print(results)