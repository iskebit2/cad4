# core/marquee_selector.py

import numpy as np
import glm

from domain.element import Node, Frame, Area, Link


class MarqueeSelector:
    DRAG_THRESHOLD = 5.0

    def __init__(self, engine, selection_manager, selection_policy):
        self.engine = engine
        self.sel = selection_manager
        self.policy = selection_policy

        self.is_active = False
        self.start = None
        self.end = None

        # Kivy widget koordinat sistemi
        self.win_w = 0
        self.win_h = 0

    # ------------------------------------------------------------------
    # MARQUEE STATE
    # ------------------------------------------------------------------

    def start_selection(self, x, y):
        self.start = (float(x), float(y))
        self.end = (float(x), float(y))
        self.is_active = True

    def update_selection(self, x, y):
        if self.is_active:
            self.end = (float(x), float(y))

    def end_selection(self):
        if not self.is_active or self.start is None or self.end is None:
            self._reset()
            return []

        selected = []

        if self._is_drag_valid():
            selected = self._get_elements()

            if selected:
                mode = self.policy.get_marquee_mode()
                self.sel.select_multiple(selected, mode=mode)

        self._reset()
        return selected

    def cancel_selection(self):
        self._reset()

    def get_box_coords(self):
        if self.is_active and self.start and self.end:
            return (*self.start, *self.end)

        return None

    def _reset(self):
        self.is_active = False
        self.start = None
        self.end = None

    # ------------------------------------------------------------------
    # GEOMETRY
    # ------------------------------------------------------------------

    def _is_drag_valid(self):
        if self.start is None or self.end is None:
            return False

        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]

        return (dx * dx + dy * dy) ** 0.5 > self.DRAG_THRESHOLD

    # ------------------------------------------------------------------
    # RECTANGLE
    # ------------------------------------------------------------------

    def _get_rect(self):
        """
        Mouse ve projection aynı Kivy widget koordinat sistemindedir.

        x: soldan sağa
        y: yukarıdan aşağıya

        Bu nedenle GLFW framebuffer scaling kullanılmaz.
        """

        if self.start is None or self.end is None:
            return None

        # Widget boyutunu güncel tut
        self.win_w = float(self.engine.w)
        self.win_h = float(self.engine.h)

        x1, y1 = self.start
        x2, y2 = self.end

        return (
            min(x1, x2),
            min(y1, y2),
            max(x1, x2),
            max(y1, y2),

            # True -> soldan sağa değil, sağdan sola seçim
            x2 < x1,

            self.win_w,
            self.win_h,
        )

    # ------------------------------------------------------------------
    # ELEMENT SELECTION
    # ------------------------------------------------------------------

    def _get_elements(self):

        rect = self._get_rect()

        if rect is None:
            return []

        x1, y1, x2, y2, cross, win_w, win_h = rect

        cam = self.engine.cam

        mvp = (
            cam.get_projection_matrix()
            @ cam.get_view_matrix()
        )

        selected = []

        for element in self.engine.scene.all_elements.values():

            if self._in_rect(
                element,
                (x1, y1),
                (x2, y2),
                mvp,
                win_w,
                win_h,
                cross,
            ):
                selected.append(element)

        return selected

    # ------------------------------------------------------------------
    # ELEMENT TYPE
    # ------------------------------------------------------------------

    def _in_rect(
        self,
        element,
        minp,
        maxp,
        mvp,
        win_w,
        win_h,
        cross,
    ):

        if isinstance(element, Node):
            return self._node_in(
                element,
                *minp,
                *maxp,
                mvp,
                win_w,
                win_h,
            )

        if isinstance(element, (Frame, Link)):
            return self._line_in(
                element.node_i,
                element.node_j,
                *minp,
                *maxp,
                mvp,
                win_w,
                win_h,
                cross,
            )

        if isinstance(element, Area):
            return self._area_in(
                element,
                *minp,
                *maxp,
                mvp,
                win_w,
                win_h,
                cross,
            )

        return False

    # ------------------------------------------------------------------
    # NODE
    # ------------------------------------------------------------------

    def _node_in(
        self,
        node,
        x1,
        y1,
        x2,
        y2,
        mvp,
        win_w,
        win_h,
    ):

        p = self._project(
            node.x,
            node.y,
            node.z,
            mvp,
            win_w,
            win_h,
        )

        if p is None:
            return False

        NODE_PIXEL_RADIUS = 4  # ekranda ~4 piksel tolerans
        return (
            x1 - NODE_PIXEL_RADIUS <= p[0] <= x2 + NODE_PIXEL_RADIUS
            and y1 - NODE_PIXEL_RADIUS <= p[1] <= y2 + NODE_PIXEL_RADIUS
        )

    # ------------------------------------------------------------------
    # FRAME / LINK
    # ------------------------------------------------------------------

    def _line_in(
        self,
        ni,
        nj,
        x1,
        y1,
        x2,
        y2,
        mvp,
        win_w,
        win_h,
        cross,
    ):

        p1 = self._project(
            ni.x,
            ni.y,
            ni.z,
            mvp,
            win_w,
            win_h,
        )

        p2 = self._project(
            nj.x,
            nj.y,
            nj.z,
            mvp,
            win_w,
            win_h,
        )

        if p1 is None or p2 is None:
            return False

        in1 = (
            x1 <= p1[0] <= x2
            and
            y1 <= p1[1] <= y2
        )

        in2 = (
            x1 <= p2[0] <= x2
            and
            y1 <= p2[1] <= y2
        )

        # Window selection:
        # Elemanın tamamı kutunun içinde olmalı.
        if not cross:
            return in1 and in2

        # Crossing selection:
        # Bir ucu içeride veya doğru kutuyu kesiyorsa seç.
        return (
            in1
            or in2
            or self._line_rect(
                p1,
                p2,
                x1,
                y1,
                x2,
                y2,
            )
        )

    # ------------------------------------------------------------------
    # AREA
    # ------------------------------------------------------------------

    def _area_in(
        self,
        area,
        x1,
        y1,
        x2,
        y2,
        mvp,
        win_w,
        win_h,
        cross,
    ):

        points = [
            self._project(
                node.x,
                node.y,
                node.z,
                mvp,
                win_w,
                win_h,
            )
            for node in area.nodes
        ]

        points = [
            p for p in points
            if p is not None
        ]

        if not points:
            return False

        # Window selection:
        # Alanın bütün köşeleri kutu içinde olmalı.
        if not cross:
            return all(
                x1 <= p[0] <= x2
                and
                y1 <= p[1] <= y2
                for p in points
            )

        # Crossing selection:
        # En az bir köşe içerideyse seç.
        if any(
            x1 <= p[0] <= x2
            and
            y1 <= p[1] <= y2
            for p in points
        ):
            return True

        # Ya da alanın bir kenarı kutuyu kesiyorsa seç.
        n = len(points)

        return any(
            self._line_rect(
                points[i],
                points[(i + 1) % n],
                x1,
                y1,
                x2,
                y2,
            )
            for i in range(n)
        )

    # ------------------------------------------------------------------
    # 3D -> 2D
    # ------------------------------------------------------------------

    def _project(
        self,
        x,
        y,
        z,
        mvp,
        win_w,
        win_h,
    ):

        try:
            clip = mvp * glm.vec4(
                x,
                y,
                z,
                1.0,
            )

            if clip.w <= 0:
                return None

            ndc = glm.vec3(clip) / clip.w

            # OpenGL NDC:
            #
            #     y = -1  alt
            #     y = +1  üst
            #
            # Mouse/Kivy:
            #
            #     y = 0    üst
            #     y = h    alt
            #
            # Bu yüzden Y ters çevriliyor.

            px = (ndc.x + 1.0) * win_w / 2.0
            py = (1.0 - ndc.y) * win_h / 2.0

            return px, py

        except Exception:
            return None

    # ------------------------------------------------------------------
    # LINE / RECTANGLE INTERSECTION
    # ------------------------------------------------------------------

    def _line_rect(self, p1, p2, x1, y1, x2, y2):
        """
        Line segment ile axis-aligned rectangle kesişim testi.
        Liang-Barsky algoritması — hızlı ve doğru.
        """
        xa, ya = p1
        xb, yb = p2
        
        dx = xb - xa
        dy = yb - ya
        
        p = [-dx, dx, -dy, dy]
        q = [xa - x1, x2 - xa, ya - y1, y2 - ya]
        
        u1 = 0.0
        u2 = 1.0
        
        for i in range(4):
            if p[i] == 0:
                # Paralel — bu kenarın dışındaysa kesişmez
                if q[i] < 0:
                    return False
            else:
                t = q[i] / p[i]
                if p[i] < 0:
                    if t > u2:
                        return False
                    if t > u1:
                        u1 = t
                else:
                    if t < u1:
                        return False
                    if t < u2:
                        u2 = t
        
        return True
