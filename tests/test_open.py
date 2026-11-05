
import math
import os

import json
import zipfile
from pathlib import Path

from domain.project import Project
from logging_config import CadLogger
logger = CadLogger.get(__name__)

class GeneralLoadDistributor:
    def __init__(self, frames: dict, zones: dict):
        self.frames = frames
        self.zones = zones

    def _is_point_in_polygon(self, x, y, poly_coords):
        n = len(poly_coords)
        inside = False
        p1x, p1y = poly_coords[0][0], poly_coords[0][1]
        for i in range(1, n + 1):
            p2x, p2y = poly_coords[i % n][0], poly_coords[i % n][1]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    def _distance_point_to_segment_2d(self, px, py, x1, y1, x2, y2):
        l2 = (x2 - x1)**2 + (y2 - y1)**2
        if l2 == 0:
            return ((px - x1)**2 + (py - y1)**2)**0.5
        t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / l2))
        proj_x = x1 + t * (x2 - x1)
        proj_y = y1 + t * (y2 - y1)
        return ((px - proj_x)**2 + (py - proj_y)**2)**0.5

    def distribute_all_zone_loads(self, target_step: float = 200.0):
        master_results = {}
        step_m = target_step / 1000.0
        dA = step_m * step_m

        for z_id, z_data in self.zones.items():
            coords = z_data["coords"]
            load_keys = [k for k in z_data.keys() if k != "coords"]
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)

            y = min_y
            while y <= max_y:
                x = min_x
                while x <= max_x:
                    if self._is_point_in_polygon(x, y, coords):
                        closest_frame = None
                        min_dist = float('inf')
                        for f_id, f_nodes in self.frames.items():
                            x1, y1 = f_nodes[0][0], f_nodes[0][1]
                            x2, y2 = f_nodes[1][0], f_nodes[1][1]
                            dist = self._distance_point_to_segment_2d(x, y, x1, y1, x2, y2)
                            if dist < min_dist:
                                min_dist = dist
                                closest_frame = f_id
                        
                        if closest_frame is not None:
                            for l_type in load_keys:
                                l_info = z_data[l_type]
                                mag = l_info["mag"]
                                direction = l_info["dir"]
                                if l_type not in master_results:
                                    master_results[l_type] = {f: {"total_force": 0.0, "direction": direction} for f in self.frames}
                                master_results[l_type][closest_frame]["total_force"] += mag * dA

                    x += target_step
                y += target_step

        formatted_outputs = {}
        for l_type, frames_data in master_results.items():
            formatted_outputs[l_type] = {}
            for f_id, data in frames_data.items():
                f_nodes = self.frames[f_id]
                length = ((f_nodes[1][0] - f_nodes[0][0])**2 + (f_nodes[1][1] - f_nodes[0][1])**2 + (f_nodes[1][2] - f_nodes[0][2])**2)**0.5
                length_m = length / 1000.0
                if length_m > 0:
                    total_f = data["total_force"]
                    formatted_outputs[l_type][f_id] = {
                        "line_load_kN_per_m": total_f / length_m,
                        "total_force_kN": total_f,
                        "direction": data["direction"]
                    }
        return formatted_outputs
    


class AnalyticalCD4Reader:
    def __init__(self, filepath: str = "model_projesi.cd4", tol: float = 1.0):
        self.filepath = Path(filepath)
        self.tol = tol
        self.data = self._load_json()
        self.nodes_map = {n["unique_id"]: (n["x"], n["y"], n["z"]) for n in self.scene.get("nodes", [])}

    def _load_json(self) -> dict:
        if not self.filepath.exists():
            return {}
        with zipfile.ZipFile(self.filepath, "r") as zf:
            if "project.json" in zf.namelist():
                return json.loads(zf.read("project.json").decode("utf-8"))
        return {}

    @property
    def scene(self) -> dict:
        return self.data.get("scene", {})

    def _get_polygon_coords(self, polygon: dict) -> list:
        return [self.nodes_map[nid] for nid in polygon.get("node_ids", []) if nid in self.nodes_map]

    @staticmethod
    def _calculate_plane(coords: list):
        n = len(coords)
        if n < 3:
            return None
        
        nx, ny, nz = 0.0, 0.0, 0.0
        cx, cy, cz = 0.0, 0.0, 0.0

        for i in range(n):
            x1, y1, z1 = coords[i]
            x2, y2, z2 = coords[(i + 1) % n]
            
            nx += (y1 - y2) * (z1 + z2)
            ny += (z1 - z2) * (x1 + x2)
            nz += (x1 - x2) * (y1 + y2)
            
            cx += x1
            cy += y1
            cz += z1

        length = math.sqrt(nx*nx + ny*ny + nz*nz)
        if length < 1e-9:
            return None
        
        A, B, C = nx / length, ny / length, nz / length
        centroid = (cx / n, cy / n, cz / n)
        D = -(A * centroid[0] + B * centroid[1] + C * centroid[2])
        return (A, B, C, D)

    def _point_to_plane_distance(self, pt, plane) -> float:
        x, y, z = pt
        A, B, C, D = plane
        return abs(A * x + B * y + C * z + D)

    def get_surface_polygons(self) -> list:
        """
        Surface tipli poligonları istenen formatta döndürür:
        [{"label": ..., "coords": [...]}, ...]
        """
        surfaces = []
        for p in self.scene.get("polygons", []):
            if p.get("poly_type") == "SURFACE":
                coords = self._get_polygon_coords(p)
                surfaces.append({
                    "label": p.get("label", f"Polygon_{p.get('unique_id')}"),
                    "coords": [list(c) for c in coords]
                })
        return surfaces

    def get_frames_dict_on_polygon(self, polygon_label: str) -> dict:
        """
        Polygon label'ına göre düzlem üzerindeki frame'leri döner:
        { frame_label: [node_i.coords, node_j.coords], ... }
        """
        target_polygon = None
        for p in self.scene.get("polygons", []):
            if p.get("poly_type") == "SURFACE" and p.get("label") == polygon_label:
                target_polygon = p
                break
        
        if not target_polygon:
            return {}

        poly_coords = self._get_polygon_coords(target_polygon)
        plane = self._calculate_plane(poly_coords)
        if not plane:
            return {}

        result = {}
        for frame in self.scene.get("frames", []):
            ni_id = frame.get("node_i_id")
            nj_id = frame.get("node_j_id")
            
            ni_coords = self.nodes_map.get(ni_id)
            nj_coords = self.nodes_map.get(nj_id)
            
            if not ni_coords or not nj_coords:
                continue

            if (self._point_to_plane_distance(ni_coords, plane) <= self.tol and 
                self._point_to_plane_distance(nj_coords, plane) <= self.tol):
                
                f_label = frame.get("label", f"Frame_{frame.get('unique_id')}")
                result[f_label] = [list(ni_coords), list(nj_coords)]

        return result


if __name__ == "__main__":
    path = "model_projesi.cd4"
    reader = AnalyticalCD4Reader(path, tol=1.0)
    
    surfaces = reader.get_surface_polygons()
    #print("Surface Poligonlar:")
    #print(json.dumps(surfaces, indent=4))
    #print("-" * 50)

    # Örn: Seçili veya ismi bilinen polygon üzerine Dead ve Live yük atama
    # my_polygon.add_uniform_to_frame_load(pattern_name="DEAD", value=2.5, dist_type=DistType.ONE_WAY)
    # my_polygon.add_uniform_to_frame_load(pattern_name="LIVE", value=3.0, dist_type=DistType.TWO_WAY)
    
    # for surf in surfaces:
    #     label = surf["label"]
    #     frames_dict = reader.get_frames_dict_on_polygon(label)
    #     #print(f"Surface '{label}' Düzlemindeki Frame'ler:")
    #     #print(json.dumps(frames_dict, indent=4))
    #     #print("-" * 50)