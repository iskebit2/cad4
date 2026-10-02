# tests/test_frame_simple.py
import numpy as np
from domain.element import Node, Frame, Section
from domain.definition import SectionType
from geometry.frame_builder import FrameBuilder
import logging
logger = logging.getLogger(__name__)

# DOĞRU: Node(x, y, z, label)
n1 = Node(0, 0, 0, "N1")
n2 = Node(1000, 0, 0, "N2")  # 1000 mm = 1 m

# DOĞRU: Section(name, profile_type, profile_params, material=None, color)
section = Section(
    name="TEST",
    profile_type=SectionType.RECT,
    profile_params={"b": 100, "h": 200},
    color=(0.8, 0.8, 0.8)
)

# DOĞRU: Frame(node_i, node_j, section, rotation_deg, label)
frame = Frame(n1, n2, section, 0, "F1")

# Builder
builder = FrameBuilder()
verts, colors, idxs = builder.build(frame)

# logger.debug(f"Vertex count: {len(verts)//6}")
# logger.debug(f"Index count: {len(idxs)}")
# logger.debug(f"First 12 indices: {idxs[:12] if len(idxs) >= 12 else idxs}")

# Vertex'leri kontrol et
if len(verts) > 0:
    verts_3d = verts.reshape(-1, 6)
    # logger.debug(f"\nİlk 4 vertex (pozisyon):")
    for i in range(min(4, len(verts_3d))):
        # logger.debug(f"  {i}: ({verts_3d[i,0]:.1f}, {verts_3d[i,1]:.1f}, {verts_3d[i,2]:.1f})")
    
    # logger.debug(f"\nİlk 4 vertex (normal):")
    for i in range(min(4, len(verts_3d))):
        # logger.debug(f"  {i}: ({verts_3d[i,3]:.2f}, {verts_3d[i,4]:.2f}, {verts_3d[i,5]:.2f})")