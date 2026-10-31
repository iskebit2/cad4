# tools/polygon_load_transfer.py

"""Geometric transfer of polygon area loads to explicitly associated frames."""
from __future__ import annotations

from collections import defaultdict
from typing import Any
from copy import deepcopy
import numpy as np
import math
from data.enums import DistType, LoadDirection
from domain.definition import AreaUniformLoad, FrameDistributedLoad
from domain.element import Polygon

_EPS = 1e-9

def _t_to_effective_x(
    t_full: float,
    intervals: list[tuple[float, float]],
    full_len: float,
) -> float:
    """Tam frame üzerindeki t (0..1) → polygon içindeki x (0..eff_len)."""
    x_eff = 0.0
    for t0, t1 in intervals:
        if t_full <= t0:
            break
        if t_full >= t1:
            x_eff += (t1 - t0) * full_len
        else:
            x_eff += (t_full - t0) * full_len
            break
    return x_eff

def _point_in_polygon_2d(point, polygon) -> bool:
    """2D point-in-polygon testi (ray casting)."""
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xc = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xc:
                inside = not inside
    return inside


def _point_segment_param(pt, a, b) -> tuple[float, float]:
    """Nokta-doğru parçası mesafesi ve parametresi (t ∈ [0,1])."""
    
    px, py = pt
    ax, ay = a
    bx, by = b
    dx = bx - ax
    dy = by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return 0.0, math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / L2
    t = max(0.0, min(1.0, t))
    cx = ax + dx * t
    cy = ay + dy * t
    return t, math.hypot(px - cx, py - cy)

def build_polygon_frame_loads(
    scene, polygon, loads=None, *,
    dist_type=None,
    step: float = 200.0,
    n_bins: int = 12,
) -> dict[int, dict[str, FrameDistributedLoad]]:
    """Build frame load sets from only the frame IDs explicitly associated to a polygon."""
    if scene is None or polygon is None:
        raise ValueError("Sahne ve polygon gereklidir.")
    if len(getattr(polygon, "nodes", ())) < 3:
        raise ValueError("Yük aktarımı için polygon en az üç node içermelidir.")

    selected_loads = list(
        loads if loads is not None else getattr(polygon, "assigned_loads", ())
    )
    if not selected_loads:
        raise ValueError("Polygon üzerinde aktarılacak alan yükü yok.")

    associated_ids = {
        int(frame_id)
        for frame_id in getattr(polygon, "associated_frame_ids", ())
    }
    if not associated_ids:
        raise ValueError("Önce polygon için aktarım hedefi frame'leri seçin.")
    frames = [
        frame for frame in scene.frames.values()
        if int(frame.unique_id) in associated_ids
    ]
    if len(frames) != len(associated_ids):
        found = {int(frame.unique_id) for frame in frames}
        missing = sorted(associated_ids - found)
        raise ValueError(f"İlişkili frame bulunamadı: {missing}")

    u, v, normal, origin, polygon_2d = _polygon_coordinates(polygon)
    area = _polygon_area(polygon_2d)
    if area <= _EPS:
        raise ValueError("Polygon alanı sıfır veya geçersiz.")

    frame_data = []
    for frame in frames:
        data = _project_frame(frame, origin, u, v, normal, polygon_2d)
        if data is not None:
            frame_data.append(data)
    if not frame_data:
        raise ValueError(
            "İlişkili frame'lerden hiçbiri polygon düzlemiyle kesişmiyor."
        )

    distribution = DistType.from_input(
        dist_type if dist_type is not None
        else getattr(polygon, "transfer_dist_type", None)
    )
    # ★ Grid sampling profili (TWO_WAY için)
    q_profiles: dict[int, list[tuple[float, float, float, float]]] | None = None
    if distribution == DistType.TWO_WAY:
        q_profiles = _tributary_q_profiles_grid(
                                    polygon, frame_data,
                                    load_value=1.0,
                                    step=step,
                                    n_bins=n_bins,
                                )
        if not q_profiles:
            raise ValueError("Grid sampling: kiriş profili üretilemedi.")

    result: dict[int, dict[str, FrameDistributedLoad]] = defaultdict(dict)
    for load in selected_loads:
        if not isinstance(load, AreaUniformLoad):
            raise TypeError(...)
        if not load.pattern_name:
            raise ValueError(...)

        for frame_data_item in frame_data:
            frame = frame_data_item["frame"]
            frame_id = int(frame.unique_id)
            effective_length = frame_data_item["effective_length"]
            if effective_length < _EPS:
                continue

            coord_sys, load_dir = _frame_load_direction(load.direction)
            load_set = result[frame_id].get(load.pattern_name)
            if load_set is None:
                load_set = FrameDistributedLoad(
                    pattern_name=load.pattern_name,
                    coord_sys=coord_sys,
                    load_dir=load_dir,
                    mode="REPLACE",
                    direction=load.direction,
                    coordinate_system=load.coordinate_system,
                    dist_type=(
                        "two_way" if distribution == DistType.TWO_WAY
                        else "one_way"
                    ),
                )
                result[frame_id][load.pattern_name] = load_set
            elif (load_set.coord_sys, load_set.load_dir) != (coord_sys, load_dir):
                raise ValueError(
                    f"'{load.pattern_name}' pattern'inde uyumsuz yönler var."
                )

            if q_profiles is not None and frame_id in q_profiles:
                # ★ Profil tabanlı segmentler
                for x1_rel, x2_rel, q1, q2 in q_profiles[frame_id]:
                    q1_final = q1 * float(load.value)
                    q2_final = q2 * float(load.value)
                    load_set.add_segment(x1_rel, x2_rel, q1_final, q2_final)
            else:
                # Uniform — ONE_WAY / veya profil yoksa fallback
                tributary_areas = _tributary_areas(polygon_2d, frame_data, distribution)
                ta = tributary_areas.get(frame_id, 0.0)
                q_line = float(load.value) * ta / effective_length
                if abs(q_line) <= _EPS:
                    continue
                for start, end in frame_data_item["intervals"]:
                    load_set.add_segment(start, end, q_line, q_line)

    return dict(result)


def _polygon_coordinates(polygon):
    nodes = list(polygon.nodes)
    points = np.asarray(
        [(node.x, node.y, node.z) for node in nodes], dtype=float,
    )
    origin = points[0]
    normal = np.asarray(polygon.calculate_normal(nodes), dtype=float)
    normal_length = float(np.linalg.norm(normal))
    if not np.isfinite(normal).all() or normal_length <= _EPS:
        raise ValueError("Polygon düzlemi hesaplanamadı.")
    normal /= normal_length

    first_edge = points[1] - origin
    first_edge -= normal * float(np.dot(first_edge, normal))
    edge_length = float(np.linalg.norm(first_edge))
    if edge_length <= _EPS:
        raise ValueError("Polygonun ilk kenarı geçersiz.")
    u = first_edge / edge_length
    v = np.cross(normal, u)
    v /= float(np.linalg.norm(v))

    scale = max(float(np.linalg.norm(points.max(axis=0) - points.min(axis=0))), 1.0)
    distances = np.abs((points - origin) @ normal)
    if float(distances.max(initial=0.0)) > scale * 1e-7:
        raise ValueError("Alan yükü düzlemsel olmayan polygon'a aktarılamaz.")
    polygon_2d = np.column_stack(((points - origin) @ u, (points - origin) @ v))
    return u, v, normal, origin, polygon_2d


def _project_frame(frame, origin, u, v, normal, polygon_2d):
    if not getattr(frame, "node_i", None) or not getattr(frame, "node_j", None):
        return None
    points = np.asarray(
        [
            (frame.node_i.x, frame.node_i.y, frame.node_i.z),
            (frame.node_j.x, frame.node_j.y, frame.node_j.z),
        ],
        dtype=float,
    )
    if not np.isfinite(points).all():
        return None
    delta = points - origin
    scale = max(float(np.linalg.norm(points[1] - points[0])), 1.0)
    if float(np.max(np.abs(delta @ normal))) > scale * 1e-7:
        return None

    points_2d = np.column_stack((delta @ u, delta @ v))
    intervals = _segment_polygon_intervals(points_2d[0], points_2d[1], polygon_2d)
    length = float(np.linalg.norm(points[1] - points[0]))
    effective_fraction = sum(end - start for start, end in intervals)
    effective_length = length * effective_fraction
    if length <= _EPS or effective_length <= _EPS:
        return None

    midpoint = sum(
        (end - start) * (points_2d[0] + (points_2d[1] - points_2d[0]) * ((start + end) / 2))
        for start, end in intervals
    ) / effective_fraction
    return {
                "frame": frame,
                "intervals": intervals,
                "effective_length": effective_length,
                "full_length": length,   # ★
                "midpoint": midpoint,
            }


def _segment_polygon_intervals(start, end, polygon):
    direction = end - start
    if float(np.linalg.norm(direction)) <= _EPS:
        return []
    breaks = [0.0, 1.0]
    for index, edge_start in enumerate(polygon):
        edge_end = polygon[(index + 1) % len(polygon)]
        edge = edge_end - edge_start
        denominator = _cross_2d(direction, edge)
        if abs(denominator) <= _EPS:
            continue
        offset = edge_start - start
        t = _cross_2d(offset, edge) / denominator
        s = _cross_2d(offset, direction) / denominator
        if -_EPS <= t <= 1.0 + _EPS and -_EPS <= s <= 1.0 + _EPS:
            breaks.append(min(1.0, max(0.0, t)))
    breaks = sorted(set(round(value, 12) for value in breaks))
    intervals = []
    for t0, t1 in zip(breaks, breaks[1:]):
        if t1 - t0 <= _EPS:
            continue
        if _point_in_polygon(start + direction * ((t0 + t1) / 2), polygon):
            intervals.append((t0, t1))
    return intervals


def _point_in_polygon(point, polygon):
    x, y = point
    inside = False
    for index, first in enumerate(polygon):
        second = polygon[(index + 1) % len(polygon)]
        edge = second - first
        offset = np.asarray((x, y), dtype=float) - first
        scale = max(float(np.linalg.norm(edge)), 1.0)
        if (
            abs(_cross_2d(edge, offset)) <= _EPS * scale
            and -_EPS <= float(np.dot(offset, edge))
            <= float(np.dot(edge, edge)) + _EPS
        ):
            return True
        if (first[1] > y) != (second[1] > y):
            crossing_x = (
                (second[0] - first[0]) * (y - first[1])
                / (second[1] - first[1]) + first[0]
            )
            if x < crossing_x:
                inside = not inside
    return inside


def _tributary_areas(polygon, frames, distribution):
    areas = defaultdict(float)
    if distribution == DistType.TWO_WAY:
        groups = defaultdict(list)
        for item in frames:
            groups[tuple(np.round(item["midpoint"], 10))].append(item)
        representatives = [items[0] for items in groups.values()]
        for index, frame_data in enumerate(representatives):
            cell = polygon
            point = frame_data["midpoint"]
            for other_index, other in enumerate(representatives):
                if index == other_index:
                    continue
                other_point = other["midpoint"]
                normal = other_point - point
                if float(np.linalg.norm(normal)) <= _EPS:
                    continue
                boundary = (float(np.dot(other_point, other_point))
                            - float(np.dot(point, point))) / 2.0
                cell = _clip_half_plane(cell, normal, boundary)
                if not cell:
                    break
            cell_area = _polygon_area(cell)
            group = groups[tuple(np.round(point, 10))]
            total_length = sum(item["effective_length"] for item in group)
            for item in group:
                areas[int(item["frame"].unique_id)] = (
                    cell_area * item["effective_length"] / total_length
                )
        return dict(areas)

    axis = 1 if distribution in (
        DistType.ONE_WAY, DistType.ONE_WAY_U1,
    ) else 0
    groups: list[list[dict[str, Any]]] = []
    for item in sorted(frames, key=lambda value: value["midpoint"][axis]):
        coordinate = float(item["midpoint"][axis])
        if groups and abs(
            coordinate - float(groups[-1][0]["midpoint"][axis])
        ) <= _EPS:
            groups[-1].append(item)
        else:
            groups.append([item])

    centers = [float(group[0]["midpoint"][axis]) for group in groups]
    for index, group in enumerate(groups):
        lower = (
            (centers[index - 1] + centers[index]) / 2.0
            if index > 0 else None
        )
        upper = (
            (centers[index] + centers[index + 1]) / 2.0
            if index + 1 < len(groups) else None
        )
        cell = _clip_axis(polygon, axis, lower, upper)
        cell_area = _polygon_area(cell)
        total_length = sum(item["effective_length"] for item in group)
        if total_length <= _EPS:
            continue
        for item in group:
            frame_id = int(item["frame"].unique_id)
            areas[frame_id] += (
                cell_area * item["effective_length"] / total_length
            )
    return dict(areas)

def _tributary_q_profiles_grid(
    polygon,
    frame_data: list[dict],
    load_value: float,
    *,
    step: float = 200.0,
    n_bins: int = 12,
) -> dict[int, list[tuple[float, float, float, float]]]:
    import math
    import numpy as np

    if len(polygon.nodes) < 3:
        return {}

    # Polygon 2D düzlemi
    nodes = polygon.nodes
    origin = np.array([nodes[0].x, nodes[0].y, nodes[0].z])
    normal = np.array(Polygon.calculate_normal(nodes), dtype=float)
    n_len = float(np.linalg.norm(normal))
    if n_len < 1e-9:
        return {}
    normal = normal / n_len

    first_edge = np.array([
        nodes[1].x - nodes[0].x,
        nodes[1].y - nodes[0].y,
        nodes[1].z - nodes[0].z,
    ])
    first_edge -= normal * float(np.dot(first_edge, normal))
    fe_len = float(np.linalg.norm(first_edge))
    if fe_len < 1e-9:
        return {}
    u_axis = first_edge / fe_len
    v_axis = np.cross(normal, u_axis)

    polygon_2d = np.array([
        [float(np.dot(np.array([nd.x, nd.y, nd.z]) - origin, u_axis)),
         float(np.dot(np.array([nd.x, nd.y, nd.z]) - origin, v_axis))]
        for nd in nodes
    ])

    # Frame 2D — fd'yi doğrudan kullan
    frame_lookup: dict[int, dict] = {}
    for fd in frame_data:
        frame = fd["frame"]
        fid = int(frame.unique_id)

        pi = np.array([frame.node_i.x, frame.node_i.y, frame.node_i.z])
        pj = np.array([frame.node_j.x, frame.node_j.y, frame.node_j.z])

        pi_2d = (
            float(np.dot(pi - origin, u_axis)),
            float(np.dot(pi - origin, v_axis)),
        )
        pj_2d = (
            float(np.dot(pj - origin, u_axis)),
            float(np.dot(pj - origin, v_axis)),
        )

        frame_lookup[fid] = {
            "pi_2d": pi_2d,
            "pj_2d": pj_2d,
            "eff_len": float(fd["effective_length"]),
            "full_len": float(fd["full_length"]),
            "intervals": fd["intervals"],          # ★ fd'den
            "frame": frame,
        }

    if not frame_lookup:
        return {}

    # Grid taraması
    min_u, min_v = polygon_2d.min(axis=0)
    max_u, max_v = polygon_2d.max(axis=0)

    if step <= 0:
        step = 200.0

    dA = step * step
    q_cell = float(load_value) * dA

    bins: dict[int, dict[int, float]] = {fid: {} for fid in frame_lookup}

    nu = max(1, int(math.ceil((max_u - min_u) / step)))
    nv = max(1, int(math.ceil((max_v - min_v) / step)))

    for iu in range(nu):
        for iv in range(nv):
            cu = min_u + (iu + 0.5) * step
            cv = min_v + (iv + 0.5) * step

            if not _point_in_polygon_2d((cu, cv), polygon_2d.tolist()):
                continue

            best_fid = None
            best_dist = float("inf")
            best_t = 0.0
            for fid, fdata in frame_lookup.items():
                t, dist = _point_segment_param(
                    (cu, cv), fdata["pi_2d"], fdata["pj_2d"],
                )
                if dist < best_dist:
                    best_dist = dist
                    best_fid = fid
                    best_t = t

            if best_fid is None:
                continue

            fdata = frame_lookup[best_fid]
            eff_len = fdata["eff_len"]
            full_len = fdata["full_len"]
            intervals = fdata["intervals"]

            if eff_len < 1e-9 or not intervals:
                continue

            x_eff = _t_to_effective_x(best_t, intervals, full_len)
            bin_size = eff_len / max(1, n_bins)
            bin_idx = min(n_bins - 1, max(0, int(x_eff / bin_size)))

            bins[best_fid][bin_idx] = (
                bins[best_fid].get(bin_idx, 0.0) + q_cell
            )

    # Bin → segment
    result: dict[int, list[tuple[float, float, float, float]]] = {}
    for fid, fdata in frame_lookup.items():
        bin_dict = bins.get(fid, {})
        eff_len = fdata["eff_len"]
        if eff_len < 1e-9:
            continue

        bin_size = eff_len / n_bins
        q_by_bin = [0.0] * n_bins
        for bin_idx, force in bin_dict.items():
            q_by_bin[bin_idx] = force / bin_size if bin_size > 0 else 0.0

        if max(q_by_bin) < 1e-9:
            continue

        segments: list[tuple[float, float, float, float]] = []
        for i in range(n_bins):
            q_mid = q_by_bin[i]
            q_left = q_by_bin[i - 1] if i > 0 else q_mid
            q_right = q_by_bin[i + 1] if i < n_bins - 1 else q_mid
            x1_rel = i / n_bins
            x2_rel = (i + 1) / n_bins
            q1 = (q_left + q_mid) * 0.5
            q2 = (q_mid + q_right) * 0.5
            segments.append((x1_rel, x2_rel, q1, q2))

        result[fid] = segments

    return result

def _clip_axis(polygon, axis, lower, upper):
    clipped = list(polygon)
    if lower is not None:
        clipped = _clip_half_plane(
            clipped, -np.eye(2)[axis], -float(lower),
        )
    if upper is not None:
        clipped = _clip_half_plane(
            clipped, np.eye(2)[axis], float(upper),
        )
    return clipped


def _clip_half_plane(polygon, normal, boundary):
    if len(polygon) == 0:
        return []
    result = []
    previous = polygon[-1]
    previous_inside = float(np.dot(normal, previous)) <= boundary + _EPS
    for current in polygon:
        current_inside = float(np.dot(normal, current)) <= boundary + _EPS
        if current_inside != previous_inside:
            direction = current - previous
            denominator = float(np.dot(normal, direction))
            if abs(denominator) > _EPS:
                t = (boundary - float(np.dot(normal, previous))) / denominator
                result.append(previous + direction * t)
        if current_inside:
            result.append(current)
        previous = current
        previous_inside = current_inside
    return result


def _polygon_area(polygon):
    if len(polygon) < 3:
        return 0.0
    points = np.asarray(polygon, dtype=float)
    return abs(float(
        np.dot(points[:, 0], np.roll(points[:, 1], 1))
        - np.dot(points[:, 1], np.roll(points[:, 0], 1))
    )) / 2.0


def _cross_2d(first, second):
    return float(first[0] * second[1] - first[1] * second[0])


def _frame_load_direction(direction):
    codes = {
        LoadDirection.LOCAL_1: ("Local", "1"),
        LoadDirection.LOCAL_2: ("Local", "2"),
        LoadDirection.LOCAL_3: ("Local", "3"),
        LoadDirection.GLOBAL_X: ("Global", "4"),
        LoadDirection.GLOBAL_Y: ("Global", "5"),
        LoadDirection.GLOBAL_Z: ("Global", "6"),
        LoadDirection.GRAVITY: ("Global", "7"),
        LoadDirection.PROJECTED_X: ("Global", "8"),
        LoadDirection.PROJECTED_Y: ("Global", "9"),
        LoadDirection.PROJECTED_Z: ("Global", "10"),
    }
    try:
        return codes[direction]
    except KeyError as error:
        raise ValueError(f"Desteklenmeyen alan yükü yönü: {direction!r}") from error


def transfer_polygon_loads_to_frames(
    scene, polygon, *, pattern: str | None = None,
) -> dict[int, dict[str, FrameDistributedLoad]]:
    """Build and apply this polygon's area loads, replacing its prior contribution."""
    

    loads = list(getattr(polygon, "assigned_loads", ()))
    if pattern is not None:
        loads = [load for load in loads if load.pattern_name == pattern]

    
    generated = build_polygon_frame_loads(scene, polygon, loads)

    manager = getattr(getattr(scene, "project", None), "loads", None)
    if manager is not None and hasattr(manager, "replace_polygon_frame_transfers"):
        manager.replace_polygon_frame_transfers(
            scene, int(polygon.unique_id), generated,
        )
    else:
        for frame_id, pattern_loads in generated.items():
            frame = next(
                item for item in scene.frames.values()
                if int(item.unique_id) == frame_id
            )
            for pattern_name, load_set in pattern_loads.items():
                frame.dist_load_sets[pattern_name] = deepcopy(load_set)
                frame.mark_dirty()
    return generated
