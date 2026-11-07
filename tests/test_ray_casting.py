# tests/test_ray_casting.py
from __future__ import annotations

import pytest
import numpy as np
from pyglm import glm

class DummyCamera:
    """Test için basit kamera mock'u (View ve Projection matrisleri ile)."""
    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height
        self.position = glm.vec3(0.0, 0.0, 100.0)
        self.target = glm.vec3(0.0, 0.0, 0.0)
        self.up = glm.vec3(0.0, 1.0, 0.0)

    def get_view_matrix(self):
        return glm.lookAt(self.position, self.target, self.up)

    def get_projection_matrix(self):
        return glm.perspective(glm.radians(45.0), self.width / self.height, 0.1, 1000.0)

def screen_to_ray(x, y, camera, win_w, win_h):
    """Ekran piksellerini 3D dünyada bir ışına (ray origin + direction) dönüştürür."""
    proj = camera.get_projection_matrix()
    view = camera.get_view_matrix()
    inv_mvp = glm.inverse(proj * view)

    # NDC koordinatlarına çevir (-1 to 1)
    ndc_x = (2.0 * x) / win_w - 1.0
    ndc_y = 1.0 - (2.0 * y) / win_h
    
    # Near ve Far düzlemleri için clip space noktaları
    clip_near = glm.vec4(ndc_x, ndc_y, -1.0, 1.0)
    clip_far  = glm.vec4(ndc_x, ndc_y,  1.0, 1.0)

    world_near = inv_mvp * clip_near
    world_far  = inv_mvp * clip_far

    if world_near.w != 0:
        world_near /= world_near.w
    if world_far.w != 0:
        world_far /= world_far.w

    origin = glm.vec3(world_near)
    direction = glm.normalize(glm.vec3(world_far) - origin)
    return origin, direction

def ray_intersect_sphere(ray_origin, ray_dir, sphere_center, radius):
    """Ray ile Node (küre) kesişim testi."""
    oc = ray_origin - sphere_center
    a = glm.dot(ray_dir, ray_dir)
    b = 2.0 * glm.dot(oc, ray_dir)
    c = glm.dot(oc, oc) - radius * radius
    discriminant = b * b - 4 * a * c
    return discriminant >= 0

def ray_intersect_segment_distance(ray_origin, ray_dir, p1, p2):
    """Ray ile Frame/Çizgi (segment) arasındaki minimum mesafeyi hesaplar (Paralel durumlar dahil)."""
    p1 = np.array(p1, dtype=float)
    p2 = np.array(p2, dtype=float)
    ro = np.array(ray_origin, dtype=float)
    rd = np.array(ray_dir, dtype=float)
    
    v = p2 - p1
    w = ro - p1
    
    a = np.dot(v, v)
    b = np.dot(v, rd)
    c = np.dot(rd, rd)
    d = np.dot(v, w)
    e = np.dot(rd, w)
    
    denom = a * c - b * b
    if abs(denom) < 1e-6:
        # Paralel / Collinear durum: Segmentin orta noktasından ışına olan mesafeyi alalım
        mid_point = (p1 + p2) * 0.5
        w_mid = mid_point - ro
        projection = np.dot(w_mid, rd)
        if projection < 0:
            return float('inf') # Işının arkasında
        closest_point_on_ray = ro + projection * rd
        return np.linalg.norm(mid_point - closest_point_on_ray)
        
    s = (b * e - c * d) / denom
    t = (a * e - b * d) / denom
    
    s = max(0.0, min(1.0, s))
    if t < 0:
        return float('inf')
        
    closest_point_on_segment = p1 + s * v
    closest_point_on_ray = ro + t * rd
    
    return np.linalg.norm(closest_point_on_segment - closest_point_on_ray)

# --- TESTLER ---

def test_screen_to_ray_generation():
    """Ekran merkezinden atılan ışının kamera bakış yönünde olduğunu doğrula."""
    cam = DummyCamera(800, 600)
    origin, direction = screen_to_ray(400, 300, cam, 800, 600)
    
    # Merkezden atılan ışın doğrudan (0, 0, -1) yönüne bakmalı (bakış ekseni boyunca)
    assert origin.z > 0
    assert abs(direction.x) < 1e-3
    assert abs(direction.y) < 1e-3
    assert direction.z < 0

def test_ray_node_collision():
    """Tam üstüne tıklandığında ray'in node'u (küreyi) yakaladığını test et."""
    cam = DummyCamera(800, 600)
    # (0,0,0) dünyadaki orijine denk gelen ekran pikselini bulalım veya tersini yapalım
    origin, direction = screen_to_ray(400, 300, cam, 800, 600)
    
    # Işın üzerinde bir noktaya node koyalım
    node_pos = origin + direction * 50.0
    
    hit = ray_intersect_sphere(origin, direction, node_pos, radius=2.0)
    assert hit is True

def test_ray_frame_distance_collision():
    """Işının bir Frame çizgisinin yakınından geçerken mesafesinin çok küçük olduğunu test et."""
    origin = glm.vec3(0, 0, 100)
    direction = glm.vec3(0, 0, -1) # Z ekseni boyunca dümdüz aşağı
    
    # X=0, Y=0 hattında uzanan bir frame
    p1 = (0.0, 0.0, 0.0)
    p2 = (0.0, 0.0, 50.0)
    
    dist = ray_intersect_segment_distance(origin, direction, p1, p2)
    assert dist < 1e-3 # Tam üstünden geçiyor, mesafe sıfır olmalı