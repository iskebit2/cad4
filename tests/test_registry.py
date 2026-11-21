# tests/test_registry.py
from ui.helpers.registry import discover_panels
import ui.panels as pkg

specs = discover_panels(pkg)
print(f"--- {len(specs)} panel ---")
for s in specs:
    print(f"  {s.name:20s} | {s.category:12s} | quick={s.quick!s:5s} | ctx={s.context}")