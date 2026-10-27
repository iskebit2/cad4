# ui/file_dialog.py
"""
ImGuiFileDialog — Kivy FileChooserListView'ın basitleştirilmiş karşılığı.

Kullanım:
    dlg = ImGuiFileDialog()
    dlg.open(mode="open", filters=[".json"],
             title="Proje Aç",
             on_select=lambda path: pass("Seçildi:", path))
    # her frame:
    dlg.draw()

Kapanınca result callback çağrılır. Bağımsızdır, hiçbir şeye bağımlı değil.
"""
import os
from typing import Callable, List, Optional

import imgui


class ImGuiFileDialog:
    """Basit ImGui dosya seçici.

    mode: "open" veya "save"
    """

    def __init__(self):
        self.visible = False
        self.mode = "open"                 # open | save
        self.filters: List[str] = [".json"]
        self.on_select: Optional[Callable[[str], None]] = None
        self.on_cancel: Optional[Callable[[], None]] = None

        self.current_dir = os.path.abspath(os.getcwd())
        self.selected_file: Optional[str] = None
        self.filename_input = ""
        self.error = ""

        self._first_open = True
        self._entries_cache = []       # (name, is_dir, fullpath)
        self._cache_dir = None

    # ------------------------------------------------------------------
    def open(self,
             mode: str = "open",
             filters: Optional[List[str]] = None,
             title: str = "Dosya Seç",
             initial_dir: Optional[str] = None,
             default_name: str = "",
             on_select: Optional[Callable[[str], None]] = None,
             on_cancel: Optional[Callable[[], None]] = None):
        self.visible = True
        self.mode = mode
        self.filters = filters or [".json"]
        self.on_select = on_select
        self.on_cancel = on_cancel
        self.title = title
        self.error = ""
        self.selected_file = None
        self.filename_input = default_name
        self._first_open = True
        if initial_dir and os.path.isdir(initial_dir):
            self.current_dir = os.path.abspath(initial_dir)

    def close(self, cancelled: bool = False):
        self.visible = False
        if cancelled and callable(self.on_cancel):
            self.on_cancel()

    # ------------------------------------------------------------------
    def draw(self):
        if not self.visible:
            return

        if self._first_open:
            io = imgui.get_io()
            w, h = 640.0, 480.0
            imgui.set_next_window_position(
                (io.display_size[0] - w) * 0.5,
                (io.display_size[1] - h) * 0.5,
                condition=imgui.FIRST_USE_EVER,
            )
            imgui.set_next_window_size(w, h, condition=imgui.FIRST_USE_EVER)
            self._first_open = False

        flags = (
            imgui.WINDOW_NO_RESIZE
            | imgui.WINDOW_NO_COLLAPSE
            | imgui.WINDOW_NO_SAVED_SETTINGS
        )
        expanded, opened = imgui.begin(self.title, True, flags)
        if not opened:
            self.close(cancelled=True)
            imgui.end()
            return

        # --- Konum çubuğu ---
        imgui.text("Klasör:")
        imgui.same_line()

        imgui.push_item_width(-90)
        new_dir = imgui.input_text("##dir", self.current_dir, 512)[1]
        imgui.pop_item_width()
        if new_dir != self.current_dir and os.path.isdir(new_dir):
            self.current_dir = os.path.abspath(new_dir)
            self.selected_file = None
            self._cache_dir = None

        imgui.same_line()
        if imgui.button("Up"):
            parent = os.path.dirname(self.current_dir)
            if parent and os.path.isdir(parent):
                self.current_dir = parent
                self.selected_file = None
                self._cache_dir = None

        imgui.separator()
        parent_dir = os.path.dirname(self.current_dir.rstrip(os.sep))
        if parent_dir and parent_dir != self.current_dir:
            if imgui.selectable("[..]  üst klasör##parent", False)[0]:
                self.current_dir = parent_dir
                self.selected_file = None
                self._cache_dir = None
        # --- Dosya listesi (scrollable) ---
        list_height = -100.0
        imgui.begin_child("file_list", height=list_height, border=True)

        self._refresh_entries()
        for name, is_dir, full in self._entries_cache:
            icon = "[D]" if is_dir else "  "
            label = f"{icon}  {name}##{full}"
            selected = (self.selected_file == full)
            if imgui.selectable(label, selected)[0]:
                if is_dir:
                    self.current_dir = full
                    self.selected_file = None
                    self._cache_dir = None
                    break
                else:
                    self.selected_file = full
                    # YENİ: dosya adını input'a yaz
                    self.filename_input = name

        imgui.end_child()

        imgui.separator()

        # --- Dosya adı (save modunda) ---
        if self.mode == "save":
            imgui.text("Dosya adı:")
            imgui.same_line()
            imgui.push_item_width(-1)
            self.filename_input = imgui.input_text(
                "##fname", self.filename_input, 256
            )[1]
            imgui.pop_item_width()
        else:
            sel_txt = os.path.basename(self.selected_file) if self.selected_file else "(seçilmedi)"
            imgui.text_colored(f"Seçili: {sel_txt}", 0.7, 0.9, 0.7, 1.0)

        if self.error:
            imgui.text_colored(self.error, 1.0, 0.4, 0.4, 1.0)

        # --- Alt butonlar ---
        imgui.spacing()
        avail = imgui.get_content_region_available_width()
        btn_w = (avail - 8) * 0.5

        # İptal
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.45, 0.20, 0.20, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.60, 0.28, 0.28, 1.0)
        if imgui.button("İptal", width=btn_w):
            self.close(cancelled=True)
        imgui.pop_style_color(2)
        imgui.same_line()

        # Tamam
        imgui.push_style_color(imgui.COLOR_BUTTON, 0.20, 0.55, 0.30, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_HOVERED, 0.28, 0.68, 0.40, 1.0)
        imgui.push_style_color(imgui.COLOR_BUTTON_ACTIVE, 0.35, 0.78, 0.50, 1.0)
        if imgui.button("Tamam", width=btn_w):
            self._confirm()
        imgui.pop_style_color(3)

        imgui.end()

    # ------------------------------------------------------------------
    def _confirm(self):
        target = None
        if self.mode == "save":
            name = (self.filename_input or "").strip()
            if not name:
                self.error = "Dosya adı gerekli"
                return
            if not any(name.endswith(ext) for ext in self.filters):
                name += self.filters[0]
            target = os.path.join(self.current_dir, name)
        else:
            if not self.selected_file:
                self.error = "Bir dosya seçin"
                return
            target = self.selected_file

        if callable(self.on_select):
            self.on_select(target)
        self.visible = False

    # ------------------------------------------------------------------
    def _refresh_entries(self):
        if self._cache_dir == self.current_dir:
            return
        self._cache_dir = self.current_dir
        self._entries_cache = []

        try:
            entries = []
            # Önce klasörler
            for name in sorted(os.listdir(self.current_dir)):
                if name.startswith("."):
                    continue
                full = os.path.join(self.current_dir, name)
                is_dir = os.path.isdir(full)
                if is_dir:
                    entries.append((name, True, full))
            # Sonra filtreye uyan dosyalar
            for name in sorted(os.listdir(self.current_dir)):
                if name.startswith("."):
                    continue
                full = os.path.join(self.current_dir, name)
                if os.path.isdir(full):
                    continue
                if self.filters and not any(name.endswith(ext) for ext in self.filters):
                    continue
                entries.append((name, False, full))

            self._entries_cache = entries
        except Exception as e:
            self._entries_cache = []
            self.error = f"Klasör okunamadı: {e}"