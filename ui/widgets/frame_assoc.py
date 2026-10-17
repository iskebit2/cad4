# ui/widgets/frame_assoc.py
import imgui


class FrameAssocWidget:

    @staticmethod
    def draw(poly, scene, selected_fids: set):
        """
        Assoc frame listesi (Sütunlu görünüm).
        Döner: (action, payload)
            action: None | "remove" | "select" | "isolate" | "focus" | "remove_selected"
            payload: frame_id veya liste
        """
        action = None
        payload = None

        imgui.text_colored("ASSOC FRAME'LER", 0.8, 0.85, 0.95, 1.0)
        imgui.separator()

        assoc_ids = list(getattr(poly, "associated_frame_ids", []))

        imgui.text(f"Toplam: {len(assoc_ids)}")
        imgui.same_line()
        if selected_fids:
            imgui.text_colored(f" | Seçili: {len(selected_fids)}",
                               0.95, 0.75, 0.4, 1.0)
        imgui.separator()

        if not assoc_ids:
            imgui.text_colored("Assoc frame yok.", 0.6, 0.6, 0.6, 1.0)
            imgui.spacing()
            imgui.text_colored("'Modelden Ekle' ile frame ekleyin.",
                               0.7, 0.7, 0.7, 1.0)
            return action, payload

        # Scroll'lu liste
        child_visible = imgui.begin_child("assoc_list", width=0, height=200, border=True)
        if child_visible:
            frames_dict = getattr(scene, "frames", {}) if scene else {}

            # 3 Sütunlu tablo yapısı
            imgui.columns(3, "assoc_table", True)
            imgui.set_column_width(0, 100)
            imgui.set_column_width(1, 75)

            # Sütun Başlıkları
            imgui.text_colored("Seç / ID", 0.8, 0.8, 0.8, 1.0)
            imgui.next_column()
            imgui.text_colored("Uzunluk", 0.8, 0.8, 0.8, 1.0)
            imgui.next_column()
            imgui.text_colored("Koordinatlar (i → j)", 0.8, 0.8, 0.8, 1.0)
            imgui.next_column()
            imgui.separator()

            for fid in assoc_ids:
                frame = frames_dict.get(fid) if isinstance(frames_dict, dict) else None
                is_sel = fid in selected_fids

                # 1. Sütun: Checkbox + ID
                changed, checked = imgui.checkbox(f"F{fid}##chk_{fid}", is_sel)
                if changed:
                    if checked:
                        selected_fids.add(fid)
                    else:
                        selected_fids.discard(fid)

                imgui.next_column()

                # 2. Sütun: Uzunluk
                L = frame.get_length() if frame and hasattr(frame, "get_length") else 0
                imgui.text(f"{L:.1f}")
                imgui.next_column()

                # 3. Sütun: Koordinatlar
                if frame is not None:
                    ni = getattr(frame, "node_i", None)
                    nj = getattr(frame, "node_j", None)
                    xi = getattr(ni, "x", 0) if ni else 0
                    yi = getattr(ni, "y", 0) if ni else 0
                    zi = getattr(ni, "z", 0) if ni else 0
                    xj = getattr(nj, "x", 0) if nj else 0
                    yj = getattr(nj, "y", 0) if nj else 0
                    zj = getattr(nj, "z", 0) if nj else 0
                    coord_str = f"({xi:.0f},{yi:.0f},{zi:.0f})→({xj:.0f},{yj:.0f},{zj:.0f})"
                else:
                    coord_str = "Veri yok"

                imgui.text(coord_str)

                # Sağ tık menüsü
                if imgui.begin_popup_context_item(f"ctx_{fid}"):
                    if imgui.menu_item("Sahneye git")[0]:
                        action, payload = "focus", fid
                    if imgui.menu_item("Sadece bunu göster")[0]:
                        action, payload = "isolate", fid
                    if imgui.menu_item("Assoc'tan çıkar")[0]:
                        action, payload = "remove", fid
                    imgui.end_popup()

                imgui.next_column()

            imgui.columns(1)  # Sütun modunu kapat

        imgui.end_child()

        # Toplu aksiyonlar
        imgui.spacing()
        n_sel = len(selected_fids)
        if n_sel > 0:
            if imgui.button(f"Seçili {n_sel} frame'i çıkar", width=200):
                action, payload = "remove_selected", list(selected_fids)
        else:
            imgui.text_colored("Seçim yok.", 0.6, 0.6, 0.6, 1.0)

        return action, payload