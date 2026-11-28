# ui/panels/command_panel.py
from __future__ import annotations

import shlex
from collections import deque

from imgui_bundle import imgui

from ui.base.panel_base import Category, PanelBase


# ANSI benzeri renk paleti
COLOR_INFO    = (0.80, 0.85, 0.95)
COLOR_SUCCESS = (0.35, 0.90, 0.45)
COLOR_WARN    = (1.00, 0.78, 0.20)
COLOR_ERROR   = (1.00, 0.40, 0.40)
COLOR_ECHO    = (0.55, 0.78, 1.00)
COLOR_PROMPT  = (0.35, 0.90, 0.55)
COLOR_LINK    = (0.45, 0.85, 1.00)


class CommandPanel(PanelBase):
    __abstract__ = False
    panel_name = "command_panel"
    title = "Komut Satırı"
    category = Category.MANAGEMENT
    quick = True
    shortcut = "F1"
    menu_label = "Komut Satırı"
    icon = "⌨"
    context = ()
    uses_draft = False
    show_apply_bar = False
    use_standard_layout = True

    width = 760
    height = 420
    pos_first_use = (120.0, 520.0)

    HISTORY_MAX = 200
    OUTPUT_MAX_LINES = 1000

    def __init__(self, app=None, **overrides):
        super().__init__(app=app, **overrides)
        self._input: str = ""
        self._history: deque[str] = deque(maxlen=self.HISTORY_MAX)
        self._history_idx: int = -1
        # Her satır: (text, color, command_link | None)
        self._output: deque[tuple[str, tuple[float, float, float], str | None]] = deque(
            maxlen=self.OUTPUT_MAX_LINES
        )
        self._reclaim_focus: bool = False
        self._catalog_cache: list[tuple[str, str]] | None = None
        self._catalog_dict: dict[str, str] = {}
        self._append("Komut terminali hazır. Tüm komutlar için 'help' yazın.", COLOR_INFO)

    # ------------------------------------------------------------------
    # Çıktı API'si
    # ------------------------------------------------------------------
    def append_info(self, text: str) -> None:
        self._append(text, COLOR_INFO)

    def append_success(self, text: str) -> None:
        self._append(text, COLOR_SUCCESS)

    def append_warn(self, text: str) -> None:
        self._append(text, COLOR_WARN)

    def append_error(self, text: str) -> None:
        self._append(text, COLOR_ERROR)

    def append_echo(self, text: str) -> None:
        """Harici komutları terminale yazar (put_command ile)."""
        self._append(text, COLOR_ECHO)

    def append_result(self, text: str, level: str = "info") -> None:
        if not text:
            return
        fn = {
            "success": self.append_success,
            "warn": self.append_warn,
            "error": self.append_error,
            "echo": self.append_echo,
        }.get(level, self.append_info)
        fn(text)

    def _append(
        self,
        text: str,
        color: tuple[float, float, float],
        command_link: str | None = None,
    ) -> None:
        self._output.append((text, color, command_link))

    # ------------------------------------------------------------------
    # PanelBase kancaları
    # ------------------------------------------------------------------
    def open(self, **kwargs) -> None:
        super().open(**kwargs)
        self._reclaim_focus = True
        self._catalog_cache = None
        self._catalog_dict = {}

    def draw_header(self) -> None:
        # Sadece durum satırı; buton yok
        catalog = self._get_catalog()
        imgui.text_disabled(f"Komut: {len(catalog)}  |  Geçmiş: {len(self._history)}")

    def draw_settings(self) -> None:
        # Tek bir çocuk alan: output + input aynı scroll bölgesinde
        avail = imgui.get_content_region_avail()
        imgui.begin_child("##cmd_terminal", imgui.ImVec2(0, avail.y), False)

        self._draw_output()

        # Input satırı her zaman output'un altında, aynı scroll bölgesinde
        imgui.push_style_color(imgui.Col_.text, imgui.ImVec4(*COLOR_PROMPT, 1.0))
        imgui.text_unformatted("CAD4 >")
        imgui.pop_style_color()
        imgui.same_line()

        imgui.set_next_item_width(-1)
        if self._reclaim_focus:
            imgui.set_keyboard_focus_here()
            self._reclaim_focus = False

        flags = (
            imgui.InputTextFlags_.enter_returns_true
            | imgui.InputTextFlags_.callback_history
            | imgui.InputTextFlags_.callback_completion
        )
        submitted, value = imgui.input_text(
            "##cmd_input", self._input, flags, self._on_input_callback,
        )
        if submitted:
            self._submit(value)
            self._input = ""
            self._reclaim_focus = True
        else:
            self._input = value

        # Otomatik scroll: en alta
        if imgui.get_scroll_y() >= imgui.get_scroll_max_y() - 1.0:
            imgui.set_scroll_here_y(1.0)

        imgui.end_child()

    # ------------------------------------------------------------------
    # Çıktı alanı — Ctrl+Click link desteği
    # ------------------------------------------------------------------
    def _draw_output(self) -> None:
        for text, color, link in self._output:
            if link is not None:
                self._draw_clickable_line(text, color, link)
            else:
                imgui.push_style_color(imgui.Col_.text, imgui.ImVec4(*color, 1.0))
                imgui.text_unformatted(text)
                imgui.pop_style_color()

    def _draw_clickable_line(
        self,
        text: str,
        color: tuple[float, float, float],
        command: str,
    ) -> None:
        """Ctrl+Click ile komutu input'a alır."""
        # Ctrl basılıysa link rengi + underline hissi
        ctrl = imgui.get_io().key_ctrl
        hover_color = (0.35, 0.75, 1.00) if ctrl else color

        imgui.push_style_color(imgui.Col_.text, imgui.ImVec4(*hover_color, 1.0))
        imgui.text_unformatted(text)
        imgui.pop_style_color()

        # Tıklanabilir alan: text'in bounding box'ı
        min_rect = imgui.get_item_rect_min()
        max_rect = imgui.get_item_rect_max()
        imgui.set_cursor_screen_pos(min_rect)

        # Görünmez buton: text genişliği kadar
        size = imgui.ImVec2(max_rect.x - min_rect.x, max_rect.y - min_rect.y)
        imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0, 0, 0, 0))
        imgui.push_style_color(imgui.Col_.button_hovered, imgui.ImVec4(0, 0, 0, 0))
        imgui.push_style_color(imgui.Col_.button_active, imgui.ImVec4(0, 0, 0, 0))
        clicked = imgui.invisible_button(f"##link_{id(text)}", size)
        imgui.pop_style_color(3)

        if clicked and ctrl:
            self._input = command
            self._reclaim_focus = True
            # Komutu hemen çalıştırma; sadece input'a al (VS Code tarzı)
        elif clicked:
            # Ctrl yoksa sadece tooltip göster
            imgui.set_tooltip(f"Ctrl+Click ile komut satırına al: {command}")

    # ------------------------------------------------------------------
    # Input callback
    # ------------------------------------------------------------------
    def _on_input_callback(self, data: imgui.InputTextCallbackData) -> int:
        if data.event_flag == imgui.InputTextFlags_.callback_history:
            return self._handle_history(data)
        if data.event_flag == imgui.InputTextFlags_.callback_completion:
            return self._handle_completion(data)
        return 0

    def _handle_history(self, data: imgui.InputTextCallbackData) -> int:
        if not self._history:
            return 0
        if data.event_key == imgui.Key.up_arrow:
            if self._history_idx == -1:
                self._history_idx = len(self._history) - 1
            else:
                self._history_idx = max(0, self._history_idx - 1)
            new_text = self._history[self._history_idx]
        elif data.event_key == imgui.Key.down_arrow:
            if self._history_idx == -1:
                return 0
            self._history_idx += 1
            if self._history_idx >= len(self._history):
                self._history_idx = -1
                new_text = ""
            else:
                new_text = self._history[self._history_idx]
        else:
            return 0

        data.delete_chars(0, data.buf_text_len)
        data.insert_chars(0, new_text)
        return 0

    def _handle_completion(self, data: imgui.InputTextCallbackData) -> int:
        current = data.buf.strip()
        if not current or " " in current:
            return 0
        prefix = current.lower()
        matches = [
            n for n, _ in self._get_catalog()
            if n.lower().startswith(prefix)
        ]
        if len(matches) == 1:
            completed = matches[0] + " "
            data.delete_chars(0, data.buf_text_len)
            data.insert_chars(0, completed)
        elif len(matches) > 1:
            self.append_info("  " + "   ".join(matches))
        return 0

    # ------------------------------------------------------------------
    # Komut gönderimi
    # ------------------------------------------------------------------
    def _submit(self, raw: str) -> None:
        text = raw.strip()
        if not text:
            return
        if not self._history or self._history[-1] != text:
            self._history.append(text)
        self._history_idx = -1
        # Echo satırını ayrı renkte göster (prompt dahil)
        self._append(f"CAD4 > {text}", COLOR_ECHO)
        self._dispatch(text)

    def _dispatch(self, text: str) -> None:
        try:
            parts = shlex.split(text, posix=True)
        except ValueError as err:
            self.append_error(f"Sözdizimi hatası: {err}")
            return
        if not parts:
            return

        raw_name = parts[0]
        args = parts[1:]

        # Built-in komutlar (küçük harf)
        lname = raw_name.lower()
        if lname == "help":
            self._cmd_help(args[0].lower() if args else None)
            return
        if lname in ("clear", "cls"):
            self._output.clear()
            return

        registry = self.app.command_registry
        # ✅ Gerçek adı bul (case-insensitive)
        real_name = self._resolve_command_name(raw_name)
        if real_name is None:
            self.append_error(
                f"Bilinmeyen komut: '{raw_name}'. Tüm liste için 'help' yazın."
            )
            return

        command = registry.build(real_name, args)
        if command is None:
            usage = registry.get_usage(real_name)
            self.append_warn(
                f"Eksik/hatalı parametre -> Kullanım: {real_name} {usage}".strip()
            )
            return
        print("command:", command)
        self.app.put_command(command)

    def _resolve_command_name(self, raw: str) -> str | None:
        """Verilen adı registry'de büyük/küçük harf duyarsız arar."""
        registry = self.app.command_registry
        if registry.has(raw):
            return raw
        low = raw.lower()
        for name, _ in self._get_catalog():
            if name.lower() == low:
                return name
        return None

    # ------------------------------------------------------------------
    # Katalog ve Yardım
    # ------------------------------------------------------------------
    def _get_catalog(self) -> list[tuple[str, str]]:
        if self._catalog_cache is not None:
            return self._catalog_cache
        builtins = [("clear", ""), ("cls", ""), ("help", "[komut_adi]")]
        registry = self.app.command_registry
        self._catalog_cache = sorted(builtins + registry.catalog(), key=lambda x: x[0])
        self._catalog_dict = dict(self._catalog_cache)
        return self._catalog_cache

    def _cmd_help(self, filter_prefix: str | None = None) -> None:
        catalog = self._get_catalog()
        if filter_prefix:
            fp = filter_prefix.lower()
            catalog = [(n, u) for n, u in catalog if n.lower().startswith(fp)]
        if not catalog:
            self.append_warn(f"'{filter_prefix}' ile eşleşen komut bulunamadı.")
            return

        self.append_info(f"Kayıtlı Komutlar ({len(catalog)}) — Ctrl+Click ile komut satırına al:")
        for name, usage in catalog:
            line = f"  {name:<24} {usage}".rstrip()
            # Tıklanabilir link: sadece komut adı değil, tüm satır
            self._append(line, COLOR_LINK, command_link=name)