# tests/inspect_load_dirs.py
from domain.project import Project

p = Project.load("model_projesi.cd4")
scene = p.scene

from collections import Counter
counts = Counter()

for f in scene.frames.values():
    sets = getattr(f, "dist_load_sets", {}) or {}
    for pat, ls in sets.items():
        key = (getattr(ls, "coord_sys", "?"), getattr(ls, "load_dir", "?"))
        counts[key] += 1

print("FrameDistributedLoadSet dağılımı:")
for (csys, ld), cnt in counts.most_common():
    print(f"  coord_sys={csys!r:12s} load_dir={ld!r:5s} → {cnt} set")