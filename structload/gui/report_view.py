# gui/report_view.py
import io
import logging
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.core.image import Image as CoreImage
from kivy.metrics import dp, sp

# Varsayılan Tema ve Font Tanimlari (main'den devralınabilir veya override edilebilir)
THEME = {
    "bg_card": (0.13, 0.15, 0.19, 1),
    "primary": (0.22, 0.58, 0.93, 1),
    "accent": (0.1, 0.75, 0.6, 1),
    "text_main": (0.95, 0.96, 0.98, 1),
    "text_sub": (0.65, 0.70, 0.78, 1),
    "tbl_header": (0.20, 0.28, 0.38, 1),
    "tbl_unit": (0.16, 0.22, 0.30, 1),
    "tbl_row_even": (0.14, 0.17, 0.22, 1),
    "tbl_row_odd": (0.11, 0.13, 0.17, 1),
}
from kivy.core.text import LabelBase
LabelBase.register(
    name="CustomFont", 
    fn_regular="assets/fonts/Roboto-Regular.ttf"  # Kendi ttf yolun
)

FONT = {
    "family": "CustomFont",
    "section": 18,
    "heading": 16,
    "body": 13,
    "table": 12,
    "small": 12,
}


class CardContainer(BoxLayout):
    """Yuvarlatılmış arka plana sahip kart kutusu."""

    def __init__(self, bg_color=THEME["bg_card"], radius=10, padding_dp=12, spacing_dp=10, **kwargs):
        super().__init__(
            orientation="vertical",
            padding=dp(padding_dp),
            spacing=dp(spacing_dp),
            size_hint_y=None,
            **kwargs
        )
        self.bind(minimum_height=self.setter("height"))

        with self.canvas.before:
            Color(*bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(radius)])

        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size


class AutoLabel(Label):
    """Metni genişliğe göre kıran dinamik Label."""

    def __init__(self, font_sp=FONT["body"], font_name=FONT["family"], is_bold=False, text_color=THEME["text_main"], **kwargs):
        super().__init__(
            font_size=sp(font_sp),
            font_name=font_name,
            bold=is_bold,
            color=text_color,
            size_hint=(1, None),
            valign="middle",
            halign="left",
            **kwargs
        )
        self.bind(width=self._update_text_size)
        self.bind(texture_size=self._update_height)

    def _update_text_size(self, instance, width):
        self.text_size = (max(0, width), None)

    def _update_height(self, instance, texture_size):
        self.height = max(texture_size[1] + dp(8), dp(28))


CELL_PAD_X = dp(10)      # hücre içi yatay boşluk
CELL_PAD_Y = dp(8)       # hücre içi dikey boşluk
MIN_CELL_W = dp(70)      # min hücre genişliği
MAX_CELL_W = dp(260)     # max hücre genişliği
MIN_ROW_H = dp(34)       # min satır yüksekliği

class ReportView(CardContainer):
    """Her türlü veriyi (ReportDataFrame, Dict, List, Görsel, String) 

    otomatik ayrıştırıp Kivy kartına dönüştüren akıllı rapor bileşeni.
    """

    def __init__(self, data, **kwargs):
        super().__init__(**kwargs)
        if data is not None:
            self._render_data(data)

    def _render_data(self, data):
        """Verinin tipini tespit edip uygun render metodunu çağırır."""
        
        # 1. ReportDataFrame
        if hasattr(data, "columns") and hasattr(data, "iterrows"):
            self._render_report_dataframe(data)

        # 2. Dictionary (Rüzgar raporundaki w_report gibi)
        elif isinstance(data, dict):
            for key, val in data.items():
                # Özel anahtarlar
                if key == "image":
                    img_widget = self._load_kivy_image(val)
                    if img_widget:
                        self.add_widget(img_widget)
                else:
                    # İç içe geçen diğer raporlar için alt kart aç
                    if val is not None:
                        # Eğer anahtar bir başlık niteliğindeyse ekle
                        if isinstance(key, str) and not key.startswith("_"):
                            self.add_widget(
                                AutoLabel(text=str(key), font_sp=FONT["heading"], is_bold=True, text_color=THEME["primary"])
                            )
                        self._render_data(val)

        # 3. Liste
        elif isinstance(data, (list, tuple)):
            for item in data:
                self._render_data(item)

        # 4. Düz Metin / Sayı
        else:
            self.add_widget(AutoLabel(text=str(data), font_sp=FONT["body"]))

    def _render_report_dataframe(self, report):
        """ReportDataFrame'i başlık, açıklama, tablo ve görselleriyle basar."""
        

        # ---------- Başlık & Açıklama ----------
        if getattr(report, "custom_title", None):
            self.add_widget(AutoLabel(
                text=str(report.custom_title),
                font_sp=FONT["heading"], is_bold=True,
                text_color=THEME["accent"],
            ))
        if getattr(report, "custom_desc", None):
            self.add_widget(AutoLabel(
                text=str(report.custom_desc),
                font_sp=FONT["small"], text_color=THEME["text_sub"],
            ))

        if len(report) == 0:
            return

        columns = list(report.columns)
        n_cols = len(columns)
        has_desc = bool(getattr(report, "column_descriptions", None))
        has_units = bool(getattr(report, "column_units", None))

        # ---------- 1) TÜM SATIRLARI HAZIRLA ----------
        # (Aynı veriyi 3 katmanda birden kullanmak yerine tek yerden üret)
        rows_data = []   # [ {"row_type": ..., "values": [...], "bg": ...}, ... ]

        # Başlık satırı
        rows_data.append({
            "row_type": "header",
            "values": [str(c) for c in columns],
            "bg": THEME["tbl_header"],
            "bold": True,
            "font_sp": FONT["table"],
            "text_color": THEME["text_main"],
        })

        # Açıklama satırı
        if has_desc:
            rows_data.append({
                "row_type": "desc",
                "values": [
                    str(report.column_descriptions.get(c, "") or "")
                    for c in columns
                ],
                "bg": THEME["tbl_unit"],
                "bold": False,
                "font_sp": FONT["small"],
                "text_color": THEME["text_sub"],
            })

        # Birim satırı
        if has_units:
            rows_data.append({
                "row_type": "unit",
                "values": [
                    f"[{report.column_units.get(c, '')}]"
                    if report.column_units.get(c, "") else ""
                    for c in columns
                ],
                "bg": THEME["tbl_unit"],
                "bold": False,
                "font_sp": FONT["small"],
                "text_color": THEME["primary"],
            })

        # Veri satırları
        for idx, (_, row) in enumerate(report.iterrows()):
            values = (
                report._format_row(row)
                if hasattr(report, "_format_row")
                else [str(v) for v in row.values]
            )
            bg = THEME["tbl_row_even"] if idx % 2 == 0 else THEME["tbl_row_odd"]
            rows_data.append({
                "row_type": "data",
                "values": [str(v) for v in values],
                "bg": bg,
                "bold": False,
                "font_sp": FONT["table"],
                "text_color": THEME["text_main"],
            })

        # ---------- 2) SÜTUN GENİŞLİKLERİNİ ÖNCEDEN HESAPLA ----------
        col_widths = [MIN_CELL_W] * n_cols

        for row in rows_data:
            for i, val in enumerate(row["values"]):
                w = self._measure_text(
                    text=val,
                    font_name=FONT["family"],
                    font_size=sp(row["font_sp"]),
                    bold=row["bold"],
                )
                w = max(MIN_CELL_W, min(w + 2 * CELL_PAD_X, MAX_CELL_W))
                if w > col_widths[i]:
                    col_widths[i] = w

        # ---------- 3) SATIR YÜKSEKLİKLERİNİ ÖNCEDEN HESAPLA ----------
        # Her satır için: hücre metni sütun genişliğine göre kaç satıra kırılır?
        row_heights = []
        for row in rows_data:
            max_lines = 1
            for i, val in enumerate(row["values"]):
                inner_w = col_widths[i] - 2 * CELL_PAD_X
                lines = self._count_wrapped_lines(
                    text=val,
                    font_name=FONT["family"],
                    font_size=sp(row["font_sp"]),
                    bold=row["bold"],
                    max_width=inner_w,
                )
                max_lines = max(max_lines, lines)
            text_h = self._measure_text_height(
                font_name=FONT["family"],
                font_size=sp(row["font_sp"]),
                bold=row["bold"],
                lines=max_lines,
            )
            row_heights.append(max(MIN_ROW_H, text_h + 2 * CELL_PAD_Y))

        # ---------- 4) TEK BİR GRID OLUŞTUR (manuel konumlama) ----------
        total_w = sum(col_widths)
        total_h = sum(row_heights)

        table = GridLayout(
            cols=n_cols,
            rows=len(rows_data),
            size_hint=(None, None),
            width=total_w,
            height=total_h,
            spacing=dp(1),
            padding=0,
        )

        # Y pozisyonlarını Kivy'nin ters sırasına göre hesapla
        # GridLayout children'ı soldan-sağa, üstten-alta yerleştirir.
        for r_idx, row in enumerate(rows_data):
            bg = row["bg"]

            for c_idx, val in enumerate(row["values"]):
                w = col_widths[c_idx]
                h = row_heights[r_idx]

                cell = Label(
                    text=val,
                    size_hint=(None, None),
                    width=w,
                    height=h,
                    font_size=sp(row["font_sp"]),
                    font_name=FONT["family"],
                    bold=row["bold"],
                    color=row["text_color"],
                    halign="center",
                    valign="middle",
                    text_size=(w - 2 * CELL_PAD_X, h - 2 * CELL_PAD_Y),
                    shorten=False,
                )

                # Arka planı HÜCRE TAM BOYUTUNDA çiz (satır yüksekliği kadar)
                with cell.canvas.before:
                    Color(*bg)
                    cell._bg = Rectangle(pos=cell.pos, size=(w, h))

                cell.bind(
                    pos=lambda inst, p: setattr(inst._bg, "pos", p),
                    size=lambda inst, s: setattr(inst._bg, "size", s),
                )

                table.add_widget(cell)

        # ---------- 5) SCROLLVIEW ----------
        table_scroll = ScrollView(
            do_scroll_x=True, do_scroll_y=False,
            size_hint=(1, None),
            height=min(total_h + dp(12), dp(360)),
        )
        table_scroll.add_widget(table)
        self.add_widget(table_scroll)

        # ---------- 6) GÖRSELLER ----------
        for g_item in getattr(report, "graphics", []) or []:
            g_title = g_item.get("title")
            g_desc = g_item.get("description")
            if g_title:
                self.add_widget(AutoLabel(
                    text=str(g_title), font_sp=FONT["heading"],
                    is_bold=True, text_color=THEME["accent"],
                ))
            if g_desc:
                self.add_widget(AutoLabel(
                    text=str(g_desc), font_sp=FONT["small"],
                    text_color=THEME["text_sub"],
                ))
            raw = g_item.get("image") or g_item.get("data")
            k_img = self._load_kivy_image(raw)
            if k_img:
                self.add_widget(k_img)

    def _load_kivy_image(self, raw_graphic):
        if raw_graphic is None:
            return None
        try:
            buf = None
            if hasattr(raw_graphic, "savefig"):
                buf = io.BytesIO()
                raw_graphic.savefig(buf, format="png", bbox_inches="tight", facecolor="#15181e")
                buf.seek(0)
            elif isinstance(raw_graphic, io.BytesIO):
                buf = raw_graphic
                buf.seek(0)
            elif isinstance(raw_graphic, bytes):
                buf = io.BytesIO(raw_graphic)
                buf.seek(0)
            elif isinstance(raw_graphic, str):
                return Image(source=raw_graphic, size_hint_y=None, height=dp(260), fit_mode="contain")

            if buf:
                cim = CoreImage(buf, ext="png")
                return Image(texture=cim.texture, size_hint_y=None, height=dp(260), fit_mode="contain")
        except Exception as e:
            logging.error(f"Görsel yükleme hatası: {e}")
        return None

    def _measure_text(self, text, font_name, font_size, bold=False) -> float:
        """Metnin piksel genişliğini ölçer (tek satır)."""
        if not text:
            return 0.0
        try:
            from kivy.core.text import Label as CoreLabel
            lbl = CoreLabel(
                text=str(text),
                font_name=font_name,
                font_size=font_size,
                bold=bold,
            )
            lbl.refresh()
            return lbl.texture.size[0]
        except Exception:
            # Fallback: karakter başı ~0.55 * font_size
            return len(str(text)) * font_size * 0.55


    def _measure_text_height(self, font_name, font_size, bold=False, lines=1) -> float:
        """Bir metnin `lines` satırda kapladığı yüksekliği tahmin eder."""
        try:
            from kivy.core.text import Label as CoreLabel
            lbl = CoreLabel(
                text="Ağ",
                font_name=font_name,
                font_size=font_size,
                bold=bold,
            )
            lbl.refresh()
            line_h = lbl.texture.size[1]
        except Exception:
            line_h = font_size * 1.3
        return line_h * lines


    def _count_wrapped_lines(
        self, text, font_name, font_size, bold=False, max_width=100
    ) -> int:
        """
        Metnin `max_width` pikselde kaç satıra kırılacağını tahmin eder.
        Kelime bazlı basit kırma (Kivy'nin kendi kırma algoritmasına yakın).
        """
        if not text:
            return 1
        if max_width <= 0:
            return 1

        words = str(text).split()
        if not words:
            return 1

        try:
            from kivy.core.text import Label as CoreLabel

            def text_w(s):
                if not s:
                    return 0.0
                lbl = CoreLabel(
                    text=s, font_name=font_name,
                    font_size=font_size, bold=bold,
                )
                lbl.refresh()
                return lbl.texture.size[0]
        except Exception:
            def text_w(s):
                return len(s) * font_size * 0.55

        lines = 1
        current = ""
        for w in words:
            candidate = (current + " " + w).strip()
            if text_w(candidate) <= max_width:
                current = candidate
            else:
                lines += 1
                current = w

        return lines

    @staticmethod
    def _cell(text, bold=False, bg_color=THEME["tbl_row_even"], text_color=THEME["text_main"], font_sp=FONT["table"], col_width=dp(140)):
        label = Label(
            text=str(text),
            size_hint=(None, None),
            width=col_width,
            halign="center",
            valign="middle",
            font_size=sp(font_sp),
            font_name=FONT["family"],
            color=text_color,
            bold=bold,
        )

        # label.bind(width=lambda inst, w: setattr(inst, "text_size", (max(0, w - dp(8)), None)))
        label.bind(texture_size=lambda inst, t: setattr(inst, "height", max(t[1] + dp(12), dp(36))))
        label.bind(texture_size=lambda instance, value: setattr(instance, 'width', value[0] + dp(20)))

        with label.canvas.before:
            Color(*bg_color)
            label._bg_rect = Rectangle(pos=label.pos, size=label.size)

        label.bind(pos=lambda inst, pos: setattr(inst._bg_rect, "pos", pos), size=lambda inst, sz: setattr(inst._bg_rect, "size", sz))
        return label