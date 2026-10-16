# tests/diagnose_zones.py
from domain.project import Project

project = Project.load("model_projesi.cd4")
scene = project.scene

print(f"Toplam polygon: {len(scene.polygons)}")
print()

for pid, poly in scene.polygons.items():
    pt = getattr(poly, "poly_type", None)
    pt_repr = pt.name if hasattr(pt, "name") else repr(pt)
    wp = getattr(poly, "windplane", {}) or {}
    print(f"  id={pid}")
    print(f"    label    = {poly.label!r}")
    print(f"    poly_type= {pt_repr}")
    print(f"    is_temp  = {getattr(poly, 'is_temporary', None)}")
    print(f"    nodes    = {len(poly.nodes)}")
    print(f"    windplane keys = {list(wp.keys())}")
    print(f"    windplane      = {wp}")
    print()