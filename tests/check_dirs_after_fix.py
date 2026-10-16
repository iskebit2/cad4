# tests/check_dirs_after_fix.py
from tools.s2kloader import S2KLoader
from collections import Counter

loader = S2KLoader("examples/model4.$2k")   # veya mevcut S2K dosyanız
p = loader.load()

cnt = Counter()
for f in p.scene.frames.values():
    for pat, ls in (getattr(f, "dist_load_sets", {}) or {}).items():
        cnt[(pat, ls.load_dir, ls.coord_sys)] += 1

print("S2K'den yüklenen load_dir dağılımı:")
for (pat, ld, cs), c in cnt.most_common(30):
    print(f"  pat={pat!r:25s} load_dir={ld!r:3s} coord={cs!r:8s} → {c}")