from domain.project import Project
from tools.wind_service import WindSceneAdapter
from tools.wind_zone_distribution_service import WindZoneDistributionService

project = Project.load("model_projesi.cd4")
scene = project.scene

print(f"Başlangıç polygon: {len(scene.polygons)}")

# 1) Rüzgar analizi
try:
    WindSceneAdapter.run_wind_analysis_and_update_scene(
        scene=scene,
        w_dir=(1, 0, 0),
    )
except Exception as e:
    print(f"[!] Analiz hatası: {e}")
    raise

print(f"Analiz sonrası polygon: {len(scene.polygons)}")
for pid, poly in scene.polygons.items():
    pt = getattr(poly, "poly_type", None)
    pt_name = pt.name if hasattr(pt, "name") else str(pt)
    print(f"  {poly.label} ({pt_name}) windplane_keys={list(poly.windplane.keys())}")

# 2) Zone → Frame dağıtımı
n = WindZoneDistributionService.distribute(scene, clear_existing=True)
print(f"\n{n} segment atandı.")

project.save("model_projesi_wind.cd4")
print("Kaydedildi: model_projesi_wind.cd4")