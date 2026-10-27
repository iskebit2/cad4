from imgui_bundle import *



# Sembol fontunu birleştir (merge mode)
config = imgui.ImFontConfig()
config.merge_mode = True
hello_imgui.load_font_ttf("fonts/seguisym.ttf", 16.0, config)