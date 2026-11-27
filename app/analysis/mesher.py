# app/analysis/mesher.py
from __future__ import annotations

import math
from dataclasses import dataclass, field

from domain.definition import FrameDistributedLoad, FrameGravityLoad, LoadSegment
from domain.element import Area, Frame, Link, Node

_DEFAULT_MESH_MAX_LENGTH = 1000.0


@dataclass
class SolverMesh:
    nodes: dict[str, Node] = field(default_factory=dict)
    frames: dict[str, Frame] = field(default_factory=dict)
    areas: dict[str, Area] = field(default_factory=dict)
    links: dict[str, Link] = field(default_factory=dict)
    frame_children: dict[int, list[str]] = field(default_factory=dict)
    parent_frame_id: dict[str, int] = field(default_factory=dict)
    internal_node_keys: set[str] = field(default_factory=set)


def _node_key(uid: int) -> str:
    return f"N_{uid}"


def _clone_node(node: Node) -> Node:
    return Node(
        x=node.x,
        y=node.y,
        z=node.z,
        label=node.label,
        restraint=node.restraint,
        loads=list(node.loads),
        coord_sys=node.coord_sys,
        coord_type=node.coord_type,
        special_jt=node.special_jt,
        constraint_name=node.constraint_name,
        mass_coord_sys=node.mass_coord_sys,
        load_pattern=node.load_pattern,
        mass_1=node.mass_1,
        mass_2=node.mass_2,
        mass_3=node.mass_3,
        mmi_1=node.mmi_1,
        mmi_2=node.mmi_2,
        mmi_3=node.mmi_3,
        added_mass_1=node.added_mass_1,
        added_mass_2=node.added_mass_2,
        added_mass_3=node.added_mass_3,
        added_mmi_1=node.added_mmi_1,
        added_mmi_2=node.added_mmi_2,
        added_mmi_3=node.added_mmi_3,
        spring_u1=node.spring_u1,
        spring_u2=node.spring_u2,
        spring_u3=node.spring_u3,
        spring_r1=node.spring_r1,
        spring_r2=node.spring_r2,
        spring_r3=node.spring_r3,
        unique_id=node.unique_id,
    )


def _point_to_segment_ratio(
    px: float,
    py: float,
    pz: float,
    ax: float,
    ay: float,
    az: float,
    bx: float,
    by: float,
    bz: float,
    tol: float = 1e-5,
) -> float | None:
    vx, vy, vz = bx - ax, by - ay, bz - az
    len_sq = vx * vx + vy * vy + vz * vz
    if len_sq <= tol * tol:
        return None
    wx, wy, wz = px - ax, py - ay, pz - az
    t = (wx * vx + wy * vy + wz * vz) / len_sq
    if t <= tol or t >= 1.0 - tol:
        return None
    cx = ax + t * vx
    cy = ay + t * vy
    cz = az + t * vz
    if math.dist((px, py, pz), (cx, cy, cz)) > tol:
        return None
    return t


def _segment_intersect_ratios(
    a1: tuple[float, float, float],
    b1: tuple[float, float, float],
    a2: tuple[float, float, float],
    b2: tuple[float, float, float],
    tol: float = 1e-5,
) -> tuple[float, float] | None:
    u = (b1[0] - a1[0], b1[1] - a1[1], b1[2] - a1[2])
    v = (b2[0] - a2[0], b2[1] - a2[1], b2[2] - a2[2])
    w = (a1[0] - a2[0], a1[1] - a2[1], a1[2] - a2[2])

    a = u[0] * u[0] + u[1] * u[1] + u[2] * u[2]
    b = u[0] * v[0] + u[1] * v[1] + u[2] * v[2]
    c = v[0] * v[0] + v[1] * v[1] + v[2] * v[2]
    d = u[0] * w[0] + u[1] * w[1] + u[2] * w[2]
    e = v[0] * w[0] + v[1] * w[1] + v[2] * w[2]
    denom = a * c - b * b

    if denom <= tol * tol:
        return None

    sc = (b * e - c * d) / denom
    tc = (a * e - b * d) / denom
    if sc <= tol or sc >= 1.0 - tol or tc <= tol or tc >= 1.0 - tol:
        return None

    p1 = (a1[0] + sc * u[0], a1[1] + sc * u[1], a1[2] + sc * u[2])
    p2 = (a2[0] + tc * v[0], a2[1] + tc * v[1], a2[2] + tc * v[2])
    if math.dist(p1, p2) > tol:
        return None
    return sc, tc


def _frame_mesh_ratios(
    frame: Frame,
    all_nodes: list[Node],
    all_frames: list[Frame],
    tol: float = 1e-5,
) -> list[float]:
    L = frame.get_length()
    if L <= tol:
        return [0.0, 1.0]

    ratios: list[float] = [0.0, 1.0]

    if frame.auto_mesh:
        if frame.mesh_num_segments >= 2:
            n_segments = int(frame.mesh_num_segments)
        elif frame.mesh_max_length > 0.0:
            n_segments = max(1, math.ceil(L / float(frame.mesh_max_length)))
        else:
            n_segments = max(1, math.ceil(L / _DEFAULT_MESH_MAX_LENGTH))
        if n_segments > 1:
            for i in range(1, n_segments):
                ratios.append(i / float(n_segments))

    ni, nj = frame.node_i, frame.node_j
    if (frame.mesh_at_joints or frame.add_at_elm_int) and ni and nj:
        for nd in all_nodes:
            if nd.unique_id in (ni.unique_id, nj.unique_id):
                continue
            t = _point_to_segment_ratio(
                nd.x, nd.y, nd.z,
                ni.x, ni.y, ni.z,
                nj.x, nj.y, nj.z,
                tol=tol,
            )
            if t is not None:
                ratios.append(t)

    if (frame.mesh_at_frames or frame.add_at_elm_int) and ni and nj:
        a1 = (ni.x, ni.y, ni.z)
        b1 = (nj.x, nj.y, nj.z)
        for other in all_frames:
            if other.unique_id == frame.unique_id or not other.node_i or not other.node_j:
                continue
            a2 = (other.node_i.x, other.node_i.y, other.node_i.z)
            b2 = (other.node_j.x, other.node_j.y, other.node_j.z)
            hit = _segment_intersect_ratios(a1, b1, a2, b2, tol=tol)
            if hit is not None:
                ratios.append(hit[0])

    ratios.sort()
    unique: list[float] = [0.0]
    for r in ratios:
        if r >= 1.0 - tol:
            continue
        if r - unique[-1] > tol:
            unique.append(r)
    unique.append(1.0)
    return unique


def _slice_dist_load_sets(
    frame: Frame,
    t0: float,
    t1: float,
    total_length: float,
) -> dict[str, FrameDistributedLoad]:
    if not frame.dist_load_sets:
        return {}
    dt = t1 - t0
    if dt <= 0.0:
        return {}

    sliced_sets: dict[str, FrameDistributedLoad] = {}
    for key, ls in frame.dist_load_sets.items():
        new_segs: list[LoadSegment] = []
        is_rel = bool(ls.is_relative)
        for seg in ls.segments:
            sx1 = float(seg.x1)
            sx2 = float(seg.x2)
            sq1 = float(seg.q1)
            sq2 = float(seg.q2)

            if not is_rel and total_length > 0.0:
                sx1 /= total_length
                sx2 /= total_length

            if sx2 <= sx1:
                continue

            ov0 = max(t0, sx1)
            ov1 = min(t1, sx2)
            if ov1 <= ov0:
                continue

            q_start = sq1 + (sq2 - sq1) * ((ov0 - sx1) / (sx2 - sx1))
            q_end = sq1 + (sq2 - sq1) * ((ov1 - sx1) / (sx2 - sx1))
            local_x1 = (ov0 - t0) / dt
            local_x2 = (ov1 - t0) / dt
            new_segs.append(LoadSegment(x1=local_x1, x2=local_x2, q1=q_start, q2=q_end))

        if new_segs:
            sliced_sets[key] = FrameDistributedLoad(
                pattern_name=ls.pattern_name,
                coord_sys=ls.coord_sys,
                load_dir=ls.load_dir,
                mode=ls.mode,
                force_or_moment=ls.force_or_moment,
                direction=ls.direction,
                is_relative=True,
                coordinate_system=ls.coordinate_system,
                dist_type=ls.dist_type,
                segments=new_segs,
            )
    return sliced_sets


def _clone_gravity_loads(frame: Frame) -> list[FrameGravityLoad]:
    return [
        FrameGravityLoad(
            pattern_name=g.pattern_name,
            multiplier_x=g.multiplier_x,
            multiplier_y=g.multiplier_y,
            multiplier_z=g.multiplier_z,
            coordinate_system=g.coordinate_system,
        )
        for g in (getattr(frame, "gravity_loads", None) or [])
    ]


def build_solver_mesh(math_model, coord_tol: float = 1e-4) -> SolverMesh:
    mesh = SolverMesh()

    raw_nodes = list((getattr(math_model, "nodes", None) or {}).values())
    raw_frames = list((getattr(math_model, "frames", None) or {}).values())
    raw_areas = list((getattr(math_model, "areas", None) or {}).values())
    raw_links = list((getattr(math_model, "links", None) or {}).values())

    coord_index: dict[tuple[int, int, int], Node] = {}
    uid_to_node: dict[int, Node] = {}

    def _grid_bucket(x: float, y: float, z: float) -> tuple[int, int, int]:
        inv = 1.0 / coord_tol
        return (round(x * inv), round(y * inv), round(z * inv))

    for nd in raw_nodes:
        c_node = _clone_node(nd)
        n_key = _node_key(c_node.unique_id)
        mesh.nodes[n_key] = c_node
        uid_to_node[nd.unique_id] = c_node
        coord_index[_grid_bucket(c_node.x, c_node.y, c_node.z)] = c_node

    next_internal_id = -1

    def _get_or_create_point_node(x: float, y: float, z: float) -> Node:
        nonlocal next_internal_id
        bucket = _grid_bucket(x, y, z)
        existing = coord_index.get(bucket)
        if existing is not None and math.dist(existing.coords, (x, y, z)) <= coord_tol:
            return existing

        new_node = Node(x=x, y=y, z=z, label=f"~M{abs(next_internal_id)}", unique_id=next_internal_id)
        n_key = _node_key(next_internal_id)
        mesh.nodes[n_key] = new_node
        mesh.internal_node_keys.add(n_key)
        coord_index[bucket] = new_node
        next_internal_id -= 1
        return new_node

    for frame in raw_frames:
        ni_orig = frame.node_i
        nj_orig = frame.node_j
        if ni_orig is None or nj_orig is None:
            continue

        ni_mesh = uid_to_node.get(ni_orig.unique_id) or _get_or_create_point_node(
            ni_orig.x, ni_orig.y, ni_orig.z
        )
        nj_mesh = uid_to_node.get(nj_orig.unique_id) or _get_or_create_point_node(
            nj_orig.x, nj_orig.y, nj_orig.z
        )

        ratios = _frame_mesh_ratios(frame, raw_nodes, raw_frames)
        total_len = frame.get_length()

        seg_nodes: list[Node] = [ni_mesh]
        for t in ratios[1:-1]:
            px = ni_mesh.x + t * (nj_mesh.x - ni_mesh.x)
            py = ni_mesh.y + t * (nj_mesh.y - ni_mesh.y)
            pz = ni_mesh.z + t * (nj_mesh.z - ni_mesh.z)
            seg_nodes.append(_get_or_create_point_node(px, py, pz))
        seg_nodes.append(nj_mesh)

        n_sub = len(seg_nodes) - 1
        children_keys: list[str] = []

        for idx in range(n_sub):
            t0 = ratios[idx]
            t1 = ratios[idx + 1]
            sub_key = f"F_{frame.unique_id}_{idx}" if n_sub > 1 else f"F_{frame.unique_id}"
            sub_label = f"{frame.label}_{idx + 1}" if (n_sub > 1 and frame.label) else frame.label

            sub_frame = Frame(
                node_i=seg_nodes[idx],
                node_j=seg_nodes[idx + 1],
                section=frame.section,
                rotation_deg=frame.rotation_deg,
                release_i=dict(frame.release_i) if (idx == 0 and frame.release_i) else None,
                release_j=dict(frame.release_j) if (idx == n_sub - 1 and frame.release_j) else None,
                gravity_loads=_clone_gravity_loads(frame),
                dist_load_sets=_slice_dist_load_sets(frame, t0, t1, total_len),
                modifiers=dict(frame.modifiers),
                rigid_factor=frame.rigid_factor,
                offset_length_i=frame.offset_length_i if idx == 0 else 0.0,
                offset_length_j=frame.offset_length_j if idx == n_sub - 1 else 0.0,
                label=sub_label,
                unique_id=frame.unique_id if n_sub == 1 else next_internal_id,
            )
            if n_sub > 1:
                next_internal_id -= 1

            mesh.frames[sub_key] = sub_frame
            children_keys.append(sub_key)
            mesh.parent_frame_id[sub_key] = frame.unique_id

        mesh.frame_children[frame.unique_id] = children_keys

    for area in raw_areas:
        mapped_nodes = [
            uid_to_node.get(nd.unique_id) or _get_or_create_point_node(nd.x, nd.y, nd.z)
            for nd in area.nodes
        ]
        mat = area.material or (area.area_section.material if area.area_section else None)
        a_key = f"A_{area.unique_id}"
        mesh.areas[a_key] = Area(
            nodes=mapped_nodes,
            _thickness_val=area.thickness,
            material=mat,
            section_name=area.section_name,
            area_section=area.area_section,
            mat_prop=area.mat_prop,
            thick_over=area.thick_over,
            offset_over=area.offset_over,
            gravity_loads=list(area.gravity_loads),
            uniform_loads=list(area.uniform_loads),
            uniform_to_frame_loads=list(area.uniform_to_frame_loads),
            label=area.label,
            unique_id=area.unique_id,
        )

    for link in raw_links:
        if link.node_i is None or link.node_j is None:
            continue
        ni_mesh = uid_to_node.get(link.node_i.unique_id) or _get_or_create_point_node(
            link.node_i.x, link.node_i.y, link.node_i.z
        )
        nj_mesh = uid_to_node.get(link.node_j.unique_id) or _get_or_create_point_node(
            link.node_j.x, link.node_j.y, link.node_j.z
        )
        l_key = f"L_{link.unique_id}"
        mesh.links[l_key] = Link(
            node_i=ni_mesh,
            node_j=nj_mesh,
            propname=link.propname,
            label=link.label,
            unique_id=link.unique_id,
        )

    return mesh