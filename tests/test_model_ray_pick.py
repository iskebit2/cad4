# tests/test_model_ray_pick.py
from __future__ import annotations

import os
import pytest
import numpy as np
from domain.project import Project

def test_real_model_frame_ray_pick():
    import os
    candidates = [
        "model_projesi.cd4",
        r"D:\Program\cad4\model_projesi.cd4",
        "D:/Program/cad4/model_projesi.cd4",
    ]
    path = None
    for p in candidates:
        if os.path.exists(p):
            path = p
            break

    print(f"[DEBUG] cwd={os.getcwd()}")
    print(f"[DEBUG] candidates={[(p, os.path.exists(p)) for p in candidates]}")
    print(f"[DEBUG] path={path}")

    if path is None:
        pytest.skip("Proje dosyası bulunamadı")

    project = Project.load(path)
    math_model = project.math_model
    
    assert len(math_model.frames) > 0, "Modelde test edilecek hiç frame yok."

    first_frame_id = list(math_model.frames.keys())[0]
    frame = math_model.frames[first_frame_id]

    node_a = getattr(frame, "node_i", None)
    node_b = getattr(frame, "node_j", None)
    if node_a is None or node_b is None:
        pytest.skip(f"Frame düğümleri eksik: {first_frame_id}")

    p1 = np.array([node_a.x, node_a.y, node_a.z], dtype=float)
    p2 = np.array([node_b.x, node_b.y, node_b.z], dtype=float)

    # Frame'in orta noktasından dikine bir ray kurgula
    mid_point = (p1 + p2) * 0.5
    ray_origin = mid_point + np.array([0.0, 0.0, 50.0], dtype=float)
    ray_dir = np.array([0.0, 0.0, -1.0], dtype=float)

    v = p2 - p1
    w = ray_origin - p1
    a = np.dot(v, v)
    b = np.dot(v, ray_dir)
    c = np.dot(ray_dir, ray_dir)
    d = np.dot(v, w)
    e = np.dot(ray_dir, w)
    
    denom = a * c - b * b
    if abs(denom) < 1e-6:
        w_mid = mid_point - ray_origin
        projection = np.dot(w_mid, ray_dir)
        closest_point_on_ray = ray_origin + projection * ray_dir
        distance = np.linalg.norm(mid_point - closest_point_on_ray)
    else:
        s = (b * e - c * d) / denom
        t = (a * e - b * d) / denom
        s = max(0.0, min(1.0, s))
        closest_point_on_segment = p1 + s * v
        closest_point_on_ray = ray_origin + t * ray_dir
        distance = np.linalg.norm(closest_point_on_segment - closest_point_on_ray)

    print(f"\n[Gerçek Model Ray Pick Testi] Frame ID: {first_frame_id}")
    print(f"  • P1: {p1}, P2: {p2}")
    print(f"  • Hesaplanan Kesişim Mesafesi: {distance:.5f}")

    assert distance < 1.0, f"Ray çubuğu ıskaladı! Mesafe: {distance}"