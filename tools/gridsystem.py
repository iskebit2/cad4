# tools/gridsystem.py
import ctypes

from pyglm import glm

from data.enums import GridPlane
from domain.definition import GridPlaneDef

glm.silence(2)
import numpy as np
from OpenGL.GL import (
    GL_ARRAY_BUFFER,
    GL_FALSE,
    GL_FLOAT,
    GL_LINES,
    GL_STATIC_DRAW,
    glBindBuffer,
    glBindVertexArray,
    glBufferData,
    glDeleteBuffers,
    glDeleteVertexArrays,
    glDrawArrays,
    glEnableVertexAttribArray,
    glGenBuffers,
    glGenVertexArrays,
    glIsBuffer,
    glIsVertexArray,
    glUniform1f,
    glUniformMatrix4fv,
    glVertexAttribPointer,
)

from logging_config import CadLogger

logger = CadLogger.get(__name__)

COLOR_MAJOR  = (0.55, 0.55, 0.60)
COLOR_MINOR  = (0.25, 0.27, 0.32)
COLOR_X_AXIS = (0.70, 0.25, 0.25)
COLOR_Y_AXIS = (0.25, 0.70, 0.25)
COLOR_Z_AXIS = (0.25, 0.45, 0.70)


class GridSystem:
    GRID_ALPHA = 0.55
    VERTEX_FLOATS = 6
    VERTEX_STRIDE = VERTEX_FLOATS * 4

    def __init__(self, shader_program):
        self.shader = shader_program

        # Düzlem görünürlük durumları
        self.planes = {
            GridPlane.XY: {"visible": True},
            GridPlane.XZ: {"visible": False},
            GridPlane.YZ: {"visible": False},
        }
        # Kullanıcı tanımlı eğik plane'ler
        self.user_planes: list[GridPlaneDef] = []
        # Hangisi "aktif work plane"?
        self.active_user_plane: str | None = None

        # Tekla / ETABS tarzı aks koordinat listeleri (mm veya proje biriminde)
        self.x_coords = [0.0, 4000.0, 8000.0]
        self.y_coords = [0.0, 5000.0, 10000.0]
        self.z_coords = [0.0, 4000.0]

        self.origin = glm.vec3(0.0, 0.0, 0.0)
        self._gpu = {name: {"vao": None, "vbo": None, "count": 0} for name in self.planes}

    @property
    def origin_x(self) -> float:
        return float(self.origin.x)

    @property
    def origin_y(self) -> float:
        return float(self.origin.y)

    @property
    def origin_z(self) -> float:
        return float(self.origin.z)

    @property
    def planes_visibility(self) -> dict[str, bool]:
        return {p.name: bool(d.get("visible", False)) for p, d in self.planes.items()}
    
    def set_origin(self, x, y, z):
        self.origin = glm.vec3(float(x), float(y), float(z))
        self.rebuild_all()

    def set_coords(self, x_list, y_list, z_list):
        self.x_coords = sorted(set(float(v) for v in x_list)) if x_list else []
        self.y_coords = sorted(set(float(v) for v in y_list)) if y_list else []
        self.z_coords = sorted(set(float(v) for v in z_list)) if z_list else []
        self.rebuild_all()

    def set_plane(self, plane: GridPlane, visible=None):
        if plane not in self.planes:
            return
        if visible is not None:
            self.planes[plane]["visible"] = bool(visible)
        self._rebuild_plane(plane)

    def _rebuild_plane(self, plane: GridPlane):
        if plane not in self.planes:
            return
        p = self.planes[plane]
        if not p["visible"]:
            self._clear_plane(plane)
            return

        ox, oy, oz = self.origin.x, self.origin.y, self.origin.z
        xs = [ox + x for x in self.x_coords]
        ys = [oy + y for y in self.y_coords]
        zs = [oz + z for z in self.z_coords]

        if len(xs) < 2 or len(ys) < 2 or len(zs) < 2:
            self._clear_plane(plane)
            return

        vertices = []

        if plane == GridPlane.XY:
            # Sadece z=0 kotunda (origin z ile birlikte zs[0])
            z = zs[0]
            min_x, max_x = xs[0], xs[-1]
            min_y, max_y = ys[0], ys[-1]

            # X eksenine paralel çizgiler (her y için bir çizgi, X boyunca)
            for i, y in enumerate(ys):
                color = COLOR_X_AXIS if i == 0 else COLOR_MAJOR
                vertices.extend([min_x, y, z, *color])
                vertices.extend([max_x, y, z, *color])

            # Y eksenine paralel çizgiler (her x için bir çizgi, Y boyunca)
            for i, x in enumerate(xs):
                color = COLOR_Y_AXIS if i == 0 else COLOR_MAJOR
                vertices.extend([x, min_y, z, *color])
                vertices.extend([x, max_y, z, *color])

        elif plane == GridPlane.XZ:
            # Sadece y=0 düzleminde
            y = ys[0]
            min_x, max_x = xs[0], xs[-1]
            min_z, max_z = zs[0], zs[-1]

            # X eksenine paralel (her z için)
            for i, z in enumerate(zs):
                color = COLOR_X_AXIS if i == 0 else COLOR_MAJOR
                vertices.extend([min_x, y, z, *color])
                vertices.extend([max_x, y, z, *color])

            # Z eksenine paralel (her x için)
            for i, x in enumerate(xs):
                color = COLOR_Z_AXIS if i == 0 else COLOR_MAJOR
                vertices.extend([x, y, min_z, *color])
                vertices.extend([x, y, max_z, *color])

        elif plane == GridPlane.YZ:
            # Sadece x=0 düzleminde
            x = xs[0]
            min_y, max_y = ys[0], ys[-1]
            min_z, max_z = zs[0], zs[-1]

            # Y eksenine paralel (her z için)
            for i, z in enumerate(zs):
                color = COLOR_Y_AXIS if i == 0 else COLOR_MAJOR
                vertices.extend([x, min_y, z, *color])
                vertices.extend([x, max_y, z, *color])

            # Z eksenine paralel (her y için)
            for i, y in enumerate(ys):
                color = COLOR_Z_AXIS if i == 0 else COLOR_MAJOR
                vertices.extend([x, y, min_z, *color])
                vertices.extend([x, y, max_z, *color])

        self._upload_plane(plane, vertices)

    def _upload_plane(self, plane: GridPlane, vertices: list):
        gpu = self._gpu[plane]
        self._delete_plane_gpu(plane)

        count = len(vertices) // self.VERTEX_FLOATS
        if count == 0:
            return

        data = np.asarray(vertices, dtype=np.float32)
        vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_STATIC_DRAW)

        stride = self.VERTEX_STRIDE
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(12))

        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)

        gpu["vao"] = vao
        gpu["vbo"] = vbo
        gpu["count"] = count

    def _delete_plane_gpu(self, plane: GridPlane):
        gpu = self._gpu[plane]
        try:
            if gpu["vao"] and glIsVertexArray(gpu["vao"]):
                glDeleteVertexArrays(1, [int(gpu["vao"])])
        except Exception:
            pass
        try:
            if gpu["vbo"] and glIsBuffer(gpu["vbo"]):
                glDeleteBuffers(1, [int(gpu["vbo"])])
        except Exception:
            pass
        gpu["vao"] = None
        gpu["vbo"] = None
        gpu["count"] = 0

    def _clear_plane(self, plane: GridPlane):
        self._delete_plane_gpu(plane)

    def draw(self, mvp_matrix):
        if not self.shader:
            return
        self.shader.use()

        mvp_loc = self.shader.get_loc("mvp")
        if mvp_loc != -1:
            glUniformMatrix4fv(mvp_loc, 1, GL_FALSE, glm.value_ptr(mvp_matrix))

        alpha_loc = self.shader.get_loc("alpha")
        if alpha_loc != -1:
            glUniform1f(alpha_loc, self.GRID_ALPHA)

        for plane, gpu in self._gpu.items():
            if not gpu["vao"] or gpu["count"] == 0:
                continue
            glBindVertexArray(gpu["vao"])
            glDrawArrays(GL_LINES, 0, gpu["count"])
        glBindVertexArray(0)

    def cleanup(self):
        for plane in self._gpu:
            self._delete_plane_gpu(plane)
        self.shader = None

    def info(self):
        return {
            "x_coords": self.x_coords,
            "y_coords": self.y_coords,
            "z_coords": self.z_coords,
        }

    def get_label_anchors(self):
        """
        Her görünür plane için label anchor noktaları döner.
        Returns: list[dict] -> {'pos': (x,y,z), 'text': 'X1', 'axis': 'X', 'plane': GridPlane}
        """
        ox, oy, oz = self.origin.x, self.origin.y, self.origin.z
        xs = [ox + x for x in self.x_coords]
        ys = [oy + y for y in self.y_coords]
        zs = [oz + z for z in self.z_coords]

        if not xs or not ys or not zs:
            return []

        labels = []

        for plane, p in self.planes.items():
            if not p["visible"]:
                continue

            if plane == GridPlane.XY:
                y_edge = ys[0]
                z0 = zs[0]
                for i, x in enumerate(xs):
                    labels.append({
                        "pos": (x, y_edge, z0),
                        "text": f"X{i+1}",
                        "axis": "X",
                        "plane": plane,
                    })
                x_edge = xs[0]
                for i, y in enumerate(ys):
                    labels.append({
                        "pos": (x_edge, y, z0),
                        "text": f"Y{i+1}",
                        "axis": "Y",
                        "plane": plane,
                    })

            elif plane == GridPlane.XZ:
                y_edge = ys[0]
                z0 = zs[0]
                for i, x in enumerate(xs):
                    labels.append({
                        "pos": (x, y_edge, z0),
                        "text": f"X{i+1}",
                        "axis": "X",
                        "plane": plane,
                    })
                x_edge = xs[0]
                for i, z in enumerate(zs):
                    labels.append({
                        "pos": (x_edge, y_edge, z),
                        "text": f"Z{i+1}",
                        "axis": "Z",
                        "plane": plane,
                    })

            elif plane == GridPlane.YZ:
                x_edge = xs[0]
                z0 = zs[0]
                for i, y in enumerate(ys):
                    labels.append({
                        "pos": (x_edge, y, z0),
                        "text": f"Y{i+1}",
                        "axis": "Y",
                        "plane": plane,
                    })
                for i, z in enumerate(zs):
                    labels.append({
                        "pos": (x_edge, ys[0], z),
                        "text": f"Z{i+1}",
                        "axis": "Z",
                        "plane": plane,
                    })

        return labels
    
    def get_bounds(self):
        """Gridin min/max sınırlarını ve merkezini hesaplar."""
        if not self.x_coords or not self.y_coords or not self.z_coords:
            return glm.vec3(0,0,0), 1000.0
        
        min_x, max_x = self.x_coords[0], self.x_coords[-1]
        min_y, max_y = self.y_coords[0], self.y_coords[-1]
        min_z, max_z = self.z_coords[0], self.z_coords[-1]
        
        center = glm.vec3(
            self.origin.x + (min_x + max_x) * 0.5,
            self.origin.y + (min_y + max_y) * 0.5,
            self.origin.z + (min_z + max_z) * 0.5
        )
        
        size = float(max(max_x - min_x, max_y - min_y, max_z - min_z))
        if size < 1.0:
            size = 1000.0
            
        return center, size

    # ------------------------------------------------------------------
    def add_user_plane(self, pdef: GridPlaneDef):
        # Aynı isimde varsa üzerine yaz
        self.user_planes = [p for p in self.user_planes
                            if p.name != pdef.name]
        self.user_planes.append(pdef)
        self.rebuild_user_plane(pdef)

    def set_user_planes(self, planes: list[GridPlaneDef]):
        """Replace runtime work planes with the project's persisted definitions."""
        self.user_planes = list(planes)
        names = {plane.name for plane in self.user_planes}
        if self.active_user_plane not in names:
            self.active_user_plane = None
        self.rebuild_all()

    def remove_user_plane(self, name: str):
        pdef = self.get_user_plane(name)
        if pdef is None:
            return
        self.user_planes = [p for p in self.user_planes if p.name != name]
        key = f"user::{name}"
        self._delete_gpu_by_key(key)
        if self.active_user_plane == name:
            self.active_user_plane = None

    def get_user_plane(self, name: str) -> GridPlaneDef | None:
        for p in self.user_planes:
            if p.name == name:
                return p
        return None

    def set_active_user_plane(self, name: str | None):
        self.active_user_plane = name

    def rebuild_user_plane(self, pdef: GridPlaneDef):
        self._rebuild_user_plane(pdef)

    def rebuild_all(self):
        # Global plane'ler
        for plane in self.planes:
            if self.planes[plane]["visible"]:
                self._rebuild_plane(plane)
            else:
                self._clear_plane(plane)
        # User plane'ler
        for pdef in self.user_planes:
            self._rebuild_user_plane(pdef)

    # ------------------------------------------------------------------
    def _rebuild_user_plane(self, pdef: GridPlaneDef):
        key = f"user::{pdef.name}"
        if not pdef.visible:
            self._delete_gpu_by_key(key)
            return

        origin, u, v, n = pdef.get_uv_frame()

        su = pdef.spacing_u
        sv = pdef.spacing_v
        cu = pdef.count_u
        cv = pdef.count_v

        color = pdef.color
        axis_u_color = (0.70, 0.25, 0.25)
        axis_v_color = (0.25, 0.70, 0.25)

        iu_min, iu_max = -cu, cu
        iv_min, iv_max = -cv, cv

        verts = []

        # U yönünde çizgiler (V sabit)
        for j in range(iv_min, iv_max + 1):
            p_a = origin + u * (iu_min * su) + v * (j * sv)
            p_b = origin + u * (iu_max * su) + v * (j * sv)
            c = axis_u_color if j == 0 else color
            verts.extend([p_a.x, p_a.y, p_a.z, *c])
            verts.extend([p_b.x, p_b.y, p_b.z, *c])

        # V yönünde çizgiler (U sabit)
        for i in range(iu_min, iu_max + 1):
            p_a = origin + u * (i * su) + v * (iv_min * sv)
            p_b = origin + u * (i * su) + v * (iv_max * sv)
            c = axis_v_color if i == 0 else color
            verts.extend([p_a.x, p_a.y, p_a.z, *c])
            verts.extend([p_b.x, p_b.y, p_b.z, *c])

        self._upload_plane_by_key(key, verts)

    def _upload_plane_by_key(self, key: str, vertices: list):
        self._delete_gpu_by_key(key)
        count = len(vertices) // self.VERTEX_FLOATS
        if count == 0:
            return
        data = np.asarray(vertices, dtype=np.float32)
        vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        glBindVertexArray(vao)
        glBindBuffer(GL_ARRAY_BUFFER, vbo)
        glBufferData(GL_ARRAY_BUFFER, data.nbytes, data, GL_STATIC_DRAW)
        stride = self.VERTEX_STRIDE
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride,
                              ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride,
                              ctypes.c_void_p(12))
        glBindBuffer(GL_ARRAY_BUFFER, 0)
        glBindVertexArray(0)
        self._gpu[key] = {"vao": vao, "vbo": vbo, "count": count}

    def _delete_gpu_by_key(self, key: str):
        gpu = self._gpu.pop(key, None)
        if not gpu:
            return
        try:
            if gpu.get("vao") and glIsVertexArray(gpu["vao"]):
                glDeleteVertexArrays(1, [int(gpu["vao"])])
        except Exception:
            pass
        try:
            if gpu.get("vbo") and glIsBuffer(gpu["vbo"]):
                glDeleteBuffers(1, [int(gpu["vbo"])])
        except Exception:
            pass