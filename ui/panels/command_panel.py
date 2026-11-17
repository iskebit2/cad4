# ui/panels/command_panel.py
from __future__ import annotations

import shlex
from collections import deque

from imgui_bundle import imgui

from ui.base.panel_base import Category, PanelBase


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
    OUTPUT_MAX_LINES = 500

    def __init__(self, app=None, **overrides):
        super().__init__(app=app, **overrides)
        self._input: str = ""
        self._history: deque[str] = deque(maxlen=self.HISTORY_MAX)
        self._history_idx: int = -1
        self._output: deque[tuple[str, tuple[float, float, float]]] = deque(
            maxlen=self.OUTPUT_MAX_LINES
        )
        self._reclaim_focus: bool = False
        self._append("Komut terminali hazır. Tüm komutlar için 'help' yazın.", (0.70, 0.85, 1.00))

    # ------------------------------------------------------------------
    # Çıktı API'si
    # ------------------------------------------------------------------
    def append_info(self, text: str) -> None:
        self._append(text, (0.80, 0.85, 0.95))

    def append_success(self, text: str) -> None:
        self._append(text, (0.35, 0.90, 0.45))

    def append_warn(self, text: str) -> None:
        self._append(text, (1.00, 0.78, 0.20))

    def append_error(self, text: str) -> None:
        self._append(text, (1.00, 0.40, 0.40))

    def append_result(self, text: str, level: str = "info") -> None:
        if not text:
            return
        fn = {
            "success": self.append_success,
            "warn": self.append_warn,
            "error": self.append_error,
        }.get(level, self.append_info)
        fn(text)

    def _append(self, text: str, color: tuple[float, float, float]) -> None:
        self._output.append((text, color))

    # ------------------------------------------------------------------
    # PanelBase kancaları
    # ------------------------------------------------------------------
    def open(self, **kwargs) -> None:
        super().open(**kwargs)
        self._reclaim_focus = True

    def draw_header(self) -> None:
        catalog = self._get_catalog()
        imgui.text_disabled(f"Komut: {len(catalog)} | Geçmiş: {len(self._history)}")
        imgui.same_line()
        if imgui.button("Temizle", imgui.ImVec2(85, 0)):
            self._output.clear()
            self._history_idx = -1
            self._reclaim_focus = True
        imgui.same_line()
        if imgui.button("Yardım", imgui.ImVec2(85, 0)):
            self._cmd_help()
            self._reclaim_focus = True

    def draw_settings(self) -> None:
        self._draw_output()
        imgui.separator()
        self._draw_hint_bar()
        self._draw_input()

    # ------------------------------------------------------------------
    # Çıktı alanı
    # ------------------------------------------------------------------
    def _draw_output(self) -> None:
        available = imgui.get_content_region_avail()
        output_h = max(110.0, available.y - 62.0)

        imgui.begin_child("##cmd_output", imgui.ImVec2(0, output_h), True)
        for text, color in self._output:
            imgui.push_style_color(imgui.Col_.text, imgui.ImVec4(*color, 1.0))
            imgui.text_unformatted(text)
            imgui.pop_style_color()

        if imgui.get_scroll_y() >= imgui.get_scroll_max_y() - 1.0:
            imgui.set_scroll_here_y(1.0)
        imgui.end_child()

    # ------------------------------------------------------------------
    # Canlı Yönlendirme / Otomatik Tamamlama Şeridi
    # ------------------------------------------------------------------
    def _draw_hint_bar(self) -> None:
        raw = self._input.lstrip()
        if not raw:
            imgui.text_disabled("İpucu: Komut adını yazın (TAB: tamamla, ↑/↓: geçmiş)")
            return

        token = raw.split()[0].lower()
        catalog = self._get_catalog()
        exact = next(((n, u) for n, u in catalog if n == token), None)

        if exact is not None:
            name, usage = exact
            sig = f"{name} {usage}".strip()
            imgui.text_colored(imgui.ImVec4(0.45, 0.85, 1.0, 1.0), f"Kullanım: {sig}")
            return

        matches = [n for n, _ in catalog if n.startswith(token)]
        if matches:
            preview = ", ".join(matches[:8])
            if len(matches) > 8:
                preview += f" (+{len(matches) - 8})"
            imgui.text_colored(imgui.ImVec4(0.95, 0.80, 0.35, 1.0), f"Eşleşenler: {preview}")
        else:
            imgui.text_colored(imgui.ImVec4(0.95, 0.45, 0.45, 1.0), f"Eşleşme yok: '{token}'")

    # ------------------------------------------------------------------
    # Terminal Giriş Alanı (ImGui Callback ile Geçmiş & TAB Tamamlama)
    # ------------------------------------------------------------------
    def _on_input_callback(self, data: imgui.InputTextCallbackData) -> int:
        if data.event_flag == imgui.InputTextFlags_.callback_history:
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
            self._input = new_text
            return 0

        if data.event_flag == imgui.InputTextFlags_.callback_completion:
            current = data.buf.strip()
            if not current or " " in current:
                return 0
            prefix = current.lower()
            matches = [n for n, _ in self._get_catalog() if n.startswith(prefix)]
            if len(matches) == 1:
                completed = matches[0] + " "
                data.delete_chars(0, data.buf_text_len)
                data.insert_chars(0, completed)
                self._input = completed
            elif len(matches) > 1:
                self.append_info("  " + "   ".join(matches))
            return 0

        return 0

    def _draw_input(self) -> None:
        imgui.text_colored(imgui.ImVec4(0.35, 0.90, 0.55, 1.0), "CAD4 >")
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
            "##cmd_input",
            self._input,
            flags,
            self._on_input_callback,
        )
        if submitted:
            self._submit(value)
            self._input = ""
            self._reclaim_focus = True
            return
        self._input = value

    # ------------------------------------------------------------------
    # Komut Çözümleme ve Gönderim
    # ------------------------------------------------------------------
    def _submit(self, raw: str) -> None:
        text = raw.strip()
        if not text:
            return
        if not self._history or self._history[-1] != text:
            self._history.append(text)
        self._history_idx = -1
        self._append(f"CAD4 > {text}", (0.55, 0.78, 1.00))
        self._dispatch(text)

    def _dispatch(self, text: str) -> None:
        try:
            parts = shlex.split(text)
        except ValueError as err:
            self.append_error(f"Sözdizimi hatası: {err}")
            return

        if not parts:
            return
        name = parts[0].lower()
        args = parts[1:]

        if name == "help":
            self._cmd_help(args[0].lower() if args else None)
            return
        if name in ("clear", "cls"):
            self._output.clear()
            return

        registry = getattr(self.app, "_command_registry", None)
        if registry is None:
            self.append_error("CommandRegistry yüklü değil.")
            return

        if not registry.has_factory(name):
            self.append_error(f"Bilinmeyen komut: '{name}'. Tüm liste için 'help' yazın.")
            return

        command = registry.build_by_name(name, args)
        if command is None:
            usage = registry.get_usage(name)
            self.append_warn(f"Eksik/hatalı parametre -> Kullanım: {name} {usage}".strip())
            return

        self.app.command_queue.put(command)

    # ------------------------------------------------------------------
    # Katalog ve Yardım
    # ------------------------------------------------------------------
    def _get_catalog(self) -> list[tuple[str, str]]:
        builtins = [
            ("clear", ""),
            ("cls", ""),
            ("help", "[komut_adi]"),
        ]
        registry = getattr(self.app, "_command_registry", None)
        if registry is None:
            return builtins
        return sorted(builtins + registry.get_command_catalog(), key=lambda item: item[0])

    def _cmd_help(self, filter_prefix: str | None = None) -> None:
        catalog = self._get_catalog()
        if filter_prefix:
            catalog = [(n, u) for n, u in catalog if filter_prefix in n]
        if not catalog:
            self.append_warn(f"'{filter_prefix}' ile eşleşen komut bulunamadı.")
            return

        self.append_info(f"Kayıtlı Komutlar ({len(catalog)}):")
        for name, usage in catalog:
            line = f"  {name:<24} {usage}".rstrip()
            self.append_info(line)