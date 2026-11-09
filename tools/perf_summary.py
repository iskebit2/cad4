# tools/perf_summary.py
import re
from collections import defaultdict
from pathlib import Path

log = Path("logs/cad.log").read_text(encoding="utf-8", errors="replace")

patterns = {
    "update_geo_total": r"\[update_geo\] TOTAL: ([\d.]+) ms",
    "gp_total": r"\[GP\] TOTAL: ([\d.]+) ms",
    "mm_total": r"\[MathModel.update_geo\] TOTAL: ([\d.]+) ms",
    "assoc_total": r"\[Plane.refresh_assoc\] \S+ TOTAL: ([\d.]+) ms",
    "frame_upd": r"\[FrameRenderer.update\] TOTAL: ([\d.]+) ms",
    "area_upd": r"\[AreaRenderer.update\] TOTAL: ([\d.]+) ms",
    "node_upd": r"\[NodeRenderer.update\] TOTAL: ([\d.]+) ms",
    "link_upd": r"\[LinkRenderer.update\] TOTAL: ([\d.]+) ms",
    "id_pass": r"\[MathModel.render\] id_pass: ([\d.]+) ms",
    "color_pass": r"\[MathModel.render\] color_pass: ([\d.]+) ms",
    "scene_render_slow": r"\[SceneRender\] SLOW TOTAL: ([\d.]+) ms",
    "frame_slow": r"\[CadApp.frame\] SLOW: ([\d.]+) ms",
}

for name, pat in patterns.items():
    vals = [float(x) for x in re.findall(pat, log)]
    if not vals:
        print(f"{name:20s} — yok")
        continue
    vals.sort()
    n = len(vals)
    print(f"{name:20s} n={n:5d}  min={vals[0]:7.1f}  med={vals[n//2]:7.1f}  "
          f"p95={vals[int(n*0.95)]:7.1f}  max={vals[-1]:7.1f} ms")