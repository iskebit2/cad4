# geometry/sd_to_areas.py
import math

import glm
import numpy as np
from typing import List, Optional, Tuple
from domain.element import Node, Frame, Area
from domain.definition import Section, Material, SectionType
from logging_config import CadLogger

logger = CadLogger.get(__name__)


def _frame_local_frame(frame: Frame) -> Tuple[glm.vec3, glm.vec3, glm.vec3]:
    """Frame'in (e1=axis, e2, e3) ortonormal çerçevesi. glm.mat3 sıralamasına bağımlı değil."""
    dx = frame.node_j.x - frame.node_i.x
    dy = frame.node_j.y - frame.node_i.y
    dz = frame.node_j.z - frame.node_i.z
    L = (dx*dx + dy*dy + dz*dz) ** 0.5
    if L < 1e-9:
        raise ValueError("sıfır uzunluklu frame")
    e1 = glm.vec3(dx/L, dy/L, dz/L)

    # e2: dünya Z'sine dik (e1 Z'ye paralel değilse)
    ref = glm.vec3(0, 0, 1) if abs(e1.z) < 0.9999 else glm.vec3(1, 0, 0)
    e2 = glm.normalize(ref - e1 * glm.dot(ref, e1))
    e3 = glm.normalize(glm.cross(e1, e2))

    if abs(frame.rotation_deg) > 1e-9:
        a = math.radians(frame.rotation_deg)
        ca, sa = math.cos(a), math.sin(a)
        e2_new = e2 * ca + e3 * sa
        e3_new = -e2 * sa + e3 * ca
        e2, e3 = glm.normalize(e2_new), glm.normalize(e3_new)

    return e1, e2, e3

def sd_frame_to_areas(
    frame: Frame,
    thickness: float,
    material: Optional[Material] = None,
    section_name: str = "",
    label_prefix: str = "",
) -> Tuple[List[Area], List[str]]:
    errors: List[str] = []
    section: Section = frame.section

    if section is None or section.profile_type != SectionType.CUSTOM:
        return [], [f"Frame '{frame.label}': SD section değil"]

    sd = getattr(section, 'sd_section', None)
    if sd is None or not sd.shapes:
        return [], [f"Frame '{frame.label}': sd_section yok veya boş"]

    poly = next(
        (s for s in sd.shapes if getattr(s, 'shape_kind', '') == 'Polygon' and len(s.points) >= 3),
        None,
    )
    if poly is None:
        return [], [f"Frame '{frame.label}': SD Polygon shape yok"]

    # Frame düşey mi?
    dx = frame.node_j.x - frame.node_i.x
    dy = frame.node_j.y - frame.node_i.y
    dz = frame.node_j.z - frame.node_i.z
    L = (dx*dx + dy*dy + dz*dz) ** 0.5
    if L < 1e-9:
        return [], [f"Frame '{frame.label}': sıfır uzunluklu frame"]
    if abs(abs(dz) / L - 1.0) > 1e-3:
        return [], [f"Frame '{frame.label}': düşey değil (|axis.z/L|={abs(dz/L):.4f})"]

    # Local frame — glm.mat3 sıralamasından bağımsız
    e1, e2, e3 = _frame_local_frame(frame)

    # Ekstra güvence: kesit düzlemi XY'de olmalı (düşey frame → otomatik)
    if abs(e2.z) > 1e-3 or abs(e3.z) > 1e-3:
        return [], [f"Frame '{frame.label}': kesit düzlemi XY'de değil "
                    f"(e2.z={e2.z:.4f}, e3.z={e3.z:.4f})"]

    mat = material if material is not None else section.material
    ni, nj = frame.node_i, frame.node_j

    pts_i, pts_j = [], []
    for p in poly.points:
        u, v = float(p.x), float(p.y)
        pi = glm.vec3(ni.x, ni.y, ni.z) + u * e2 + v * e3
        pj = glm.vec3(nj.x, nj.y, nj.z) + u * e2 + v * e3
        pts_i.append((pi.x, pi.y, pi.z))
        pts_j.append((pj.x, pj.y, pj.z))

    N = len(pts_i)
    areas: List[Area] = []
    base_label = label_prefix or frame.label or "A"

    for k in range(N):
        k2 = (k + 1) % N
        corners = [pts_i[k], pts_i[k2], pts_j[k2], pts_j[k]]
        nodes = [Node(x, y, z) for (x, y, z) in corners]
        area = Area(nodes, thickness=thickness, label=f"{base_label}_A{k+1}")
        area.material = mat
        area.section_name = section_name or section.name
        areas.append(area)

    return areas, errors