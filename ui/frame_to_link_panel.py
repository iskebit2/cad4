import imgui

from domain.element import Frame
from tools.frame_to_link import DEFAULT_LINK_PROP_NAME, ensure_default_link_prop


class FrameToLinkPanel:
    def __init__(self):
        self.visible = False
        self.app = None
        self.selected_prop = DEFAULT_LINK_PROP_NAME
        self.delete_original = True
        self.keep_loads = False   # şimdilik desteklenmiyor

    def draw(self):
        if not self.visible:
            return
        imgui.set_next_window_size(360, 220, imgui.FIRST_USE_EVER)
        expanded, opened = imgui.begin("Frame → Link", True)
        if not opened:
            self.visible = False
        if not expanded:
            imgui.end()
            return

        scn = self.app.engine.scene if self.app and self.app.engine else None
        frames = [e for e in (scn.get_selected() if scn else []) if isinstance(e, Frame)]
        if not frames:
            imgui.text_colored("Önce frame seçin.", 1.0, 0.6, 0.3, 1.0)
            imgui.end()
            return

        imgui.text(f"Seçili frame: {len(frames)}")

        # LinkProp listesi
        props = list(self.app.current_project.link_props.keys())
        if not props:
            imgui.text_colored("Projede LinkProp yok.", 1.0, 0.5, 0.5, 1.0)
            if imgui.button("DefaultLink Oluştur"):
                ensure_default_link_prop(self.app.current_project)
            imgui.end()
            return

        if self.selected_prop not in props:
            self.selected_prop = props[0]

        # Combo
        if imgui.begin_combo("LinkProp", self.selected_prop):
            for p in props:
                is_sel = (p == self.selected_prop)
                clicked, _ = imgui.selectable(p, is_sel)
                if clicked:
                    self.selected_prop = p
            imgui.end_combo()

        imgui.checkbox("Orijinal Frame'i sil", self.delete_original)
        imgui.separator()

        if imgui.button("Dönüştür", width=120, height=28):
            self.app.convert_selected_frames_to_links(
                link_prop_name=self.selected_prop,
                delete_original=self.delete_original,
            )
            self.visible = False

        imgui.end()