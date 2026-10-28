# ui/file_dialog.py

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from imgui_bundle import imgui

Mode = Literal["open", "save"]


@dataclass
class _Entry:
    name: str
    is_dir: bool
    full: str


class ImGuiFileDialog:
    """Basit ImGui dosya seçici.

    mode: "open" veya "save"
    """

    # Sabitler
    DEFAULT_FILTERS: tuple[str, ...] = (".json",)
    WINDOW_SIZE = (640.0, 480.0)
    LIST_MIN_HEIGHT = 120.0

    def __init__(self) -> None:
        # Görünürlük / mod
        self.visible: bool = False
        self.mode: Mode = "open"
        self.title: str = "Dosya Seç"

        # Filtreler (küçük harfe normalize edilmiş)
        self.filters: list[str] = list(self.DEFAULT_FILTERS)

        # Callback'ler
        self.on_select: Callable[[str], None] | None = None
        self.on_cancel: Callable[[], None] | None = None

        # Navigasyon
        self.current_dir: str = os.path.abspath(os.getcwd())
        self.selected_file: str | None = None
        self.filename_input: str = ""
        self.error: str = ""

        # Pencere konumlandırma
        self._center_next: bool = True

        # Dizin içeriği önbelleği
        self._entries: list[_Entry] = []
        self._cache_key: str | None = None

    # ------------------------------------------------------------------
    # Genel API
    # ------------------------------------------------------------------
    def open(
        self,
        mode: Mode = "open",
        filters: list[str] | None = None,
        title: str = "Dosya Seç",
        initial_dir: str | None = None,
        default_name: str = "",
        on_select: Callable[[str], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
    ) -> None:
        if mode not in ("open", "save"):
            raise ValueError(f"Geçersiz mod: {mode!r}")

        self.visible = True
        self.mode = mode
        self.title = title
        self.filters = [f.lower() for f in (filters or self.DEFAULT_FILTERS)]
        self.on_select = on_select
        self.on_cancel = on_cancel

        self.error = ""
        self.selected_file = None
        self.filename_input = default_name
        self._center_next = True
        self._cache_key = None  # içeriği yeniden oku

        if initial_dir:
            self._navigate_to(initial_dir)

    def close(self, cancelled: bool = False) -> None:
        """Pencereyi kapat. `cancelled=True` ise `on_cancel` tetiklenir."""
        if not self.visible:
            return
        self.visible = False
        if cancelled:
            cb = self.on_cancel
            if callable(cb):
                cb()

    # ------------------------------------------------------------------
    # Çizim
    # ------------------------------------------------------------------
    def draw(self) -> None:
        if not self.visible:
            return

        if self._center_next:
            io = imgui.get_io()
            w, h = self.WINDOW_SIZE
            x = max(0.0, (io.display_size.x - w) * 0.5)
            y = max(0.0, (io.display_size.y - h) * 0.5)
            imgui.set_next_window_pos(imgui.ImVec2(x, y), imgui.Cond_.appearing)
            imgui.set_next_window_size(imgui.ImVec2(w, h), imgui.Cond_.appearing)
            self._center_next = False

        flags = (
            imgui.WindowFlags_.no_resize
            | imgui.WindowFlags_.no_collapse
            | imgui.WindowFlags_.no_saved_settings
        )

        expanded, opened = imgui.begin(self.title, True, flags)
        try:
            if not opened:
                self.close(cancelled=True)
                return
            if not expanded:
                return

            self._draw_dir_bar()
            imgui.separator()
            self._draw_entry_list()
            imgui.separator()
            self._draw_footer()
        finally:
            imgui.end()

    # ------------------------------------------------------------------
    # Alt bölümler
    # ------------------------------------------------------------------
    def _draw_dir_bar(self) -> None:
        imgui.text("Klasör:")
        imgui.same_line()

        imgui.push_item_width(-90)
        # "Enter" ile onayla → _dir_input_committed
        changed, new_dir = imgui.input_text("##dir", self.current_dir)
        enter = imgui.is_key_pressed(imgui.Key.enter) and imgui.is_item_focused()
        if (changed or enter) and os.path.isdir(new_dir):
            self._navigate_to(new_dir)
        imgui.pop_item_width()

        # Sadece Enter ile (veya focus kaybı + geçerliyse) uygula
        if changed and os.path.isdir(new_dir):
            self._navigate_to(new_dir)

        imgui.same_line()
        if imgui.button("Yukarı"):
            parent = os.path.dirname(self.current_dir.rstrip(os.sep))
            if parent and os.path.isdir(parent) and parent != self.current_dir:
                self._navigate_to(parent)

    def _draw_entry_list(self) -> None:
        # Kalan alandan footer + dosya adı için pay ayır
        footer_h = imgui.get_text_line_height() + 16.0  # buton satırı
        fname_h = imgui.get_text_line_height() + 8.0 if self.mode == "save" else imgui.get_text_line_height()
        err_h = imgui.get_text_line_height() + 4.0 if self.error else 0.0
        list_h = max(
            self.LIST_MIN_HEIGHT,
            imgui.get_content_region_avail().y - footer_h - fname_h - err_h - 24.0,
        )

        imgui.begin_child(
            "##entries", imgui.ImVec2(0, list_h), imgui.ChildFlags_.borders
        )
        try:
            self._refresh_entries()

            # Üst klasör satırı list en üstte
            parent = os.path.dirname(self.current_dir.rstrip(os.sep))
            if parent and parent != self.current_dir:
                if imgui.selectable("[..]  üst klasör##parent", False)[0]:
                    self._navigate_to(parent)

            for entry in self._entries:
                icon = "[D]" if entry.is_dir else "   "
                label = f"{icon}  {entry.name}"
                selected = (self.selected_file == entry.full)

                # push_id ile label çakışmalarını önle
                imgui.push_id(entry.full)
                clicked = imgui.selectable(label, selected)[0]
                imgui.pop_id()

                if clicked:
                    if entry.is_dir:
                        self._navigate_to(entry.full)
                        break
                    self.selected_file = entry.full
                    self.filename_input = entry.name
                    self.error = ""
        finally:
            imgui.end_child()

    def _draw_footer(self) -> None:
        # Hata
        if self.error:
            imgui.text_colored(imgui.ImVec4(1.0, 0.4, 0.4, 1.0), self.error)

        # Dosya adı alanı
        if self.mode == "save":
            imgui.text("Dosya adı:")
            imgui.same_line()
            imgui.push_item_width(-1)
            changed, self.filename_input = imgui.input_text(
                "##fname", self.filename_input,
                imgui.InputTextFlags_.enter_returns_true,
            )
            imgui.pop_item_width()
            if changed:
                self.error = ""
        else:
            sel_txt = os.path.basename(self.selected_file) if self.selected_file else "(seçilmedi)"
            imgui.text_colored(imgui.ImVec4(0.7, 0.9, 0.7, 1.0), f"Seçili: {sel_txt}")

        imgui.spacing()
        avail = imgui.get_content_region_avail().x
        btn_w = max(80.0, (avail - 8.0) * 0.5)

        # İptal
        imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.45, 0.20, 0.20, 1.0))
        imgui.push_style_color(imgui.Col_.button_hovered, imgui.ImVec4(0.60, 0.28, 0.28, 1.0))
        cancelled = imgui.button("İptal", imgui.ImVec2(btn_w, 0))
        imgui.pop_style_color(2)
        imgui.same_line()

        # Tamam
        imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.20, 0.55, 0.30, 1.0))
        imgui.push_style_color(imgui.Col_.button_hovered, imgui.ImVec4(0.28, 0.68, 0.40, 1.0))
        imgui.push_style_color(imgui.Col_.button_active, imgui.ImVec4(0.35, 0.78, 0.50, 1.0))
        confirmed = imgui.button("Tamam", imgui.ImVec2(btn_w, 0))
        imgui.pop_style_color(3)

        if cancelled:
            self.close(cancelled=True)
        elif confirmed:
            self._confirm()

    # ------------------------------------------------------------------
    # Navigasyon
    # ------------------------------------------------------------------
    def _navigate_to(self, path: str) -> None:
        if not os.path.isdir(path):
            self.error = f"Klasör bulunamadı: {path}"
            return
        new = os.path.abspath(path)
        if new != self.current_dir:
            self.current_dir = new
            self.selected_file = None
            self._cache_key = None  # yeniden tara
            self.error = ""

    # ------------------------------------------------------------------
    # Onay
    # ------------------------------------------------------------------
    def _confirm(self) -> None:
        self.error = ""
        target: str | None = None

        if self.mode == "save":
            name = (self.filename_input or "").strip()
            if not name:
                self.error = "Dosya adı gerekli"
                return
            # Yol ayracı içeren isimleri reddet (save modunda basit isim beklenir)
            if os.path.basename(name) != name:
                self.error = "Sadece dosya adı girin (klasör yolu değil)"
                return

            if self.filters and not self._matches_filter(name):
                name += self.filters[0]
            target = os.path.join(self.current_dir, name)

            if os.path.exists(target):
                # Basit üzerine-yazma onayı: hata olarak göster, tekrar Tamam'a basınca geç
                if self.error != "Dosya zaten var. Üzerine yazmak için tekrar Tamam'a basın.":
                    self.error = "Dosya zaten var. Üzerine yazmak için tekrar Tamam'a basın."
                    return
                self.error = ""
        else:
            if not self.selected_file:
                self.error = "Bir dosya seçin"
                return
            if not os.path.isfile(self.selected_file):
                self.error = "Seçili dosya artık mevcut değil"
                return
            target = self.selected_file

        assert target is not None
        cb = self.on_select

        # Önce kapat, sonra callback → callback içinde open() çağrılabilir
        self.visible = False
        if callable(cb):
            cb(target)

    # ------------------------------------------------------------------
    # Yardımcılar
    # ------------------------------------------------------------------
    def _matches_filter(self, name: str) -> bool:
        if not self.filters:
            return True
        lower = name.lower()
        return any(lower.endswith(ext) for ext in self.filters)

    def _refresh_entries(self) -> None:
        # normcase ile Windows'ta büyük/küçük harf farkını yok say
        key = os.path.normcase(self.current_dir)
        if self._cache_key == key:
            return
        self._cache_key = key
        self._entries = []

        dirs: list[_Entry] = []
        files: list[_Entry] = []
        try:
            # scandir: is_dir bilgisi bedava gelir, tek geçiş
            with os.scandir(self.current_dir) as it:
                for de in it:
                    if de.name.startswith("."):
                        continue
                    try:
                        is_dir = de.is_dir()
                    except OSError:
                        continue
                    if is_dir:
                        dirs.append(_Entry(de.name, True, de.path))
                    elif self._matches_filter(de.name):
                        files.append(_Entry(de.name, False, de.path))
        except OSError as e:
            self.error = f"Klasör okunamadı: {e}"
            self._entries = []
            return

        dirs.sort(key=lambda e: e.name.lower())
        files.sort(key=lambda e: e.name.lower())
        self._entries = dirs + files