# tests/inspect_saved_sets.py
from domain.project import Project

p = Project.load("model_projesi.cd4")

for f in list(p.scene.frames.values())[:3]:
    sets = getattr(f, "dist_load_sets", {}) or {}
    print(f"Frame {f.label}: {len(sets)} set")
    for pat, s in sets.items():
        seg_type = type(s.segments[0]).__name__ if s.segments else "boş"
        print(f"  [{pat}] pattern_name={s.pattern_name!r} "
              f"coord={s.coord_sys} dir={s.load_dir} mode={s.mode} "
              f"segments={len(s.segments)} tip={seg_type}")
        for seg in s.segments[:3]:
            if hasattr(seg, "q1"):
                print(f"    LoadSegment x1={seg.x1:.3f} q1={seg.q1:.3f}")
            elif isinstance(seg, dict):
                print(f"    dict x1={seg.get('x1')} q1={seg.get('q1')}")