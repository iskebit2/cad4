# tests/bench_label_batch.py
import sys, os, math, time
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import glm
import numpy as np
from OpenGL.GL import *
from app.cad_window import CadWindow
from core.camera import Camera
from tools.font_atlas import FontAtlas
from render.label_batch import LabelBatch


def _make_camera(w, h):
    try:
        cam = Camera()
    except TypeError:
        try:
            cam = Camera(w, h)
        except TypeError:
            cam = Camera(width=w, height=h)
    for name in ("set_aspect", "set_viewport", "resize"):
        fn = getattr(cam, name, None)
        if callable(fn):
            try:
                fn(w, h); break
            except TypeError:
                try:
                    fn(float(w) / float(h)); break
                except Exception:
                    pass
    return cam


class Bench:
    def run(self):
        self.win = CadWindow(1280, 720, "LabelBatch Bench")
        self.win.create()
        self.win.on_resize = self.on_resize
        self._init()
        self.win.run(self.on_render)
        self.win.shutdown()

    def _init(self):
        self.cam = _make_camera(1280, 720)

        ttf = None
        for p in ["C:/Windows/Fonts/consola.ttf",
                  "C:/Windows/Fonts/arial.ttf"]:
            if os.path.isfile(p):
                ttf = p; break

        self.atlas = FontAtlas(ttf_path=ttf, size=32, supersample=2)
        self.batch = LabelBatch(self.atlas)
        self.batch.init_gl()

        self.N = 5000
        # Tüm label'lar için statik veri        rng = np.random.default_rng(42)
        xs = (np.arange(self.N) % 100) * 500.0
        ys = (np.arange(self.N) // 100) * 500.0
        zs = np.zeros(self.N)
        self.positions = np.stack([xs, ys, zs], axis=1).astype(np.float32)
        self.texts = [f"X{i+1}" for i in range(self.N)]
        self.colors = np.tile(np.array([0.9, 0.6, 0.3, 1.0], dtype=np.float32),
                              (self.N, 1))
        self.pixel_sizes = np.full(self.N, 14.0, dtype=np.float32)
        self.anchors = ["center"] * self.N

        self.frame = 0
        self.samples = 0
        self.t_begin = 0.0
        self.t_add = 0.0
        self.t_flush = 0.0

        self.N_WARMUP = 20
        self.N_SAMPLES = 60

        self.orbit_angle = 0.0

    def _update_camera(self, dt):
        self.orbit_angle += dt * 0.8
        a = self.orbit_angle
        x = 2500.0 + math.cos(a) * 25000.0
        y = 2500.0 + math.sin(a) * 25000.0
        z = 12000.0 + math.sin(a * 0.5) * 3000.0
        cam = self.cam
        for attr, val in (("position", glm.vec3(x, y, z)),
                          ("target", glm.vec3(2500.0, 2500.0, 0.0))):
            if hasattr(cam, attr):
                try:
                    setattr(cam, attr, val)
                except Exception:
                    pass

    def _cam_pos_tuple(self):
        cam = self.cam
        for attr in ("position", "eye"):
            if hasattr(cam, attr):
                p = getattr(cam, attr)
                if hasattr(p, "x"):
                    return (p.x, p.y, p.z)
                if isinstance(p, (list, tuple)) and len(p) >= 3:
                    return (p[0], p[1], p[2])
        return (0.0, 0.0, 0.0)

    def on_render(self, dt):
        self.frame += 1
        self._update_camera(dt)

        glClearColor(0.1, 0.1, 0.15, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        try:
            view = self.cam.get_view_matrix()
            proj = self.cam.get_projection_matrix()
        except Exception as e:
            print(f"[HATA] {e}")
            import glfw; glfw.set_window_should_close(self.win.window, True)
            return

        cam_pos = self._cam_pos_tuple()

        t0 = time.perf_counter()
        self.batch.begin(view, proj, cam_pos,
                         screen_h=self.win.height,
                         fov_y_rad=math.radians(45.0))
        t1 = time.perf_counter()

        self.batch.add_many(
            positions=self.positions,
            texts=self.texts,
            colors=self.colors,
            pixel_sizes=self.pixel_sizes,
            anchors=self.anchors,
        )
        t2 = time.perf_counter()

        self.batch.flush()
        glFinish()
        t3 = time.perf_counter()

        if self.frame > self.N_WARMUP:
            self.t_begin += (t1 - t0)
            self.t_add   += (t2 - t1)
            self.t_flush += (t3 - t2)
            self.samples += 1

        if self.samples >= self.N_SAMPLES:
            n = self.samples
            print()
            print("=" * 64)
            print(f"N = {self.N} labels   ({n} frame ortalaması)")
            print("-" * 64)
            print(f"  begin     : {self.t_begin/n*1000:8.2f} ms")
            print(f"  add_many  : {self.t_add/n*1000:8.2f} ms   (NumPy vektörize)")
            print(f"  flush     : {self.t_flush/n*1000:8.2f} ms   (glFinish dahil)")
            total = (self.t_begin + self.t_add + self.t_flush) / n * 1000
            print(f"  TOTAL     : {total:8.2f} ms   (~{1000/total:.0f} FPS)")
            print("=" * 64)
            import glfw; glfw.set_window_should_close(self.win.window, True)

    def on_resize(self, w, h):
        if self.cam:
            fn = getattr(self.cam, "set_aspect", None)
            if callable(fn):
                try: fn(w, h)
                except TypeError:
                    try: fn(float(w) / float(h))
                    except Exception: pass


Bench().run()