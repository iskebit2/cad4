# domain/local_axes.py
import glm
import math
from typing import Tuple

def frame_local_axes(node_i, node_j, rotation_deg: float = 0.0):
    """
    Frame için 3x3 dönüşüm matrisi döner (global → local).
    SAP2000 konvansiyonu:
      - 1-ekseni: i → j yönü
      - 2-ekseni: başlangıçta global Z'ye dik, XY düzleminde
      - 3-ekseni: sağ el kuralı (cross product)
      - rotation_deg: 1-eksen etrafında saat yönü tersi dönme
    """
    dx = node_j.x - node_i.x
    dy = node_j.y - node_i.y
    dz = node_j.z - node_i.z
    L = math.sqrt(dx*dx + dy*dy + dz*dz)
    if L < 1e-9:
        return glm.mat3(1.0)
    e1 = glm.vec3(dx/L, dy/L, dz/L)
    
    # Referans vektör: 1-ekseni global Z'ye paralel değilse Z, paralelse X
    ref = glm.vec3(0, 0, 1) if abs(e1.z) < 0.9999 else glm.vec3(1, 0, 0)
    
    e2 = glm.normalize(ref - e1 * glm.dot(ref, e1))  # yatay 2-eksen
    e3 = glm.cross(e1, e2)                            # sağ el: 1×2 = 3
    
    # Rotation uygula (1-eksen etrafında)
    if abs(rotation_deg) > 1e-9:
        a = math.radians(rotation_deg)
        ca, sa = math.cos(a), math.sin(a)
        e2_new = e2 * ca + e3 * sa
        e3_new = -e2 * sa + e3 * ca
        e2, e3 = glm.normalize(e2_new), glm.normalize(e3_new)
    
    # 3x3 matris: satırlar lokal eksenler (global → local dönüşümü)
    return glm.mat3(e1, e2, e3)


def polygon_normal(nodes, use_newell=True):
    """Newell metodu ile polygon normal vektörü (kavisli olmayan, planlı)."""
    n = glm.vec3(0, 0, 0)
    if use_newell:
        N = len(nodes)
        for i in range(N):
            a = nodes[i]
            b = nodes[(i + 1) % N]
            n.x += (a.y - b.y) * (a.z + b.z)
            n.y += (a.z - b.z) * (a.x + b.x)
            n.z += (a.x - b.x) * (a.y + b.y)
    else:
        # 3 noktadan cross product (convex için)
        if len(nodes) < 3: return glm.vec3(0, 0, 1)
        v1 = glm.vec3(nodes[1].x-nodes[0].x, nodes[1].y-nodes[0].y, nodes[1].z-nodes[0].z)
        v2 = glm.vec3(nodes[2].x-nodes[0].x, nodes[2].y-nodes[0].y, nodes[2].z-nodes[0].z)
        n = glm.cross(v1, v2)
    L = glm.length(n)
    return n / L if L > 1e-9 else glm.vec3(0, 0, 1)


def polygon_plane_axes(nodes):
    """
    Polygon düzlemi için (e_u, e_v, n) ortonormal frame.
    - n: normal
    - e_u: ilk kenar yönü (projected)
    - e_v: n × e_u
    """
    N = polygon_normal(nodes)
    # İlk kenar yönü
    u = glm.vec3(nodes[1].x-nodes[0].x, nodes[1].y-nodes[0].y, nodes[1].z-nodes[0].z)
    # Normal'e dik hale getir
    u = u - N * glm.dot(u, N)
    if glm.length(u) < 1e-6:
        # Yedek: global X'i projeksiyonla
        u = glm.vec3(1, 0, 0) - N * N.x
    u = glm.normalize(u)
    v = glm.normalize(glm.cross(N, u))
    return u, v, N


def align_frame_to_polygon_plane(frame, polygon_nodes):
    """
    Frame'in local 3-eksenini poligon normaline hizalar.
    Sonuç: frame.rotation_deg güncellenir ve dönen açı (derece) döner.

    Parametreler
    ------------
    frame : Frame
        Hizalanacak frame (node_i, node_j, rotation_deg kullanılır).
    polygon_nodes : List[Node]
        Hedef poligonun node listesi (>= 3 node).

    Döner
    -----
    float : uygulanan rotation açısı (derece, -180..180).
            Hizalama yapılamadıysa 0.0 ve frame.rotation_deg değişmez.
    """
    if len(polygon_nodes) < 3:
        return 0.0

    # Hedef normal
    _, _, n_poly = polygon_plane_axes(polygon_nodes)

    # Frame'in 1-ekseni
    e1 = glm.vec3(*frame.get_axis())
    L = glm.length(e1)
    if L < 1e-9:
        return 0.0
    e1 = e1 / L

    # Frame poligon düzlemine paralel mi? Değilse (frame düşeyken) hizalama anlamsız.
    if abs(glm.dot(e1, n_poly)) > 0.999:
        # Frame normal'e paralel (düşey çubuk) → döndürülemez, atla
        return 0.0

    # rotation = 0 ile frame'in doğal 3-eksenini bul
    R0 = frame_local_axes(frame.node_i, frame.node_j, 0.0)
    # R0 sütunları: e1, e2, e3
    # glm.mat3 column-major: R0[0] = e1, R0[1] = e2, R0[2] = e3
    e3_natural = glm.vec3(R0[2][0], R0[2][1], R0[2][2])

    # e3_natural ile n_poly arasındaki açı
    dot = glm.dot(e3_natural, n_poly)
    dot = max(-1.0, min(1.0, dot))
    angle_rad = math.acos(dot)

    # İşaret: e1 × e3_natural ile n_poly'nin z bileşenine bak
    cross = glm.cross(e1, e3_natural)
    sign = 1.0 if glm.dot(cross, n_poly) >= 0.0 else -1.0

    angle_deg = math.degrees(angle_rad) * sign

    # -180..180 aralığına normalize et
    while angle_deg > 180.0:
        angle_deg -= 360.0
    while angle_deg < -180.0:
        angle_deg += 360.0

    frame.rotation_deg = angle_deg
    frame.mark_dirty()
    return angle_deg

# ============================================================================
# POLYGON / LOAD DIRECTION YARDIMCILARI
# ============================================================================

def classify_load_direction(load_dir_enum, poly_u, poly_v, poly_n,
                            cos_threshold: float = 0.85):
    """
    Poligon yükünün yönünü sınıflandır.
    
    Döner: ("NORMAL" | "U" | "V" | "GRAV" | "GX" | "GY" | "GZ" | "UNKNOWN", 
            yük vektörü glm.vec3)
    
    Parametreler
    ------------
    load_dir_enum : LoadDirection
    poly_u, poly_v, poly_n : glm.vec3 — polygon düzlem eksenleri
    cos_threshold : 0.85 (~32°) — bu açıdan yakınsa o eksene ait sayılır
    
    Notlar
    ------
    - "GLOBAL_X/Y/Z" ve "GRAV" girdileri önce dünya vektörüne çevrilir
    - "LOCAL_1/2/3" girdileri poligon eksenlerine göre yorumlanır:
        LOCAL_1 → poly_u
        LOCAL_2 → poly_v
        LOCAL_3 → poly_n  (basınç gibi davranır)
    """
    from domain.definition import LoadDirection

    # 1. Girdi yönünü dünya vektörüne çevir
    if load_dir_enum == LoadDirection.GLOBAL_X:
        world_v = glm.vec3(1, 0, 0)
    elif load_dir_enum == LoadDirection.GLOBAL_Y:
        world_v = glm.vec3(0, 1, 0)
    elif load_dir_enum == LoadDirection.GLOBAL_Z:
        world_v = glm.vec3(0, 0, 1)
    elif load_dir_enum == LoadDirection.GRAVITY:
        world_v = glm.vec3(0, 0, -1)
    elif load_dir_enum == LoadDirection.LOCAL_1:
        world_v = poly_u
    elif load_dir_enum == LoadDirection.LOCAL_2:
        world_v = poly_v
    elif load_dir_enum == LoadDirection.LOCAL_3:
        world_v = poly_n
    elif load_dir_enum == LoadDirection.PROJECTED_X:
        world_v = glm.vec3(1, 0, 0)
    elif load_dir_enum == LoadDirection.PROJECTED_Y:
        world_v = glm.vec3(0, 1, 0)
    elif load_dir_enum == LoadDirection.PROJECTED_Z:
        world_v = glm.vec3(0, 0, 1)
    else:
        return "UNKNOWN", glm.vec3(0, 0, -1)

    v = glm.normalize(world_v) if glm.length(world_v) > 1e-9 else world_v

    # 2. Sınıflandırma: hangi eksene en yakın?
    dots = {
        "NORMAL": abs(glm.dot(v, poly_n)),   # poligon normali (basınç)
        "U":      abs(glm.dot(v, poly_u)),
        "V":      abs(glm.dot(v, poly_v)),
    }
    best = max(dots, key=dots.get)
    if dots[best] >= cos_threshold:
        return best, v

    # 3. Dünya eksenlerine yakınlık (düşey duvar gibi özel durumlar için)
    world_dots = {
        "GX": abs(v.x),
        "GY": abs(v.y),
        "GZ": abs(v.z),
        "GRAV": abs(-v.z),   # aşağı yön
    }
    best_w = max(world_dots, key=world_dots.get)
    if world_dots[best_w] >= cos_threshold:
        return best_w, v

    return "UNKNOWN", v


def polygon_plane_frame(polygon_nodes):
    """
    Polygon düzlem eksenlerini (origin, u, v, n) olarak döner.
    polygon_plane_axes'in bir üst katmanı — origin de dahil.
    """
    if len(polygon_nodes) < 3:
        return glm.vec3(0), glm.vec3(1, 0, 0), glm.vec3(0, 1, 0), glm.vec3(0, 0, 1)

    u, v, n = polygon_plane_axes(polygon_nodes)
    # Origin: centroid
    cx = sum(nd.x for nd in polygon_nodes) / len(polygon_nodes)
    cy = sum(nd.y for nd in polygon_nodes) / len(polygon_nodes)
    cz = sum(nd.z for nd in polygon_nodes) / len(polygon_nodes)
    origin = glm.vec3(cx, cy, cz)
    return origin, u, v, n


def project_point_to_plane(point, plane_origin, plane_normal):
    """
    Noktayı düzleme dik projeksiyonla indir.
    Döner: (proj_point, signed_distance)
    """
    p = glm.vec3(*point) if not isinstance(point, glm.vec3) else point
    diff = p - plane_origin
    d = glm.dot(diff, plane_normal)
    proj = p - plane_normal * d
    return proj, d


def point_to_segment_distance_3d(p, a, b):
    """
    3D uzayda P noktasının AB doğru parçasına en kısa mesafesi.
    a, b, p: (x, y, z) tuple veya glm.vec3
    """
    pa = glm.vec3(*a) if not isinstance(a, glm.vec3) else a
    pb = glm.vec3(*b) if not isinstance(b, glm.vec3) else b
    pp = glm.vec3(*p) if not isinstance(p, glm.vec3) else p

    ab = pb - pa
    L2 = glm.dot(ab, ab)
    if L2 < 1e-12:
        return glm.length(pp - pa)
    t = glm.dot(pp - pa, ab) / L2
    t = max(0.0, min(1.0, t))
    proj = pa + ab * t
    return glm.length(pp - proj)