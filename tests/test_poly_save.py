import tempfile
from pathlib import Path
from data.enums import PolygonType
from domain.element import Node
from domain.polygon import Polygon
from domain.project import Project

# Polygon oluştur
p = Project()
s = p.scene
n1 = Node(0, 0, 0, label="n1")
n2 = Node(1000, 0, 0, label="n2")
n3 = Node(1000, 1000, 0, label="n3")
n4 = Node(0, 1000, 0, label="n4")
for nd in (n1, n2, n3, n4):
    s.add_node(nd)

poly = Polygon(
    [n1, n2, n3, n4],
    label="TestPoly",
    poly_type=PolygonType.SURFACE_TWOWAY,
)
s.add_polygon(poly)

# Kaydet
path = Path(tempfile.gettempdir()) / "poly_test.cd4"
p.save(str(path))
#print(f"Kaydedildi: {path}")

# JSON içinde ne var?
import json
import zipfile
with zipfile.ZipFile(path) as zf:
    payload = json.loads(zf.read("project.json"))
    polys = payload["scene"]["polygons"]
    #print(f"\nJSON poly_type: {polys[0].get('poly_type')!r}")

# Aç
p2 = Project.load(str(path))
p2_polys = list(p2.project.polygons.values())
#print(f"\nAçıldı: {len(p2_polys)} polygon")
for pp in p2_polys:
    #print(f"  label={pp.label}  poly_type={pp.poly_type!r}  "
          f"name={pp.poly_type.name if hasattr(pp.poly_type, 'name') else 'YOK'}")