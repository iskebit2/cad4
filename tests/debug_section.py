# tools/debug_section.py
import sys
from domain.project import Project

path = sys.argv[1] if len(sys.argv) > 1 else "test_model2.cd4"
p = Project.load(path)

# Frame'lerin kesitlerine bak, A>1e5 olanları göster
seen = set()
print("=== Şüpheli kesitler (A > 1e5 mm²) ===")
for f in p.scene.frames.values():
    sec = f.section
    if sec is None:
        continue
    name = sec.name
    if name in seen:
        continue
    seen.add(name)
    pp = sec.profile_params or {}
    A = pp.get("Area", 0)
    if A > 1e5:
        print(f"\nKesit: {name}")
        print(f"  profile_type: {sec.profile_type}")
        print(f"  profile_params: {pp}")
        print(f"  catalog_props: {getattr(sec, 'catalog_props', {})}")
        print(f"  catalog_source: {getattr(sec, 'catalog_source', '')}")