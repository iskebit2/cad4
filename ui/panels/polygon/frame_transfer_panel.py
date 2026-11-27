# ui/panels/polygon/frame_transfer_panel.py
from __future__ import annotations

from imgui_bundle import imgui
import app.commands as cmd
from app.commands import polygon_commands as PLC
import app.commands as cmd
from app.settings.categories import Category
from tools.area_to_frame import TransferBatch
from ui.base.inspector_panel import InspectorPanel


class FrameTransferPanel(InspectorPanel):
    panel_name = "frame_transfer_panel"
    title = "Frame Yük Aktarımı"
    category = Category.DRAW
    context = ("project", "engine")
    width = 480
    height = 520
    pos_first_use = (920.0, 140.0)

    def __init__(self, app=None, **overrides) -> None:
        super().__init__(app=app, **overrides)
        self.project = None
        self.engine = None
        self.batch: TransferBatch | None = None
        self._mode: str = "replace"

    def open(self, batch: TransferBatch | None = None, **kwargs) -> None:
        if batch is not None:
            self.batch = batch
            self._mode = batch.mode
        super().open(**kwargs)

    def draw_content(self) -> None:
        if self.batch is None or self.project is None:
            imgui.text_disabled("Aktarılacak hazırlanmış yük paketi yok.")
            return

        imgui.text_colored(imgui.ImVec4(0.5, 0.85, 1.0, 1.0), self.batch.source_label)
        imgui.text(
            f"Hedef Frame: {self.batch.frame_count} | "
            f"Toplam Segment: {self.batch.segment_count} | "
            f"Pattern: {', '.join(self.batch.pattern_names)}"
        )
        imgui.separator()

        if imgui.radio_button("Add (Mevcut yüklerin üstüne ekle)##ft_add", self._mode == "add"):
            self._mode = "add"
        if imgui.radio_button("Replace (Mevcut yükleri değiştir)##ft_rep", self._mode == "replace"):
            self._mode = "replace"
        if imgui.radio_button("Delete (İlgili pattern yüklerini sil)##ft_del", self._mode == "delete"):
            self._mode = "delete"

        imgui.spacing()
        loads_visible = bool(self.app and self.app.get_loads_visible())
        btn_label = "Yük Render Gizle##ft_rnd" if loads_visible else "Yükleri Render Et##ft_rnd"
        if imgui.button(btn_label, imgui.ImVec2(-1, 28)):
            self.app.put_command(cmd.ToggleLoadsVisible(not loads_visible))

        imgui.separator()
        flags = (
            imgui.TableFlags_.borders
            | imgui.TableFlags_.row_bg
            | imgui.TableFlags_.sizing_stretch_prop
            | imgui.TableFlags_.scroll_y
        )
        if imgui.begin_table("##ft_preview_tbl", 4, flags, imgui.ImVec2(0, 220)):
            imgui.table_setup_column("Frame", imgui.TableColumnFlags_.width_fixed, 80)
            imgui.table_setup_column("Pattern", imgui.TableColumnFlags_.width_fixed, 120)
            imgui.table_setup_column("Eksen", imgui.TableColumnFlags_.width_fixed, 70)
            imgui.table_setup_column("Segment", imgui.TableColumnFlags_.width_stretch)
            imgui.table_headers_row()
            frames = self.project.math_model.frames
            for fid, pats in sorted(self.batch.staged_loads.items()):
                fr = frames.get(fid)
                fname = fr.label if fr and fr.label else f"Frame {fid}"
                for pname, dload in pats.items():
                    imgui.table_next_row()
                    imgui.table_set_column_index(0)
                    imgui.text(fname)
                    imgui.table_set_column_index(1)
                    imgui.text(pname)
                    imgui.table_set_column_index(2)
                    imgui.text(f"{dload.coord_sys} {dload.load_dir}")
                    imgui.table_set_column_index(3)
                    imgui.text(f"{len(dload.segments)} adet")
            imgui.end_table()

        imgui.spacing()
        if imgui.button("Apply##ft_apply", imgui.ImVec2(140, 32)):
            self.batch.mode = self._mode
            self.app.put_command(cmd.CommitFrameTransferBatch(self.batch))
            self.app.put_command(cmd.ToggleLoadsVisible(True))
            self.close()
        imgui.same_line()
        if imgui.button("Cancel##ft_cancel", imgui.ImVec2(140, 32)):
            self.batch = None
            self.close()