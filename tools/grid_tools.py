# tools/grid_tools.py
from __future__ import annotations

from core.units import Dimension, UnitSystem, convert_value
from domain.grid import Grid


def sync_grid_from_s2k_lines(project, grid_lines: list[dict]) -> None:
    if not grid_lines:
        return

    buckets: dict[str, dict[float, str]] = {"X": {}, "Y": {}, "Z": {}}
    for gl in grid_lines:
        direction = str(gl.get("axis_dir", gl.get("line_type", "X"))).upper()
        v = float(gl.get("ordinate", 0.0))
        lbl = str(gl.get("grid_id") or gl.get("label") or gl.get("name") or "").strip()
        if "X" in direction:
            key = "X"
        elif "Y" in direction or "V" in direction:
            key = "Y"
        elif "Z" in direction:
            key = "Z"
        else:
            continue
        if v not in buckets[key] or (lbl and not buckets[key][v]):
            buckets[key][v] = lbl

    def _extract(axis_key: str) -> tuple[list[float], list[str]]:
        items = sorted(buckets[axis_key].items(), key=lambda kv: kv[0])
        coords = [c for c, _ in items]
        labels = [lbl if lbl else f"{axis_key}{i + 1}" for i, (_, lbl) in enumerate(items)]
        return coords, labels

    xs, x_labels = _extract("X")
    ys, y_labels = _extract("Y")
    zs, z_labels = _extract("Z")

    target = project.unit_system
    bubble = convert_value(Dimension.LENGTH, 1000.0, UnitSystem.N_MM, target)
    overflow = convert_value(Dimension.LENGTH, 200.0, UnitSystem.N_MM, target)

    project.scene.grid = Grid(
        x_coords=xs, y_coords=ys, z_coords=zs,
        x_labels=x_labels, y_labels=y_labels, z_labels=z_labels,
        bubble_offset=bubble, label_overflow=overflow,
    )
    project.scene.mark_dirty()
    project.invalidate_grid_planes()


def filtered_grid_axes(project) -> list:
    from geometry.geometry_processor import GeometryProcessor
    return GeometryProcessor.process_grid_axes(project.grid, project.active_plane)