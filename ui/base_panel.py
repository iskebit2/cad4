# ui/base_panel.py
"""
BasePanel — Tüm ImGui panellerinin ortak iskeleti.

Alt sınıflar sadece draw_content() yazar. Base:
  - begin/end + başlık + kapatma butonu
  - ilk açılış konumu (FIRST_USE_EVER)
  - focus/hover durumu (is_hovered, is_focused)
  - focus renk efekti (başlık rengi)
  - hata yakalama (draw_content'te exception)
  - genişlik/yükseklik yönetimi
  - aç/kapa API

Kullanım:
    class MyPanel(BasePanel):
        def __init__(self):
            super().__init__(title="Panelim", width=380, height=560,
                             pos_first_use=(500, 100))
        def draw_content(self):
            imgui.text("Merhaba")
            if imgui.button("Tıkla"):
                ...

    panel = MyPanel()
    panel.open()
    # her frame: panel.draw()
"""
from typing import Optional, Tuple

import imgui


class BasePanel:

    # Focus renk tonları — alt sınıf override edebilir
    TITLE_NORMAL       = (0.10, 0.13, 0.18, 1.00)
    TITLE_NORMAL_ACT   = (0.16, 0.20, 0.28, 1.00)
    TITLE_HOVERED      = (0.15, 0.30, 0.45, 1.00)
    TITLE_HOVERED_ACT  = (0.20, 0.40, 0.60, 1.00)
    TITLE_FOCUSED      = (0.20, 0.50, 0.75, 1.00)
    TITLE_FOCUSED_ACT  = (0.25, 0.60, 0.90, 1.00)

    def __init__(
        self,
        title: str = "Panel",
        width: float = 380.0,
        height: float = 560.0,
        pos_first_use: Optional[Tuple[float, float]] = None,
        closable: bool = True,
        window_flags: int = 0,
    ):
        self.title = title
        self.width = width
        self.height = height
        self.pos_first_use = pos_first_use
        self.closable = closable
        self.window_flags = window_flags

        # State
        self.visible = False
        self.is_hovered = False
        self.is_focused = False
        self._first_open = True

        # Özel: alt sınıfların değiştirebileceği ayarlar
        self._want_close = False   # bu frame'de X'e basıldı mı?

    # ==================================================================
    # Yaşam döngüsü
    # ==================================================================
    def open(self):
        """Paneli aç. Alt sınıflar override edebilir (scene vermek vs.)."""
        self.visible = True
        self._first_open = True

    def close(self):
        """Paneli kapat."""
        self.visible = False
        self.is_hovered = False
        self.is_focused = False

    def toggle(self):
        if self.visible:
            self.close()
        else:
            self.open()

    # ==================================================================
    # Ana draw — begin/end burada
    # ==================================================================
    def draw(self):
        if not self.visible:
            return

        self._position_window()
        self._push_title_colors()

        expanded, opened = imgui.begin(self.title, self.closable,
                                       self.window_flags)

        self._pop_title_colors()

        if not opened:
            # Kullanıcı X'e bastı
            self._want_close = True
            self.close()
            imgui.end()
            return

        self._want_close = False

        # --- İçerik (alt sınıf) ---
        try:
            self.draw_content()
        except Exception:
            import traceback
            traceback.print_exc()
            imgui.text_colored("İçerik hatası (konsola bak)",
                               1.0, 0.4, 0.4, 1.0)

        # --- Focus state (end'den önce) ---
        self.is_hovered = imgui.is_window_hovered()
        self.is_focused = imgui.is_window_focused()

        imgui.end()

    # ==================================================================
    # Alt sınıf override eder
    # ==================================================================
    def draw_content(self):
        imgui.text(f"{self.title} — içerik yok")

    # ==================================================================
    # İç yardımcılar
    # ==================================================================
    def _position_window(self):
        if not self._first_open:
            return
        if self.pos_first_use is not None:
            imgui.set_next_window_position(
                self.pos_first_use[0], self.pos_first_use[1],
                condition=imgui.FIRST_USE_EVER,
            )
        imgui.set_next_window_size(
            self.width, self.height,
            condition=imgui.FIRST_USE_EVER,
        )
        self._first_open = False

    def _push_title_colors(self):
        if self.is_focused:
            imgui.push_style_color(imgui.COLOR_TITLE_BACKGROUND,
                                   *self.TITLE_FOCUSED)
            imgui.push_style_color(imgui.COLOR_TITLE_BACKGROUND_ACTIVE,
                                   *self.TITLE_FOCUSED_ACT)
        elif self.is_hovered:
            imgui.push_style_color(imgui.COLOR_TITLE_BACKGROUND,
                                   *self.TITLE_HOVERED)
            imgui.push_style_color(imgui.COLOR_TITLE_BACKGROUND_ACTIVE,
                                   *self.TITLE_HOVERED_ACT)
        else:
            imgui.push_style_color(imgui.COLOR_TITLE_BACKGROUND,
                                   *self.TITLE_NORMAL)
            imgui.push_style_color(imgui.COLOR_TITLE_BACKGROUND_ACTIVE,
                                   *self.TITLE_NORMAL_ACT)

    def _pop_title_colors(self):
        imgui.pop_style_color(2)

    # ==================================================================
    # Yardımcı metotlar — alt sınıflar kullanabilir
    # ==================================================================
    @staticmethod
    def ascii_arrow(is_open: bool) -> str:
        """Genişletilmiş şık ok işaretleri."""
        return "▼" if is_open else ">"  # veya  "▾" ve "▸" 

    @staticmethod
    def ascii_check(checked: bool) -> str:
        return "[x]" if checked else "[ ]"