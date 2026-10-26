# tools/s2k/handlers/grids.py
"""GRID LINES."""
import pandas as pd

from tools.s2k.context import LoadContext


def _safe_float(row, key, default=0.0):
    val = row.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def handle_grid_lines(ctx: LoadContext, df: pd.DataFrame) -> None:
    ctx.df_grid_lines = df
    if df is None or df.empty:
        return
    for _, r in df.iterrows():
        sys_name = str(r.get("CoordSys", "Global")).strip()
        line_id = str(r.get("GridID", r.get("ID", ""))).strip()
        ordinate = _safe_float(r, "XRYZCoord", _safe_float(r, "Ordinate", 0.0))
        axis_dir = str(r.get("AxisDir", r.get("LineType", "X"))).strip().upper()
        if line_id:
            ctx.grid_lines.append({
                "coord_sys": sys_name,
                "id": line_id,
                "ordinate": ordinate,
                "axis_dir": axis_dir,
                "bubble": str(r.get("Bubble", "")).strip(),
            })