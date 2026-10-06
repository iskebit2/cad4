import numpy as np

class Analitik:
    def __init__(self, sap_instance):
        self.sap = sap_instance
        self.current_plane = None  # (normal_vector, point_on_plane)
        self.TOL = 1e-9
        
    # --------------------------------------------------
    # DÜZLEM TANIMLAMA FONKSİYONLARI
    # --------------------------------------------------
    
    def set_plane(self, p0: np.ndarray, normal: np.ndarray) -> bool:
        """Düzlemi hafızaya alır"""
        norm = np.linalg.norm(normal)
        if norm == 0: 
            return False
        self.current_plane = (normal / norm, p0)
        return True

    def get_current_plane(self):
        return self.current_plane

    def define_by_point_global(self, axis="XY"):
        """Seçili noktadan global düzlem oluşturur"""
        selected = self.sap.get_selected_objects()
        points = [obj for obj in selected if obj.get('type') == 'Point']
        
        if not points: 
            return False
        
        p0 = self.sap.get_point_coords(points[0]['name'])
        normals = {
            "XY": np.array([0, 0, 1]),
            "XZ": np.array([0, 1, 0]),
            "YZ": np.array([1, 0, 0])
        }
        return self.set_plane(p0, normals[axis])

    def define_by_frame_local(self, plane_type="12"):
        """
        Seçili frame'in veya 2 seçili noktanın lokal düzlemini tanımlar
        plane_type:
            "12" → 1-2 düzlemi (normal = local 3)
            "13" → 1-3 düzlemi (normal = local 2)
        """

        import numpy as np

        selected = self.sap.get_selected_objects()

        frames = [obj for obj in selected if obj.get('type') == 'Frame']
        points = [obj for obj in selected if obj.get('type') == 'Point']

        # --------------------------------------------------
        # 1) FRAME SEÇİLİYSE (mevcut davranış)
        # --------------------------------------------------
        if frames:
            f_name = frames[0]['name']
            p1, p2 = self.sap.get_frame_endpoints(f_name)

            l1, l2, l3, T = self.sap.get_frame_local_axes(f_name)

            normal = l3 if plane_type == "12" else l2
            return self.set_plane(p1, normal)

        # --------------------------------------------------
        # 2) FRAME YOK, AMA 2 NOKTA VARSA
        # --------------------------------------------------
        if len(points) == 2:
            p1 = np.array(self.sap.get_point_coords(points[0]['name']), dtype=float)
            p2 = np.array(self.sap.get_point_coords(points[1]['name']), dtype=float)

            v1 = p2 - p1
            norm = np.linalg.norm(v1)
            if norm < 1e-6:
                return False

            l1 = v1 / norm

            # Global Z ile referans al
            z_global = np.array([0.0, 0.0, 1.0])

            # Eğer neredeyse paralelse, Global Y al
            if abs(np.dot(l1, z_global)) > 0.99:
                z_global = np.array([0.0, 1.0, 0.0])

            l2 = np.cross(z_global, l1)
            l2 /= np.linalg.norm(l2)

            l3 = np.cross(l1, l2)
            l3 /= np.linalg.norm(l3)

            normal = l3 if plane_type == "12" else l2
            return self.set_plane(p1, normal)

        return False


    def define_by_3_points(self):
        """Seçili 3 noktadan düzlem oluşturur"""
        selected = self.sap.get_selected_objects()
        pts = [obj for obj in selected if obj.get('type') == 'Point']
        if len(pts) < 3: 
            return False
        
        coords = [self.sap.get_point_coords(p['name']) for p in pts[:3]]
        v1 = coords[1] - coords[0]
        v2 = coords[2] - coords[0]
        normal = np.cross(v1, v2)
        
        norm = np.linalg.norm(normal)
        if norm == 0: 
            return False
            
        return self.set_plane(coords[0], normal)

    def define_by_area(self):
        """Seçili Area'nın düzlemini alır"""
        selected = self.sap.get_selected_objects()
        areas = [obj for obj in selected if obj.get('type') == 'Area']
        if not areas: 
            return False
            
        a_name = areas[0]['name']
        ret = self.sap.SapModel.AreaObj.GetTransformationMatrix(a_name)
        if ret[0] is None:
            return False
            
        T = np.array(ret[0]).reshape(3, 3)
        normal = T[:, 2]  # Local 3
        _, pt_names, _ = self.sap.SapModel.AreaObj.GetPoints(a_name)
        p0 = self.sap.get_point_coords(pt_names[0])
        
        norm = np.linalg.norm(normal)
        if norm == 0: 
            return False
            
        return self.set_plane(p0, normal)
    
    # --------------------------------------------------
    # GEOMETRİK HESAP FONKSİYONLARI
    # --------------------------------------------------
    
    @staticmethod
    def point_on_segment(P, A, B, tol=1e-6):
        """Bir noktanın bir doğru parçası üzerinde olup olmadığını kontrol eder"""
        return abs(np.linalg.norm(A - P) + np.linalg.norm(B - P) - np.linalg.norm(B - A)) < tol
    
    @staticmethod
    def get_projection_point(p, a, b):
        """Bir noktanın bir doğru üzerine dik izdüşümünü bulur"""
        ap = p - a
        ab = b - a
        t = np.dot(ap, ab) / np.dot(ab, ab)
        p_proj = a + t * ab
        return p_proj
    
    @staticmethod
    def dist_point_to_segment(p, a, b):
        """Bir noktanın bir doğru parçasına olan en kısa mesafesini hesaplar"""
        import numpy as np
        p, a, b = np.array(p), np.array(a), np.array(b)
        if np.all(a == b): 
            return np.linalg.norm(p - a)
        
        ap = p - a
        ab = b - a
        t = np.dot(ap, ab) / np.dot(ab, ab)
        t = max(0, min(1, t))
        closest_point = a + t * ab
        return np.linalg.norm(p - closest_point)
    
    @staticmethod
    def calculate_3d_area(points):
        """3D düzlemsel poligonun alanını hesaplar"""
        area = 0.0
        for i in range(len(points)):
            j = (i + 1) % len(points)
            area += ((points[i][1]*points[j][2] - points[j][1]*points[i][2])**2 + 
                     (points[i][2]*points[j][0] - points[j][2]*points[i][0])**2 + 
                     (points[i][0]*points[j][1] - points[j][0]*points[i][1])**2)**0.5
        return area / 2.0
    
    @staticmethod
    def check_planarity(points, tolerance=1e-4):
        """
        Noktaların aynı düzlemde olup olmadığını kontrol eder
        
        Args:
            points: np.array, shape (n, 3)
            tolerance: tolerans değeri
            
        Returns:
            tuple: (is_planar, max_distance)
        """
        if len(points) < 4:
            return True, 0  # 3 nokta her zaman düzlemsel
        
        # İlk 3 noktadan düzlem normalini oluştur
        v1 = points[1] - points[0]
        v2 = points[2] - points[0]
        normal = np.cross(v1, v2)
        norm_val = np.linalg.norm(normal)
        
        if norm_val == 0:
            return False, -1
        
        n = normal / norm_val
        
        # Diğer tüm noktaların düzleme mesafesini kontrol et
        max_dist = 0
        is_planar = True
        
        for i in range(3, len(points)):
            dist = abs(np.dot(n, (points[i] - points[0])))
            if dist > max_dist:
                max_dist = dist
            
            if dist > tolerance:
                is_planar = False
        
        return is_planar, max_dist
    
    @staticmethod
    def line_line_intersection_2d(A1, B1, A2, B2, plane="XY"):
        """
        İki doğrunun 2D projeksiyonundaki kesişimini bulur
        
        Args:
            A1, B1: Birinci doğrunun uç noktaları (3D)
            A2, B2: İkinci doğrunun uç noktaları (3D)
            plane: Projeksiyon düzlemi ("XY", "XZ", "YZ")
            
        Returns:
            tuple: (t, s) parametreleri veya (None, None)
        """
        # Düzlem indisleri
        plane_map = {"XY": (0, 1), "XZ": (0, 2), "YZ": (1, 2)}
        if plane not in plane_map:
            raise ValueError("Geçersiz düzlem: XY, XZ veya YZ olmalı")
        
        i, j = plane_map[plane]
        
        # 2D projeksiyon
        p1 = A1[[i, j]]
        d1 = B1[[i, j]] - A1[[i, j]]
        p2 = A2[[i, j]]
        d2 = B2[[i, j]] - A2[[i, j]]
        
        # 2D kesişim kontrolü
        M = np.column_stack((d1, -d2))
        det = np.linalg.det(M)
        
        if abs(det) < 1e-9:
            return None, None
        
        try:
            t, s = np.linalg.solve(M, p2 - p1)
        except np.linalg.LinAlgError:
            return None, None
            
        return t, s
    
    def get_plane_equation(self):
        """Aktif düzlemin denklemini ax + by + cz + d = 0 formunda döndürür"""
        if not self.current_plane:
            return None
        
        normal, p0 = self.current_plane
        a, b, c = normal
        d = -np.dot(normal, p0)
        return a, b, c, d
    
    def distance_point_to_plane(self, point):
        """Bir noktanın aktif düzleme olan uzaklığını hesaplar"""
        if not self.current_plane:
            return None
        
        normal, p0 = self.current_plane
        n = normal / np.linalg.norm(normal)
        return abs(np.dot(n, (point - p0)))
    
    def project_point_to_plane(self, point):
        """Bir noktayı aktif düzleme projekte eder"""
        if not self.current_plane:
            return None
        
        normal, p0 = self.current_plane
        n = normal / np.linalg.norm(normal)
        
        # İzdüşüm: P_yeni = P_eski + ( (P0 - P_eski) . n ) * n
        distance_to_plane = np.dot((p0 - point), n)
        target_pos = point + (distance_to_plane * n)
        
        return target_pos
    
    def line_plane_intersection(self, line_start, line_end):
        """
        Bir doğrunun aktif düzlemle kesişim noktasını bulur
        
        Args:
            line_start: Doğrunun başlangıç noktası
            line_end: Doğrunun bitiş noktası
            
        Returns:
            np.array: Kesişim noktası veya None
        """
        if not self.current_plane:
            return None
        
        normal, p0 = self.current_plane
        n = normal / np.linalg.norm(normal)
        
        # Doğru vektörü
        u = line_end - line_start
        denom = np.dot(n, u)
        
        if abs(denom) < self.TOL:
            return None  # Doğru düzleme paralel
        
        t = np.dot(n, (p0 - line_start)) / denom
        intersection_point = line_start + t * u
        
        return intersection_point
    
    def find_closest_point_on_frames(self, point, frame_names):
        """
        Bir noktanın verilen framelere en yakın noktasını bulur
        
        Args:
            point: Referans noktası
            frame_names: Frame isimleri listesi
            
        Returns:
            tuple: (closest_point, frame_name, distance)
        """
        min_distance = float('inf')
        closest_point = None
        closest_frame = None
        
        for f_name in frame_names:
            try:
                A, B = self.sap.get_frame_endpoints(f_name)
                proj_point = self.get_projection_point(point, A, B)
                distance = np.linalg.norm(point - proj_point)
                
                if distance < min_distance:
                    min_distance = distance
                    closest_point = proj_point
                    closest_frame = f_name
            except Exception:
                continue
        
        return closest_point, closest_frame, min_distance
    
    def get_bounding_box(self, points):
        """
        Noktalar için sınırlayıcı kutu (bounding box) hesaplar
        
        Args:
            points: Nokta koordinatları listesi
            
        Returns:
            dict: Bounding box değerleri
        """
        if not points:
            return None
        
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        zs = [p[2] for p in points]
        
        return {
            "xmin": min(xs),
            "xmax": max(xs),
            "ymin": min(ys),
            "ymax": max(ys),
            "zmin": min(zs),
            "zmax": max(zs),
        }
    
    def calculate_line_angles(self, p1, p2):
        """
        İki nokta arasındaki doğrunun açılarını hesaplar
        
        Returns:
            dict: Çeşitli açı değerleri
        """
        diff = p2 - p1
        dx, dy, dz = diff
        dist_3d = np.linalg.norm(diff)
        dist_2d_xy = np.linalg.norm(diff[:2])
        
        # XY düzlemindeki açı (X aksıyla yapılan açı)
        angle_xy = np.degrees(np.arctan2(dy, dx))
        
        # Düşey eğim açısı
        angle_vertical = 0.0
        if dist_3d > self.TOL:
            angle_vertical = np.degrees(np.arcsin(dz / dist_3d))
        
        # Eğim yüzdesi
        slope_pct = (dz / dist_2d_xy * 100) if dist_2d_xy > self.TOL else float('inf')
        
        return {
            "delta": (dx, dy, dz),
            "distance_3d": dist_3d,
            "distance_2d": dist_2d_xy,
            "angle_xy": angle_xy,
            "angle_vertical": angle_vertical,
            "slope_percent": slope_pct
        }