from imgui_bundle import imgui

from ui.file_dialog import ImGuiFileDialog


def test_directory_input_does_not_pass_legacy_buffer_size(monkeypatch):
    calls = []
    dialog = ImGuiFileDialog()
    monkeypatch.setattr(imgui, "text", lambda *args: None)
    monkeypatch.setattr(imgui, "same_line", lambda *args: None)
    monkeypatch.setattr(imgui, "push_item_width", lambda *args: None)
    monkeypatch.setattr(imgui, "pop_item_width", lambda: None)
    monkeypatch.setattr(
        imgui, "input_text",
        lambda *args: (calls.append(args) or (False, dialog.current_dir)),
    )
    monkeypatch.setattr(imgui, "is_key_pressed", lambda *args: False)
    monkeypatch.setattr(imgui, "is_item_focused", lambda: False)
    monkeypatch.setattr(imgui, "button", lambda *args: False)

    dialog._draw_dir_bar()

    assert calls == [("##dir", dialog.current_dir)]


def test_save_filename_input_passes_flags_as_third_argument(monkeypatch):
    calls = []
    dialog = ImGuiFileDialog()
    dialog.mode = "save"
    monkeypatch.setattr(imgui, "text", lambda *args: None)
    monkeypatch.setattr(imgui, "same_line", lambda *args: None)
    monkeypatch.setattr(imgui, "push_item_width", lambda *args: None)
    monkeypatch.setattr(imgui, "pop_item_width", lambda: None)
    monkeypatch.setattr(
        imgui, "input_text",
        lambda *args: (calls.append(args) or (False, dialog.filename_input)),
    )
    monkeypatch.setattr(imgui, "spacing", lambda: None)
    monkeypatch.setattr(imgui, "get_content_region_avail", lambda: imgui.ImVec2(300, 200))
    monkeypatch.setattr(imgui, "push_style_color", lambda *args: None)
    monkeypatch.setattr(imgui, "pop_style_color", lambda *args: None)
    monkeypatch.setattr(imgui, "button", lambda *args: False)
    monkeypatch.setattr(imgui, "text_colored", lambda *args: None)

    dialog._draw_footer()

    assert calls == [
        ("##fname", "", imgui.InputTextFlags_.enter_returns_true)
    ]
