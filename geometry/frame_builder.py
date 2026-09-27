# geometry/frame_builder.py

import numpy as np
from typing import Tuple
from domain.element import Frame
from geometry.profile_generator import ProfileGenerator
import mapbox_earcut as earcut
import logging

logger = logging.getLogger(__name__)


def normalize(v):
    n = np.linalg.norm(v)
    if n < 1e-10:
        return np.array([0, 0, 1], dtype=np.float32)
    return v / n


class FrameBuilder:

    def __init__(self):
        self.profile_gen = ProfileGenerator()

    def _ensure_closed_cw(self, profile):
        if len(profile) < 3:
            return profile

        area = 0.0

        for i in range(len(profile)):
            x1, y1 = profile[i]
            x2, y2 = profile[(i + 1) % len(profile)]
            area += x1 * y2 - x2 * y1

        if area > 0:
            profile = profile[::-1]

        return profile

    def _prepare_geometry(self, frame):
        """
        Profil ve elemanın 3B yerel koordinat sistemini hazırlar.

        Returns
        -------
        profile : np.ndarray
        start_ring : np.ndarray
        end_ring : np.ndarray
        """

        profile = self.profile_gen.get_profile(
            frame.section.profile_type,
            frame.section.profile_params
        )

        profile = self._ensure_closed_cw(profile)

        # Profil döndürme
        if frame.rotation_deg != 0:

            angle = np.radians(frame.rotation_deg)

            c = np.cos(angle)
            s = np.sin(angle)

            R2 = np.array([
                [c, -s],
                [s,  c]
            ])

            profile = (R2 @ profile.T).T

        start = np.array(
            [
                frame.node_i.x,
                frame.node_i.y,
                frame.node_i.z
            ],
            dtype=np.float32
        )

        end = np.array(
            [
                frame.node_j.x,
                frame.node_j.y,
                frame.node_j.z
            ],
            dtype=np.float32
        )

        axis = end - start
        length = np.linalg.norm(axis)

        if length < 1e-6:
            return (
                profile,
                np.empty((0, 3), dtype=np.float32),
                np.empty((0, 3), dtype=np.float32)
            )

        v1 = axis / length

        world_up = np.array(
            [0, 0, 1],
            dtype=np.float32
        )

        if abs(np.dot(v1, world_up)) > 0.99:

            v2 = np.array(
                [1, 0, 0],
                dtype=np.float32
            )

            v3 = np.array(
                [0, 1, 0],
                dtype=np.float32
            )

        else:

            v3 = world_up.copy()

            v2 = normalize(
                np.cross(v3, v1)
            )

            v3 = normalize(
                np.cross(v1, v2)
            )

        R = np.column_stack(
            (v1, v2, v3)
        )

        N = len(profile)

        local = np.zeros(
            (N, 3),
            dtype=np.float32
        )

        # Profil X → local Y
        # Profil Y → local Z
        local[:, 1] = profile[:, 0]
        local[:, 2] = profile[:, 1]

        start_ring = start + (R @ local.T).T
        end_ring = end + (R @ local.T).T

        return profile, start_ring, end_ring

    def build(
        self,
        frame: Frame
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:

        profile, start_ring, end_ring = self._prepare_geometry(frame)

        if len(start_ring) == 0:
            return (
                np.array([], dtype=np.float32),
                np.array([], dtype=np.float32),
                np.array([], dtype=np.uint32)
            )

        N = len(profile)

        verts = []
        idxs = []

        # ---------------------------------------------------------
        # SIDE FACES
        # ---------------------------------------------------------

        for i in range(N):

            i_next = (i + 1) % N

            v0 = start_ring[i]
            v1 = start_ring[i_next]
            v2 = end_ring[i_next]
            v3 = end_ring[i]

            normal = normalize(
                np.cross(
                    v1 - v0,
                    v2 - v0
                )
            )

            base = len(verts) // 6

            for p in [v0, v1, v2, v3]:

                verts.extend([
                    p[0], p[1], p[2],
                    normal[0], normal[1], normal[2]
                ])

            idxs.extend([
                base,
                base + 1,
                base + 2,

                base,
                base + 2,
                base + 3
            ])

        # ---------------------------------------------------------
        # END CAPS
        # ---------------------------------------------------------

        if N >= 3:

            profile_2d = profile[:, :2]

            rings = np.array(
                [N],
                dtype=np.uint32
            )

            tri = earcut.triangulate_float32(
                profile_2d,
                rings
            ).tolist()

            # -----------------------------------------------------
            # START CAP
            # -----------------------------------------------------

            # Side face loopunun kullandığı v1 artık güvenilir
            # bir normal kaynağı olmadığından ekseni tekrar alıyoruz.
            axis = end_ring[0] - start_ring[0]
            axis = normalize(axis)

            n_start = -axis

            base = len(verts) // 6

            for p in start_ring:

                verts.extend([
                    p[0], p[1], p[2],
                    n_start[0],
                    n_start[1],
                    n_start[2]
                ])

            for i in range(0, len(tri), 3):

                idxs.extend([
                    base + tri[i],
                    base + tri[i + 2],
                    base + tri[i + 1]
                ])

            # -----------------------------------------------------
            # END CAP
            # -----------------------------------------------------

            n_end = axis

            base = len(verts) // 6

            for p in end_ring:

                verts.extend([
                    p[0], p[1], p[2],
                    n_end[0],
                    n_end[1],
                    n_end[2]
                ])

            for i in range(0, len(tri), 3):

                idxs.extend([
                    base + tri[i],
                    base + tri[i + 1],
                    base + tri[i + 2]
                ])

        # ---------------------------------------------------------
        # COLORS
        # ---------------------------------------------------------

        color = np.array(
            frame.section.color,
            dtype=np.float32
        )

        if frame.is_selected:

            color = np.array(
                [0.2, 1.0, 0.2],
                dtype=np.float32
            )

        colors = np.tile(
            color,
            (len(verts) // 6, 1)
        )

        logger.debug(
            f"FrameBuilder: "
            f"{len(verts) // 6} vertices, "
            f"{len(idxs)} triangle indices"
        )

        return (
            np.array(verts, dtype=np.float32),
            colors,
            np.array(idxs, dtype=np.uint32)
        )

    def build_lines(self, frame: Frame) -> np.ndarray:
        """
        Frame geometrisinin gerçek kenarlarını oluşturur.

        Burada triangle indexleri KULLANILMAZ.

        Çizilen kenarlar:
            - Profilin başlangıç çevresi
            - Profilin bitiş çevresi
            - Profil köşeleri boyunca boyuna kenarlar
        """

        profile, start_ring, end_ring = self._prepare_geometry(frame)

        if len(start_ring) == 0:
            return np.array([], dtype=np.uint32)

        N = len(profile)

        line_indices = []

        # ---------------------------------------------------------
        # SIDE EDGES
        #
        # Her profil köşesinden diğer uca bir boyuna çizgi.
        # ---------------------------------------------------------

        side_base = 0

        for i in range(N):

            line_indices.extend([
                side_base + 4 * i,
                side_base + 4 * i + 3
            ])

        # ---------------------------------------------------------
        # SIDE PROFILE EDGES
        #
        # Her yan yüzün profil doğrultusundaki iki kenarı.
        #
        # Dikkat:
        # Her side face için vertexler ayrı üretildiğinden
        # burada i'inci face'in kendi dört vertexini kullanıyoruz.
        # ---------------------------------------------------------

        for i in range(N):

            base = 4 * i

            line_indices.extend([
                base,
                base + 1,

                base + 1,
                base + 2,

                base + 2,
                base + 3,

                base + 3,
                base
            ])

        # ---------------------------------------------------------
        # START CAP PROFILE
        #
        # build() içerisinde start cap, side vertexlerinden sonra
        # geliyor.
        #
        # Side vertex sayısı = 4 * N
        # ---------------------------------------------------------

        start_cap_base = 4 * N

        for i in range(N):

            j = (i + 1) % N

            line_indices.extend([
                start_cap_base + i,
                start_cap_base + j
            ])

        # ---------------------------------------------------------
        # END CAP PROFILE
        # ---------------------------------------------------------

        end_cap_base = start_cap_base + N

        for i in range(N):

            j = (i + 1) % N

            line_indices.extend([
                end_cap_base + i,
                end_cap_base + j
            ])

        return np.array(
            line_indices,
            dtype=np.uint32
        )

    def build_simple_lines(self, frame: Frame) -> np.ndarray:
        """
        Frame'in sadece merkez eksenini çizen basit çizgi.
        Returns: vertices array [x,y,z, nx,ny,nz] (2 nokta = 1 çizgi)
        """
        start = np.array([frame.node_i.x, frame.node_i.y, frame.node_i.z], dtype=np.float32)
        end = np.array([frame.node_j.x, frame.node_j.y, frame.node_j.z], dtype=np.float32)
        
        axis = end - start
        length = np.linalg.norm(axis)
        if length < 1e-6:
            return np.array([], dtype=np.float32)
        
        d = axis / length
        
        # 2 nokta, her biri: pos3 + normal3 = 6 float
        verts = np.array([
            start[0], start[1], start[2], d[0], d[1], d[2],
            end[0],   end[1],   end[2],   d[0], d[1], d[2]
        ], dtype=np.float32)
        
        return verts