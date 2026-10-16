# tests/verify_wind_save.py
from domain.project import Project

p = Project.load("model_projesi_wind.cd4")
scene = p.scene

print(f"Polygons: {len(scene.polygons)}")
for pid, poly in scene.polygons.items():
    pt = poly.poly_type.name if hasattr(poly.poly_type, "name") else str(poly.poly_type)
    print(f"  {poly.label} ({pt}) temp={poly.is_temporary}")

print(f"\nFrames: {len(scene.frames)}")
total_sets = 0
total_segments = 0
for f in scene.frames.values():
    sets = getattr(f, "dist_load_sets", {}) or {}
    total_sets += len(sets)
    for s in sets.values():
        total_segments += len(s.segments)

print(f"Toplam pattern set: {total_sets}")
print(f"Toplam segment: {total_segments}")

# İlk 5 frame'i detaylı göster
print("\nİlk 5 frame:")
for f in list(scene.frames.values())[:5]:
    sets = getattr(f, "dist_load_sets", {}) or {}
    if sets:
        print(f"  {f.label}:")
        for pat, s in sets.items():
            print(f"    [{pat}] {len(s.segments)} segment | "
                  f"coord={s.coord_sys} dir={s.load_dir} mode={s.mode}")