# core/cad4_exchange.py
"""
CAD4 ↔ AutoCAD iki yönlü veri alışverişi.

SAP yerine kendi Scene modelimizi kullanır:
    Node, Frame, Area, Link, Polygon

Kullanım:
    from core.cad4_exchange import CAD4AutoCADBridge

    bridge = CAD4AutoCADBridge()
    bridge.connect()

    # CAD4 → AutoCAD
    bridge.export_scene(scene, layer_config={...})

    # AutoCAD → CAD4
    bridge.import_selected_into(scene, unit_factor=1.0)
"""
import array
import logging
from contextlib import contextmanager
from typing import Optional, Dict, List, Tuple

import pythoncom
from pyautocad import Autocad, APoint

from domain.scene import Scene
from domain.element import Node, Frame, Area, Link, Polygon

logger = logging.getLogger(__name__)


# ============================================================
# AutoCAD Bağlantı Katmanı (SAP sürümünden uyarlanmış)
# ============================================================

class AutoCADConnector:
    """AutoCAD COM bağlantısı ve temel çizim işlemleri."""

    def __init__(self, create_if_not_exists=True):
        try:
            self.acad = Autocad(create_if_not_exists=create_if_not_exists)
            self.doc = self.acad.ActiveDocument
            self.model = self.acad.model
            logger.info("AutoCAD bağlantısı başarılı")
        except Exception as e:
            logger.error(f"AutoCAD bağlantı hatası: {e}")
            raise

    @contextmanager
    def active_layer(self, layer_name: str, color: Optional[int] = None):
        old = self.doc.ActiveLayer
        layers = self.doc.Layers
        try:
            try:
                layer = layers.Item(layer_name)
            except Exception:
                layer = layers.Add(layer_name)
                if color is not None:
                    layer.Color = color
            self.doc.ActiveLayer = layer
            yield
        finally:
            self.doc.ActiveLayer = old

    # ---------- Çizimler ----------

    def add_point(self, p):
        self.doc.SendCommand(
            f"_POINT {p[0]},{p[1]},{p[2]} \n"
        )

    def add_line(self, p1, p2):
        self.doc.SendCommand(
            f"_LINE {p1[0]},{p1[1]},{p1[2]} {p2[0]},{p2[1]},{p2[2]} \n"
        )

    def add_3dpoly(self, points, close=False):
        cmd = "_3DPOLY "
        for x, y, z in points:
            cmd += f"{x},{y},{z} "
        if close and points:
            x, y, z = points[0]
            cmd += f"{x},{y},{z} "
        cmd += "\n"
        self.doc.SendCommand(cmd)

    def add_tag(self, obj, tag_value: str, app_name="CAD4_TAG_APP"):
        """Son nesneye XData olarak tag ekle (opsiyonel)."""
        try:
            try:
                self.doc.RegisteredApplications.Add(app_name)
            except Exception:
                pass

            d_type = array.array('i', [1001, 1000])
            d_val = [app_name, str(tag_value)]
            obj.SetXData(d_type, d_val)
            logger.debug(f"Tag atandı: {tag_value}")
        except Exception as e:
            logger.warning(f"Tag atanamadı: {e}")

    def zoom_extents(self):
        try:
            self.acad.app.ZoomExtents()
        except Exception:
            pass

    def get_selection(self):
        """AutoCAD'de seçili nesneleri döndürür."""
        return self.doc.PickfirstSelectionSet

    def clear_selection(self):
        try:
            self.doc.SendCommand("_SELECT \n \n")
        except Exception:
            pass


# ============================================================
# CAD4 ↔ AutoCAD Bridge
# ============================================================

class CAD4AutoCADBridge:
    """Scene ile AutoCAD arasında iki yönlü transfer."""

    # AutoCAD ObjectName → CAD4 tipi
    OBJ_LINE = "AcDbLine"
    OBJ_POINT = "AcDbPoint"
    OBJ_3DPOLY = "AcDb3dPolyline"
    OBJ_LWPOLY = "AcDbPolyline"
    OBJ_POLYLINE = "AcDb2dPolyline"

    def __init__(self):
        self.acad: Optional[AutoCADConnector] = None

    # --------------------------------------------------
    # BAĞLANTI
    # --------------------------------------------------

    def connect(self) -> bool:
        try:
            self.acad = AutoCADConnector(create_if_not_exists=True)
            return True
        except Exception as e:
            logger.error(f"AutoCAD bağlantısı kurulamadı: {e}")
            return False

    def disconnect(self):
        self.acad = None

    @property
    def connected(self) -> bool:
        return self.acad is not None

    # ==================================================
    # CAD4 → AutoCAD  (EXPORT)
    # ==================================================

    def export_scene(self, scene: Scene,
                     layer_config: Optional[Dict[str, Tuple[str, int]]] = None,
                     tag_with_label: bool = False) -> Dict[str, int]:
        """
        Scene'deki tüm elemanları AutoCAD'e çizer.

        Returns:
            {"nodes": n, "frames": n, "areas": n, "links": n, "polygons": n}
        """
        if not self.connected:
            logger.error("AutoCAD bağlı değil")
            return {}

        if layer_config is None:
            layer_config = {
                "nodes":    ("CAD4_NODES",    1),
                "frames":   ("CAD4_FRAMES",   3),
                "areas":    ("CAD4_AREAS",    5),
                "links":    ("CAD4_LINKS",    6),
                "polygons": ("CAD4_POLYGONS", 4),
            }

        counts = {
            "nodes": 0, "frames": 0, "areas": 0, "links": 0, "polygons": 0
        }

        # --- NODES ---
        name, color = layer_config["nodes"]
        with self.acad.active_layer(name, color):
            for node in scene.nodes.values():
                try:
                    self.acad.add_point((node.x, node.y, node.z))
                    counts["nodes"] += 1
                except Exception as e:
                    logger.warning(f"Node {node.label} export hatası: {e}")

        # --- FRAMES ---
        name, color = layer_config["frames"]
        with self.acad.active_layer(name, color):
            for frame in scene.frames.values():
                try:
                    ni, nj = frame.node_i, frame.node_j
                    self.acad.add_line(
                        (ni.x, ni.y, ni.z),
                        (nj.x, nj.y, nj.z),
                    )
                    counts["frames"] += 1
                except Exception as e:
                    logger.warning(f"Frame {frame.label} export hatası: {e}")

        # --- LINKS ---
        name, color = layer_config["links"]
        with self.acad.active_layer(name, color):
            for link in scene.links.values():
                try:
                    ni, nj = link.node_i, link.node_j
                    self.acad.add_line(
                        (ni.x, ni.y, ni.z),
                        (nj.x, nj.y, nj.z),
                    )
                    counts["links"] += 1
                except Exception as e:
                    logger.warning(f"Link {link.label} export hatası: {e}")

        # --- AREAS ---
        name, color = layer_config["areas"]
        with self.acad.active_layer(name, color):
            for area in scene.areas.values():
                try:
                    pts = [(n.x, n.y, n.z) for n in area.nodes]
                    if len(pts) >= 3:
                        self.acad.add_3dpoly(pts, close=True)
                        counts["areas"] += 1
                except Exception as e:
                    logger.warning(f"Area {area.label} export hatası: {e}")

        # --- POLYGONS ---
        name, color = layer_config["polygons"]
        with self.acad.active_layer(name, color):
            for polygon in scene.polygons.values():
                try:
                    pts = [(n.x, n.y, n.z) for n in polygon.nodes]
                    if len(pts) >= 3:
                        self.acad.add_3dpoly(pts, close=True)
                        counts["polygons"] += 1
                except Exception as e:
                    logger.warning(f"Polygon {polygon.label} export hatası: {e}")

        self.acad.zoom_extents()
        logger.info(f"Export tamamlandı: {counts}")
        return counts

    # ==================================================
    # AutoCAD → CAD4  (IMPORT)
    # ==================================================

    def import_selected_into(self, scene: Scene,
                             unit_factor: float = 1.0,
                             layer_filter: Optional[List[str]] = None,
                             auto_connect_nodes: bool = True,
                             import_as: str = "auto") -> Dict[str, int]:
        """
        AutoCAD'de seçili nesneleri Scene'e ekler.

        Args:
            scene: hedef Scene
            unit_factor: ölçek (ör. mm→m için 0.001)
            layer_filter: sadece bu layer'ları işle (None = hepsi)
            auto_connect_nodes: Frame/Area/Link için node'ları paylaş
            import_as: "auto" | "frame" | "area" | "node" | "link"
                       auto: LINE→Frame, POLYLINE→Area, POINT→Node

        Returns:
            {"nodes": n, "frames": n, "areas": n, "links": n}
        """
        if not self.connected:
            logger.error("AutoCAD bağlı değil")
            return {}

        selection = self.acad.get_selection()
        if selection.Count == 0:
            logger.warning("AutoCAD'de seçili nesne yok")
            return {}

        counts = {"nodes": 0, "frames": 0, "areas": 0, "links": 0}
        node_cache: Dict[Tuple[float, float, float], Node] = {}

        for obj in selection:
            if layer_filter and obj.Layer not in layer_filter:
                continue

            try:
                obj_name = obj.ObjectName

                if obj_name == self.OBJ_LINE:
                    if import_as in ("auto", "frame", "link"):
                        self._import_line(
                            scene, obj, unit_factor,
                            node_cache, auto_connect_nodes,
                            as_type=("link" if import_as == "link" else "frame"),
                            counts=counts,
                        )

                elif obj_name == self.OBJ_POINT:
                    if import_as in ("auto", "node"):
                        self._import_point(
                            scene, obj, unit_factor,
                            node_cache, counts,
                        )

                elif obj_name in (self.OBJ_3DPOLY, self.OBJ_LWPOLY,
                                  self.OBJ_POLYLINE):
                    if import_as in ("auto", "area"):
                        self._import_polyline(
                            scene, obj, unit_factor,
                            node_cache, auto_connect_nodes, counts,
                        )

            except Exception as e:
                logger.warning(f"Import hatası ({obj.ObjectName}): {e}")
                continue

        logger.info(f"Import tamamlandı: {counts}")
        return counts

    # --------------------------------------------------
    # IMPORT YARDIMCILARI
    # --------------------------------------------------

    def _import_line(self, scene, obj, unit_factor,
                     node_cache, auto_connect, as_type, counts):
        start = obj.StartPoint
        end = obj.EndPoint

        p1 = self._scaled(start, unit_factor)
        p2 = self._scaled(end, unit_factor)

        n1 = self._get_or_create_node(scene, p1, node_cache, auto_connect)
        n2 = self._get_or_create_node(scene, p2, node_cache, auto_connect)

        if as_type == "link":
            link = Link(node_i=n1, node_j=n2)
            scene.add_link(link)
            counts["links"] += 1
        else:
            frame = Frame(node_i=n1, node_j=n2, section=None)
            scene.add_frame(frame)
            counts["frames"] += 1

    def _import_point(self, scene, obj, unit_factor,
                      node_cache, counts):
        pos = obj.Coordinates
        x = pos[0] * unit_factor
        y = pos[1] * unit_factor
        z = (pos[2] if len(pos) > 2 else 0.0) * unit_factor
        key = (round(x, 6), round(y, 6), round(z, 6))

        if key in node_cache:
            return

        node = Node(x=x, y=y, z=z)
        scene.add_node(node)
        node_cache[key] = node
        counts["nodes"] += 1

    def _import_polyline(self, scene, obj, unit_factor,
                         node_cache, auto_connect, counts):
        coords = obj.Coordinates

        is_3d = (obj.ObjectName == self.OBJ_3DPOLY)
        step = 3 if is_3d else 2
        elevation = float(getattr(obj, "Elevation", 0.0))

        points: List[Tuple[float, float, float]] = []
        for i in range(0, len(coords), step):
            x = coords[i] * unit_factor
            y = coords[i + 1] * unit_factor
            if is_3d:
                z = coords[i + 2] * unit_factor
            else:
                z = elevation * unit_factor
            points.append((x, y, z))

        # Ardışık mükerrer noktaları temizle
        unique: List[Tuple[float, float, float]] = []
        for p in points:
            if not unique or p != unique[-1]:
                unique.append(p)
        # Kapanış noktası tekrarı
        if len(unique) > 1 and unique[0] == unique[-1]:
            unique.pop()

        if len(unique) < 3:
            return

        # Node'ları oluştur (paylaşımlı)
        nodes = [self._get_or_create_node(scene, p, node_cache, auto_connect)
                 for p in unique]

        area = Area(nodes=nodes, thickness=0.0)
        scene.add_area(area)
        counts["areas"] += 1

    def _get_or_create_node(self, scene, xyz, cache, auto_connect):
        """Aynı koordinattaki node'u paylaş; yoksa oluştur."""
        if not auto_connect:
            node = Node(x=xyz[0], y=xyz[1], z=xyz[2])
            scene.add_node(node)
            return node

        key = (round(xyz[0], 6), round(xyz[1], 6), round(xyz[2], 6))
        if key in cache:
            return cache[key]

        # Scene içinde de ara (dışarıdan eklenmiş olabilir)
        for n in scene.nodes.values():
            if (round(n.x, 6), round(n.y, 6), round(n.z, 6)) == key:
                cache[key] = n
                return n

        node = Node(x=xyz[0], y=xyz[1], z=xyz[2])
        scene.add_node(node)
        cache[key] = node
        return node

    def _scaled(self, pt, factor) -> Tuple[float, float, float]:
        """AutoCAD 3'lü noktayı ölçekle."""
        x = pt[0] * factor
        y = pt[1] * factor
        z = (pt[2] if len(pt) > 2 else 0.0) * factor
        return (x, y, z)


# ============================================================
# KISA YOLLAR
# ============================================================

def export_scene_to_autocad(scene: Scene, **kwargs) -> bool:
    bridge = CAD4AutoCADBridge()
    if not bridge.connect():
        return False
    counts = bridge.export_scene(scene, **kwargs)
    return bool(counts)


def import_selected_into_scene(scene: Scene, **kwargs) -> bool:
    bridge = CAD4AutoCADBridge()
    if not bridge.connect():
        return False
    counts = bridge.import_selected_into(scene, **kwargs)
    return bool(counts)


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    from domain.scene import Scene
    from domain.element import Node, Frame, Area

    # --- Test sahnesi ---
    scene = Scene()
    n1 = Node(0.0, 0.0, 0.0, "N1"); scene.add_node(n1)
    n2 = Node(5.0, 0.0, 0.0, "N2"); scene.add_node(n2)
    n3 = Node(5.0, 5.0, 0.0, "N3"); scene.add_node(n3)
    n4 = Node(0.0, 5.0, 0.0, "N4"); scene.add_node(n4)

    scene.add_frame(Frame(node_i=n1, node_j=n2, section=None, label="F1"))
    scene.add_area(Area(nodes=[n1, n2, n3, n4], thickness=100.0, label="A1"))

    bridge = CAD4AutoCADBridge()
    if bridge.connect():
        print("Bağlantı OK")
        counts = bridge.export_scene(scene)
        print("Export:", counts)

        input("AutoCAD'de seçim yapıp ENTER'a basın (import testi)...")
        counts2 = bridge.import_selected_into(scene, unit_factor=1.0)
        print("Import:", counts2)