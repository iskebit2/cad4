# ui/widgets/polygon_2d_view.py

import math
import imgui


# ----------------------------------------------------------------------
#  Yardımcı: 2D vektör işlemleri (küçük ve bağımlılıksız)
# ----------------------------------------------------------------------
def _add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _mul(a, s):
    return (a[0] * s, a[1] * s)


def _len(a):
    return math.hypot(a[0], a[1])


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _rot(v, deg):
    rad = math.radians(deg)
    cs, sn = math.cos(rad), math.sin(rad)
    return (v[0] * cs - v[1] * sn, v[0] * sn + v[1] * cs)


# ----------------------------------------------------------------------
#  Polygon2DView
# ----------------------------------------------------------------------
class Polygon2DView:
    """
    2D canvas görünümü.

    Sorumluluklar:
      - Model uzayı (poly düzlemi) → ekran dönüşümü
      - View döndürme (orthogonal, sadece görüntü)
      - Pan / zoom (imleç merkezli)
      - Hit-test ve seçim (tek / çoklu / rubber-band)
      - Grid, eksen, HUD çizimi

    Model verisine asla yazmaz; sadece okur. Döndürme view_rotation ile
    yapılır ve load_polygon sırasında KORUNUR.
    """

    # ----- Renkler (ABGR) -----
    COL_BG          = 0xFF1A1A1A
    COL_GRID        = 0xFF2A2A2A
    COL_GRID_MAJOR  = 0xFF3A3A3A
    COL_AXIS_X      = 0xFF4040C0
    COL_AXIS_Y      = 0xFF40C040
    COL_POLY_EDGE   = 0xFFBBBBBB
    COL_POLY_FILL   = 0x30A0A0A0
    COL_PT          = 0xFFE0E0E0
    COL_PT_HOVER    = 0xFFFFD060
    COL_PT_SEL      = 0xFF60D0FF
    COL_RUBBER      = 0x60FFD060

    # ----- Sabitler -----
    HIT_RADIUS_PX   = 9.0
    MIN_ZOOM        = 0.02
    MAX_ZOOM        = 80.0
    ZOOM_STEP       = 1.15

    def __init__(self):
        # Model
        self.plane = None
        self._points = []           # [(fid, (x, y)), ...] sıralı
        self._bounds = None         # (minx, miny, maxx, maxy)

        # View transform
        self.zoom = 1.0
        self.pan = (0.0, 0.0)       # world uzayında merkez ofseti
        self.view_rotation = 0.0    # derece, sadece görüntü

        # Görsel ayarlar
        self.show_grid = True
        self.show_axes = True

        # Etkileşim durumu
        self.selected_fids = set()
        self.hover_fid = None
        self.clicked_fid = None     # panel tarafından tüketilir
        self.clicked_empty = False  # panel tarafından tüketilir

        # Drag (rubber-band / pan) durumu
        self._panning = False
        self._pan_anchor = None     # ekran px
        self._rubber = False
        self._rubber_start = None   # ekran px
        self._rubber_end = None     # ekran px
        self._first_load = True

    # ------------------------------------------------------------------
    #  Yükleme
    # ------------------------------------------------------------------
    def load_polygon(self, poly, scene):
        """
        Yeni polygon yükler. view_rotation / zoom KORUNUR.
        Sadece model içeriği ve bounds yenilenir.
        """
        self.plane = self._build_plane(poly, scene)
        self._points = list(self._iter_points())
        self._bounds = self._compute_bounds()

        # İlk yüklemede içeriği sığdır
        if self._first_load and self._bounds:
            self.fit_to_content()
            self._first_load = False

    # ------------------------------------------------------------------
    #  Veri modelinize bağlanacak tek yerler
    # ------------------------------------------------------------------
    def _build_plane(self, poly, scene):
        """
        Poly'den 2D düzlem nesnesi üret.
        Varsayılan: poly üzerinde zaten bir 'plane' varsa onu döndür.
        Kendi veri modelinize göre düzenleyin.
        """
        return getattr(poly, "plane", None)

    def _iter_points(self):
        """
        Plane içindeki (frame_id, (x, y)) çiftlerini sırayla döndür.
        Sıra, polygon kenar çizgisi için kullanılır.
        """
        if not self.plane:
            return
        frames = getattr(self.plane, "frames", None)
        if not frames:
            return
        for item in frames:
            fid = getattr(item, "id", getattr(item, "fid", None))
            if fid is None:
                continue
            x = getattr(item, "x", None)
            y = getattr(item, "y", None)
            if x is None or y is None:
                # alternatif: item.pos / item.p
                p = getattr(item, "pos", getattr(item, "p", None))
                if p is not None and len(p) >= 2:
                    x, y = p[0], p[1]
            if x is None or y is None:
                continue
            yield fid, (float(x), float(y))

    # ------------------------------------------------------------------
    #  Bounds / fit
    # ------------------------------------------------------------------
    def _compute_bounds(self):
        if not self._points:
            return None
        xs = [p[0] for _, p in self._points]
        ys = [p[1] for _, p in self._points]
        return (min(xs), min(ys), max(xs), max(ys))

    def fit_to_content(self, view_w=800.0, view_h=500.0, margin=0.85):
        """İçeriği verilen view boyutuna sığdır."""
        if not self._bounds:
            return
        minx, miny, maxx, maxy = self._bounds
        w = max(1e-6, maxx - minx)
        h = max(1e-6, maxy - miny)
        self.zoom = max(self.MIN_ZOOM,
                        min(margin * min(view_w / w, view_h / h), self.MAX_ZOOM))
        cx = (minx + maxx) * 0.5
        cy = (miny + maxy) * 0.5
        self.pan = (-cx, -cy)   # merkezi dünyaya taşı

    # ------------------------------------------------------------------
    #  View API (panel tarafından çağrılır)
    # ------------------------------------------------------------------
    def rotate_view(self, delta_deg, absolute=False):
        """Sadece görüntüyü döndürür. Model verisi değişmez."""
        if absolute:
            self.view_rotation = float(delta_deg)
        else:
            self.view_rotation += float(delta_deg)
        # 90° katlarına oturt
        self.view_rotation = round(self.view_rotation / 90.0) * 90.0
        self.view_rotation %= 360.0

    def zoom_at_center(self, factor):
        self.zoom = max(self.MIN_ZOOM,
                        min(self.zoom * factor, self.MAX_ZOOM))

    def reset_view(self):
        self.view_rotation = 0.0
        self.pan = (0.0, 0.0)
        self.fit_to_content()

    # ------------------------------------------------------------------
    #  Dönüşümler
    # ------------------------------------------------------------------
    def _world_to_screen_factory(self, cx, cy, cw, ch):
        """Canvas köşesi (cx,cy) ve boyutu (cw,ch) için dönüşüm kapanışı."""
        rot = self.view_rotation
        zoom = self.zoom
        pan = self.pan
        half_w = cw * 0.5
        half_h = ch * 0.5

        def to_screen(x, y):
            xr, yr = _rot((x, y), rot)
            sx = cx + half_w + (xr + pan[0]) * zoom
            sy = cy + half_h - (yr + pan[1]) * zoom
            return sx, sy

        def from_screen(sx, sy):
            dx = (sx - cx - half_w) / zoom - pan[0]
            dy = -(sy - cy - half_h) / zoom - pan[1]
            wx, wy = _rot((dx, dy), -rot)
            return wx, wy

        return to_screen, from_screen

    # ------------------------------------------------------------------
    #  Ana çizim
    # ------------------------------------------------------------------
    def draw(self, imgui_ctx, draw_list, canvas_pos, canvas_size):
        cx, cy = canvas_pos
        cw, ch = canvas_size
        if cw <= 1 or ch <= 1:
            return

        # Arka plan
        draw_list.add_rect_filled(cx, cy, cx + cw, cy + ch, self.COL_BG)

        to_screen, from_screen = self._world_to_screen_factory(cx, cy, cw, ch)

        # Grid + eksenler
        if self.show_grid:
            self._draw_grid(draw_list, cx, cy, cw, ch, to_screen, from_screen)
        if self.show_axes:
            self._draw_axes(draw_list, cx, cy, cw, ch, to_screen)

        # Polygon + noktalar
        self._draw_polygon(draw_list, to_screen)

        # Rubber-band
        if self._rubber and self._rubber_start and self._rubber_end:
            x0, y0 = self._rubber_start
            x1, y1 = self._rubber_end
            draw_list.add_rect_filled(min(x0, x1), min(y0, y1),
                                      max(x0, x1), max(y0, y1), self.COL_RUBBER)
            draw_list.add_rect(min(x0, x1), min(y0, y1),
                               max(x0, x1), max(y0, y1), 0xFFFFD060)

        # Input en sonda (hover vs. güncel dönüşümle)
        self._handle_input(imgui_ctx, cx, cy, cw, ch, to_screen, from_screen)

    # ------------------------------------------------------------------
    def _draw_grid(self, dl, cx, cy, cw, ch, to_screen, from_screen):
        # Dünya uzayında grid adımı; ekranda ~40px'e denk gelecek şekilde seç
        target_px = 40.0
        world_step = target_px / max(self.zoom, 1e-6)
        # Güzel sayıya yuvarla: 1, 2, 5 * 10^n
        exp = math.floor(math.log10(max(world_step, 1e-9)))
        base = 10 ** exp
        for m in (1, 2, 5, 10):
            if base * m >= world_step:
                world_step = base * m
                break

        # Görünür dünya aralığı (ekran köşelerinden)
        corners = [
            from_screen(cx, cy),
            from_screen(cx + cw, cy),
            from_screen(cx + cw, cy + ch),
            from_screen(cx, cy + ch),
        ]
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        minx, maxx = min(xs), max(xs)
        miny, maxy = min(ys), max(ys)

        # Dikey çizgiler (x = sabit)
        x = math.floor(minx / world_step) * world_step
        while x <= maxx:
            sx0, sy0 = to_screen(x, miny)
            sx1, sy1 = to_screen(x, maxy)
            major = abs((x / (world_step * 5)) - round(x / (world_step * 5))) < 1e-6
            dl.add_line(sx0, sy0, sx1, sy1,
                        self.COL_GRID_MAJOR if major else self.COL_GRID)
            x += world_step

        # Yatay çizgiler (y = sabit)
        y = math.floor(miny / world_step) * world_step
        while y <= maxy:
            sx0, sy0 = to_screen(minx, y)
            sx1, sy1 = to_screen(maxx, y)
            major = abs((y / (world_step * 5)) - round(y / (world_step * 5))) < 1e-6
            dl.add_line(sx0, sy0, sx1, sy1,
                        self.COL_GRID_MAJOR if major else self.COL_GRID)
            y += world_step

    # ------------------------------------------------------------------
    def _draw_axes(self, dl, cx, cy, cw, ch, to_screen):
        # Dünya orijini
        ox, oy = to_screen(0.0, 0.0)
        # X ekseni (dünya uzayında yatay)
        x0, y0 = to_screen(-1e6, 0.0)
        x1, y1 = to_screen(1e6, 0.0)
        dl.add_line(x0, y0, x1, y1, self.COL_AXIS_X, 1.0)
        # Y ekseni
        x0, y0 = to_screen(0.0, -1e6)
        x1, y1 = to_screen(0.0, 1e6)
        dl.add_line(x0, y0, x1, y1, self.COL_AXIS_Y, 1.0)
        # Orijin noktası
        dl.add_circle_filled(ox, oy, 3.0, 0xFFFFFFFF)

    # ------------------------------------------------------------------
    def _draw_polygon(self, dl, to_screen):
        if not self._points:
            return

        # Ekran koordinatları
        screen_pts = [(fid, to_screen(p[0], p[1])) for fid, p in self._points]

        # Kapalı çokgen dolgusu (basit fan; dışbükey varsayımı)
        if len(screen_pts) >= 3:
            # Dolgu: triangülasyon yerine hafif bir "convex fan"
            # (dışbükey olmayan poligonlarda hafif yanlış görünebilir ama
            #  hızlı ve bağımlılıksız. İstenirse ear-clipping eklenebilir.)
            p0 = screen_pts[0][1]
            for i in range(1, len(screen_pts) - 1):
                p1 = screen_pts[i][1]
                p2 = screen_pts[i + 1][1]
                dl.add_triangle_filled(p0[0], p0[1],
                                       p1[0], p1[1],
                                       p2[0], p2[1], self.COL_POLY_FILL)

        # Kenar çizgileri
        n = len(screen_pts)
        for i in range(n):
            a = screen_pts[i][1]
            b = screen_pts[(i + 1) % n][1]
            dl.add_line(a[0], a[1], b[0], b[1], self.COL_POLY_EDGE, 1.5)

        # Noktalar
        for fid, (sx, sy) in screen_pts:
            if fid in self.selected_fids:
                col = self.COL_PT_SEL
                r = 6.0
            elif fid == self.hover_fid:
                col = self.COL_PT_HOVER
                r = 5.5
            else:
                col = self.COL_PT
                r = 4.5
            dl.add_circle_filled(sx, sy, r, col)
            dl.add_circle(sx, sy, r + 1.0, 0xFF000000, 1.0)

    # ------------------------------------------------------------------
    #  Input handling
    # ------------------------------------------------------------------
    def _handle_input(self, imgui_ctx, cx, cy, cw, ch, to_screen, from_screen):
        io = imgui_ctx.get_io()
        mx, my = io.mouse_pos
        over = cx <= mx <= cx + cw and cy <= my <= cy + ch

        # Her karede tüketim bayraklarını sıfırla
        self.clicked_fid = None
        self.clicked_empty = False

        if not over:
            self.hover_fid = None
            self._panning = False
            self._pan_anchor = None
            self._rubber = False
            return

        # Hover
        self.hover_fid = self._hit_test(mx, my, to_screen)

        # --- Zoom (tekerlek, imleç merkezli) ---
        if io.mouse_wheel != 0:
            self._apply_zoom(io.mouse_wheel, mx, my, cx, cy, cw, ch)

        # --- Pan başlatma ---
        space_down = self._is_space_down(imgui_ctx)
        start_pan = (
            imgui_ctx.is_mouse_clicked(2)          # orta tuş
            or (space_down and imgui_ctx.is_mouse_clicked(0))
            or imgui_ctx.is_mouse_clicked(1)       # sağ tuş
        )
        if start_pan and not self._rubber:
            self._panning = True
            self._pan_anchor = (mx, my)

        if self._panning:
            if imgui_ctx.is_mouse_down(2) or imgui_ctx.is_mouse_down(1) or imgui_ctx.is_mouse_down(0):
                if self._pan_anchor:
                    dx = (mx - self._pan_anchor[0]) / self.zoom
                    dy = (my - self._pan_anchor[1]) / self.zoom
                    # pan dünya uzayında; ekran dx'i ters işaretle
                    self.pan = (self.pan[0] + dx, self.pan[1] - dy)
                    self._pan_anchor = (mx, my)
            else:
                self._panning = False
                self._pan_anchor = None

        # --- Sol tık: seçim veya rubber-band başlat ---
        if imgui_ctx.is_mouse_clicked(0) and not self._panning and not space_down:
            fid = self._hit_test(mx, my, to_screen)
            if fid is not None:
                # Frame üzerine tık → seçim
                self.clicked_fid = fid
            else:
                # Boşluğa tık → rubber-band başlat
                self._rubber = True
                self._rubber_start = (mx, my)
                self._rubber_end = (mx, my)

        # Rubber-band güncelle
        if self._rubber:
            self._rubber_end = (mx, my)
            if imgui_ctx.is_mouse_released(0):
                self._finish_rubber(to_screen)
                self._rubber = False
                self._rubber_start = None
                self._rubber_end = None

    # ------------------------------------------------------------------
    def _finish_rubber(self, to_screen):
        if not (self._rubber_start and self._rubber_end):
            return
        x0, y0 = self._rubber_start
        x1, y1 = self._rubber_end
        # Çok küçük sürükleme = basit tık → boşluk temizleme
        if abs(x1 - x0) < 3 and abs(y1 - y0) < 3:
            self.clicked_empty = True
            return

        rx0, rx1 = min(x0, x1), max(x0, x1)
        ry0, ry1 = min(y0, y1), max(y0, y1)
        hit = set()
        for fid, (wx, wy) in self._points:
            sx, sy = to_screen(wx, wy)
            if rx0 <= sx <= rx1 and ry0 <= sy <= ry1:
                hit.add(fid)
        # Panel seçim davranışını (ctrl/shift) kendisi uygular;
        # burada sadece rubber içindekileri "clicked_fid" gibi iletmek
        # yerine doğrudan seçime ekliyoruz — panel bunu bir sonraki
        # tıklama mantığıyla birleştirebilir.
        io = imgui.get_io()
        if io.key_ctrl:
            self.selected_fids ^= hit      # toggle
        elif io.key_shift:
            self.selected_fids |= hit      # ekle
        else:
            self.selected_fids = hit       # değiştir

    # ------------------------------------------------------------------
    def _apply_zoom(self, wheel, mx, my, cx, cy, cw, ch):
        factor = self.ZOOM_STEP if wheel > 0 else 1.0 / self.ZOOM_STEP
        old_zoom = self.zoom
        new_zoom = max(self.MIN_ZOOM, min(old_zoom * factor, self.MAX_ZOOM))
        if new_zoom == old_zoom:
            return
        # İmleç altındaki dünya noktası sabit kalsın
        to_screen, from_screen = self._world_to_screen_factory(cx, cy, cw, ch)
        wx, wy = from_screen(mx, my)
        self.zoom = new_zoom
        # pan'i, wx,wy tekrar mx,my'ye düşecek şekilde ayarla
        # yeni pan hesabı:
        #   sx = cx + half_w + (xr + pan_x) * zoom
        #   wx dünya noktasının dönmüş hali xr = rot(wx)
        rot = self.view_rotation
        xr, yr = _rot((wx, wy), rot)
        half_w = cw * 0.5
        half_h = ch * 0.5
        pan_x = (mx - cx - half_w) / new_zoom - xr
        pan_y = -(my - cy - half_h) / new_zoom - yr
        self.pan = (pan_x, pan_y)

    # ------------------------------------------------------------------
    def _hit_test(self, mx, my, to_screen, radius=None):
        if radius is None:
            radius = self.HIT_RADIUS_PX
        best = None
        best_d = radius
        for fid, (wx, wy) in self._points:
            sx, sy = to_screen(wx, wy)
            d = math.hypot(sx - mx, sy - my)
            if d < best_d:
                best_d = d
                best = fid
        return best

    # ------------------------------------------------------------------
    @staticmethod
    def _is_space_down(imgui_ctx):
        io = imgui_ctx.get_io()
        # pyimgui sürümlerine göre farklı alanlar
        if hasattr(io, "key_space"):
            return bool(io.key_space)
        try:
            return imgui_ctx.is_key_down(imgui.KEY_SPACE)
        except Exception:
            return False