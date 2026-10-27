# gui/hazir_yuk_karti.py
"""
Hazır yük detay kartı.
Sol taraftaki kütüphaneden seçilen yükü form halinde gösterir,
düzenlenebilir ve LoadManager'a kaydedilebilir.
"""

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.graphics import Color, Rectangle, Line
from kivy.metrics import dp

from structload.data.material_data import MATERIAL_WEIGHTS
from structload.utils.status_manager import status
from structload.utils.report_dataframe import ReportDataFrame
from structload.loads.load_definition import LoadDefinition, LoadComponent

import gui.panels as panels


# ------------------------------------------------------------------
# Yardımcı: renkli başlık çubuğu
# ------------------------------------------------------------------
def _baslik_seridi(text, bg=(0.20, 0.35, 0.55, 1)):
    """Mavi zeminli başlık şeridi."""
    box = BoxLayout(
        size_hint_y=None, height=dp(32),
        padding=(dp(10), 0),
    )
    with box.canvas.before:
        Color(*bg)
        rect = Rectangle(pos=box.pos, size=box.size)
    box.bind(
        pos=lambda w, p: setattr(rect, "pos", p),
        size=lambda w, s: setattr(rect, "size", s),
    )
    lbl = Label(
        text=text,
        bold=True,
        color=(1, 1, 1, 1),
        font_size=dp(13),
        halign="left",
        valign="middle",
    )
    lbl.bind(size=lambda l, s: setattr(l, "text_size", s))
    box.add_widget(lbl)
    return box


# ------------------------------------------------------------------
# Yardımcı: etiketli satır (label + widget)
# ------------------------------------------------------------------
def _etiketli_satir(etiket, widget, etiket_w=0.22):
    row = BoxLayout(
        size_hint_y=None, height=dp(38),
        spacing=dp(8), padding=(dp(4), 0),
    )
    lbl = Label(
        text=etiket,
        size_hint_x=etiket_w,
        halign="right",
        valign="middle",
        color=(0.30, 0.30, 0.35, 1),
        font_size=dp(12),
    )
    lbl.bind(size=lambda l, s: setattr(l, "text_size", s))
    row.add_widget(lbl)
    row.add_widget(widget)
    return row


# ------------------------------------------------------------------
# Bileşen düzenleme satırı
# ------------------------------------------------------------------
class KartBilesenSatiri(BoxLayout):
    """Kart içinde bir bileşen satırı: ad, malzeme, kalınlık, canlı değer."""

    def __init__(self, index: int, comp: dict, on_change=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(34)
        self.spacing = dp(4)
        self.on_change = on_change
        self.index = index

        # No
        self.add_widget(Label(
            text=f"{index + 1}.",
            size_hint_x=0.06,
            color=(0.55, 0.55, 0.6, 1),
            font_size=dp(11),
        ))

        # Ad
        self.ad_input = TextInput(
            text=comp.get("name", ""),
            size_hint_x=0.22, multiline=False, font_size=dp(12),
            padding=(dp(6), dp(6)),
        )
        self.ad_input.bind(text=self._degisti)
        self.add_widget(self.ad_input)

        # Tip (Malzeme / Sabit)
        self.tip_spinner = Spinner(
            text=comp.get("type", "Malzeme"),
            values=["Malzeme", "Sabit Değer"],
            size_hint_x=0.16,
            font_size=dp(12),
        )
        self.tip_spinner.bind(text=self.tip_degisti)
        self.add_widget(self.tip_spinner)

        # Malzeme
        self.malzeme_spinner = Spinner(
            text=comp.get("material", "seramik"),
            values=sorted(MATERIAL_WEIGHTS.keys()),
            size_hint_x=0.20,
            font_size=dp(12),
        )
        self.malzeme_spinner.bind(text=self._degisti)
        self.add_widget(self.malzeme_spinner)

        # Kalınlık (mm)
        self.kalinlik_input = TextInput(
            text=str(comp.get("thickness_mm", "")),
            hint_text="mm",
            size_hint_x=0.12, multiline=False,
            input_filter="float", font_size=dp(12),
            padding=(dp(6), dp(6)),
        )
        self.kalinlik_input.bind(text=self._degisti)
        self.add_widget(self.kalinlik_input)

        # Sabit değer (gizli, tip değişince görünür)
        self.deger_input = TextInput(
            text=str(comp.get("value", "")),
            hint_text="kN/m²",
            size_hint_x=0.12, multiline=False,
            input_filter="float", font_size=dp(12),
            padding=(dp(6), dp(6)),
            disabled=True, opacity=0,
        )
        self.deger_input.bind(text=self._degisti)
        self.add_widget(self.deger_input)

        # Sonuç
        self.sonuc_label = Label(
            text="—",
            size_hint_x=0.10,
            bold=True,
            color=(0.15, 0.55, 0.30, 1),
            font_size=dp(12),
        )
        self.add_widget(self.sonuc_label)

        # Kaldır
        btn = Button(
            text="✕", size_hint_x=0.02,
            background_color=(0.85, 0.25, 0.25, 1),
            font_size=dp(12),
        )
        btn.bind(on_press=self._kaldir)
        self.add_widget(btn)

        # Başlangıç görünümü
        self.tip_degisti(self.tip_spinner, self.tip_spinner.text)
        self._guncelle_deger()

    # ------------------------------------------------------------------
    def tip_degisti(self, spinner, text):
        malzeme_modu = (text == "Malzeme")
        self.malzeme_spinner.disabled = not malzeme_modu
        self.kalinlik_input.disabled = not malzeme_modu
        self.deger_input.disabled = malzeme_modu

        # Görünürlük
        self.malzeme_spinner.opacity = 1 if malzeme_modu else 0.3
        self.kalinlik_input.opacity = 1 if malzeme_modu else 0.3
        self.deger_input.opacity = 1 if not malzeme_modu else 0.3
        self._guncelle_deger()

    # ------------------------------------------------------------------
    def _degisti(self, *args):
        self._guncelle_deger()

    # ------------------------------------------------------------------
    def _guncelle_deger(self):
        try:
            if self.tip_spinner.text == "Malzeme":
                kal_m = float(self.kalinlik_input.text) / 1000.0  # mm → m
                birim = MATERIAL_WEIGHTS.get(self.malzeme_spinner.text, 0)
                deger = birim * kal_m
            else:
                deger = float(self.deger_input.text)
            self.sonuc_label.text = f"{deger:.3f}"
            self.sonuc_label.color = (0.15, 0.55, 0.30, 1)
        except (ValueError, TypeError):
            self.sonuc_label.text = "—"
            self.sonuc_label.color = (0.7, 0.7, 0.7, 1)
        if self.on_change:
            self.on_change()

    # ------------------------------------------------------------------
    def _kaldir(self, instance):
        if self.parent:
            self.parent.remove_widget(self)
        if self.on_change:
            self.on_change()

    # ------------------------------------------------------------------
    def deger(self) -> float:
        try:
            if self.tip_spinner.text == "Malzeme":
                kal_m = float(self.kalinlik_input.text) / 1000.0
                return MATERIAL_WEIGHTS.get(self.malzeme_spinner.text, 0) * kal_m
            return float(self.deger_input.text)
        except (ValueError, TypeError):
            return 0.0

    # ------------------------------------------------------------------
    def load_component(self) -> LoadComponent | None:
        ad = self.ad_input.text.strip() or "Bileşen"
        if self.tip_spinner.text == "Malzeme":
            try:
                kal_m = float(self.kalinlik_input.text) / 1000.0
            except (ValueError, TypeError):
                return None
            if kal_m <= 0:
                return None
            return LoadComponent(
                name=ad,
                material=self.malzeme_spinner.text,
                thickness=kal_m,
            )
        else:
            try:
                v = float(self.deger_input.text)
            except (ValueError, TypeError):
                return None
            return LoadComponent(name=ad, value=v)


# ==================================================================
# ANA KART
# ==================================================================
class HazirYukDetayKarti(BoxLayout):
    """
    Seçilen hazır yükü form halinde gösterir.
    Düzenlenebilir, LoadManager'a güncellenebilir.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.spacing = dp(0)
        self.padding = dp(0)

        # Arka plan (beyaz kart)
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = Rectangle(pos=self.pos, size=self.size)
            Color(0.80, 0.82, 0.86, 1)
            self._border = Line(
                rectangle=(self.x, self.y, self.width, self.height),
                width=1.2,
            )
        self.bind(pos=self._update_bg, size=self._update_bg)

        # --- Başlık şeridi ---
        self.add_widget(_baslik_seridi("YÜK TANIMI"))

        # --- Form gövdesi ---
        self.form_box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(4),
            padding=(dp(12), dp(8)),
        )
        self.form_box.bind(minimum_height=self.form_box.setter("height"))

        # ID
        self.id_input = TextInput(
            text="", multiline=False, font_size=dp(13),
            padding=(dp(8), dp(8)),
            size_hint_x=0.40,
        )
        self.form_box.add_widget(_etiketli_satir("ID", self.id_input))

        # Ad
        self.ad_input = TextInput(
            text="", multiline=False, font_size=dp(13),
            padding=(dp(8), dp(8)),
            size_hint_x=0.80,
        )
        self.form_box.add_widget(_etiketli_satir("Ad", self.ad_input))

        # Açıklama
        aciklama_lbl = Label(
            text="Açıklama",
            size_hint_y=None, height=dp(22),
            color=(0.30, 0.30, 0.35, 1),
            font_size=dp(12),
            halign="left",
        )
        aciklama_lbl.bind(size=lambda l, s: setattr(l, "text_size", s))
        self.form_box.add_widget(aciklama_lbl)

        self.aciklama_input = TextInput(
            text="", multiline=True,
            size_hint_y=None, height=dp(60),
            font_size=dp(12),
            padding=(dp(8), dp(8)),
        )
        self.form_box.add_widget(self.aciklama_input)

        # --- BİLEŞENLER başlığı ---
        self.bilesen_baslik = _baslik_seridi(
            "BİLEŞENLER", bg=(0.28, 0.42, 0.60, 1),
        )
        self.form_box.add_widget(self.bilesen_baslik)

        # Sütun başlıkları
        col_head = BoxLayout(
            size_hint_y=None, height=dp(22),
            spacing=dp(4), padding=(dp(4), 0),
        )
        for txt, w in [
            ("#", 0.06), ("Ad", 0.22), ("Tip", 0.16),
            ("Malzeme", 0.20), ("Kalınlık (mm)", 0.12),
            ("Değer (kN/m²)", 0.12), ("Sonuç", 0.10), ("", 0.02),
        ]:
            col_head.add_widget(Label(
                text=txt, size_hint_x=w,
                font_size=dp(10), bold=True,
                color=(0.40, 0.45, 0.55, 1),
            ))
        self.form_box.add_widget(col_head)

        # Bileşen listesi (scroll)
        self.bilesen_scroll = ScrollView(size_hint_y=None, height=dp(160))
        self.bilesen_layout = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(2),
        )
        self.bilesen_layout.bind(minimum_height=self.bilesen_layout.setter("height"))
        self.bilesen_scroll.add_widget(self.bilesen_layout)
        self.form_box.add_widget(self.bilesen_scroll)

        # + Bileşen ekle
        ekle_btn = Button(
            text="+ Bileşen",
            size_hint_y=None, height=dp(32),
            background_color=(0.30, 0.55, 0.75, 1),
            font_size=dp(12),
        )
        ekle_btn.bind(on_press=self._bilesen_ekle)
        self.form_box.add_widget(ekle_btn)

        # --- TOPLAM ---
        toplam_row = BoxLayout(
            size_hint_y=None, height=dp(36),
            padding=(dp(4), 0),
        )
        toplam_row.add_widget(Label(text="", size_hint_x=0.70))
        toplam_lbl = Label(
            text="TOPLAM",
            size_hint_x=0.15,
            bold=True,
            color=(0.20, 0.35, 0.55, 1),
            font_size=dp(13),
            halign="right",
        )
        toplam_lbl.bind(size=lambda l, s: setattr(l, "text_size", s))
        toplam_row.add_widget(toplam_lbl)
        self.toplam_label = Label(
            text="0.000",
            size_hint_x=0.15,
            bold=True,
            color=(0.15, 0.55, 0.30, 1),
            font_size=dp(14),
        )
        toplam_row.add_widget(self.toplam_label)
        self.form_box.add_widget(toplam_row)

        self.add_widget(self.form_box)

        # --- Alt buton: GÜNCELLE ---
        alt_box = BoxLayout(
            size_hint_y=None, height=dp(50),
            padding=(dp(12), dp(6)), spacing=dp(8),
        )
        alt_box.add_widget(Label(text="", size_hint_x=0.5))

        sil_btn = Button(
            text="SİL", size_hint_x=0.2,
            background_color=(0.75, 0.25, 0.25, 1),
            font_size=dp(12),
        )
        sil_btn.bind(on_press=self._sil)
        alt_box.add_widget(sil_btn)

        guncelle_btn = Button(
            text="YÜKÜ GÜNCELLE", size_hint_x=0.3,
            background_color=(0.20, 0.55, 0.35, 1),
            bold=True,
            font_size=dp(13),
        )
        guncelle_btn.bind(on_press=self._guncelle)
        alt_box.add_widget(guncelle_btn)

        self.add_widget(alt_box)

        # Aktif yük bilgisi
        self._aktif_id = None
        self._aktif_kategori = None

    # ------------------------------------------------------------------
    def _update_bg(self, *args):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self._border.rectangle = (self.x, self.y, self.width, self.height)

    # ------------------------------------------------------------------
    def _bilesen_ekle(self, instance, comp: dict = None):
        comp = comp or {"name": "", "type": "Malzeme",
                        "material": "seramik", "thickness_mm": ""}
        idx = len([
            c for c in self.bilesen_layout.children
            if isinstance(c, KartBilesenSatiri)
        ])
        satir = KartBilesenSatiri(
            index=idx, comp=comp, on_change=self._toplam_guncelle,
        )
        self.bilesen_layout.add_widget(satir)
        self._toplam_guncelle()
        self._yeniden_numaralandir()

    def _yeniden_numaralandir(self):
        # children ters sırada; index'i düzelt
        rows = [c for c in reversed(self.bilesen_layout.children)
                if isinstance(c, KartBilesenSatiri)]
        for i, r in enumerate(rows):
            r.index = i

    # ------------------------------------------------------------------
    def _toplam_guncelle(self):
        toplam = 0.0
        for c in self.bilesen_layout.children:
            if isinstance(c, KartBilesenSatiri):
                toplam += c.deger()
        self.toplam_label.text = f"{toplam:.3f}"

    # ------------------------------------------------------------------
    def yuk_yukle(self, definition: LoadDefinition, kategori_id: str = None):
        """LoadDefinition'ı kartta göster."""
        self._aktif_id = definition.id
        self._aktif_kategori = kategori_id

        self.id_input.text = definition.id
        self.ad_input.text = definition.name or ""
        self.aciklama_input.text = getattr(definition, "description", "") or ""

        self.bilesen_layout.clear_widgets()

        for comp in (definition.components or []):
            # LoadComponent → dict
            d = {}
            d["name"] = comp.name or ""
            if getattr(comp, "material", None):
                d["type"] = "Malzeme"
                d["material"] = comp.material
                d["thickness_mm"] = str(round((comp.thickness or 0) * 1000, 1))
            else:
                d["type"] = "Sabit Değer"
                d["value"] = str(comp.value or 0)
            self._bilesen_ekle(None, d)

        if not definition.components:
            # Boş bir satır ekle
            self._bilesen_ekle(None)

        self._toplam_guncelle()

    # ------------------------------------------------------------------
    def _sil(self, instance):
        if not self._aktif_id:
            status.warning("Silinecek yük yok.")
            return
        lm = panels.load_manager
        try:
            if self._aktif_id in lm.definitions:
                del lm.definitions[self._aktif_id]
            # Atamalardan da çıkar
            for elem, kinds in list(lm.assignments.items()):
                for tip in ("G", "Q"):
                    ids = kinds.get(tip, [])
                    if self._aktif_id in ids:
                        ids.remove(self._aktif_id)
            status.success(f"[{self._aktif_id}] silindi.")
            self.temizle()
            # Sol paneli yenilemek için App üzerinden tetikle
            app = self._get_app()
            if app and hasattr(app, "hazir_panel"):
                app.hazir_panel.sol_liste_yenile()
        except Exception as e:
            status.error(f"Silme hatası: {e}")

    # ------------------------------------------------------------------
    def _guncelle(self, instance):
        """Formdaki bilgileri LoadManager'a yaz."""
        lm = panels.load_manager
        yeni_id = self.id_input.text.strip()
        yeni_ad = self.ad_input.text.strip()

        if not yeni_id or not yeni_ad:
            status.error("ID ve Ad zorunludur.")
            return

        # ID değişmişse ve çakışıyorsa hata
        if yeni_id != self._aktif_id and yeni_id in lm.definitions:
            status.error(f"'{yeni_id}' ID'si zaten mevcut.")
            return

        # Bileşenleri topla
        bilesenler = []
        for c in reversed(self.bilesen_layout.children):
            if isinstance(c, KartBilesenSatiri):
                comp = c.load_component()
                if comp is None:
                    status.error("Geçersiz bileşen değeri.")
                    return
                bilesenler.append(comp)

        if not bilesenler:
            status.error("En az bir bileşen olmalı.")
            return

        # Eski tanımı sil (ID değişmişse)
        if self._aktif_id and self._aktif_id != yeni_id:
            if self._aktif_id in lm.definitions:
                del lm.definitions[self._aktif_id]
            for elem, kinds in lm.assignments.items():
                for tip in ("G", "Q"):
                    if self._aktif_id in kinds.get(tip, []):
                        kinds[tip] = [
                            x for x in kinds[tip] if x != self._aktif_id
                        ]
                        kinds[tip].append(yeni_id)

        # Yeni tanımı yaz
        definition = LoadDefinition(
            id=yeni_id,
            name=yeni_ad,
            load_type="G",
            components=bilesenler,
            source="user",
        )
        try:
            toplam = definition.calculate(MATERIAL_WEIGHTS)
        except Exception:
            toplam = 0.0

        lm.definitions[yeni_id] = definition
        self._aktif_id = yeni_id

        status.success(
            f"[{yeni_id}] {yeni_ad} güncellendi. Toplam: {toplam:.3f} kN/m²"
        )

        app = self._get_app()
        if app and hasattr(app, "hazir_panel"):
            app.hazir_panel.sol_liste_yenile()

    # ------------------------------------------------------------------
    def temizle(self):
        self._aktif_id = None
        self._aktif_kategori = None
        self.id_input.text = ""
        self.ad_input.text = ""
        self.aciklama_input.text = ""
        self.bilesen_layout.clear_widgets()
        self._toplam_guncelle()

    # ------------------------------------------------------------------
    def _get_app(self):
        from kivy.app import App
        return App.get_running_app()