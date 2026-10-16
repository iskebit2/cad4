# tests/check_zone_id_stability.py
from domain.project import Project

p1 = Project.load("model_projesi.cd4")
roof1 = next((poly for poly in p1.scene.polygons.values()
              if poly.label == "ROOF"), None)
print(f"ROOF unique_id (1. yükleme): {roof1.unique_id if roof1 else '?'}")

# İkinci kez yükle
p2 = Project.load("model_projesi.cd4")
roof2 = next((poly for poly in p2.scene.polygons.values()
              if poly.label == "ROOF"), None)
print(f"ROOF unique_id (2. yükleme): {roof2.unique_id if roof2 else '?'}")

if roof1 and roof2:
    print(f"Aynı mı? {roof1.unique_id == roof2.unique_id}")