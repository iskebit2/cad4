# tests/check_cpe_distribution.py
from domain.project import Project
from tools.wind_service import WindSceneAdapter

p = Project.load("model_projesi.cd4")
scene = p.scene
WindSceneAdapter.run_wind_analysis_and_update_scene(scene, w_dir=(1, 0, 0))

for poly in scene.polygons.values():
    if getattr(poly, "poly_type", None) and poly.poly_type.name == "ZONE":
        wp = poly.windplane or {}
        print(f"{poly.label}:")
        print(f"  cpe10 = {wp.get('cpe10')}")
        print(f"  cpe1  = {wp.get('cpe1')}")