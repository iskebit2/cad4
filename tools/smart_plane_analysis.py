import numpy as np
from OpenGL.GL import *


class SmartPlaneAnalyzer:
    """
    Akıllı düzlem analiz modu:
    - Fare ile çubuk (Frame) hover tespiti
    - Tıklama ile çubuk seçimi
    - Space ile yerel eksen düzlemi döngüsü
    - Enter ile Convex Hull tabanlı sınır poligonu hesabı
    """

    # --- Sabitler ---
    PIXEL_TOLERANCE = 10.0        # hover için piksel toleransı
    HOVER_COLOR     = (0.0, 0.85, 0.85, 0.55)   # turkuaz, yarı saydam
    SELECTED_COLOR  = (0.0, 0.70, 0.75, 0.90)   # koyu turkuaz
    PREVIEW_COLOR   = (0.0, 0.85, 0.85, 0.18)   # hafif turkuaz
    HOVER_LINE_WIDTH    = 6.0
    SELECTED_LINE_WIDTH = 7.0

    def __init__(self, scene_controller=None, scene_provider=None):
        # Sahne lazy olarak çekilir; sonradan set edilse bile günceli görür.
        self._scene_provider = scene_provider or (lambda: scene_controller)

        
        self.selected_frame = None
        self.hovered_frame = None

        # Yerel eksen çiftleri kombinasyonları
        self.plane_indices = [("1", "2"), ("1", "3"), ("2", "3")]
        self.current_plane_idx = 0

        # Viewport boyutları (başlangıç)
        self.viewport_width = 800
        self.viewport_height = 600

        # Render döngüsünde son kullanılan matrisler (billboard vb. için)
        self._last_view_matrix = None
        self._last_proj_matrix = None

    # ------------------------------------------------------------------ #
    # Sahne erişimi
    # ------------------------------------------------------------------ #
    @property
    def scene(self):
        """Her erişimde güncel sahneyi döndürür."""
        return self._scene_provider()

    def _get_frames_dict(self):
        """Sahnedeki frame sözlüğünü güvenli şekilde döndürür."""
        scene = self.scene
        if scene is None:
            return {}
        frames = getattr(scene, "frames", None)
        if isinstance(frames, dict):
            return frames
        # Liste veya başka bir yapıysa normalize et
        if frames:
            try:
                return {getattr(f, "id", i): f for i, f in enumerate(frames)}
            except Exception:
                return {}
        return {}



    def reset_selection(self):
        """Seçimleri ve hover durumunu sıfırlar."""
        self.selected_frame = None
        self.hovered_frame = None
        self.current_plane_idx = 0

    def set_viewport(self, width, height):
        """Pencere/Viewport boyutu değiştiğinde günceller."""
        self.viewport_width = max(1, int(width))
        self.viewport_height = max(1, int(height))

    # ------------------------------------------------------------------ #
    # Kullanıcı girişleri
    # ------------------------------------------------------------------ #
    def handle_mouse_click(self, mouse_pos):
        """Tıklama anında hover edilen çubuğu ana referans olarak seçer."""
        
        if self.hovered_frame is not None:
            self.selected_frame = self.hovered_frame
            self.current_plane_idx = 0
        else:
            # Boşluğa tıklandı → seçimi iptal et
            self.selected_frame = None

    def handle_key_press(self, key):
        """Space ile düzlem döngüsü, Enter ile analizi tetikler."""
        
        if key in ("space", "Space") and self.selected_frame is not None:
            self.current_plane_idx = (
                self.current_plane_idx + 1
            ) % len(self.plane_indices)
            return True

        if key in ("return", "Return", "enter", "Enter") and self.selected_frame is not None:
            self.execute_plane_analysis()
            return True

        return False
    
    def _project_world_to_pixels(self, world_pt, view_matrix, proj_matrix):
        """Dünya noktasını ekran piksel koordinatına çevirir."""
        V = np.array(view_matrix, dtype=float)
        P = np.array(proj_matrix, dtype=float)

        p_h = np.array([world_pt[0], world_pt[1], world_pt[2], 1.0])
        clip = P @ (V @ p_h)
        if clip[3] <= 1e-9:
            return None      # kamera arkasında
        ndc = clip[:3] / clip[3]
        if not (-1.0 <= ndc[0] <= 1.0 and -1.0 <= ndc[1] <= 1.0):
            return None      # ekran dışında
        px = (ndc[0] + 1.0) * 0.5 * self.viewport_width
        # NOT: __screen_to_ray__ Y'yi tersliyor; burada aynı formatta olmalı
        # Snap'te: py = (1 - ndc.y) * h/2 — üstten-aşağı
        py_top = (1.0 - ndc[1]) * 0.5 * self.viewport_height
        return (px, py_top)

    def _point_to_pixel_segment(self, p, a, b):
        """2D piksel uzayında nokta-segment mesafesi."""
        ax, ay = a
        bx, by = b
        px, py = p
        abx = bx - ax
        aby = by - ay
        ab_len2 = abx * abx + aby * aby
        if ab_len2 < 1e-9:
            return float(np.hypot(px - ax, py - ay))
        t = ((px - ax) * abx + (py - ay) * aby) / ab_len2
        t = max(0.0, min(1.0, t))
        projx = ax + t * abx
        projy = ay + t * aby
        return float(np.hypot(px - projx, py - projy))

    def handle_mouse_move(self, mouse_pos, view_matrix, proj_matrix, viewport_size):
        
        scene = self.scene
        if scene is None:
            return

        self.set_viewport(*viewport_size)

        # Frame'leri ekran uzayında test et
        frames = self._get_frames_dict()
        x, y = mouse_pos

        closest = None
        closest_px = float("inf")

        # view/proj matrislerini parametre olarak alalım ama metod adı önemli
        # → eng.cam.get_view_matrix() kullan
        # Burada engine'e erişim: scene.parent veya elinde nasıl varsa
        # Alternatif: view/proj'u parametre olarak kabul et (engine'den gelirken doğru olanı gönder)

        for frame in frames.values():
            if not hasattr(frame, "node_i") or not hasattr(frame, "node_j"):
                continue
            try:
                p1 = np.array(frame.node_i.coord if hasattr(frame.node_i, "coord")
                            else frame.node_i.coords, dtype=float)
                p2 = np.array(frame.node_j.coord if hasattr(frame.node_j, "coord")
                            else frame.node_j.coords, dtype=float)
            except Exception:
                continue

            # 2D projeksiyon (piksel)
            px1 = self._project_world_to_pixels(p1, view_matrix, proj_matrix)
            px2 = self._project_world_to_pixels(p2, view_matrix, proj_matrix)
            if px1 is None or px2 is None:
                continue

            # Pikselden segment'e mesafe
            d = self._point_to_pixel_segment((x, y), px1, px2)
            if d < closest_px:
                closest_px = d
                closest = frame

        
        self.hovered_frame = closest if closest_px < 15.0 else None

    def _compute_world_tolerance(self, frames):
        """
        Sahnedeki ortalama çubuk uzunluğuna göre dünya-uzayı toleransı.
        Ortalama çubuk uzunluğunun %5'i (mm/cm/m fark etmez).
        """
        if not frames:
            return 0.8
        lengths = []
        for f in frames.values():
            try:
                p1 = np.array(f.node_i.coords, dtype=float)
                p2 = np.array(f.node_j.coords, dtype=float)
                L = np.linalg.norm(p2 - p1)
                if L > 1e-6:
                    lengths.append(L)
            except Exception:
                continue
        if not lengths:
            return 0.8
        avg = float(np.mean(lengths))
        # Ortalama 3000mm çubuk → tolerans 150mm
        return max(avg * 0.05, 1e-3)
    # ------------------------------------------------------------------ #
    # Düzlem analizi
    # ------------------------------------------------------------------ #
    def execute_plane_analysis(self):
        """Seçilen düzlemdeki çubukları filtreler ve Convex Hull hesaplar."""
        if self.selected_frame is None:
            return
        scene = self.scene
        if scene is None:
            return

        axes = self.plane_indices[self.current_plane_idx]
        normal = self._calculate_plane_normal(self.selected_frame, axes)
        plane_point = self._get_frame_midpoint(self.selected_frame)

        projected_points = []
        frames = self._get_frames_dict()

        for frame in frames.values():
            if not hasattr(frame, "node_i") or not hasattr(frame, "node_j"):
                continue
            if not self._is_frame_on_plane(frame, self.selected_frame, normal, plane_point):
                continue

            try:
                p_i = np.array(frame.node_i.coords, dtype=float)
                p_j = np.array(frame.node_j.coords, dtype=float)
            except Exception:
                continue

            projected_points.append(self._project_to_plane(p_i, plane_point, normal))
            projected_points.append(self._project_to_plane(p_j, plane_point, normal))

        if not projected_points:
            return

        pts_array = np.array(projected_points, dtype=float)
        hull = self._compute_convex_hull(pts_array)

        if hasattr(scene, "set_boundary_polygon"):
            scene.set_boundary_polygon(hull)

    # ------------------------------------------------------------------ #
    # Render katmanları
    # ------------------------------------------------------------------ #
    def render(self):
        """Tüm görsel katmanları sırayla çizer (engine render döngüsünden çağır)."""
        
        self.render_preview()
        self.render_selected()
        self.render_hover()

    def render_hover(self):
        if self.hovered_frame is None:
            return
       

        f = self.hovered_frame
        try:
            p1 = np.array(f.node_i.coord if hasattr(f.node_i, "coord") else f.node_i.coords, dtype=float)
            p2 = np.array(f.node_j.coord if hasattr(f.node_j, "coord") else f.node_j.coords, dtype=float)
        except Exception as e:
            print(f"[R] HATA: {e}")
            return

        

        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glDisable(GL_TEXTURE_2D)
        glDisable(GL_CULL_FACE)
        glLineWidth(1.0)                  # ← 10 yap
        glColor4f(*self.HOVER_COLOR)      # ← SAF KIRMIZI (alfa bile yok)

        glBegin(GL_LINES)
        glVertex3f(p1[0], p1[1], p1[2])
        glVertex3f(p2[0], p2[1], p2[2])
        glEnd()

        glLineWidth(1.0)
        glEnable(GL_DEPTH_TEST)

    def render_selected(self):
        """Seçili çubuğu yeşil kalın çizgi olarak vurgular."""
        if self.selected_frame is None:
            return
        f = self.selected_frame
        try:
            p1 = np.array(f.node_i.coords, dtype=float)
            p2 = np.array(f.node_j.coords, dtype=float)
        except Exception:
            return

        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glDisable(GL_TEXTURE_2D)
        glLineWidth(self.SELECTED_LINE_WIDTH)
        glColor4f(*self.SELECTED_COLOR)

        glBegin(GL_LINES)
        glVertex3f(p1[0], p1[1], p1[2])
        glVertex3f(p2[0], p2[1], p2[2])
        glEnd()

        glLineWidth(1.0)
        glEnable(GL_DEPTH_TEST)

    def render_preview(self):
        """Seçili çubuğun bulunduğu düzlemi yarı saydam quad olarak çizer."""
        if self.selected_frame is None:
            return

        axes = self.plane_indices[self.current_plane_idx]
        normal = self._calculate_plane_normal(self.selected_frame, axes)

        try:
            p1 = np.array(self.selected_frame.node_i.coords, dtype=float)
            p2 = np.array(self.selected_frame.node_j.coords, dtype=float)
        except Exception:
            return

        mid = (p1 + p2) * 0.5

        # Düzlem içi iki dik vektör
        tangent = p2 - p1
        tn = np.linalg.norm(tangent)
        if tn < 1e-9:
            return
        tangent /= tn

        binormal = np.cross(normal, tangent)
        bn = np.linalg.norm(binormal)
        if bn < 1e-9:
            return
        binormal /= bn

        # Sahne ölçeğine göre quad yarıçapı (çubuk uzunluğunun 1.5 katı)
        radius = max(tn * 1.5, 100.0)

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glDisable(GL_LIGHTING)
        glDisable(GL_TEXTURE_2D)
        glColor4f(*self.PREVIEW_COLOR)

        glBegin(GL_QUADS)
        for s in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            v = mid + tangent * (s[0] * radius) + binormal * (s[1] * radius)
            glVertex3f(v[0], v[1], v[2])
        glEnd()

        glDisable(GL_BLEND)
        glEnable(GL_DEPTH_TEST)

    # ------------------------------------------------------------------ #
    # Geometri / matematik yardımcıları
    # ------------------------------------------------------------------ #
    def _screen_to_ray(self, mouse_pos, view_matrix, proj_matrix):
        """Ekran koordinatını dünya uzayında bir ışına çevirir."""
        x, y = mouse_pos
        ny = self.viewport_height - y  # OpenGL bottom-left

        ndc_x = (2.0 * x) / self.viewport_width - 1.0
        ndc_y = (2.0 * ny) / self.viewport_height - 1.0

        P = np.array(proj_matrix, dtype=float)
        V = np.array(view_matrix, dtype=float)

        # Singular matris koruması
        if abs(np.linalg.det(P)) < 1e-12 or abs(np.linalg.det(V)) < 1e-12:
            return np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.0, -1.0])

        try:
            near_eye = np.linalg.solve(P, np.array([ndc_x, ndc_y, -1.0, 1.0]))
            far_eye  = np.linalg.solve(P, np.array([ndc_x, ndc_y,  1.0, 1.0]))
        except np.linalg.LinAlgError:
            return np.array([0.0, 0.0, 0.0]), np.array([0.0, 0.0, -1.0])

        near_eye /= near_eye[3]
        far_eye  /= far_eye[3]

        near_world = np.linalg.solve(V, near_eye); near_world /= near_world[3]
        far_world  = np.linalg.solve(V, far_eye);  far_world  /= far_world[3]

        ray_origin = near_world[:3]
        ray_dir = far_world[:3] - near_world[:3]
        n = np.linalg.norm(ray_dir)
        if n > 1e-9:
            ray_dir /= n
        return ray_origin, ray_dir

    def _ray_to_segment_distance(self, ro, rd, p1, p2):
        """Işın ile doğru parçası arasındaki en kısa mesafe."""
        u = p2 - p1
        v = rd
        w = ro - p1

        a = float(np.dot(u, u))
        b = float(np.dot(u, v))
        c = float(np.dot(v, v))
        d = float(np.dot(u, w))
        e = float(np.dot(v, w))
        D = a * c - b * b

        if D < 1e-9:  # paralel
            if a < 1e-12:
                return float(np.linalg.norm(w))
            s = float(np.clip(-d / a, 0.0, 1.0))
            closest = p1 + s * u
            to_pt = closest - ro
            proj = np.dot(to_pt, v)
            perp = to_pt - proj * v
            return float(np.linalg.norm(perp))

        sc = float(np.clip((b * e - c * d) / D, 0.0, 1.0))
        tc = max(0.0, (a * e - b * d) / D)
        qp = w + sc * u - tc * v
        return float(np.linalg.norm(qp))


    # ------------------------------------------------------------------ #
    # Düzlem yardımcıları (projeye göre özelleştirilebilir)
    # ------------------------------------------------------------------ #
    def _get_frame_midpoint(self, frame):
        """Çubuğun orta noktasını döndürür (düzlem referans noktası)."""
        p1 = np.array(frame.node_i.coords, dtype=float)
        p2 = np.array(frame.node_j.coords, dtype=float)
        return (p1 + p2) * 0.5

    def _calculate_plane_normal(self, frame, axes):
        """
        Seçilen çubuğun yerel eksen kombinasyonuna göre normal vektör üretir.
        Şimdilik Z ekseni; projedeki yerel eksen sistemine göre özelleştir.
        """
        return np.array([0.0, 0.0, 1.0], dtype=float)

    def _is_frame_on_plane(self, frame, reference_frame, normal, plane_point,
                           tol_ratio=0.02):
        """
        Çubuğun ilgili düzlemde olup olmadığını kontrol eder.
        Referans çubuk uzunluğunun `tol_ratio` kadarını eşik kabul eder.
        """
        try:
            p1 = np.array(frame.node_i.coords, dtype=float)
            p2 = np.array(frame.node_j.coords, dtype=float)
        except Exception:
            return False

        ref_len = np.linalg.norm(
            np.array(reference_frame.node_j.coords, dtype=float)
            - np.array(reference_frame.node_i.coords, dtype=float)
        )
        tol = max(ref_len * tol_ratio, 1e-6)

        d1 = abs(np.dot(p1 - plane_point, normal))
        d2 = abs(np.dot(p2 - plane_point, normal))
        return d1 <= tol and d2 <= tol

    def _project_to_plane(self, point, plane_point, normal):
        """3B noktayı düzleme izdüşürüp 2B yerel koordinat döndürür."""
        normal = normal / max(np.linalg.norm(normal), 1e-12)

        v = point - plane_point
        dist = np.dot(v, normal)
        projected = point - dist * normal

        # Düzlem içi ortonormal baz
        t = np.array([1.0, 0.0, 0.0])
        if abs(np.dot(t, normal)) > 0.9:
            t = np.array([0.0, 1.0, 0.0])
        t = t - np.dot(t, normal) * normal
        t /= max(np.linalg.norm(t), 1e-12)
        b = np.cross(normal, t)

        local = projected - plane_point
        return np.array([np.dot(local, t), np.dot(local, b)], dtype=float)

    def _compute_convex_hull(self, points):
        """
        Andrew's Monotone Chain algoritması ile Convex Hull hesaplar.
        Girdi ve çıktı 2B nokta dizisidir (Nx2).
        """
        if points is None or len(points) == 0:
            return np.empty((0, 2), dtype=float)

        # Tekrarlayan noktaları temizle
        points = np.unique(points, axis=0)
        if len(points) <= 3:
            return points

        x = points[:, 0]
        y = points[:, 1]
        idx = np.lexsort((y, x))
        sorted_pts = points[idx]

        def cross(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        lower = []
        for p in sorted_pts:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)

        upper = []
        for p in reversed(sorted_pts):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)

        return np.array(lower[:-1] + upper[:-1], dtype=float)