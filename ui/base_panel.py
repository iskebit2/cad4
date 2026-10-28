# ui/base_panel.py
from __future__ import annotations


class BasePanel:
    """
    Tüm panellerin ortak tabanı.

    - Görünürlük, pencere boyutu/konumu, toolbar entegrasyonu burada.
    - `set_context(ctx)` varsayılanı ctx'i attribute olarak yazar.
    - Alt sınıflar `super().__init__(title=..., width=..., height=..., pos_first_use=...)`
      çağırıp kendi alanlarını ekler.
    """

    visible: bool = False
    app = None

    def __init__(
        self,
        title: str = "Panel",
        width: float = 420.0,
        height: float = 480.0,
        pos_first_use: tuple[float, float] = (100.0, 100.0),
        **kwargs,                       # alt sınıf ekstra parametre geçirirse sessizce yut
    ):
        self.title = title
        self.width = float(width)
        self.height = float(height)
        self.pos_first_use = tuple(pos_first_use)

        self.app = None
        self.visible = False

        # alt sınıf __init__ sonuna eklerken kullanabilir
        for k, v in kwargs.items():
            setattr(self, k, v)

    # ------------------------------------------------------------------
    # Yaşam döngüsü
    # ------------------------------------------------------------------
    def open(self, **kwargs):
        self.visible = True

    def close(self):
        self.visible = False

    # ------------------------------------------------------------------
    # Bağlam
    # ------------------------------------------------------------------
    def set_context(self, ctx: dict):
        for k, v in (ctx or {}).items():
            setattr(self, k, v)

    # ------------------------------------------------------------------
    # ImGui çizim iskeleti — alt sınıf `draw_content()` yazar
    # ------------------------------------------------------------------
    def draw(self):
        if not self.visible:
            return
        from imgui_bundle import imgui
        imgui.set_next_window_size(
            imgui.ImVec2(self.width, self.height), imgui.Cond_.first_use_ever
        )
        imgui.set_next_window_pos(
            imgui.ImVec2(*self.pos_first_use), imgui.Cond_.first_use_ever
        )

        expanded, opened = imgui.begin(self.title, True)
        try:
            if not opened:
                self.close()
                return
            if expanded:
                self.draw_content()
        finally:
            imgui.end()

    def draw_content(self):
        """Alt sınıf override eder."""
