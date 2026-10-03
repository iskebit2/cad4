# gui/panels.py
"""
Yük Atama GUI - Kivy
Seçilen döşeme/kirişe kütüphaneden ölü ve hareketli yük atar.

Geliştirmeler:
- StatusBar (popup yerine)
- Debug panel
- Bileşen ekleme: kütüphaneden seçim, canlı değer güncelleme
- ReportDataFrame entegrasyonu
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.uix.togglebutton import ToggleButton
from kivy.properties import StringProperty, NumericProperty, ListProperty
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle, Line

from structload.data.material_data import MATERIAL_WEIGHTS, LIVE_LOADS
from structload.data.preset_loader import PresetLibrary

from structload.loads.load_definition import LoadDefinition, LoadComponent
from structload.loads.load_manager import LoadManager

from structload.utils.status_manager import status
from structload.utils.report_dataframe import ReportDataFrame
from structload.gui.status_bar import StatusBar
from structload.gui.debug_panel import DebugPanel


# ============================================================
# GLOBAL LOAD MANAGER
# ============================================================

load_manager = LoadManager(material_weights=MATERIAL_WEIGHTS)
preset_library = PresetLibrary()


def set_globals(manager: LoadManager, library: PresetLibrary):
    global load_manager, preset_library
    load_manager = manager
    preset_library = library


# ============================================================
# YARDIMCI FONKSİYONLAR
# ============================================================

def malzeme_listesi_getir():
    return sorted(MATERIAL_WEIGHTS.keys())


def canli_yuk_listesi_getir():
    return [(k, v["name"], v["value"]) for k, v in LIVE_LOADS.items()]


def benzersiz_id_uret(prefix: str) -> str:
    mevcut = [
        d.id for d in load_manager.definitions.values()
        if d.id.startswith(prefix)
    ]
    sayi = 1
    while f"{prefix}{sayi:02d}" in mevcut:
        sayi += 1
    return f"{prefix}{sayi:02d}"
#


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

    def __init__(self, on_close=None, **kwargs):
        super().__init__(**kwargs)
        self.on_close = on_close
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
        self.add_widget(self._baslik_seridi_kapatli("YÜK TANIMI"))
        

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
        lm = load_manager
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
        lm = load_manager
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

    # ------------------------------------------------------------------
    def _baslik_seridi_kapatli(self, text, bg=(0.20, 0.35, 0.55, 1)):
        """Mavi şerit + sağda ✕ kapat butonu."""
        box = BoxLayout(
            size_hint_y=None, height=dp(32),
            padding=(dp(10), 0), spacing=dp(4),
        )
        with box.canvas.before:
            Color(*bg)
            rect = Rectangle(pos=box.pos, size=box.size)
        box.bind(
            pos=lambda w, p: setattr(rect, "pos", p),
            size=lambda w, s: setattr(rect, "size", s),
        )

        lbl = Label(
            text=text, bold=True,
            color=(1, 1, 1, 1), font_size=dp(13),
            halign="left", valign="middle",
        )
        lbl.bind(size=lambda l, s: setattr(l, "text_size", s))
        box.add_widget(lbl)

        kapat_btn = Button(
            text="✕",
            size_hint_x=None, width=dp(28),
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1),
            font_size=dp(14),
            bold=True,
        )
        kapat_btn.bind(on_press=self._kapat)
        box.add_widget(kapat_btn)
        return box

    # ------------------------------------------------------------------
    def _kapat(self, instance):
        if self.on_close:
            self.on_close()

# ============================================================
# GELİŞMİŞ BİLEŞEN SATIRI
# ============================================================

class BilesenSatiri(BoxLayout):
    """
    Gelişmiş G yükü bileşeni satırı.
    - Kütüphaneden hazır malzeme seçimi
    - Kalınlık girildikçe canlı değer güncelleme
    - Renkli durum göstergesi
    """

    def __init__(self, on_change=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(42)
        self.spacing = dp(4)
        self.padding = dp(2)
        self.on_change = on_change

        # Ad
        self.ad_input = TextInput(
            hint_text="Bileşen adı",
            size_hint_x=0.26,
            multiline=False,
            font_size=dp(13),
        )
        self.add_widget(self.ad_input)

        # Tip
        self.tip_spinner = Spinner(
            text="Malzeme",
            values=["Malzeme", "Sabit Değer"],
            size_hint_x=0.16,
        )
        self.tip_spinner.bind(text=self.tip_degisti)
        self.add_widget(self.tip_spinner)

        # Malzeme
        self.malzeme_spinner = Spinner(
            text="seramik",
            values=malzeme_listesi_getir(),
            size_hint_x=0.20,
        )
        self.malzeme_spinner.bind(text=self._hesapla)
        self.add_widget(self.malzeme_spinner)

        # Değer input
        self.deger_input = TextInput(
            hint_text="Değer",
            size_hint_x=0.12,
            multiline=False,
            input_filter="float",
            font_size=dp(13),
        )
        self.deger_input.bind(text=self._hesapla)
        self.add_widget(self.deger_input)

        # Kalınlık
        self.kalinlik_input = TextInput(
            hint_text="Kalınlık",
            size_hint_x=0.12,
            multiline=False,
            input_filter="float",
            font_size=dp(13),
        )
        self.kalinlik_input.bind(text=self._hesapla)
        self.add_widget(self.kalinlik_input)

        # Sonuç label (canlı)
        self.sonuc_label = Label(
            text="—",
            size_hint_x=0.10,
            color=(0.2, 0.6, 0.3, 1),
            bold=True,
            font_size=dp(12),
        )
        self.add_widget(self.sonuc_label)

        # Kaldır
        self.kaldir_btn = Button(
            text="✕",
            size_hint_x=0.04,
            background_color=(0.8, 0.2, 0.2, 1),
            font_size=dp(14),
        )
        self.kaldir_btn.bind(on_press=self.kaldir)
        self.add_widget(self.kaldir_btn)

    # ------------------------------------------------------------------
    def tip_degisti(self, spinner, text):
        malzeme_modu = (text == "Malzeme")
        self.malzeme_spinner.disabled = not malzeme_modu
        self.kalinlik_input.disabled = not malzeme_modu
        self.deger_input.disabled = malzeme_modu
        if malzeme_modu:
            self.deger_input.text = ""
        else:
            self.kalinlik_input.text = ""
        self._hesapla()

    # ------------------------------------------------------------------
    def _hesapla(self, *args):
        """Canlı değer hesaplama."""
        try:
            if self.tip_spinner.text == "Malzeme":
                malzeme = self.malzeme_spinner.text
                kalinlik = float(self.kalinlik_input.text)
                if kalinlik <= 0:
                    raise ValueError
                birim_hacim = MATERIAL_WEIGHTS.get(malzeme, 0)
                deger = birim_hacim * kalinlik
                self.sonuc_label.text = f"{deger:.3f}"
                self.sonuc_label.color = (0.2, 0.6, 0.3, 1)
            else:
                deger = float(self.deger_input.text)
                self.sonuc_label.text = f"{deger:.3f}"
                self.sonuc_label.color = (0.2, 0.6, 0.3, 1)
        except (ValueError, TypeError):
            self.sonuc_label.text = "—"
            self.sonuc_label.color = (0.7, 0.7, 0.7, 1)

        if self.on_change:
            self.on_change()

    # ------------------------------------------------------------------
    def kaldir(self, instance):
        parent = self.parent
        if parent:
            parent.remove_widget(self)
        if self.on_change:
            self.on_change()

    # ------------------------------------------------------------------
    def load_component_olustur(self):
        ad = self.ad_input.text.strip() or "Bileşen"
        tip = self.tip_spinner.text

        if tip == "Malzeme":
            malzeme = self.malzeme_spinner.text
            try:
                kalinlik = float(self.kalinlik_input.text)
            except (ValueError, TypeError):
                return None
            if kalinlik <= 0:
                return None
            return LoadComponent(name=ad, material=malzeme, thickness=kalinlik)
        else:
            try:
                deger = float(self.deger_input.text)
            except (ValueError, TypeError):
                return None
            return LoadComponent(name=ad, value=deger)

    # ------------------------------------------------------------------
    def deger_hesapla(self) -> float:
        """Bileşenin hesaplanmış değerini döner (rapor için)."""
        try:
            if self.tip_spinner.text == "Malzeme":
                kalinlik = float(self.kalinlik_input.text)
                birim = MATERIAL_WEIGHTS.get(self.malzeme_spinner.text, 0)
                return birim * kalinlik
            return float(self.deger_input.text)
        except (ValueError, TypeError):
            return 0.0


# ============================================================
# HAZIR YÜK PANELİ
# ============================================================

class HazirYukPaneli(BoxLayout):
    """Sol: kütüphane. Sağ: istenirse açılan detay kartı."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.spacing = dp(8)
        self.padding = dp(6)

        self._detay_acik = False

        # ==================================================
        # SOL: kütüphane + toggle butonu
        # ==================================================
        sol = BoxLayout(
            orientation="vertical", spacing=dp(6),
            size_hint_x=1.0,           # başta tam genişlik
        )
        self.sol = sol

        # Üst satır: başlık + aç/kapa butonu
        ust = BoxLayout(size_hint_y=None, height=dp(42), spacing=dp(6))

        # Kategori spinner
        kategoriler = preset_library.kategori_listesi()
        self.kategori_map = {label: kid for kid, label, _ in kategoriler}
        self.kategori_spinner = Spinner(
            text=kategoriler[0][1] if kategoriler else "",
            values=[label for _, label, _ in kategoriler],
            size_hint_x=0.55,
        )
        self.kategori_spinner.bind(text=self.kategori_degisti)
        ust.add_widget(self.kategori_spinner)

        # Detay aç/kapa
        self.detay_btn = Button(
            text="▶ Detay", size_hint_x=0.30,
            background_color=(0.30, 0.55, 0.75, 1),
        )
        self.detay_btn.bind(on_press=self.detay_toggle)
        ust.add_widget(self.detay_btn)

        # Yeni yük oluştur (kartı açar ve boş form verir)
        yeni_btn = Button(
            text="+ Yeni", size_hint_x=0.15,
            background_color=(0.20, 0.55, 0.35, 1),
        )
        yeni_btn.bind(on_press=self.yeni_yuk)
        ust.add_widget(yeni_btn)

        sol.add_widget(ust)

        # Meta
        meta = preset_library.meta.get("conversion", {})
        sol.add_widget(Label(
            text=(
                f"Kaynak: {preset_library.meta.get('source', '')}  |  "
                f"Dönüşüm: {meta.get('from','')} → {meta.get('to','')}"
            ),
            size_hint_y=None, height=dp(22),
            color=(0.4, 0.4, 0.4, 1), font_size=dp(10),
        ))

        # Sütun başlıkları
        baslik = BoxLayout(size_hint_y=None, height=dp(26))
        baslik.add_widget(Label(text="Yük Adı", size_hint_x=0.60, bold=True, font_size=dp(11)))
        baslik.add_widget(Label(text="kgf/m²", size_hint_x=0.20, bold=True, font_size=dp(11)))
        baslik.add_widget(Label(text="kN/m²", size_hint_x=0.20, bold=True, font_size=dp(11)))
        sol.add_widget(baslik)

        # Liste
        self.scroll = ScrollView()
        self.liste_layout = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(2),
        )
        self.liste_layout.bind(minimum_height=self.liste_layout.setter("height"))
        self.scroll.add_widget(self.liste_layout)
        sol.add_widget(self.scroll)

        # Bilgi
        self.bilgi_label = Label(
            text="Bir yüke tıklayın → detay kartı açılır.",
            size_hint_y=None, height=dp(28),
            color=(0.35, 0.35, 0.40, 1), font_size=dp(11),
        )
        sol.add_widget(self.bilgi_label)

        self.add_widget(sol)

        # ==================================================
        # SAĞ: detay kartı (başta gizli)
        # ==================================================
        self.detay_kart = HazirYukDetayKarti(
            size_hint_x=None, width=0,       # başta 0 genişlik
            opacity=0,
            on_close=self.detay_kapat,
        )
        self.add_widget(self.detay_kart)

        if kategoriler:
            self.kategori_degisti(self.kategori_spinner, kategoriler[0][1])

    # ------------------------------------------------------------------
    # Detay panel aç/kapa
    # ------------------------------------------------------------------
    def detay_toggle(self, instance):
        if self._detay_acik:
            self.detay_kapat()
        else:
            self.detay_ac()

    def detay_ac(self):
        self._detay_acik = True
        self.sol.size_hint_x = 0.42
        self.detay_kart.size_hint_x = 0.58
        self.detay_kart.width = 0  # size_hint_x kullanılıyor
        self.detay_kart.opacity = 1
        self.detay_btn.text = "◀ Gizle"

    def detay_kapat(self):
        self._detay_acik = False
        self.sol.size_hint_x = 1.0
        self.detay_kart.size_hint_x = None
        self.detay_kart.width = 0
        self.detay_kart.opacity = 0
        self.detay_btn.text = "▶ Detay"

    # ------------------------------------------------------------------
    # Kategori / liste
    # ------------------------------------------------------------------
    def kategori_degisti(self, spinner, label):
        kid = self.kategori_map.get(label)
        if not kid:
            return
        cat = preset_library.categories[kid]
        self.bilgi_label.text = f"Tip: {cat.get('load_type','G')}"
        self.liste_yenile(kid)

    def liste_yenile(self, kategori_id):
        self.liste_layout.clear_widgets()
        yukler = preset_library.kategori_yukleri(kategori_id)

        for idx, y in enumerate(yukler):
            satir = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(2))

            isim_btn = Button(
                text=y["name"], size_hint_x=0.60,
                halign="left", valign="middle",
                background_color=(0.92, 0.94, 0.97, 1),
                color=(0.10, 0.15, 0.25, 1),
                font_size=dp(11),
            )
            isim_btn.bind(
                on_press=lambda inst, k=kategori_id, i=idx: self.satir_sec(k, i),
            )
            satir.add_widget(isim_btn)

            kgf_text = f"{y['kgf']:.2f}" if y.get("kgf") is not None else "-"
            satir.add_widget(Label(text=kgf_text, size_hint_x=0.20, font_size=dp(11)))
            satir.add_widget(Label(
                text=f"{y['kn']:.2f}", size_hint_x=0.20,
                color=(0.10, 0.55, 0.30, 1), bold=True, font_size=dp(11),
            ))
            self.liste_layout.add_widget(satir)

    # ------------------------------------------------------------------
    def satir_sec(self, kategori_id, item_index):
        """Hazır yükü kartta göster (kart kapalıysa açar)."""
        yukler = preset_library.kategori_yukleri(kategori_id)
        y = yukler[item_index]
        yuk_adi = y["name"]

        lm = load_manager

        mevcut = None
        for d in lm.definitions.values():
            if d.name == yuk_adi:
                mevcut = d
                break

        if not self._detay_acik:
            self.detay_ac()

        if mevcut:
            self.detay_kart.yuk_yukle(mevcut, kategori_id)
            self.bilgi_label.text = f"Düzenleniyor: [{mevcut.id}] {mevcut.name}"
            return

        try:
            load_type = preset_library.categories[kategori_id].get("load_type", "G")
            prefix = "G" if load_type == "G" else "Q"
            yeni_id = benzersiz_id_uret(prefix)

            definition = preset_library.load_definition_olustur(
                kategori_id=kategori_id,
                item_index=item_index,
                load_id=yeni_id,
                load_type=load_type,
            )
            lm.add_definition(definition)
            self.detay_kart.yuk_yukle(definition, kategori_id)
            self.bilgi_label.text = f"Yeni: [{yeni_id}] {definition.name}"
            status.success(f"[{yeni_id}] {definition.name} oluşturuldu.")
        except Exception as e:
            status.error(f"Hazır yük yüklenemedi: {e}")

    # ------------------------------------------------------------------
    def yeni_yuk(self, instance):
        """Boş form ile kartı açar (yeni G yükü)."""
        from structload.loads.load_definition import LoadDefinition

        if not self._detay_acik:
            self.detay_ac()

        yeni_id = benzersiz_id_uret("G")
        bos = LoadDefinition(
            id=yeni_id, name="", load_type="G",
            components=[], source="user",
        )
        self.detay_kart.yuk_yukle(bos, None)
        self.bilgi_label.text = f"Yeni yük oluşturuluyor: {yeni_id}"

    # ------------------------------------------------------------------
    def sol_liste_yenile(self):
        kid = self.kategori_map.get(self.kategori_spinner.text)
        if kid:
            self.liste_yenile(kid)

# ============================================================
# YÜK TANIMLAMA PANELİ
# ============================================================

class YukTanimlamaPaneli(BoxLayout):
    """G ve Q yüklerini tanımlama paneli."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.spacing = dp(6)
        self.padding = dp(6)

        self.tabs = TabbedPanel(do_default_tab=False)
        self.tabs.tab_width = dp(140)

        # G sekmesi
        g_tab = TabbedPanelItem(text="Ölü Yük (G)")
        self.g_panel = self._g_paneli_olustur()
        g_tab.add_widget(self.g_panel)
        self.tabs.add_widget(g_tab)

        # Q sekmesi
        q_tab = TabbedPanelItem(text="Hareketli Yük (Q)")
        self.q_panel = self._q_paneli_olustur()
        q_tab.add_widget(self.q_panel)
        self.tabs.add_widget(q_tab)

        self.add_widget(self.tabs)

    # --------------------------------------------------------
    # G PANELİ
    # --------------------------------------------------------
    def _g_paneli_olustur(self):
        layout = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(4))

        # ID / Ad
        ust = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(4))
        ust.add_widget(Label(text="ID:", size_hint_x=0.08))
        self.g_id_input = TextInput(
            text=benzersiz_id_uret("G"), size_hint_x=0.18, multiline=False,
        )
        ust.add_widget(self.g_id_input)
        ust.add_widget(Label(text="Ad:", size_hint_x=0.08))
        self.g_ad_input = TextInput(
            hint_text="Örn: Konut Döşemesi",
            size_hint_x=0.66,
            multiline=False,
        )
        ust.add_widget(self.g_ad_input)
        layout.add_widget(ust)

        # Bileşen başlıkları
        baslik = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(4))
        baslik.add_widget(Label(text="Ad", size_hint_x=0.26, bold=True, font_size=dp(12)))
        baslik.add_widget(Label(text="Tip", size_hint_x=0.16, bold=True, font_size=dp(12)))
        baslik.add_widget(Label(text="Malzeme", size_hint_x=0.20, bold=True, font_size=dp(12)))
        baslik.add_widget(Label(text="Değer", size_hint_x=0.12, bold=True, font_size=dp(12)))
        baslik.add_widget(Label(text="Kalınlık", size_hint_x=0.12, bold=True, font_size=dp(12)))
        baslik.add_widget(Label(text="kN/m²", size_hint_x=0.10, bold=True, font_size=dp(12)))
        baslik.add_widget(Label(text="", size_hint_x=0.04))
        layout.add_widget(baslik)

        # Bileşen listesi
        self.g_bilesen_scroll = ScrollView()
        self.g_bilesen_layout = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(2),
        )
        self.g_bilesen_layout.bind(minimum_height=self.g_bilesen_layout.setter("height"))
        self.g_bilesen_scroll.add_widget(self.g_bilesen_layout)
        layout.add_widget(self.g_bilesen_scroll)

        # Toplam satırı
        self.g_toplam_label = Label(
            text="Toplam: 0.000 kN/m²",
            size_hint_y=None,
            height=dp(28),
            bold=True,
            color=(0.2, 0.5, 0.8, 1),
            halign="right",
        )
        self.g_toplam_label.bind(size=lambda l, s: setattr(l, "text_size", s))
        layout.add_widget(self.g_toplam_label)

        # Butonlar
        btn_layout = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        ekle_btn = Button(text="+ Bileşen Ekle", size_hint_x=0.35)
        ekle_btn.bind(on_press=self.bilesen_ekle)
        btn_layout.add_widget(ekle_btn)

        kaydet_btn = Button(
            text="G Yükünü Kaydet",
            size_hint_x=0.65,
            background_color=(0.2, 0.6, 0.3, 1),
        )
        kaydet_btn.bind(on_press=self.g_yuku_kaydet)
        btn_layout.add_widget(kaydet_btn)
        layout.add_widget(btn_layout)

        self.bilesen_ekle(None)
        return layout

    def bilesen_ekle(self, instance):
        satir = BilesenSatiri(on_change=self._toplam_guncelle)
        self.g_bilesen_layout.add_widget(satir)
        self._toplam_guncelle()

    def _toplam_guncelle(self):
        toplam = 0.0
        for child in self.g_bilesen_layout.children:
            if isinstance(child, BilesenSatiri):
                toplam += child.deger_hesapla()
        self.g_toplam_label.text = f"Toplam: {toplam:.3f} kN/m²"

    def g_yuku_kaydet(self, instance):
        g_id = self.g_id_input.text.strip()
        g_ad = self.g_ad_input.text.strip()

        if not g_id or not g_ad:
            status.error("G yükü: ID ve Ad alanları zorunludur.")
            return

        if g_id in load_manager.definitions:
            status.error(f"'{g_id}' ID'si zaten mevcut.")
            return

        bilesenler = []
        for child in self.g_bilesen_layout.children:
            if isinstance(child, BilesenSatiri):
                comp = child.load_component_olustur()
                if comp is None:
                    status.error("Geçersiz bileşen değeri. Kalınlık veya sayı giriniz.")
                    return
                bilesenler.append(comp)

        if not bilesenler:
            status.error("En az bir bileşen eklemelisiniz.")
            return

        definition = LoadDefinition(
            id=g_id,
            name=g_ad,
            load_type="G",
            components=bilesenler,
            source="user",
        )

        try:
            load_manager.add_definition(definition)
            toplam = definition.calculate(MATERIAL_WEIGHTS)
            status.success(f"[{g_id}] {g_ad} kaydedildi. Toplam: {toplam:.3f} kN/m²")

            # Formu sıfırla
            self.g_id_input.text = benzersiz_id_uret("G")
            self.g_ad_input.text = ""
            for child in list(self.g_bilesen_layout.children):
                self.g_bilesen_layout.remove_widget(child)
            self.bilesen_ekle(None)
        except Exception as e:
            status.error(f"Kayıt hatası: {e}")

    # --------------------------------------------------------
    # Q PANELİ
    # --------------------------------------------------------
    def _q_paneli_olustur(self):
        layout = BoxLayout(orientation="vertical", spacing=dp(6), padding=dp(4))

        ust = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(4))
        ust.add_widget(Label(text="ID:", size_hint_x=0.1))
        self.q_id_input = TextInput(
            text=benzersiz_id_uret("Q"), size_hint_x=0.2, multiline=False,
        )
        ust.add_widget(self.q_id_input)
        ust.add_widget(Label(text="Kullanım:", size_hint_x=0.15))
        self.q_kullanim_spinner = Spinner(
            text="konut",
            values=[k for k, _, _ in canli_yuk_listesi_getir()],
            size_hint_x=0.55,
        )
        self.q_kullanim_spinner.bind(text=self.q_kullanim_degisti)
        ust.add_widget(self.q_kullanim_spinner)
        layout.add_widget(ust)

        self.q_bilgi_label = Label(
            text="",
            size_hint_y=None,
            height=dp(30),
            color=(0.2, 0.4, 0.8, 1),
        )
        layout.add_widget(self.q_bilgi_label)

        deger_layout = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(4))
        deger_layout.add_widget(Label(text="Değer (kN/m²):", size_hint_x=0.3))
        self.q_deger_input = TextInput(
            text="", size_hint_x=0.4, multiline=False, input_filter="float",
        )
        deger_layout.add_widget(self.q_deger_input)
        deger_layout.add_widget(Label(text="", size_hint_x=0.3))
        layout.add_widget(deger_layout)

        kaydet_btn = Button(
            text="Q Yükünü Kaydet",
            size_hint_y=None,
            height=dp(45),
            background_color=(0.2, 0.6, 0.3, 1),
        )
        kaydet_btn.bind(on_press=self.q_yuku_kaydet)
        layout.add_widget(kaydet_btn)

        self.q_kullanim_degisti(self.q_kullanim_spinner, "konut")
        return layout

    def q_kullanim_degisti(self, spinner, text):
        for key, name, value in canli_yuk_listesi_getir():
            if key == text:
                self.q_bilgi_label.text = f"{name}  →  {value} kN/m²"
                self.q_deger_input.text = str(value)
                break

    def q_yuku_kaydet(self, instance):
        q_id = self.q_id_input.text.strip()
        kullanim = self.q_kullanim_spinner.text

        if not q_id:
            status.error("Q yükü: ID alanı zorunludur.")
            return

        if q_id in load_manager.definitions:
            status.error(f"'{q_id}' ID'si zaten mevcut.")
            return

        try:
            deger = float(self.q_deger_input.text)
        except (ValueError, TypeError):
            status.error("Geçerli bir sayı giriniz.")
            return

        ad = kullanim
        for key, name, _ in canli_yuk_listesi_getir():
            if key == kullanim:
                ad = name
                break

        definition = LoadDefinition(
            id=q_id, name=ad, load_type="Q", value=deger, source="TS 498",
        )

        try:
            load_manager.add_definition(definition)
            status.success(f"[{q_id}] {ad} kaydedildi: {deger} kN/m²")
            self.q_id_input.text = benzersiz_id_uret("Q")
        except Exception as e:
            status.error(f"Kayıt hatası: {e}")


# ============================================================
# ELEMAN ATAMA PANELİ
# ============================================================

class ElemanAtamaPaneli(BoxLayout):
    """Seçili elemana G ve Q yükü atama paneli."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.spacing = dp(6)
        self.padding = dp(6)

        self.secili_eleman = None

        eleman_layout = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))
        eleman_layout.add_widget(Label(text="Eleman ID:", size_hint_x=0.2))
        self.eleman_input = TextInput(
            hint_text="Örn: 101, K-12", size_hint_x=0.5, multiline=False,
        )
        eleman_layout.add_widget(self.eleman_input)

        sec_btn = Button(text="Elemanı Seç", size_hint_x=0.3)
        sec_btn.bind(on_press=self.eleman_sec)
        eleman_layout.add_widget(sec_btn)
        self.add_widget(eleman_layout)

        self.eleman_bilgi = Label(
            text="Henüz eleman seçilmedi.",
            size_hint_y=None,
            height=dp(30),
            color=(0.2, 0.4, 0.8, 1),
        )
        self.add_widget(self.eleman_bilgi)

        listeler = BoxLayout(spacing=dp(8))

        # G
        g_box = BoxLayout(orientation="vertical", spacing=dp(4))
        g_box.add_widget(Label(
            text="Ölü Yükler (G)", size_hint_y=None, height=dp(30), bold=True,
        ))
        self.g_scroll = ScrollView()
        self.g_liste = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(2))
        self.g_liste.bind(minimum_height=self.g_liste.setter("height"))
        self.g_scroll.add_widget(self.g_liste)
        g_box.add_widget(self.g_scroll)
        listeler.add_widget(g_box)

        # Q
        q_box = BoxLayout(orientation="vertical", spacing=dp(4))
        q_box.add_widget(Label(
            text="Hareketli Yükler (Q)", size_hint_y=None, height=dp(30), bold=True,
        ))
        self.q_scroll = ScrollView()
        self.q_liste = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(2))
        self.q_liste.bind(minimum_height=self.q_liste.setter("height"))
        self.q_scroll.add_widget(self.q_liste)
        q_box.add_widget(self.q_scroll)
        listeler.add_widget(q_box)

        self.add_widget(listeler)

        self.toplam_label = Label(
            text="",
            size_hint_y=None,
            height=dp(60),
            color=(0.8, 0.2, 0.2, 1),
            bold=True,
        )
        self.add_widget(self.toplam_label)

        atama_btn = Button(
            text="Seçili Yükleri Elemana Ata",
            size_hint_y=None,
            height=dp(45),
            background_color=(0.2, 0.5, 0.8, 1),
        )
        atama_btn.bind(on_press=self.atama_yap)
        self.add_widget(atama_btn)

        self.liste_yenile()

    def liste_yenile(self):
        self.g_liste.clear_widgets()
        for d in sorted(load_manager.definitions.values(), key=lambda x: x.id):
            if d.load_type != "G":
                continue
            try:
                deger = d.calculate(MATERIAL_WEIGHTS)
            except Exception:
                deger = 0.0
            tb = ToggleButton(
                text=f"[{d.id}] {d.name}  ({deger:.3f} kN/m²)",
                size_hint_y=None, height=dp(38),
            )
            tb.load_id = d.id
            self.g_liste.add_widget(tb)

        self.q_liste.clear_widgets()
        for d in sorted(load_manager.definitions.values(), key=lambda x: x.id):
            if d.load_type != "Q":
                continue
            try:
                deger = d.calculate(MATERIAL_WEIGHTS)
            except Exception:
                deger = 0.0
            tb = ToggleButton(
                text=f"[{d.id}] {d.name}  ({deger:.3f} kN/m²)",
                size_hint_y=None, height=dp(38),
            )
            tb.load_id = d.id
            self.q_liste.add_widget(tb)

    def eleman_sec(self, instance):
        elem = self.eleman_input.text.strip()
        if not elem:
            status.error("Eleman ID boş olamaz.")
            return
        self.secili_eleman = elem
        self.eleman_bilgi.text = f"Seçili eleman: {elem}"
        status.info(f"Eleman seçildi: {elem}")
        self.toplam_guncelle()

    def _secili_yukleri_al(self, liste_layout):
        return [
            child.load_id
            for child in liste_layout.children
            if isinstance(child, ToggleButton) and child.state == "down"
        ]

    def atama_yap(self, instance):
        if self.secili_eleman is None:
            status.error("Önce bir eleman seçin.")
            return

        secili_g = self._secili_yukleri_al(self.g_liste)
        secili_q = self._secili_yukleri_al(self.q_liste)

        if not secili_g and not secili_q:
            status.error("En az bir yük seçin.")
            return

        for load_id in secili_g + secili_q:
            try:
                load_manager.assign(self.secili_eleman, load_id)
            except Exception as e:
                status.error(f"Atama hatası: {e}")
                return

        self.toplam_guncelle()
        status.success(
            f"{self.secili_eleman} elemanına {len(secili_g)} G ve {len(secili_q)} Q yükü atandı."
        )

    def toplam_guncelle(self):
        if self.secili_eleman is None:
            return
        try:
            g_top = load_manager.get_element_total(self.secili_eleman, "G")
            q_top = load_manager.get_element_total(self.secili_eleman, "Q")
            self.toplam_label.text = (
                f"Toplam Ölü Yük (G): {g_top:.3f} kN/m²\n"
                f"Toplam Hareketli Yük (Q): {q_top:.3f} kN/m²"
            )
        except Exception as e:
            self.toplam_label.text = f"Hata: {e}"

# gui/panels.py içindeki RaporPaneli'ni bununla değiştirin

from pathlib import Path
from structload.utils.my_document import myDocument  # opsiyonel, yoksa try/except

# ============================================================
# RAPOR PANELİ (ReportDataFrame + Word Export)
# ============================================================

class RaporPaneli(BoxLayout):
    """
    ReportDataFrame kullanarak yük raporu oluşturur.
    - test kodundaki create_report_tables() mantığıyla çalışır
    - Word belgesine aktarılabilir (myDocument)
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.spacing = dp(6)
        self.padding = dp(6)

        # Üst buton çubuğu
        btn_layout = BoxLayout(size_hint_y=None, height=dp(45), spacing=dp(6))

        yenile_btn = Button(text="Raporu Yenile", size_hint_x=0.4)
        yenile_btn.bind(on_press=self.rapor_yenile)
        btn_layout.add_widget(yenile_btn)

        export_btn = Button(
            text="📄 Word'e Aktar",
            size_hint_x=0.4,
            background_color=(0.2, 0.5, 0.8, 1),
        )
        export_btn.bind(on_press=self.word_export)
        btn_layout.add_widget(export_btn)

        # Debug export
        debug_btn = Button(text="🐛", size_hint_x=0.2)
        debug_btn.bind(on_press=self._debug_df_yazdir)
        btn_layout.add_widget(debug_btn)

        self.add_widget(btn_layout)

        # Rapor scroll
        self.scroll = ScrollView()
        self.rapor_layout = BoxLayout(
            orientation="vertical", size_hint_y=None, spacing=dp(12),
        )
        self.rapor_layout.bind(minimum_height=self.rapor_layout.setter("height"))
        self.scroll.add_widget(self.rapor_layout)
        self.add_widget(self.scroll)

        # Son oluşturulan tablolar (Word export için)
        self._tables: list[ReportDataFrame] = []

    # ==========================================================
    # create_report_tables() benzeri — test kodundaki yapı
    # ==========================================================
    def _create_report_tables(self) -> list:
        """Test kodundaki create_report_tables() ile aynı mantık."""
        tables = []
        lm = load_manager

        # ---- 1. Proje / Sistem Özeti ----
        project_info = {
            "Parametre": [
                "Sistem Adı",
                "Yük Standardı",
                "Toplam Tanımlı Yük",
                "Toplam Atama",
            ],
            "Değer": [
                "Yük Atama Sistemi",
                "TS 498 / TS EN 1991-1-1",
                str(len(load_manager.definitions)),
                str(len(load_manager.assignments)),
            ],
        }
        df_project = ReportDataFrame(
            project_info,
            custom_title="1. Sistem Özeti",
            custom_desc="Rapor içeriğine ait genel bilgiler.",
        )
        tables.append(df_project)

        # ---- 2. Tanımlı Yükler (G ve Q) ----
        yuk_satirlari = []
        for d in sorted(load_manager.definitions.values(), key=lambda x: x.id):
            try:
                deger = d.calculate(MATERIAL_WEIGHTS)
            except Exception:
                deger = 0.0
            yuk_satirlari.append({
                "ID": d.id,
                "Yük Adı": d.name,
                "Tip": d.load_type,
                "Değer (kN/m²)": round(deger, 3),
                "Kaynak": d.source or "-",
            })

        df_yukler = ReportDataFrame(
            yuk_satirlari if yuk_satirlari else [{"ID": "-", "Yük Adı": "Tanımlı yük yok",
                                                   "Tip": "-", "Değer (kN/m²)": 0,
                                                   "Kaynak": "-"}],
            custom_title="2. Tanımlı Yükler",
            custom_desc="Sistemde tanımlı ölü (G) ve hareketli (Q) yükler.",
            column_units={"Değer (kN/m²)": "kN/m²"},
        )
        tables.append(df_yukler)
        # 3. YÜK ANALİZLERİ (bileşen dökümü)
        analizler = []
        for d in sorted(lm.definitions.values(), key=lambda x: x.id):
            analizler.append(self._analiz_df(d))

        if analizler:
            # Her analiz ayrı bir tablo olarak listeye eklenir
            for df in analizler:
                tables.append(df)
        else:
            tables.append(ReportDataFrame(
                [{"Bilgi": "Analiz edilecek yük tanımı yok."}],
                custom_title="3. Yük Analizleri",
                custom_desc="Tanımlı yüklerin bileşen bazlı dökümü.",
            ))

        # ---- 4. Eleman Atamaları ----
        atama_satirlari = []
        for elem_id, assignment in load_manager.assignments.items():
            g_ids = assignment.get("G", [])
            q_ids = assignment.get("Q", [])
            if not g_ids and not q_ids:
                continue
            try:
                g_top = load_manager.get_element_total(elem_id, "G")
                q_top = load_manager.get_element_total(elem_id, "Q")
            except Exception:
                g_top = q_top = 0.0
            atama_satirlari.append({
                "Eleman ID": str(elem_id),
                "G (kN/m²)": round(g_top, 3),
                "G Yükleri": ", ".join(g_ids) if g_ids else "-",
                "Q (kN/m²)": round(q_top, 3),
                "Q Yükleri": ", ".join(q_ids) if q_ids else "-",
            })

        df_atama = ReportDataFrame(
            atama_satirlari if atama_satirlari else [{
                "Eleman ID": "-", "G (kN/m²)": 0, "G Yükleri": "-",
                "Q (kN/m²)": 0, "Q Yükleri": "-",
            }],
            custom_title="3. Eleman Atamaları",
            custom_desc="Her elemana atanmış yükler ve toplam değerler.",
            column_units={"G (kN/m²)": "kN/m²", "Q (kN/m²)": "kN/m²"},
        )
        tables.append(df_atama)

        return tables

    # ==========================================================
    # ReportDataFrame → Kivy widget
    # ==========================================================
    def _df_widget(self, df: ReportDataFrame):
        """ReportDataFrame'i Kivy tablo görünümüne çevirir."""
        box = BoxLayout(
            orientation="vertical",
            size_hint_y=None,
            spacing=dp(4),
            padding=dp(6),
        )
        box.bind(minimum_height=box.setter("height"))

        # Arka plan kart efekti
        with box.canvas.before:
            Color(0.97, 0.97, 0.98, 1)
            rect = Rectangle(pos=box.pos, size=box.size)
        box.bind(
            pos=lambda *a: setattr(rect, "pos", box.pos),
            size=lambda *a: setattr(rect, "size", box.size),
        )

        # --- Başlık ---
        if df.custom_title:
            box.add_widget(Label(
                text=df.custom_title,
                size_hint_y=None,
                height=dp(32),
                bold=True,
                color=(0.15, 0.30, 0.55, 1),
                font_size=dp(15),
                halign="left",
                valign="middle",
            ))

        # --- Açıklama ---
        if df.custom_desc:
            desc = df.custom_desc.strip()
            # Yüksekliği satır sayısına göre ayarla
            n_lines = desc.count("\n") + 1 + len(desc) // 80
            desc_label = Label(
                text=desc,
                size_hint_y=None,
                height=dp(16) * n_lines,
                color=(0.4, 0.4, 0.45, 1),
                font_size=dp(11),
                halign="left",
                valign="top",
            )
            desc_label.bind(size=lambda l, s: setattr(l, "text_size", s))
            box.add_widget(desc_label)

        if df.empty:
            box.add_widget(Label(
                text="Gösterilecek veri yok.",
                size_hint_y=None, height=dp(28),
                color=(0.6, 0.6, 0.6, 1),
            ))
            return box

        # --- Tablo ---
        # Sütun genişliklerini içeriğe göre tahmin et
        col_names = [str(c) for c in df.columns]
        n_cols = len(col_names)

        # İlk sütun biraz daha geniş olsun
        widths = []
        for i, col in enumerate(col_names):
            max_len = len(col)
            try:
                for v in df[df.columns[i]].astype(str):
                    max_len = max(max_len, len(v))
            except Exception:
                pass
            widths.append(max(0.5, min(max_len / 25.0, 2.5)))
        total_w = sum(widths) or 1
        size_hints = [w / total_w for w in widths]

        grid = GridLayout(
            cols=n_cols,
            size_hint_y=None,
            spacing=dp(1),
            padding=dp(1),
        )
        grid.bind(minimum_height=grid.setter("height"))

        # Başlık satırı (koyu arka plan)
        for i, col in enumerate(col_names):
            lbl = Label(
                text=col,
                bold=True,
                color=(1, 1, 1, 1),
                size_hint_y=None,
                height=dp(30),
                size_hint_x=size_hints[i],
                font_size=dp(12),
                halign="center",
                valign="middle",
            )
            lbl.bind(size=lambda l, s: setattr(l, "text_size", s))
            grid.add_widget(lbl)

        # Birim satırı
        if df.column_units:
            for i, col in enumerate(df.columns):
                unit_lbl = Label(
                    text=df.column_units.get(col, ""),
                    italic=True,
                    color=(0.55, 0.55, 0.6, 1),
                    size_hint_y=None,
                    height=dp(20),
                    size_hint_x=size_hints[i],
                    font_size=dp(10),
                )
                grid.add_widget(unit_lbl)

        # Veri satırları (zebra)
        for row_idx, (_, row) in enumerate(df.iterrows()):
            bg = (0.94, 0.94, 0.97, 1) if row_idx % 2 else (1, 1, 1, 1)
            for i, val in enumerate(row.values):
                cell_box = BoxLayout(
                    size_hint_y=None,
                    height=dp(26),
                    size_hint_x=size_hints[i],
                )
                with cell_box.canvas.before:
                    Color(*bg)
                    Rectangle(pos=cell_box.pos, size=cell_box.size)
                cell_box.bind(
                    pos=lambda w, p: setattr(w.canvas.before.children[-1], "pos", p),
                    size=lambda w, s: setattr(w.canvas.before.children[-1], "size", s),
                )
                lbl = Label(
                    text=str(val),
                    color=(0.1, 0.1, 0.15, 1),
                    font_size=dp(11),
                    halign="center",
                    valign="middle",
                )
                lbl.bind(size=lambda l, s: setattr(l, "text_size", s))
                cell_box.add_widget(lbl)
                grid.add_widget(cell_box)

        box.add_widget(grid)
        return box

        # ------------------------------------------------------------------
    def _analiz_df(self, d) -> ReportDataFrame:
        """
        Tek bir LoadDefinition için bileşen bazlı analiz tablosu.
        Formatı snow_load.report() ile uyumlu.
        """
        satirlar = []
        toplam = 0.0

        for i, comp in enumerate(d.components or [], 1):
            try:
                comp_val = comp.calculate(MATERIAL_WEIGHTS)
            except Exception:
                comp_val = 0.0
            toplam += comp_val

            # Malzeme veya sabit değer bilgisi
            if getattr(comp, "material", None):
                tip = "Malzeme"
                detay = (
                    f"{comp.material} × "
                    f"{(comp.thickness or 0) * 1000:.0f} mm"
                )
            else:
                tip = "Sabit"
                detay = "—"

            satirlar.append({
                "#": i,
                "Bileşen": comp.name or "-",
                "Tip": tip,
                "Detay": detay,
                "Değer": round(comp_val, 3),
            })

        # Toplam satırı
        if satirlar:
            satirlar.append({
                "#": "",
                "Bileşen": "",
                "Tip": "",
                "Detay": "TOPLAM",
                "Değer": round(toplam, 3),
            })

        aciklama = (
            f"Yük Tipi: {d.load_type}  |  "
            f"Kaynak: {d.source or '-'}  |  "
            f"Bileşen Sayısı: {len(d.components or [])}"
        )
        if d.description:
            aciklama += f"\n{d.description}"

        return ReportDataFrame(
            satirlar if satirlar else [{
                "#": "", "Bileşen": "-", "Tip": "-",
                "Detay": "-", "Değer": 0.0,
            }],
            custom_title=f"Yük Analizi — [{d.id}] {d.name}",
            custom_desc=aciklama,
            column_units={"Değer": "kN/m²"},
        )
    
    # ==========================================================
    # Rapor yenile (test kodundaki main() benzeri)
    # ==========================================================
    def rapor_yenile(self, instance=None):
        self.rapor_layout.clear_widgets()
        self._tables = self._create_report_tables()

        for table in self._tables:
            try:
                # Yuvarlama (test kodundaki gibi)
                if hasattr(table, "round_floats"):
                    table = table.round_floats(2)
                self.rapor_layout.add_widget(self._df_widget(table))
            except Exception as e:
                status.error(f"Tablo gösterilemedi: {e}")

        status.success("Rapor yenilendi.")

    # ==========================================================
    # Word export — test kodundaki main() ile aynı akış
    # ==========================================================
    def word_export(self, instance):
        try:
            from structload.utils.my_document import myDocument
        except ImportError:
            status.error("myDocument bulunamadı. utils/my_document.py gerekli.")
            return

        try:
            doc = myDocument()
            doc.apply_visual_settings()

            # Ana başlık
            doc.add_heading_numbered("YÜK ATAMA RAPORU", level=1)
            doc.add_paragraph(
                "Bu rapor TS 498 ve TS EN 1991-1-1 yönetmelikleri kullanılarak "
                "otomatik oluşturulmuştur."
            )
            doc.doc.add_paragraph()

            # Tabloları ekle
            for i, table in enumerate(self._tables, 1):
                try:
                    if hasattr(table, "round_floats"):
                        table = table.round_floats(2)
                    table.save_to_docx(doc, level=2)
                except Exception as e:
                    status.warning(f"Tablo {i} eklenemedi: {e}")

            # Kaydet
            report_path = "yuk_atama_raporu.docx"
            success = doc.save_report(report_path)

            if success:
                status.success(f"Rapor kaydedildi: {report_path}")
            else:
                status.error("Rapor kaydedilemedi.")
        except Exception as e:
            status.error(f"Word export hatası: {e}")

    # ==========================================================
    # Debug: DataFrame'i konsola yazdır
    # ==========================================================
    def _debug_df_yazdir(self, instance):
        for i, df in enumerate(self._tables, 1):
            print(f"\n===== Tablo {i}: {df.custom_title} =====")
            print(df.to_string())
            print(f"Shape: {df.shape}, Columns: {list(df.columns)}")

# ============================================================
# DEAD / LIVE CONFIG EXPORT
# ============================================================

def export_dead_config() -> dict:
    definitions = []
    for d in load_manager.definitions.values():
        if d.load_type != "G":
            continue
        try:
            value = d.calculate(MATERIAL_WEIGHTS)
        except Exception:
            value = 0.0
        definitions.append({
            "id": d.id, "name": d.name, "load_type": d.load_type,
            "value": round(value, 4),
            "unit": getattr(d, "unit", "kN/m²"),
            "source": d.source,
            "description": d.description,
        })

    assignments = {}
    for elem_id, kinds in load_manager.assignments.items():
        g_ids = list(kinds.get("G", []))
        if g_ids:
            assignments[str(elem_id)] = {"G": g_ids}

    return {"definitions": definitions, "assignments": assignments}


def export_live_config() -> dict:
    definitions = []
    for d in load_manager.definitions.values():
        if d.load_type != "Q":
            continue
        try:
            value = d.calculate(MATERIAL_WEIGHTS)
        except Exception:
            value = 0.0
        definitions.append({
            "id": d.id, "name": d.name, "load_type": d.load_type,
            "value": round(value, 4),
            "unit": getattr(d, "unit", "kN/m²"),
            "source": d.source,
            "description": d.description,
        })

    assignments = {}
    for elem_id, kinds in load_manager.assignments.items():
        q_ids = list(kinds.get("Q", []))
        if q_ids:
            assignments[str(elem_id)] = {"Q": q_ids}

    return {"definitions": definitions, "assignments": assignments}


# ============================================================
# ANA UYGULAMA
# ============================================================

class YukAtamaApp(App):

    def build(self):
        self.title = "Yük Atama Sistemi - TS 498"

        root = BoxLayout(orientation="vertical")

        # Üst: tablar
        tabs = TabbedPanel(do_default_tab=False)
        tabs.tab_width = dp(150)

        tanim_tab = TabbedPanelItem(text="1. Yük Tanımla")
        tanim_tab.add_widget(YukTanimlamaPaneli())
        tabs.add_widget(tanim_tab)

        hazir_tab = TabbedPanelItem(text="2. Hazır Yükler")
        self.hazir_panel = HazirYukPaneli()
        hazir_tab.add_widget(self.hazir_panel)
        tabs.add_widget(hazir_tab)

        atama_tab = TabbedPanelItem(text="3. Elemana Ata")
        self.atama_panel = ElemanAtamaPaneli()
        atama_tab.add_widget(self.atama_panel)
        tabs.add_widget(atama_tab)

        rapor_tab = TabbedPanelItem(text="4. Rapor")
        self.rapor_panel = RaporPaneli()
        rapor_tab.add_widget(self.rapor_panel)
        tabs.add_widget(rapor_tab)

        # 5) Debug
        debug_tab = TabbedPanelItem(text="5. Debug")
        self.debug_panel = DebugPanel()
        debug_tab.add_widget(self.debug_panel)
        tabs.add_widget(debug_tab)

        tabs.bind(current_tab=self.sekme_degisti)
        root.add_widget(tabs)

        # Alt: durum çubuğu
        self.status_bar = StatusBar(on_log_button=self._log_tabina_git)
        self._tabs = tabs
        root.add_widget(self.status_bar)

        status.info("Yük Atama Sistemi başlatıldı.")
        return root

    def _log_tabina_git(self, instance):
        for tab in self._tabs.tab_list:
            if tab.text == "5. Debug":
                self._tabs.switch_to(tab)
                break

    def sekme_degisti(self, instance, value):
        if hasattr(self, "atama_panel"):
            self.atama_panel.liste_yenile()
        if hasattr(self, "rapor_panel"):
            self.rapor_panel.rapor_yenile()


if __name__ == "__main__":
    YukAtamaApp().run()