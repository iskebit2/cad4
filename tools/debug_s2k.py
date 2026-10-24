# tools/debug_s2k.py
from tools.s2kloader import S2KLoader
from domain.project import Project

loader = S2KLoader("tests/eski_.s2k")
p = loader.load(Project())

# Atlananları bul
print(f"Frame: {len(p.scene.frames)}")
skipped = []
for f in p.scene.frames.values():
    sec = f.section
    if not sec:
        skipped.append((f.label, "no section"))
        continue
    pp = sec.profile_params or {}
    A = pp.get("Area", 0)
    if A <= 0:
        skipped.append((f.label, sec.name, pp))

print(f"Skipped: {len(skipped)}")
for s in skipped[:10]:
    print(f"  {s}")