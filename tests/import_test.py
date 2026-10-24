# tools/import_test.py
from tools.s2kloader import S2KLoader, S2KParser
from domain.project import Project
from core.analysis.material_takeoff import compute_takeoff

src = "examples/model4.$2k"

p = S2KParser(src)
df = p.get_table('PROGRAM CONTROL')
print("df.empty:", df.empty)
print("df shape:", df.shape)
print("columns:", list(df.columns))
if not df.empty:
    print(df.iloc[0].to_dict())


p = S2KLoader(src).load(Project())

# Kesit kontrolü
bad = []
for f in p.scene.frames.values():
    sec = f.section
    if sec is None:
        continue
    A = (sec.profile_params or {}).get("Area", 0)
    if A > 1e6:
        bad.append((f.label, sec.name, A))

print(f"Frame: {len(p.scene.frames)}")
print(f"Şüpheli (A>1e6): {len(bad)}")
for b in bad[:10]:
    print(f"  {b}")

t = compute_takeoff(p.scene)
print(f"\n{len(t.elements)} eleman, {t.total_mass_kg:.2f} kg "
      f"({t.total_mass_ton:.2f} ton)")

# İlk 5 frame'in kesit detayı
print("\nÖrnek kesitler:")
for f in list(p.scene.frames.values())[:5]:
    sec = f.section
    if sec is None:
        continue
    pp = sec.profile_params or {}
    print(f"  {f.label}: {sec.name}, A={pp.get('Area', 0):.0f}, "
          f"I33={pp.get('I33', 0):.2e}")

p.save("test_model2_fixed.cd4")
print("\nKaydedildi: test_model2_fixed.cd4")

# tools/import_test.py (mevcut sonuna ekle)

print("\n=== Material.density ===")
for name, m in list(p.materials.items())[:10]:
    print(f"  {name}: density={m.density:.4e} kg/mm³, E1={m.E1:.0f}")

print("\n=== İlk 3 frame.dist_loads ===")
for f in list(p.scene.frames.values())[:3]:
    print(f"  {f.label}: {len(f.dist_loads)} yük")

print("\n=== İlk 3 frame malzeme ===")
for f in list(p.scene.frames.values())[:3]:
    sec = f.section
    mat = sec.material if sec else None
    if mat:
        print(f"  {f.label}: section={sec.name}, "
              f"mat={mat.name}, density={mat.density:.4e}, "
              f"A={sec.profile_params.get('Area', 0):.0f}, "
              f"L={f.get_length():.0f}")

print("\n=== Takeoff detay ===")
from core.analysis.material_takeoff import compute_takeoff
p._migrate_materials()
t = compute_takeoff(p.scene)
print(f"Toplam: {t.total_mass_kg:.2f} kg")
print(f"Malzeme:")
for name, s in sorted(t.by_material.items()):
    print(f"  {name}: {s.element_count} eleman, {s.total_mass_kg:.2f} kg")

# Atlandı mı?
skipped = 0
for f in p.scene.frames.values():
    sec = f.section
    if sec is None:
        skipped += 1
        continue
    mat = sec.material
    if mat is None or (mat.density or 0) <= 0:
        skipped += 1
        continue
    if (sec.profile_params or {}).get("Area", 0) <= 0:
        skipped += 1
print(f"\nAtlanan frame: {skipped} / {len(p.scene.frames)}")