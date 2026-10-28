"""
ImGui font/glyph diagnostic test for CAD4.

Run from the CAD4 project root:
    python tests/test_imgui_glyphs.py

This test:
- prints which Windows font files exist;
- checks each test character against font cmap tables (when fontTools is installed);
- checks the configured ImGui glyph ranges;
- optionally opens a standalone ImGui window and renders the exact test string.

Install optional font inspection support:
    python -m pip install fonttools
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

TEST_TEXT = "→ ← ≤ ≥ ✓ ✗ ⚙ ▲ ▼ ● ○ ☀ ⚠ ℃ α β Δ ³ ₂ ▶ ◀ ▴ ▾ ▸ ◂"
MISSING_TEXT = "✓ ✗ ⚙ ☀ ⚠ ℃ ▶ ◀ ▴ ▾ ▸ ◂"

PROJECT_ROOT = Path.cwd()
WINDOWS_FONTS = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"

FONT_CANDIDATES = [
    WINDOWS_FONTS / "segoeui.ttf",
    WINDOWS_FONTS / "seguisym.ttf",
    WINDOWS_FONTS / "tahoma.ttf",
    WINDOWS_FONTS / "msyh.ttc",
    WINDOWS_FONTS / "malgun.ttf",
    PROJECT_ROOT / "assets" / "fonts" / "Roboto-Regular.ttf",
]

def report_font_files() -> None:
    print("\n=== FONT DOSYALARI ===")
    for path in FONT_CANDIDATES:
        print(f"{'VAR  ' if path.is_file() else 'YOK  '} {path}")

def report_font_coverage() -> None:
    print("\n=== FONT KARAKTER DESTEĞİ ===")
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        print("fontTools kurulu değil; ayrıntılı font kontrolü atlandı.")
        print("Kurmak için: python -m pip install fonttools")
        return

    chars = list(dict.fromkeys(TEST_TEXT.replace(" ", "")))
    for path in FONT_CANDIDATES:
        if not path.is_file() or path.suffix.lower() not in {".ttf", ".otf"}:
            continue
        try:
            font = TTFont(str(path), fontNumber=0)
            cmap = set()
            for table in font["cmap"].tables:
                cmap.update(table.cmap.keys())
            supported = [ch for ch in chars if ord(ch) in cmap]
            unsupported = [ch for ch in chars if ord(ch) not in cmap]
            print(f"\n{path.name}")
            print("  DESTEKLENEN :", " ".join(supported) if supported else "(yok)")
            print("  DESTEKLENMEYEN:", " ".join(unsupported) if unsupported else "(yok)")
            font.close()
        except Exception as exc:
            print(f"\n{path.name}: okunamadı: {exc}")

def report_imgui_ranges() -> None:
    print("\n=== IMGUI GLYPH RANGE KONTROLÜ ===")
    try:
        from imgui_bundle import imgui
        core = getattr(imgui, "core", None)
        print("imgui modülü :", getattr(imgui, "__file__", "(bilinmiyor)"))
        print("imgui sürümü :", getattr(imgui, "__version__", "(sürüm bilgisi yok)"))
        print("imgui.core   :", core)
        print("GlyphRanges  :", getattr(core, "GlyphRanges", None) if core else None)
        print("FontConfig   :", getattr(core, "FontConfig", None) if core else None)
    except Exception as exc:
        print("imgui import edilemedi:", repr(exc))
        return

    # The project theme's ranges, copied exactly for an independent check.
    ranges = [
        (0x0020, 0x00FF), (0x0100, 0x017F), (0x0180, 0x024F),
        (0x0370, 0x03FF), (0x2000, 0x206F), (0x2070, 0x209F),
        (0x20A0, 0x20CF), (0x2100, 0x214F), (0x2150, 0x218F),
        (0x2190, 0x21FF), (0x2200, 0x22FF), (0x2300, 0x23FF),
        (0x2500, 0x257F), (0x25A0, 0x25FF), (0x2600, 0x26FF),
        (0x2700, 0x27BF), (0x2B00, 0x2BFF),
    ]
    for ch in dict.fromkeys(TEST_TEXT.replace(" ", "")):
        covered = any(lo <= ord(ch) <= hi for lo, hi in ranges)
        print(f"U+{ord(ch):04X} {ch} : {'RANGE İÇİNDE' if covered else 'RANGE DIŞINDA'}")

def try_gui_test() -> None:
    print("\n=== GUI TESTİ ===")
    try:
        import glfw
        from imgui_bundle import imgui
        from imgui_bundle.python_backends.glfw_backend import GlfwRenderer
    except Exception as exc:
        print("Bağımsız GUI testi başlatılamadı; bağımlılık/API bulunamadı.")
        print("Hata:", repr(exc))
        print("Yukarıdaki font dosyası ve karakter desteği raporu yine de kullanılabilir.")
        return

    try:
        if not glfw.init():
            print("glfw.init() başarısız; GUI testi atlandı.")
            return

        window = glfw.create_window(1050, 300, "CAD4 ImGui Glyph Test", None, None)
        if not window:
            glfw.terminate()
            print("GLFW penceresi oluşturulamadı; GUI testi atlandı.")
            return

        glfw.make_context_current(window)
        imgui.create_context()
        io = imgui.get_io()

        # Load primary font with the same ranges as ui/theme.py.
        from imgui_bundle import imgui as bundle_imgui
        core = getattr(bundle_imgui, "core", None)
        ranges_data = [
            0x0020, 0x00FF, 0x0100, 0x017F, 0x0180, 0x024F,
            0x0370, 0x03FF, 0x2000, 0x206F, 0x2070, 0x209F,
            0x20A0, 0x20CF, 0x2100, 0x214F, 0x2150, 0x218F,
            0x2190, 0x21FF, 0x2200, 0x22FF, 0x2300, 0x23FF,
            0x2500, 0x257F, 0x25A0, 0x25FF, 0x2600, 0x26FF,
            0x2700, 0x27BF, 0x2B00, 0x2BFF, 0,
        ]
        font_path = next((p for p in FONT_CANDIDATES if p.is_file() and p.suffix.lower() == ".ttf"), None)
        if font_path:
            try:
                glyph_ranges = core.GlyphRanges(ranges_data) if core and hasattr(core, "GlyphRanges") else None
                font = io.fonts.add_font_from_file_ttf(str(font_path), 20, None, glyph_ranges)
                print("GUI test font:", font_path)
            except Exception:
                print("Özel font yüklenemedi; ImGui varsayılan fontuyla devam.")
                traceback.print_exc()
                io.fonts.add_font_default()
        else:
            print("TTF aday bulunamadı; ImGui varsayılan fontuyla devam.")
            io.fonts.add_font_default()

        impl = GlfwRenderer(window)
        # Backend versions differ; ask it to upload the font texture if supported.
        if hasattr(impl, "refresh_font_texture"):
            impl.refresh_font_texture()

        while not glfw.window_should_close(window):
            glfw.poll_events()
            impl.process_inputs()
            imgui.new_frame()
            imgui.set_next_window_size(
                imgui.ImVec2(1020, 250), imgui.Cond_.first_use_ever
            )
            imgui.begin("Karakter testi")
            imgui.text("Beklenen:")
            imgui.text(TEST_TEXT)
            imgui.separator()
            imgui.text("Özellikle sorunlu olanlar:")
            imgui.text(MISSING_TEXT)
            imgui.text("Bu pencerede de eksikler varsa font/atlas; burada tam ise CAD4 renderer/atlas yenileme yolu incelenmeli.")
            imgui.end()
            imgui.render()
            width, height = glfw.get_framebuffer_size(window)
            from OpenGL.GL import GL_COLOR_BUFFER_BIT, glClear, glViewport
            glViewport(0, 0, width, height)
            glClear(GL_COLOR_BUFFER_BIT)
            impl.render(imgui.get_draw_data())
            glfw.swap_buffers(window)

        impl.shutdown()
        glfw.destroy_window(window)
        glfw.terminate()
    except Exception:
        traceback.print_exc()
        try:
            glfw.terminate()
        except Exception:
            pass

def main() -> int:
    print("CAD4 ImGui glyph diagnostic")
    print("Python:", sys.version)
    print("Project root:", PROJECT_ROOT)
    report_font_files()
    report_font_coverage()
    report_imgui_ranges()
    if "--gui" in sys.argv:
        try_gui_test()
    else:
        print("\nİsteğe bağlı gerçek çizim testi için:")
        print("    python tests/test_imgui_glyphs.py --gui")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
