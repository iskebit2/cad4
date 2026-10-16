# tests/find_empty_points.py
from domain.project import Project

p = Project.load("model_projesi.cd4")
scene = p.scene

print("=== dist_loads.points BOŞ olan frame'ler ===\n")

bad_frames = []
for f in scene.frames.values():
    for i, dl in enumerate(getattr(f, "dist_loads", []) or []):
        pts = getattr(dl, "points", None)
        if not pts:
            bad_frames.append((f, i, dl))

print(f"Toplam {len(bad_frames)} hatalı yük satırı bulundu.\n")

for f, i, dl in bad_frames[:20]:
    label = getattr(f, "label", None) or f"Frame_{f.unique_id}"
    print(f"Frame {label} — Load #{i}:")
    print(f"  pattern_name = {dl.pattern_name!r}")
    print(f"  points       = {dl.points!r}")
    print(f"  coord_sys    = {getattr(dl, 'coord_sys', '?')}")
    print(f"  load_dir     = {getattr(dl, 'load_dir', '?')}")
    print(f"  mode         = {getattr(dl, 'mode', '?')}")
    print()

# Pattern dağılımı
from collections import Counter
pat_count = Counter()
for f, i, dl in bad_frames:
    pat_count[getattr(dl, "pattern_name", "?")] += 1

print("Pattern dağılımı:")
for pat, cnt in sorted(pat_count.items()):
    print(f"  {pat}: {cnt}")