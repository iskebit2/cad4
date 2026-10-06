# SAP2000 birim enum değerleri
UNIT_DEFINITIONS = {
    1: ('lb', 'in'),
    2: ('lb', 'ft'),
    3: ('kip', 'in'),
    4: ('kip', 'ft'),
    5: ('kN', 'mm'),
    6: ('kN', 'm'),
    7: ('kgf', 'mm'),
    8: ('kgf', 'm'),
    9: ('N', 'mm'),
    10: ('N', 'm'),
    11: ('Ton', 'mm'),
    12: ('Ton', 'm'),
    13: ('kN', 'cm'),
    14: ('kgf', 'cm'),
    15: ('N', 'cm'),
    16: ('Ton', 'cm')
}

# Enumerations
LOAD_PATTERN_TYPES = {
    1: "DEAD",
    2: "SUPERDEAD",
    3: "LIVE",
    4: "REDUCELIVE",
    5: "QUAKE",
    6: "WIND",
    7: "SNOW",
    8: "OTHER",
    9: "MOVE",
    10: "TEMPERATURE",
    11: "ROOFLIVE",
    12: "NOTIONAL",
    13: "PATTERNLIVE",
    14: "WAVE",
    15: "BRAKING",
    16: "CENTRIFUGAL",
    17: "FRICTION",
    18: "ICE",
    19: "WINDONLIVELOAD",
    20: "HORIZONTALEARTHPRESSURE",
    21: "VERTICALEARTHPRESSURE",
    22: "EARTHSURCHARGE",
    23: "DOWNDRAG",
    24: "VEHICLECOLLISION",
    25: "VESSELCOLLISION",
    26: "TEMPERATUREGRADIENT",
    27: "SETTLEMENT",
    28: "SHRINKAGE",
    29: "CREEP",
    30: "WATERLOADPRESSURE",
    31: "LIVELOADSURCHARGE",
    32: "LOCKEDINFORCES",
    33: "PEDESTRIANLL",
    34: "PRESTRESS",
    35: "HYPERSTATIC",
    36: "BOUYANCY",
    37: "STREAMFLOW",
    38: "IMPACT",
    39: "CONSTRUCTION"
}

LOAD_CASE_TYPES = {
    1: "LinearStatic",
    2: "NonlinearStatic",
    3: "Modal",
    4: "ResponseSpectrum",
    5: "LinearHistory",           # Modal Time History
    6: "NonlinearHistory",        # Modal Time History
    7: "LinearDynamic",           # Direct Integration Time History
    8: "NonlinearDynamic",        # Direct Integration Time History
    9: "MovingLoad",
    10: "Buckling",
    11: "SteadyState",
    12: "PowerSpectralDensity",
    13: "LinearStaticMultistep",
    14: "Hyperstatic",
    15: "ExternalResults",
    16: "StagedConstruction",
    17: "NonlinearStaticMultiStep"
}

LOAD_CASE_DESIGN_TYPES = {
    1: "DEAD", 2: "SUPERDEAD", 3: "LIVE", 4: "REDUCELIVE", 5: "QUAKE", 6: "WIND", 7: "SNOW",
    8: "OTHER", 9: "MOVE", 10: "TEMPERATURE", 11: "ROOFLIVE", 12: "NOTIONAL", 13: "PATTERNLIVE",
    14: "WAVE", 15: "BRAKING", 16: "CENTRIFUGAL", 17: "FRICTION", 18: "ICE", 19: "WINDONLIVELOAD",
    20: "HORIZONTALEARTHPRESSURE", 21: "VERTICALEARTHPRESSURE", 22: "EARTHSURCHARGE", 23: "DOWNDRAG",
    24: "VEHICLECOLLISION", 25: "VESSELCOLLISION", 26: "TEMPERATUREGRADIENT", 27: "SETTLEMENT",
    28: "SHRINKAGE", 29: "CREEP", 30: "WATERLOADPRESSURE", 31: "LIVELOADSURCHARGE",
    32: "LOCKEDINFORCES", 33: "PEDESTRIANLL", 34: "PRESTRESS", 35: "HYPERSTATIC", 36: "BOUYANCY",
    37: "STREAMFLOW", 38: "IMPACT", 39: "CONSTRUCTION", 40: "DEADWEARING", 41: "DEADWATER",
    42: "DEADMANUFACTURE", 43: "EARTHHYDROSTATIC", 44: "PASSIVEEARTHPRESSURE",
    45: "ACTIVEEARTHPRESSURE", 46: "PEDESTRIANLLREDUCED", 47: "SNOWHIGHALTITUDE", 48: "EUROLM1CHAR",
    49: "EUROLM1FREQ", 50: "EUROLM2", 51: "EUROLM3", 52: "EUROLM4"
}

OBJECT_TYPE_MAP = {
    1: "Point",
    2: "Frame",
    3: "Cable",
    4: "Tendon",
    5: "Area",
    6: "Solid",
    7: "Link"
}

import comtypes.client
import comtypes
import numpy as np
from typing import Dict, List, Optional


class cSap:
    """SAP2000 API bağlantı ve işlem sınıfı - Tüm SAP işlemleri bu sınıfta toplanır"""
    
    def __init__(self, attach: bool = True):
        
        try:
            helper = comtypes.client.CreateObject('SAP2000v1.Helper').QueryInterface(comtypes.gen.SAP2000v1.cHelper)
            if attach:
                try:
                    self.SapObject = helper.GetObject("CSI.SAP2000.API.SapObject")
                except:
                    self.SapObject = helper.CreateObjectProgID("CSI.SAP2000.API.SapObject")
                    self.SapObject.ApplicationStart()
            else:
                self.SapObject = helper.CreateObjectProgID("CSI.SAP2000.API.SapObject")
                self.SapObject.ApplicationStart()
            
            self.SapModel = self.SapObject.SapModel
            
            print("SAP2000 bağlantısı başarılı")
            print(self.get_model_info())
        except Exception as e:
            print(f"Bağlantı hatası: {str(e)}")
            self.SapModel = None

    # --------------------------------------------------
    # MODEL BİLGİLERİ VE AYARLAR
    # --------------------------------------------------
    
    def get_model_info(self) -> Dict[str, str]:
        """Model bilgilerini getirir"""
        if not self.SapModel:
            return {}
        
        info = {}
        try:
            unit_enum = self.SapModel.GetPresentUnits()
            info['Units'] = " ".join(UNIT_DEFINITIONS.get(unit_enum, ('?', '?')))
            info['Filename'] = self.SapModel.GetModelFilename()
            info['Locked'] = self.SapModel.GetModelIsLocked()
        except Exception as e:
            print(f"Bilgi alınamadı: {str(e)}")
        return info
    
    def refresh_view(self):
        """Görünümü yeniler"""
        if self.SapModel:
            self.SapModel.View.RefreshView()
    
    def set_units(self, unit_enum: int):
        """Birimleri ayarlar"""
        if self.SapModel:
            return self.SapModel.SetPresentUnits(unit_enum)
        return None
    
    def get_present_units(self):
        """Mevcut birimleri getirir"""
        if self.SapModel:
            return self.SapModel.GetPresentUnits()
        return None
    
    # --------------------------------------------------
    # SEÇİM İŞLEMLERİ
    # --------------------------------------------------
    
    def get_selected_objects(self):
        """Seçili nesneleri getirir"""
        if not self.SapModel:
            return []
        
        ret = self.SapModel.SelectObj.GetSelected()
        n = ret[0]
        types = ret[1]
        names = ret[2]
        
        selected = []
        for i in range(n):
            selected.append({
                "type_id": types[i],
                "type": OBJECT_TYPE_MAP.get(types[i], "Unknown"),
                "name": names[i]
            })
        return selected
    
    def clear_selection(self):
        """Seçimi temizler"""
        if self.SapModel:
            self.SapModel.SelectObj.ClearSelection()
    
    def select_by_coordinate_range(self, xmin, xmax, ymin, ymax, zmin, zmax, 
                                   include_intersections=True, csys="Global",
                                   select_points=True, select_frames=True,
                                   select_areas=True, select_solids=True, select_links=True):
        """Koordinat aralığına göre seçim yapar"""
        if self.SapModel:
            return self.SapModel.SelectObj.CoordinateRange(
                xmin, xmax, ymin, ymax, zmin, zmax,
                False,  # DeSelect
                csys,
                include_intersections,
                select_points,
                select_frames,
                select_areas,
                select_solids,
                select_links
            )
        return None
    
    def set_selected(self, obj_type, name: str, selected: bool = True, clear_selection: bool = True):
        """
        Nesneyi seçili/seçili değil yapar
        
        Args:
            obj_type: String ("Point", "Frame", "Area", "Link") veya integer type_id
            name: Nesne adı
            selected: True = seç, False = seçimi kaldır
            clear_selection: True = önce seçimi temizle, False = mevcut seçime ekle
        """
        if not self.SapModel:
            return None
        
        try:
            # Eğer obj_type string ise, OBJECT_TYPE_MAP kullanarak type_id bul
            if isinstance(obj_type, str):
                # String'i type_id'ye çevir
                type_id = None
                for key, value in OBJECT_TYPE_MAP.items():
                    if value == obj_type:
                        type_id = key
                        break
            else:
                type_id = obj_type
            
            if type_id not in OBJECT_TYPE_MAP:
                print(f"Geçersiz type_id: {type_id}")
                return None
            
            # Clear selection first if needed
            if selected and clear_selection:
                self.SapModel.SelectObj.ClearSelection()
            
            # Object type string
            if isinstance(obj_type, str):
                obj_type_str = obj_type
            else:
                obj_type_str = OBJECT_TYPE_MAP.get(obj_type, "")
            
            # Direct object selection
            if obj_type_str == "Point":
                return self.SapModel.PointObj.SetSelected(name, selected)
            elif obj_type_str == "Frame":
                return self.SapModel.FrameObj.SetSelected(name, selected)
            elif obj_type_str == "Area":
                return self.SapModel.AreaObj.SetSelected(name, selected)
            elif obj_type_str == "Link":
                return self.SapModel.LinkObj.SetSelected(name, selected)
            else:
                print(f"Desteklenmeyen obj_type: {obj_type_str}")
                return None
                
        except Exception as e:
            print(f"Seçim hatası (type: {obj_type}, name: {name}): {e}")
            return None
        
    def select_multiple(self, obj_type, names: list, clear_selection: bool = True):
        """Birden fazla nesneyi seçer"""
        ret= 1
        if not self.SapModel:
            return None
        
        if clear_selection:
            self.clear_selection()
        
        for name in names:
            ret= self.set_selected(obj_type, name, True, False)
        
        self.refresh_view()
        return ret

    def toggle_selection(self, obj_type, name: str):
        """Seçimi aç/kapat yapar"""
        selected_objects = self.get_selected_objects()
        
        # Nesne şu anda seçili mi?
        is_selected = any(obj['name'] == name for obj in selected_objects)
        
        # Toggle yap
        return self.set_selected(obj_type, name, not is_selected)

    def select_by_pattern(self, obj_type, pattern: str):
        """Desen eşleştirme ile nesne seçer"""
        if not self.SapModel:
            return []
        
        all_names = []
        if obj_type == "Point":
            _, all_names, _ = self.SapModel.PointObj.GetNameList()
        elif obj_type == "Frame":
            _, all_names, _ = self.SapModel.FrameObj.GetNameList()
        elif obj_type == "Area":
            _, all_names, _ = self.SapModel.AreaObj.GetNameList()
        elif obj_type == "Link":
            _, all_names, _ = self.SapModel.LinkObj.GetNameList()
        
        # Desene göre filtrele
        import re
        pattern_re = re.compile(pattern)
        matching_names = [name for name in all_names if pattern_re.search(name)]
        
        # Eşleşenleri seç
        for name in matching_names:
            self.set_selected(obj_type, name, True, False)
        
        return matching_names

    def get_selection_count(self, obj_type: str = None):
        """Seçili nesnelerin sayısını döndürür"""
        if not self.SapModel:
            return 0
        
        selected = self.get_selected_objects()
        
        if obj_type:
            # Belirli tipteki seçili nesneleri say
            count = sum(1 for obj in selected if obj['type'] == obj_type)
        else:
            # Tüm seçili nesneleri say
            count = len(selected)
        
        return count

    def invert_selection(self, obj_type: str = None):
        """Seçimi tersine çevirir"""
        if not self.SapModel:
            return None
        
        # Tüm nesneleri al
        all_objects = []
        if obj_type is None or obj_type == "Point":
            _, point_names, _ = self.SapModel.PointObj.GetNameList()
            all_objects.extend([("Point", name) for name in point_names])
        
        if obj_type is None or obj_type == "Frame":
            _, frame_names, _ = self.SapModel.FrameObj.GetNameList()
            all_objects.extend([("Frame", name) for name in frame_names])
        
        if obj_type is None or obj_type == "Area":
            _, area_names, _ = self.SapModel.AreaObj.GetNameList()
            all_objects.extend([("Area", name) for name in area_names])
        
        if obj_type is None or obj_type == "Link":
            _, link_names, _ = self.SapModel.LinkObj.GetNameList()
            all_objects.extend([("Link", name) for name in link_names])
        
        # Şu anki seçimi al
        current_selected = self.get_selected_objects()
        current_set = {(obj['type'], obj['name']) for obj in current_selected}
        
        # Tersini seç
        self.clear_selection()
        for obj_type_str, name in all_objects:
            if (obj_type_str, name) not in current_set:
                self.set_selected(obj_type_str, name, True, False)
        
        self.refresh_view()
    
    # --------------------------------------------------
    # NOKTALAR (POINTS)
    # --------------------------------------------------
    
    def get_point_coords(self, name: str) -> np.ndarray:
        """Noktanın koordinatlarını döndürür"""
        if not self.SapModel:
            raise RuntimeError("SapModel bağlantısı yok")
        
        ret = self.SapModel.PointObj.GetCoordCartesian(name)
        if len(ret) >= 3:
            return np.array(ret[:3], dtype=float)
        else:
            raise RuntimeError(f"Koordinat okunamadı: {name} -> {ret}")
    
    def add_point(self, x: float, y: float, z: float, name: str = ""):
        """Nokta ekler"""
        if not self.SapModel:
            return None
        return self.SapModel.PointObj.AddCartesian(x, y, z, name)
    
    def change_point_coords(self, name: str, x: float, y: float, z: float):
        """Nokta koordinatlarını değiştirir"""
        if not self.SapModel:
            raise RuntimeError("SapModel bağlantısı yok")
        
        if self.SapModel.GetModelIsLocked():
            raise RuntimeError("Model kilitli, koordinat değiştirilemez")
        
        ret = self.SapModel.EditPoint.ChangeCoordinates_1(name, float(x), float(y), float(z))
        print(name, float(x), float(y), float(z),"ChangeCoordinates_1 ret", ret)
        if ret != 0:
            raise RuntimeError(f"ChangeCoordinates_1 başarısız (Point='{name}', ret={ret})")
    
    def change_points_coords(self, points: dict, undo_mgr=None):
        
        
        """Birden fazla noktanın koordinatlarını değiştirir"""
        if self.SapModel.GetModelIsLocked():
            raise RuntimeError("Model kilitli")
        
        old_coords = {}
        for name, xyz in points.items():
            old_coords[name] = self.get_point_coords(name)
            self.change_point_coords(name, *xyz)
        
        
    
    def align_points(self, axis_type: int, value: float, point_names: list):
        """Noktaları belirli bir değerde hizalar"""
        if not self.SapModel:
            return None
        return self.SapModel.EditPoint.Align(axis_type, value, len(point_names), tuple(point_names))
    
    def disconnect_point(self, name: str):
        """Noktanın bağlantılarını koparır"""
        if not self.SapModel:
            return None
        return self.SapModel.EditPoint.Disconnect(1, name)
    
    def delete_special_point(self, name: str):
        """Özel noktayı siler"""
        if not self.SapModel:
            return None
        return self.SapModel.PointObj.DeleteSpecialPoint(name)
    
    def get_point_connectivity(self, name: str):
        """Noktanın bağlantı bilgilerini getirir"""
        if not self.SapModel:
            return (0, [], [], [], 0)
        return self.SapModel.PointObj.GetConnectivity(name)
    
    def get_point_restraint(self, name: str):
        """Noktanın mesnet bilgilerini getirir"""
        if not self.SapModel:
            return ([], 0)
        return self.SapModel.PointObj.GetRestraint(name)
    
    def get_all_points(self):
        """Tüm noktaları getirir"""
        if not self.SapModel:
            return []
        return self.SapModel.PointObj.GetNameList()
    
    # --------------------------------------------------
    # ÇUBUKLAR (FRAMES)
    # --------------------------------------------------
    
    def get_frame_points(self, name: str) -> np.ndarray:
        """Çubuğun uç noktalarının koordinatlarını döndürür"""
        if not self.SapModel:
            raise RuntimeError("SapModel bağlantısı yok")
        return self.SapModel.FrameObj.GetPoints(name)[:2]
    
    def get_frame_endpoints_coords(self, name: str) -> tuple:
        """Frame'in uç nokta koordinatlarını döndürür"""
        if not self.SapModel:
            raise RuntimeError("SapModel bağlantısı yok")
        
        pi, pj = self.SapModel.FrameObj.GetPoints(name)[:2]
        xi, yi, zi, _ = self.SapModel.PointObj.GetCoordCartesian(pi)
        xj, yj, zj, _ = self.SapModel.PointObj.GetCoordCartesian(pj)
        return pi, np.array([xi, yi, zi]), pj, np.array([xj, yj, zj])
    
    def get_frame_endpoints(self, name: str) -> tuple:
        """Frame'in uç nokta koordinatlarını döndürür"""
        if not self.SapModel:
            raise RuntimeError("SapModel bağlantısı yok")
        
        pi, pj = self.SapModel.FrameObj.GetPoints(name)[:2]
        xi, yi, zi, _ = self.SapModel.PointObj.GetCoordCartesian(pi)
        xj, yj, zj, _ = self.SapModel.PointObj.GetCoordCartesian(pj)
        return np.array([xi, yi, zi]), np.array([xj, yj, zj])
    
    def get_frame_length(self, name: str) -> float:
        """Çubuğun gerçek 3D uzunluğunu döndürür"""
        pts = self.get_frame_endpoints(name)
        print("pts", pts)
        p1, p2 = pts[0], pts[1]
        return float(np.linalg.norm(p2 - p1))
    
    def get_frame_all_angles(self, name: str, deg: bool = True) -> dict:
        """
        Çubuğun global eksenlerle yaptığı açıları döndürür.
        Sonuçlar varsayılan olarak derece cinsindedir.
        
        Returns:
            {
                "alpha_x": angle_with_X,
                "alpha_y": angle_with_Y,
                "alpha_z": angle_with_Z
            }
        """
        pts = self.get_frame_endpoints(name)
        p1, p2 = np.array(pts[0]), np.array(pts[1])

        v = p2 - p1
        L = np.linalg.norm(v)

        if L == 0:
            raise ValueError("Çubuk uzunluğu sıfır olamaz")

        # birim yön vektörü
        v_hat = v / L

        # global eksenler
        ex = np.array([1.0, 0.0, 0.0])
        ey = np.array([0.0, 1.0, 0.0])
        ez = np.array([0.0, 0.0, 1.0])

        # yön kosinüsleri → açı
        ax = np.arccos(np.clip(np.dot(v_hat, ex), -1.0, 1.0))
        ay = np.arccos(np.clip(np.dot(v_hat, ey), -1.0, 1.0))
        az = np.arccos(np.clip(np.dot(v_hat, ez), -1.0, 1.0))

        if deg:
            ax, ay, az = np.degrees([ax, ay, az])

        return {
            "alpha_x": float(ax),
            "alpha_y": float(ay),
            "alpha_z": float(az),
        }

    def get_frame_local_axes(self, name: str):
        """Frame'in lokal eksenlerini getirir"""
        if not self.SapModel:
            raise RuntimeError("SapModel bağlantısı yok")
        
        ret = self.SapModel.FrameObj.GetTransformationMatrix(name)
        mat, retcode = ret
        if retcode != 0:
            raise RuntimeError(f"GetTransformationMatrix başarısız (Frame='{name}', ret={retcode})")
        
        T = np.array(mat, dtype=float).reshape((3, 3))
        local1 = T[:, 0]
        local2 = T[:, 1]
        local3 = T[:, 2]
        
        return local1, local2, local3, T
    
    def get_frame_section(self, name: str):
        """Frame'in kesit bilgisini getirir"""
        if not self.SapModel:
            return None
        return self.SapModel.FrameObj.GetSection(name)
    
    def add_frame_by_points(self, point1: str, point2: str, name: str = "", prop_name: str = ""):
        """İki nokta arasında frame oluşturur"""
        if not self.SapModel:
            return None
        return self.SapModel.FrameObj.AddByPoint(point1, point2, name, prop_name)
    
    def add_frame_by_coords(self, x1: float, y1: float, z1: float, 
                           x2: float, y2: float, z2: float, name: str = ""):
        """Koordinatlarla frame oluşturur"""
        if not self.SapModel:
            return None
        return self.SapModel.FrameObj.AddByCoord(x1, y1, z1, x2, y2, z2, name)
    
    def edit_frame_connectivity(self, frame_name: str, new_p1_name: str, new_p2_name: str):
        """Frame bağlantılarını değiştirir"""
        if not self.SapModel:
            return None
        return self.SapModel.EditFrame.ChangeConnectivity(frame_name, new_p1_name, new_p2_name)
    
    def delete_frame(self, name: str):
        """Frame siler"""
        if not self.SapModel:
            return None
        return self.SapModel.FrameObj.Delete(name)
    
    def get_all_frames(self):
        """Tüm frameleri getirir"""
        if not self.SapModel:
            return []
        return self.SapModel.FrameObj.GetNameList()
    
    # --------------------------------------------------
    # ALANLAR (AREAS)
    # --------------------------------------------------
    
    def get_area_points(self, name: str) -> np.ndarray:
        """Area nesnesinin tüm köşe noktalarının koordinatlarını getirir"""
        if not self.SapModel:
            raise RuntimeError("SapModel bağlantısı yok")
        
        ret = self.SapModel.AreaObj.GetPoints(name)
        if len(ret) < 2 or not ret[1]:
            raise RuntimeError(f"Area noktaları alınamadı: {name}")
        
        point_counts = ret[0]
        point_names = ret[1]
        coords = []
        for p_name in point_names:
            p_xyz = self.get_point_coords(p_name)
            coords.append(p_xyz)
        
        return point_counts, point_names, np.array(coords, dtype=float)
    
    def get_area_edge_count(self, name: str) -> int:
        """Area'nın köşe sayısını getirir"""
        if not self.SapModel:
            return 0
        
        try:
            ret = self.SapModel.AreaObj.GetPoints(name)
            if ret[2] != 0:
                return 0
            return int(ret[0])
        except Exception:
            return 0
    
    def get_area_transformation_matrix(self, name: str):
        """Area'nın dönüşüm matrisini getirir"""
        if not self.SapModel:
            return None
        return self.SapModel.AreaObj.GetTransformationMatrix(name)
    
    def add_area_by_points(self, point_names: list, name: str = ""):
        """Noktalardan area oluşturur"""
        if not self.SapModel:
            return None
        return self.SapModel.AreaObj.AddByPoint(len(point_names), point_names, name)
    
    def add_area_by_coords(self, x_coords: list, y_coords: list, z_coords: list, name: str = ""):
        """Koordinatlardan area oluşturur"""
        if not self.SapModel:
            return None
        return self.SapModel.AreaObj.AddByCoord(len(x_coords), x_coords, y_coords, z_coords, name)
    
    def delete_area(self, name: str):
        """Area siler"""
        if not self.SapModel:
            return None
        return self.SapModel.AreaObj.Delete(name)
    
    def get_all_areas(self):
        """Tüm areaları getirir"""
        if not self.SapModel:
            return []
        return self.SapModel.AreaObj.GetNameList()
    
    # --------------------------------------------------
    # BAĞLANTILAR (LINKS)
    # --------------------------------------------------
    
    def get_link_points(self, name: str):
        """Link'in uç noktalarını getirir"""
        if not self.SapModel:
            return (None, None, 0)
        return self.SapModel.LinkObj.GetPoints(name)
    
    def add_link_by_points(self, point1: str, point2: str, name: str = ""):
        """İki nokta arasında link oluşturur"""
        if not self.SapModel:
            return None
        return self.SapModel.LinkObj.AddByPoint(point1, point2, name)
    
    def add_link_by_coords(self, x1: float, y1: float, z1: float, 
                          x2: float, y2: float, z2: float, name: str = ""):
        """Koordinatlarla link oluşturur"""
        if not self.SapModel:
            return None
        return self.SapModel.LinkObj.AddByCoord(x1, y1, z1, x2, y2, z2, name)
    
    def delete_link(self, name: str):
        """Link siler"""
        if not self.SapModel:
            return None
        return self.SapModel.LinkObj.Delete(name)
    
    def get_all_links(self):
        """Tüm linkleri getirir"""
        if not self.SapModel:
            return []
        return self.SapModel.LinkObj.GetNameList()
    
    # --------------------------------------------------
    # GEOMETRİK OFFSET İŞLEMLERİ
    # --------------------------------------------------
    
    def add_point_cartesian_safe(self, P):
        """Güvenli nokta oluşturur, nokta adını döner"""
        ret = self.SapModel.PointObj.AddCartesian(P[0], P[1], P[2], "")
        if isinstance(ret, (list, tuple)):
            if len(ret) >= 2 and ret[1] == 0:
                return ret[0]
            else:
                return None
        elif isinstance(ret, str):
            return ret
        return None
    
    def get_offset_direction(self, local1, local2, local3, plane="12"):
        """Frame düzlemine göre offset yönünü döner"""
        if plane == "12":
            return local3
        elif plane == "13":
            return local2
        else:
            raise ValueError("Geçersiz düzlem seçimi: 12 veya 13 olmalı")
    
    def offset_frame(self, frame_name, offset, plane="12", new_frame_name="", undo_mgr=None):
        """Frame'i seçilen düzleme göre offsetleyerek kopyalar"""
        # frame uç noktaları
        p1, p2 = self.get_frame_points(frame_name)
        
        # local eksenler
        local1, local2, local3, T = self.get_frame_local_axes(frame_name)
        
        # offset yönü
        offset_dir = self.get_offset_direction(local1, local2, local3, plane)
        
        # offsetli noktalar
        p1_off = p1 + offset * offset_dir
        p2_off = p2 + offset * offset_dir
        
        # noktaları oluştur
        p1_name = self.add_point_cartesian_safe(p1_off)
        p2_name = self.add_point_cartesian_safe(p2_off)
        
        if p1_name is None or p2_name is None:
            raise RuntimeError("Offset noktaları oluşturulamadı")
        
        # yeni frame
        ret = self.SapModel.FrameObj.AddByPoint(p1_name, p2_name, new_frame_name)
        new_frame = ret[0]
        
        # 🔴 UNDO KAYDI
        
        
        
        self.refresh_view()
        return ret
    
    def edit_frame_connectivity_safe(self, frame_name: str, new_p1: np.ndarray, 
                                     new_p2: np.ndarray, undo_mgr=None):
        """Tek frame edit – undo-safe"""
        # 🔴 ESKİ STATE
        old_p1_name, old_p2_name, ret = self.SapModel.FrameObj.GetPoints(frame_name)
        if ret != 0:
            raise RuntimeError("Frame noktaları okunamadı")
        
        old_p1 = np.array(self.get_point_coords(old_p1_name))
        old_p2 = np.array(self.get_point_coords(old_p2_name))
        
        try:
            # 🔴 YENİ NOKTALAR
            new_p1_name = self.add_point_cartesian_safe(new_p1)
            new_p2_name = self.add_point_cartesian_safe(new_p2)
            
            ret = self.SapModel.EditFrame.ChangeConnectivity(frame_name, new_p1_name, new_p2_name)
            if ret != 0:
                raise RuntimeError("ChangeConnectivity failed")
            
            # 🔴 UNDO KAYDI
            
            
            
        except Exception as e:
            raise e
    
    # --------------------------------------------------
    # SMART GRID VE ANALİZ FONKSİYONLARI
    # --------------------------------------------------
    
    def get_smart_grids(self, tolerance=0.02):
        """Tüm noktaları tarayıp X, Y, Z için olası grid koordinatlarını belirler"""
        point_counts, point_names, ret = self.SapModel.PointObj.GetNameList()
        if ret != 0 or not point_names:
            return {"X": [], "Y": [], "Z": []}
        
        raw_coords = {"X": [], "Y": [], "Z": []}
        
        for name in point_names:
            p = self.get_point_coords(name)
            raw_coords["X"].append(p[0])
            raw_coords["Y"].append(p[1])
            raw_coords["Z"].append(p[2])
        
        smart_grids = {}
        for axis in ["X", "Y", "Z"]:
            vals = sorted(raw_coords[axis])
            if not vals:
                smart_grids[axis] = []
                continue
                
            # Yakın değerleri grupla (Clustering)
            groups = []
            if vals:
                current_group = [vals[0]]
                for i in range(1, len(vals)):
                    if vals[i] - vals[i-1] <= tolerance:
                        current_group.append(vals[i])
                    else:
                        groups.append(np.mean(current_group))
                        current_group = [vals[i]]
                groups.append(np.mean(current_group))
            
            # Yuvarlatılmış ve tekil gridler
            smart_grids[axis] = sorted(list(set([round(g, 4) for g in groups])))
            
        return smart_grids
    
    # --------------------------------------------------
    # SAPLINK AUTO İLE İLGİLİ FONKSİYONLAR
    # --------------------------------------------------
    
    def frame_onay(self, frame_names: list, point: np.ndarray):
        """Bir noktanın herhangi bir çerçeve üzerinde olup olmadığını kontrol eder"""
        from tools.analitik import Analitik
        for frame_name in frame_names:
            try:
                F1_A, F1_B = self.get_frame_endpoints(frame_name)
                if Analitik.point_on_segment(point, F1_A, F1_B):
                    return True
            except Exception:
                continue
        return False
    
    def get_all_frames_coords(self):
        """Tüm framelerin koordinatlarını getirir"""
        frames = self.get_all_frames()
        result = []
        for frame_name in frames:
            try:
                A, B = self.get_frame_endpoints(frame_name)
                result.append((frame_name, A, B))
            except:
                continue
        return result
    
    def add_link_between_coords(self, P: np.ndarray, Q: np.ndarray, link_name: str = ""):
        """Koordinatlarla link ekler"""
        p1_name = self.add_point_cartesian_safe(P)
        p2_name = self.add_point_cartesian_safe(Q)
        
        if p1_name is None or p2_name is None:
            print("Nokta oluşturma başarısız, bağlantı oluşturulmadı.")
            return None
        
        try:
            ret = self.SapModel.LinkObj.AddByPoint(p1_name, p2_name, link_name)
            return ret
        except Exception as e:
            print(f"Bağlantı oluşturma hatası: {e}")
            return None
    
    # --------------------------------------------------
    # MODEL CHECK VE DİĞER UTILITIES
    # --------------------------------------------------
    
    def get_connectivity_info(self, point_name: str):
        """Noktanın bağlantı bilgilerini detaylı getirir"""
        num_items, obj_types, obj_names, point_nums, ret = self.get_point_connectivity(point_name)
        restraints, ret_rest = self.get_point_restraint(point_name)
        
        has_restraint = any(restraints)
        
        info = {
            "point_name": point_name,
            "num_connections": num_items,
            "connections": [],
            "has_restraint": has_restraint,
            "restraints": restraints
        }
        
        for i in range(num_items):
            info["connections"].append({
                "type": OBJECT_TYPE_MAP.get(obj_types[i], "Unknown"),
                "type_id": obj_types[i],
                "name": obj_names[i],
                "point_num": point_nums[i]
            })
        
        return info
    
    def find_dangling_elements(self):
        """Boşta kalan (dangling) elemanları bulur"""
        _, all_point_names, _ = self.SapModel.PointObj.GetNameList()
        
        dangling = {"points": [], "frames": [], "areas": [], "links": []}
        orphans = []
        
        for point_name in all_point_names:
            info = self.get_connectivity_info(point_name)
            
            # SENARYO 1: Nokta hiçbir yere bağlı değil
            if info["num_connections"] == 0 and not info["has_restraint"]:
                orphans.append(point_name)
            
            # SENARYO 2: Nokta sadece 1 elemana bağlı ve mesnet yok
            elif info["num_connections"] == 1 and not info["has_restraint"]:
                dangling["points"].append(point_name)
                conn = info["connections"][0]
                if conn["type_id"] == 2:
                    dangling["frames"].append(conn["name"])
                elif conn["type_id"] == 5:
                    dangling["areas"].append(conn["name"])
                elif conn["type_id"] == 7:
                    dangling["links"].append(conn["name"])
        
        return dangling, orphans
    
    def read_table(self, table_key: str, case_names: Optional[List[str]] = None, combo_names: Optional[List[str]] = None, numerics:  Optional[Dict] = None) -> List:
        """SAP2000 tablosunu pandas DataFrame olarak okur"""
        if not self.SapModel:
            print("SAPModel bağlantısı yok")
            return []
        
    
        # Yük durumlarını seç
        if case_names:
            ret = self.SapModel.Results.Setup.DeselectAllCasesAndCombosForOutput()
            for case_name in case_names:
                ret = self.SapModel.Results.Setup.SetCaseSelectedForOutput(case_name)

        elif combo_names:
            ret = self.SapModel.Results.Setup.DeselectAllCasesAndCombosForOutput()
            for combo_name in combo_names:
                ret = self.SapModel.Results.Setup.SetComboSelectedForOutput(combo_name)
        
        # Tablo verilerini al
        ret, _, fields, num_data, data, _ = self.SapModel.DatabaseTables.GetTableForDisplayArray(table_key, [], "", 0, [], 0, [])
        
        return fields, [data[i*len(fields):(i+1)*len(fields)] for i in range(num_data)]