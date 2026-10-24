# tools/debug_one.py
import sys
from domain.project import Project
from core.analysis.material_takeoff import compute_takeoff

path = sys.argv[1] if len(sys.argv) > 1 else "test_model.cd4"
print(f"=== {path} ===")
p = Project.load(path)

print(f"Node:   {len(p.scene.nodes)}")
print(f"Frame:  {len(p.scene.frames)}")
print(f"Area:   {len(p.scene.areas)}")
print(f"Link:   {len(p.scene.links)}")

# Takeoff detay
t = compute_takeoff(p.scene)
print(f"\nTakeoff: {len(t.elements)} eleman")
print(f"  Frame: {sum(1 for e in t.elements if e.element_type == 'Frame')}")
print(f"  Area:  {sum(1 for e in t.elements if e.element_type == 'Area')}")

# Malzeme dağılımı
print(f"\nMalzeme:")
for name, s in sorted(t.by_material.items(), key=lambda kv: -kv[1].total_mass_kg):
    print(f"  {name:20s}  {s.element_count:5d} eleman  "
          f"{s.total_mass_kg:12.2f} kg  "
          f"({s.total_mass_kg/1000:.2f} ton)")

# En ağır 5 eleman
print(f"\nEn ağır 5 eleman:")
top = sorted(t.elements, key=lambda e: -e.mass_kg)[:5]
for e in top:
    print(f"  {e.element_type} {e.label}: "
          f"{e.mass_kg:.2f} kg "
          f"(L={e.length:.0f}, A={e.area:.0f}, rho={e.density:.2e})")