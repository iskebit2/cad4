"""
LoadDistributionService — Poligon üzerindeki uniform_to_frame yüklerini
GeneralLoadDistributor ile hesaplayıp frame'lere lineer yayılı yük olarak ekler.

Sürüm 2:
  - Eğik poligonlarda doğru alan taraması (polygon u-v düzleminde)
  - One-way / Two-way ayrımı
  - 3D mesafe (yanlış frame'e yük binmesin)
  - Yön dönüşümü (polygon load direction → frame local axis)
"""
import math
import glm
from domain.definition import (
    FrameDistributedLoad, DistType, LoadDirection
)
from domain.local_axes import (
    polygon_plane_axes, polygon_plane_frame,
    classify_load_direction, point_to_segment_distance_3d,
)
from logging_config import CadLogger

logger = CadLogger.get(__name__)


class GeneralLoadDistributor:
    """
    Grid örnekleme ile yük dağıtımı.
    Polygon düzleminde (u,v) tarar, her örneği en yakın aday frame'e atar.
    """

    def __init__(self, frames_3d: dict, plane_axes: tuple, target_step: float = 200.0):
        """
        frames_3d : {frame_id: [(x1,y1,z1), (x2,y2,z2)]}
        plane_axes: (origin, u, v, n) — glm.vec3 üçlüsü
        target_step: mm cinsinden grid adımı
        """
        self.frames = frames_3d
        self.origin, self.u, self.v, self.n = plane_axes
        self.step = target_step

    # ------------------------------------------------------------------
    # YARDIMCILAR
    # ------------------------------------------------------------------
    def _poly_uv_bounds(self, poly_coords_3d):
        """
        Polygondaki her node'un (u,v) düzlem koordinatlarını hesapla,
        bounding box döndür.
        """
        uvs = []
        for p in poly_coords_3d:
            pv = glm.vec3(*p) - self.origin
            uvs.append((glm.dot(pv, self.u), glm.dot(pv, self.v)))
        us = [uv[0] for uv in uvs]
        vs = [uv[1] for uv in uvs]
        return (min(us), max(us), min(vs), max(vs))

    def _is_uv_inside_polygon(self, su, sv, poly_uv):
        """
        2D point-in-polygon (ray casting) — poligonun u-v izdüşümünde.
        poly_uv: [(u_i, v_i), ...]
        """
        inside = False
        n = len(poly_uv)
        j = n - 1
        for i in range(n):
            ui, vi = poly_uv[i]
            uj, vj = poly_uv[j]
            if ((vi > sv) != (vj > sv)):
                u_intersect = (uj - ui) * (sv - vi) / (vj - vi + 1e-12) + ui
                if su < u_intersect:
                    inside = not inside
            j = i
        return inside

    # ------------------------------------------------------------------
    # ANA DAĞITIM
    # ------------------------------------------------------------------
    def distribute(self, poly_coords_3d, load_magnitude: float):
        """
        Tek bir yük için dağıtımı yapar.
        
        Döner: {frame_id: toplam_kuvvet}
        """
        # Polygon'u (u,v) düzlemine indir
        poly_uv = []
        for p in poly_coords_3d:
            pv = glm.vec3(*p) - self.origin
            poly_uv.append((glm.dot(pv, self.u), glm.dot(pv, self.v)))

        u_min, u_max, v_min, v_max = self._poly_uv_bounds(poly_coords_3d)

        # dA = (grid adımı)² mm² → m²
        step_mm = self.step
        dA_mm2 = step_mm * step_mm
        dA_m2 = dA_mm2 * 1e-6   # mm² → m²

        frame_forces = {fid: 0.0 for fid in self.frames}

        su = u_min
        while su <= u_max:
            sv = v_min
            while sv <= v_max:
                if self._is_uv_inside_polygon(su, sv, poly_uv):
                    # (u,v) → 3D dünya noktası
                    p_world = self.origin + self.u * su + self.v * sv

                    # En yakın frame'i bul (3D mesafe)
                    closest_id = None
                    min_dist = float("inf")
                    for fid, seg in self.frames.items():
                        d = point_to_segment_distance_3d(p_world, seg[0], seg[1])
                        if d < min_dist:
                            min_dist = d
                            closest_id = fid

                    if closest_id is not None:
                        frame_forces[closest_id] += load_magnitude * dA_m2
                sv += step_mm
            su += step_mm

        return frame_forces


class LoadDistributionService:

    # Tolerans (mm) — frame uçları bu mesafede ise poligon düzlemine ait sayılır
    PLANE_TOL = 15.0
    # Açı toleransı (derece) — one-way filtre için
    DIR_TOL_DEG = 10.0

    @staticmethod
    def distribute_polygon_loads(scene, target_polygon, target_step: float = 200.0):
        """
        Poligondaki tüm uniform_to_frame yüklerini, uygun frame'lere dağıtır.
        Döner: atanan yük sayısı (frame × pattern kombinasyonu).
        """
        if not getattr(target_polygon, "uniform_to_frame_loads", None):
            return 0

        # 1. Polygon düzlem eksenleri
        if len(target_polygon.nodes) < 3:
            return 0

        origin, poly_u, poly_v, poly_n = polygon_plane_frame(target_polygon.nodes)

        # Polygondaki node'ların 3D koordinatları
        poly_coords_3d = [(nd.x, nd.y, nd.z) for nd in target_polygon.nodes]

        # 2. Poligon düzlemindeki frame'leri bul
        frames_on_plane = LoadDistributionService._collect_frames_on_plane(
            scene, origin, poly_n, tolerance=LoadDistributionService.PLANE_TOL
        )

        if not frames_on_plane:
            logger.info("[Distribute] Poligon düzleminde frame bulunamadı.")
            return 0

        # 3. Her yük için ayrı dağıtım (farklı dist_type olabilir)
        assigned_count = 0
        for load in target_polygon.uniform_to_frame_loads:
            # One-way ise adayları filtrele
            candidates = LoadDistributionService._filter_frames_one_way(
                frames_on_plane, poly_u, poly_v, load.dist_type
            )
            if not candidates:
                logger.warning(
                    f"[Distribute] '{load.pattern_name}' ({load.dist_type.value}) "
                    f"için uygun frame yok. Poligon u={poly_u}, v={poly_v}."
                )
                continue

            # Grid dağıtımı
            distributor = GeneralLoadDistributor(
                frames_3d=candidates,
                plane_axes=(origin, poly_u, poly_v, poly_n),
                target_step=target_step,
            )
            frame_forces = distributor.distribute(poly_coords_3d, load.value)

            # Frame'e line load olarak yaz
            for fid, total_force in frame_forces.items():
                if total_force <= 1e-6:
                    continue
                frame_obj = scene.frames.get(fid)
                if not frame_obj:
                    continue

                L_m = frame_obj.get_length() * 1e-3   # mm → m
                if L_m < 1e-9:
                    continue
                line_load = total_force / L_m     # kN/m

                # Aynı pattern'in eski yükünü temizle
                frame_obj.dist_loads = [
                    dl for dl in frame_obj.dist_loads
                    if dl.pattern_name != load.pattern_name
                ]

                # Yön dönüşümü
                frame_dir = LoadDistributionService._resolve_frame_load_direction(
                    load.direction, frame_obj, poly_u, poly_v, poly_n
                )

                frame_obj.dist_loads.append(FrameDistributedLoad(
                    pattern_name=load.pattern_name,
                    force_or_moment="Force",
                    direction=frame_dir,
                    p1=line_load,
                    p2=line_load,
                    d1=0.0, d2=1.0,
                    is_relative=True,
                    coordinate_system="GLOBAL",
                ))
                frame_obj.mark_dirty()
                assigned_count += 1

        return assigned_count

    # ------------------------------------------------------------------
    # FRAME TOPLAMA
    # ------------------------------------------------------------------
    @staticmethod
    def _collect_frames_on_plane(scene, plane_origin, plane_normal, tolerance=15.0):
        """
        İki ucu da poligon düzlemine tolerance mesafesinde olan frame'leri toplar.
        Döner: {frame_id: [(x1,y1,z1), (x2,y2,z2)]}
        """
        result = {}
        n = plane_normal

        for fid, frame in scene.frames.items():
            if not frame.node_i or not frame.node_j:
                continue
            pi = glm.vec3(frame.node_i.x, frame.node_i.y, frame.node_i.z)
            pj = glm.vec3(frame.node_j.x, frame.node_j.y, frame.node_j.z)

            di = abs(glm.dot(pi - plane_origin, n))
            dj = abs(glm.dot(pj - plane_origin, n))

            if di <= tolerance and dj <= tolerance:
                result[fid] = [
                    (pi.x, pi.y, pi.z),
                    (pj.x, pj.y, pj.z),
                ]
        return result

    # ------------------------------------------------------------------
    # ONE-WAY FİLTRE
    # ------------------------------------------------------------------
    @staticmethod
    def _filter_frames_one_way(frames, poly_u, poly_v, dist_type):
        """
        One-way ise adayları hedef eksene paralel olanlarla sınırlar.
        
        Mantık:
          ONE_WAY_U1 → yük U1 yönünde akar → U2'ye PARALEL frame'ler taşır
          ONE_WAY_U2 → yük U2 yönünde akar → U1'e PARALEL frame'ler taşır
          TWO_WAY    → filtre yok
        """
        if dist_type == DistType.TWO_WAY:
            return frames

        # Yükün akış yönü belirle
        # ONE_WAY_U1 → yük U1 boyunca akar, taşıyıcı U2'ye paralel
        # ONE_WAY_U2 → yük U2 boyunca akar, taşıyıcı U1'e paralel
        if dist_type in (DistType.ONE_WAY_U1, DistType.ONE_WAY):
            carrier_axis = poly_v
        elif dist_type == DistType.ONE_WAY_U2:
            carrier_axis = poly_u
        else:
            return frames

        cos_tol = math.cos(math.radians(LoadDistributionService.DIR_TOL_DEG))
        filtered = {}

        for fid, seg in frames.items():
            dx = seg[1][0] - seg[0][0]
            dy = seg[1][1] - seg[0][1]
            dz = seg[1][2] - seg[0][2]
            L = math.sqrt(dx * dx + dy * dy + dz * dz)
            if L < 1e-9:
                continue
            fd = glm.vec3(dx / L, dy / L, dz / L)
            dot = abs(glm.dot(fd, carrier_axis))
            if dot >= cos_tol:
                filtered[fid] = seg

        return filtered

    # ------------------------------------------------------------------
    # YÖN DÖNÜŞÜMÜ
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_frame_load_direction(
        poly_load_dir, frame, poly_u, poly_v, poly_n
    ) -> LoadDirection:
        """
        Poligon yükünün yönünü frame'e uygun LoadDirection'a çevir.

        İki kategori:
            1) GRAVITY family (GRAV, GLOBAL_Z, DEAD, LIVE, SNOW):
            → Frame'e de GRAVITY olarak yaz. Eğik frame'de SAP'ın GRAV
                yorumu zaten global Z'ye göre çalışır, doğru sonuç verir.
            2) SURFACE NORMAL family (WIND, LOCAL_3):
            → Frame LOCAL_2 (align edilmişse poligon normali ile çakışır).
            3) IN-PLANE (GLOBAL_X/Y düzlem içiyse):
            → Frame LOCAL_3 (düzlem içi, çubuğa dik).
            4) Diğer / bilinmeyen:
            → olduğu gibi bırak.
        """
        from domain.definition import LoadDirection

        # --- 1) Gravity family: dokunma ---
        if poly_load_dir in (LoadDirection.GRAVITY, LoadDirection.GLOBAL_Z):
            return LoadDirection.GRAVITY   # SAP'ta GRAV olarak kalır
            # (İstersen LoadDirection.GLOBAL_Z de dönebilirsin — ikisi de düşey)

        # --- 2) Surface normal family: frame local 2'ye çevir ---
        if poly_load_dir == LoadDirection.LOCAL_3:
            return LoadDirection.LOCAL_2

        # --- 3) In-plane: frame local 3'e çevir ---
        if poly_load_dir in (LoadDirection.LOCAL_1, LoadDirection.LOCAL_2):
            return LoadDirection.LOCAL_3

        # --- 4) Global X / Y: düzlemle ilişkisini kontrol et ---
        if poly_load_dir in (LoadDirection.GLOBAL_X, LoadDirection.GLOBAL_Y):
            # Bu yön düzlem normaline mi, düzleme mi paralel?
            kind, _ = classify_load_direction(
                poly_load_dir, poly_u, poly_v, poly_n
            )
            if kind == "NORMAL":
                return LoadDirection.LOCAL_2   # düzleme dik → local 2
            if kind in ("U", "V"):
                return LoadDirection.LOCAL_3   # düzlem içi → local 3
            # Global kalabilir
            return poly_load_dir

        # --- Diğer (PROJECTED_*, vs.): olduğu gibi ---
        return poly_load_dir