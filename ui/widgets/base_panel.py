# ui/base_panel.py
from __future__ import annotations
from imgui_bundle import imgui

class BasePanel:
    """
    Tüm panellerin ortak tabanı — Dinamik başlık ve sabit status bar destekli.
    """

    visible: bool = False
    app = None

    def __init__(
        self,
        title: str = "Panel",
        width: float = 420.0,
        height: float = 480.0,
        pos_first_use: tuple[float, float] = (100.0, 100.0),
        **kwargs,
    ):
        self._base_title = title
        self.title = title
        self.width = float(width)
        self.height = float(height)
        self.pos_first_use = tuple(pos_first_use)

        self.app = None
        self.visible = False

        # Status bar state'leri
        self._status_text: str = ""
        self._status_color: imgui.ImVec4 = imgui.ImVec4(0.7, 0.7, 0.7, 1.0) # Bilgi
        self._status_timeout: float = 0.0

        for k, v in kwargs.items():
            setattr(self, k, v)

    def open(self, **kwargs):
        self.visible = True

    def close(self):
        self.visible = False

    def set_context(self, ctx: dict):
        for k, v in (ctx or {}).items():
            setattr(self, k, v)

    # ------------------------------------------------------------------
    # Dinamik Arayüz API'leri (Alt sınıflar rahatça kullanır)
    # ------------------------------------------------------------------
    def set_title(self, title: str):
        """Pencere başlığını dinamik olarak değiştirir."""
        self.title = title

    def set_status(self, text: str, kind: str = "info"):
        """Durum çubuğuna mesaj yazar (info, success, warning, error)."""
        self._status_text = text
        if kind == "success":
            self._status_color = imgui.ImVec4(0.3, 0.85, 0.4, 1.0)
        elif kind == "warning":
            self._status_color = imgui.ImVec4(0.95, 0.75, 0.3, 1.0)
        elif kind == "error":
            self._status_color = imgui.ImVec4(0.95, 0.4, 0.4, 1.0)
        else:
            self._status_color = imgui.ImVec4(0.7, 0.8, 0.9, 1.0)

    # ------------------------------------------------------------------
    # ImGui Çizim İskeleti
    # ------------------------------------------------------------------
    def draw(self):
        if not self.visible:
            return

        imgui.set_next_window_size(
            imgui.ImVec2(self.width, self.height), imgui.Cond_.first_use_ever
        )
        imgui.set_next_window_pos(
            imgui.ImVec2(*self.pos_first_use), imgui.Cond_.first_use_ever
        )

        window_id = f"{self.title}###PolygonPropertiesUniqueWindow"
        expanded, opened = imgui.begin(window_id, True)
        try:
            if not opened:
                self.close()
                return
            if expanded:
                # İçerik ve Status Bar'ı ayırmak için dinamik yükseklik hesabı
                avail_size = imgui.get_content_region_avail()
                has_status = bool(self._status_text)
                content_height = avail_size.y - (30.0 if has_status else 0.0)

                # Ana içerik alanı (Scroll edilebilir)
                imgui.begin_child("##panel_content", imgui.ImVec2(avail_size.x, max(50.0, content_height)), False)

                try:
                    self.draw_content()
                finally:
                    imgui.end_child()

                # Sabit Status Bar (Pencerenin en altına yapışır)
                if has_status:
                    imgui.separator()
                    imgui.spacing()
                    imgui.text_colored(self._status_color, self._status_text)
        finally:
            imgui.end()

    def draw_content(self):
        """Alt sınıf override eder."""
        pass