# tests/debug_deep_compare.py
from tools.s2kloader import S2KLoader
from domain.project import Project

proj1 = S2KLoader("examples/d21a4.s2k").load()
proj1.save("tmp_deep.cd4")
proj2 = Project.load("tmp_deep.cd4")

# Frame yüklerini derinlemesine karşılaştır
mismatches = 0
checked = 0
for uid, f1 in proj1.scene.frames.items():
    f2 = proj2.scene.frames.get(uid)
    if f2 is None:
        print(f"❌ Frame {uid} kayıp!")
        mismatches += 1
        continue
    
    if len(f1.dist_loads) != len(f2.dist_loads):
        print(f"❌ Frame {uid}: dist_loads {len(f1.dist_loads)} → {len(f2.dist_loads)}")
        mismatches += 1
        continue
    
    for i, (l1, l2) in enumerate(zip(f1.dist_loads, f2.dist_loads)):
        checked += 1
        if l1.pattern_name != l2.pattern_name:
            print(f"❌ Frame {uid}.dist[{i}]: pattern '{l1.pattern_name}' → '{l2.pattern_name}'")
            mismatches += 1
        if l1.direction != l2.direction:
            print(f"❌ Frame {uid}.dist[{i}]: direction {l1.direction} → {l2.direction}")
            mismatches += 1
        if abs(l1.p1 - l2.p1) > 1e-9:
            print(f"❌ Frame {uid}.dist[{i}]: p1 {l1.p1} → {l2.p1}")
            mismatches += 1
        if abs(l1.p2 - l2.p2) > 1e-9:
            print(f"❌ Frame {uid}.dist[{i}]: p2 {l1.p2} → {l2.p2}")
            mismatches += 1
        if l1.direction != l2.direction:
            print(f"❌ Frame {uid}.dist[{i}]: direction farkı")
            mismatches += 1

print(f"\n=== Karşılaştırma ===")
print(f"Frame sayısı: {len(proj1.scene.frames)}")
print(f"Karşılaştırılan yük: {checked}")
print(f"Uyuşmazlık: {mismatches}")

# Enum tip kontrolü
from domain.definition import LoadDirection
for uid, f in list(proj2.scene.frames.items())[:5]:
    for l in f.dist_loads:
        assert type(l.direction) is LoadDirection, \
            f"Frame {uid}: direction tipi {type(l.direction)}, LoadDirection değil"
print("✓ Enum tipleri doğru")