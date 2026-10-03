# gui/report_panel.py
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.metrics import dp
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle
from structload.data.material_data import MATERIAL_WEIGHTS, LIVE_LOADS
from structload.data.preset_loader import PresetLibrary

from structload.loads.load_definition import LoadDefinition, LoadComponent
from structload.loads.load_manager import LoadManager

from structload.utils.status_manager import status
from structload.utils.report_dataframe import ReportDataFrame
from structload.gui.status_bar import StatusBar
from structload.gui.debug_panel import DebugPanel

from pathlib import Path
from structload.utils.my_document import myDocument  # opsiyonel, yoksa try/except


load_manager = LoadManager(material_weights=MATERIAL_WEIGHTS)

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
        self.rapor_yenile()

    # ==========================================================
    # create_report_tables() benzeri — test kodundaki yapı
    # ==========================================================
    def _create_report_tables(self) -> list:
        """Test kodundaki create_report_tables() ile aynı mantık."""
        tables = []

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

        # ---- 3. Eleman Atamaları ----
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