# core/analysis_bridge.py
"""
CAD Scene ↔ Structload proje_data köprüsü.

CAD'in Scene yapısını, structload'un beklediği proje_data dict'ine çevirir.
"""
import copy
from logging_config import CadLogger
logger = CadLogger.get(__name__)

from structload.data.defaults import proje_data as DEFAULT_DATA


def scene_to_project_data(scene, base_data=None,
                          wind_cfg=None, snow_cfg=None, eq_cfg=None):
    """
    CAD Scene'i structload proje_data formatına çevir.
    
    Parameters
    ----------
    scene : Scene
        CAD sahnesi (nodes, polygons)
    base_data : dict, optional
        Temel data (default: structload.data.defaults.proje_data)
    wind_cfg, snow_cfg, eq_cfg : dict, optional
        Override parametreler
    
    Returns
    -------
    dict — structload proje_data
    """
    data = copy.deepcopy(base_data or DEFAULT_DATA)
    
    # ============================================================
    # 1. Points — CAD node → structload format
    # ============================================================
    points = {}
    node_id_map = {}
    
    for i, (uid, node) in enumerate(scene.nodes.items(), start=1):
        label = getattr(node, 'label', '').strip()
        if not label or label in points:
            label = f"P{i}"
        
        node_id_map[uid] = label
        points[label] = [float(node.x), float(node.y), float(node.z)]
    
    # ============================================================
    # 2. Polygons — CAD polygon → structload format
    # ============================================================
    polygons = {}
    polygon_id_map = {}
    
    for i, (uid, poly) in enumerate(scene.polygons.items(), start=1):
        label = getattr(poly, 'label', '').strip()
        if not label or label in polygons:
            label = f"D{i}"
        
        polygon_id_map[uid] = label
        
        node_labels = []
        for node in poly.nodes:
            nl = node_id_map.get(node.unique_id)
            if nl:
                node_labels.append(nl)
        
        if len(node_labels) >= 3:
            polygons[label] = node_labels
    
    # ============================================================
    # 3. Data'yı güncelle
    # ============================================================
    data["points"] = points
    data["polygons"] = polygons
    
    if wind_cfg:
        data["wind_config"] = wind_cfg
    if snow_cfg:
        data["snow_config"] = snow_cfg
    if eq_cfg:
        data["earthquake_config"] = eq_cfg
    
    # Reverse map'ler
    data["_node_id_map"] = node_id_map
    data["_polygon_id_map"] = polygon_id_map
    
    logger.info(f"[Bridge] {len(points)} points, {len(polygons)} polygons")
    return data