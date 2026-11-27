# tools/polygon_load_transfer.py
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import math
from typing import Any

import numpy as np

from data.enums import DistType, LoadDirection
from domain.definition import AreaUniformLoad, FrameDistributedLoad
from domain.polygon import Polygon

_EPS = 1e-9

_POLYGON_LOCAL_TO_AXIS = {
    LoadDirection.LOCAL_1: 0,
    LoadDirection.LOCAL_2: 1,
    LoadDirection.LOCAL_3: 2,
}


def build_polygon_frame_loads(
    math_model,
    polygon,
    loads=None,
    *,
    analysis_data=None,
    dist_type=None,
    step: float = 200.0,
    n_bins: int = 12,
    zone_fields: list[tuple[list[tuple[float, float, float]], AreaUniformLoad]] | None = None,
) -> dict[int, dict[Any, FrameDistributedLoad]]:
    if math_model is None or polygon is None:
        raise ValueError("MathModel ve polygon gereklidir.")
    if len(getattr(polygon, "nodes", ())) < 3:
        raise ValueError("Yük aktarımı için polygon en az üç node içermelidir.")
    if analysis_data is None:
        raise ValueError("PolygonAnalysisData gerekli.")

    selected_loads = list(loads if loads is not None else analysis_data.assigned_loads)
    if not selected_loads and not zone_fields:
        raise ValueError("Polygon üzerinde aktarılacak alan yükü yok.")

    associated_ids = {int(frame_id) for frame_id in analysis_data.associated_frame_ids}
    if not associated_ids:
        raise ValueError("Önce polygon için aktarım hedefi frame'leri seçin.")

    frames = [
        frame for frame in math_model.frames.values()
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
        raise ValueError("İlişkili frame'lerden hiçbiri polygon düzlemiyle kesişmiyor.")

    distribution = DistType.from_input(
        dist_type if dist_type is not None else analysis_data.transfer_dist_type
    )

    result: dict[int, dict[str, FrameDistributedLoad]] = defaultdict(dict)

    if selected_loads:
        q_profiles = None
        if distribution == DistType.TWO_WAY:
            q_profiles = _tributary_q_profiles_grid(
                polygon_2d,
                frame_data,
                step=step,
                n_bins=n_bins,
                distribution=distribution,
            )
        tributary_areas = None if q_profiles is not None else _tributary_areas(
            polygon_2d, frame_data, distribution
        )

        for load in selected_loads:
            if not isinstance(load, AreaUniformLoad):
                raise TypeError("AreaUniformLoad bekleniyor.")
            if not load.pattern_name:
                raise ValueError("Pattern adı boş olamaz.")
            _accumulate_uniform_load(
                result=result,
                load=load,
                frame_data=frame_data,
                polygon_axes=(u, v, normal),
                distribution=distribution,
                q_profiles=q_profiles,
                tributary_areas=tributary_areas,
            )

    if zone_fields:
        
        zone_layers_by_load = defaultdict(list)
        for coords_3d, z_load in zone_fields:
            pts_3d = np.asarray(coords_3d, dtype=float)
            if pts_3d.ndim != 2 or pts_3d.shape[0] < 3:
                
                continue
            delta = pts_3d - origin
            pts_2d = np.column_stack((delta @ u, delta @ v))
            key = (z_load.pattern_name, z_load.direction, z_load.coordinate_system)
            zone_layers_by_load[key].append((pts_2d, float(z_load.value)))
        

        for (pattern_name, direction, coord_sys_name), layers in zone_layers_by_load.items():
            q_profiles = _tributary_q_profiles_grid(
                polygon_2d, frame_data, step=step, n_bins=n_bins,
                distribution=distribution, zone_layers=layers,
            )
            
            if not q_profiles:
                continue
            probe_load = AreaUniformLoad(
                pattern_name=pattern_name,
                direction=direction,
                value=1.0,
                coordinate_system=coord_sys_name,
            )
            _accumulate_uniform_load(
                result=result,
                load=probe_load,
                frame_data=frame_data,
                polygon_axes=(u, v, normal),
                distribution=distribution,
                q_profiles=q_profiles,
                tributary_areas=None,
            )

    # result: dict[int, dict[Any, FrameDistributedLoad]] = defaultdict(dict)
    return {
        frame_id: loads
        for frame_id, loads in result.items()
        if loads
    }

def _accumulate_uniform_load(
    *,
    result: dict[int, dict[Any, FrameDistributedLoad]],
    load: AreaUniformLoad,
    frame_data: list[dict],
    polygon_axes: tuple[np.ndarray, np.ndarray, np.ndarray],
    distribution: DistType,
    q_profiles: dict[int, list[tuple[float, float, float, float]]] | None,
    tributary_areas: dict[int, float] | None,
) -> None:
    for item in frame_data:
        frame = item["frame"]
        frame_id = int(frame.unique_id)
        effective_length = item["effective_length"]
        if effective_length < _EPS:
            continue

        resolved_directions = _resolve_frame_load_directions(frame, load, polygon_axes)
        
        for (coord_sys, load_dir), direction_sign in resolved_directions:
            # ✅ FrameDistributedLoad ile aynı key formatı
            force_or_moment = "Force"
            key = (load.pattern_name, load_dir, coord_sys, force_or_moment)

            load_set = result[frame_id].get(key)
            if load_set is None:
                load_set = FrameDistributedLoad(
                    pattern_name=load.pattern_name,
                    coord_sys=coord_sys,
                    load_dir=load_dir,
                    mode="REPLACE",
                    force_or_moment=force_or_moment,
                    direction=load.direction,
                    coordinate_system=load.coordinate_system,
                    dist_type="two_way" if distribution == DistType.TWO_WAY else "one_way",
                )
                result[frame_id][key] = load_set

            if q_profiles is not None:
                segments = q_profiles.get(frame_id)
                if not segments:
                    continue
                for x1_rel, x2_rel, q1, q2 in segments:
                    q1_final = direction_sign * q1 * float(load.value)
                    q2_final = direction_sign * q2 * float(load.value)
                    if abs(q1_final) <= _EPS and abs(q2_final) <= _EPS:
                        continue
                    load_set.add_segment(x1_rel, x2_rel, q1_final, q2_final)
            elif tributary_areas is not None:
                ta = tributary_areas.get(frame_id, 0.0)
                q_line = direction_sign * float(load.value) * ta / effective_length
                if abs(q_line) <= _EPS:
                    continue
                for start, end in item["intervals"]:
                    load_set.add_segment(start, end, q_line, q_line)

def merge_frame_distributed_loads(
    math_model,
    staged: dict[int, dict[Any, FrameDistributedLoad]],
    mode: str,
) -> list[int]:
    touched: list[int] = []
    for frame_id, pattern_loads in staged.items():
        frame = math_model.frames.get(int(frame_id))
        if frame is None:
            continue

        changed = False

        for key, incoming in pattern_loads.items():
            # Yeni key formatı: (pattern, load_dir, coord_sys, force_or_moment)
            if isinstance(key, tuple) and len(key) == 4:
                target_key = key
            elif isinstance(incoming, FrameDistributedLoad) and hasattr(incoming, "key"):
                target_key = incoming.key
            else:
                # Geriye dönük: key str ise incoming'den türet
                target_key = (
                    incoming.pattern_name,
                    incoming.load_dir,
                    incoming.coord_sys,
                    getattr(incoming, "force_or_moment", "Force"),
                )

            if mode == "delete":
                if target_key in frame.dist_load_sets:
                    del frame.dist_load_sets[target_key]
                    changed = True
                else:
                    # Aynı pattern'in tüm load_dir'lerini sil
                    pattern_name = incoming.pattern_name
                    to_del = [
                        k for k in frame.dist_load_sets
                        if (k[0] if isinstance(k, tuple) else k) == pattern_name
                    ]
                    for k in to_del:
                        del frame.dist_load_sets[k]
                        changed = True
            elif mode == "replace":
                frame.dist_load_sets[target_key] = deepcopy(incoming)
                changed = True
            elif mode == "add":
                existing = frame.dist_load_sets.get(target_key)
                if existing is None:
                    frame.dist_load_sets[target_key] = deepcopy(incoming)
                    changed = True
                else:
                    for seg in incoming.segments:
                        existing.add_segment(seg.x1, seg.x2, seg.q1, seg.q2)
                    changed = True
        if changed:
            frame.mark_dirty()
            touched.append(int(frame_id))
    return touched


def _polygon_coordinates(polygon):
    nodes = list(polygon.nodes)
    points = np.asarray([(node.x, node.y, node.z) for node in nodes], dtype=float)
    origin = points.mean(axis=0)
    normal = np.asarray(Polygon.calculate_normal(nodes), dtype=float)
    normal_length = float(np.linalg.norm(normal))
    if not np.isfinite(normal).all() or normal_length <= _EPS:
        raise ValueError("Polygon düzlemi hesaplanamadı.")
    normal /= normal_length

    first_edge = points[1] - points[0]
    first_edge -= normal * float(np.dot(first_edge, normal))
    edge_length = float(np.linalg.norm(first_edge))
    if edge_length <= _EPS:
        raise ValueError("Polygonun ilk kenarı geçersiz.")
    u = first_edge / edge_length
    v = np.cross(normal, u)
    v /= float(np.linalg.norm(v))

    delta = points - origin
    distances = np.abs(delta @ normal)
    polygon_scale = float(np.linalg.norm(points.max(axis=0) - points.min(axis=0)))
    tol = max(polygon_scale, 1.0) * 1e-6
    if float(distances.max(initial=0.0)) > tol:
        if float(distances.max()) > polygon_scale * 0.05:
            raise ValueError("Polygon düzlemden çok sapıyor.")
        points = points - np.outer(delta @ normal, normal)

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
    frame_len = float(np.linalg.norm(points[1] - points[0]))
    polygon_scale = float(np.linalg.norm(polygon_2d.max(axis=0) - polygon_2d.min(axis=0)))
    tol = max(frame_len, polygon_scale, 1.0) * 1e-5
    distance = float(np.max(np.abs(delta @ normal)))
    if distance > tol:
        return None
    if distance > tol * 0.01:
        points = points - np.outer(delta @ normal, normal)
        delta = points - origin

    points_2d = np.column_stack((delta @ u, delta @ v))
    intervals = _segment_polygon_intervals(points_2d[0], points_2d[1], polygon_2d)
    if not intervals:
        return None
    effective_fraction = sum(end - start for start, end in intervals)
    effective_length = frame_len * effective_fraction
    if frame_len <= _EPS or effective_length <= _EPS:
        return None

    midpoint = sum(
        (end - start) * (points_2d[0] + (points_2d[1] - points_2d[0]) * ((start + end) / 2))
        for start, end in intervals
    ) / effective_fraction
    return {
        "frame": frame,
        "pi_2d": (float(points_2d[0][0]), float(points_2d[0][1])),
        "pj_2d": (float(points_2d[1][0]), float(points_2d[1][1])),
        "intervals": intervals,
        "effective_length": effective_length,
        "full_length": frame_len,
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


def _point_in_polygon(point, polygon) -> bool:
    x, y = point
    inside = False
    for index, first in enumerate(polygon):
        second = polygon[(index + 1) % len(polygon)]
        edge = second - first
        offset = np.asarray((x, y), dtype=float) - first
        scale = max(float(np.linalg.norm(edge)), 1.0)
        if (
            abs(_cross_2d(edge, offset)) <= _EPS * scale
            and -_EPS <= float(np.dot(offset, edge)) <= float(np.dot(edge, edge)) + _EPS
        ):
            return True
        if (first[1] > y) != (second[1] > y):
            crossing_x = (
                (second[0] - first[0]) * (y - first[1]) / (second[1] - first[1]) + first[0]
            )
            if x < crossing_x:
                inside = not inside
    return inside


def _tributary_areas(polygon, frames, distribution):
    areas = defaultdict(float)
    axis = 1 if distribution in (DistType.ONE_WAY, DistType.ONE_WAY_U1) else 0
    groups: list[list[dict[str, Any]]] = []
    for item in sorted(frames, key=lambda value: value["midpoint"][axis]):
        coordinate = float(item["midpoint"][axis])
        if groups and abs(coordinate - float(groups[-1][0]["midpoint"][axis])) <= _EPS:
            groups[-1].append(item)
        else:
            groups.append([item])

    centers = [float(group[0]["midpoint"][axis]) for group in groups]
    for index, group in enumerate(groups):
        lower = (centers[index - 1] + centers[index]) / 2.0 if index > 0 else None
        upper = (centers[index] + centers[index + 1]) / 2.0 if index + 1 < len(groups) else None
        cell = _clip_axis(polygon, axis, lower, upper)
        cell_area = _polygon_area(cell)
        total_length = sum(item["effective_length"] for item in group)
        if total_length <= _EPS:
            continue
        for item in group:
            frame_id = int(item["frame"].unique_id)
            areas[frame_id] += cell_area * item["effective_length"] / total_length
    return dict(areas)


def _tributary_q_profiles_grid(
    polygon_2d: np.ndarray,
    frame_data: list[dict],
    *,
    step: float = 200.0,
    n_bins: int = 12,
    distribution: DistType = DistType.TWO_WAY,
    zone_layers: list[tuple[np.ndarray, float]] | None = None,
) -> dict[int, list[tuple[float, float, float, float]]]:
    min_u, min_v = polygon_2d.min(axis=0)
    max_u, max_v = polygon_2d.max(axis=0)
    if step <= 0:
        step = 200.0

    dA = step * step
    nu = max(1, int(math.ceil((max_u - min_u) / step)))
    nv = max(1, int(math.ceil((max_v - min_v) / step)))

    # ✅ Her frame'in bounding box'ını genişletip grid hücrelerine ata
    cell_size = step * 2.0  # komşuluk toleransı
    buckets: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for fd in frame_data:
        x1, y1 = fd["pi_2d"]
        x2, y2 = fd["pj_2d"]
        bx0 = min(x1, x2) - cell_size
        bx1 = max(x1, x2) + cell_size
        by0 = min(y1, y2) - cell_size
        by1 = max(y1, y2) + cell_size
        iu0 = max(0, int((bx0 - min_u) // step))
        iu1 = min(nu - 1, int((bx1 - min_u) // step))
        iv0 = max(0, int((by0 - min_v) // step))
        iv1 = min(nv - 1, int((by1 - min_v) // step))
        for iu in range(iu0, iu1 + 1):
            for iv in range(iv0, iv1 + 1):
                buckets[(iu, iv)].append(fd)

    bins: dict[int, dict[int, float]] = {int(fd["frame"].unique_id): {} for fd in frame_data}
    one_way_axis = 1 if distribution in (DistType.ONE_WAY, DistType.ONE_WAY_U1) else 0

    for iu in range(nu):
        for iv in range(nv):
            cu = float(min_u + (iu + 0.5) * step)
            cv = float(min_v + (iv + 0.5) * step)
            if not _point_in_polygon((cu, cv), polygon_2d):
                continue

            if zone_layers is not None:
                cell_pressure = 0.0
                for zone_poly, z_val in zone_layers:
                    if _point_in_polygon((cu, cv), zone_poly):
                        cell_pressure += z_val
                if abs(cell_pressure) <= _EPS:
                    continue
            else:
                cell_pressure = 1.0

            q_cell = cell_pressure * dA
            best_fd = None
            best_dist = float("inf")
            best_t = 0.0

            candidates = buckets.get((iu, iv), frame_data)   # ✅ sadece komşu frame'ler
            for fd in candidates:
                t, dist = _point_segment_param((cu, cv), fd["pi_2d"], fd["pj_2d"])
                if distribution != DistType.TWO_WAY:
                    px = fd["pi_2d"][0] + (fd["pj_2d"][0] - fd["pi_2d"][0]) * t
                    py = fd["pi_2d"][1] + (fd["pj_2d"][1] - fd["pi_2d"][1]) * t
                    dist = abs((cv - py) if one_way_axis == 1 else (cu - px))
                if dist < best_dist:
                    best_dist = dist
                    best_fd = fd
                    best_t = t

            if best_fd is None:
                continue
            

            eff_len = float(best_fd["effective_length"])
            full_len = float(best_fd["full_length"])
            intervals = best_fd["intervals"]
            if eff_len <= _EPS or not intervals:
                continue

            x_eff = _t_to_effective_x(best_t, intervals, full_len)
            bin_size = eff_len / max(1, n_bins)
            bin_idx = min(n_bins - 1, max(0, int(x_eff / bin_size)))
            fid = int(best_fd["frame"].unique_id)
            bins[fid][bin_idx] = bins[fid].get(bin_idx, 0.0) + q_cell

    result: dict[int, list[tuple[float, float, float, float]]] = {}
    for fd in frame_data:
        fid = int(fd["frame"].unique_id)
        bin_dict = bins.get(fid, {})
        eff_len = float(fd["effective_length"])
        if eff_len <= _EPS or not bin_dict:
            continue

        bin_size = eff_len / n_bins
        q_by_bin = [0.0] * n_bins
        for bin_idx, force in bin_dict.items():
            q_by_bin[bin_idx] = force / bin_size

        if max(abs(v) for v in q_by_bin) <= _EPS:
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
            if abs(q1) <= _EPS and abs(q2) <= _EPS:
                continue
            segments.append((x1_rel, x2_rel, q1, q2))
        if segments:
            result[fid] = segments

    return result


def _t_to_effective_x(t_full: float, intervals: list[tuple[float, float]], full_len: float) -> float:
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


def _point_segment_param(pt, a, b) -> tuple[float, float]:
    px, py = pt
    ax, ay = a
    bx, by = b
    dx = bx - ax
    dy = by - ay
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return 0.0, math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return t, math.hypot(px - (ax + dx * t), py - (ay + dy * t))


def _clip_axis(polygon, axis, lower, upper):
    clipped = list(polygon)
    if lower is not None:
        clipped = _clip_half_plane(clipped, -np.eye(2)[axis], -float(lower))
    if upper is not None:
        clipped = _clip_half_plane(clipped, np.eye(2)[axis], float(upper))
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
    return abs(
        float(
            np.dot(points[:, 0], np.roll(points[:, 1], 1))
            - np.dot(points[:, 1], np.roll(points[:, 0], 1))
        )
    ) / 2.0


def _cross_2d(first, second):
    return float(first[0] * second[1] - first[1] * second[0])


def _frame_local_axes(frame) -> np.ndarray:
    return np.asarray(frame.get_transformation_matrix(), dtype=float)


def _match_local_axis(frame, polygon_axes, load_direction, cos_tol=0.99):
    poly_idx = _POLYGON_LOCAL_TO_AXIS[load_direction]
    poly_axis = np.asarray(polygon_axes[poly_idx], dtype=float)
    axis_len = float(np.linalg.norm(poly_axis))
    if axis_len <= _EPS:
        return None, 1.0
    poly_axis /= axis_len

    frame_axes = _frame_local_axes(frame)
    dots = frame_axes.T @ poly_axis
    abs_dots = np.abs(dots)
    best_idx = int(np.argmax(abs_dots))
    if abs_dots[best_idx] < cos_tol:
        return None, 1.0
    sign = 1.0 if dots[best_idx] >= 0.0 else -1.0
    return best_idx + 1, sign


def _resolve_frame_load_directions(frame, load, polygon_axes):
    direction = load.direction

    if direction == LoadDirection.GRAVITY:
        return [(("Global", "7"), 1.0)]

    if direction == LoadDirection.GLOBAL_X:
        return [(("Global", "4"), 1.0)]

    if direction == LoadDirection.GLOBAL_Y:
        return [(("Global", "5"), 1.0)]

    if direction == LoadDirection.GLOBAL_Z:
        return [(("Global", "6"), 1.0)]

    poly_idx = _POLYGON_LOCAL_TO_AXIS[direction]
    poly_axis = np.asarray(polygon_axes[poly_idx], dtype=float)
    poly_axis /= np.linalg.norm(poly_axis)

    frame_axes = _frame_local_axes(frame)
    components = frame_axes.T @ poly_axis
    
    return [
        (("Local", str(i + 1)), float(components[i]))
        for i in (1, 2)
        if abs(components[i]) > _EPS
    ]