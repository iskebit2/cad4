# ui/properties_window.py
import imgui
import logging
import traceback
from typing import List, Optional, Dict, Any
import numpy as np

from domain.element import Node, Frame, Area, Link, Restraint

logger = logging.getLogger(__name__)

class PropertiesWindow:
    """Properties penceresi - element özelliklerini düzenler"""
    
    def __init__(self, selection_manager, scene_renderer, definition_manager=None):
        self.selection = selection_manager
        self.renderer = scene_renderer
        self.def_mgr = definition_manager
        
        # Pencere durumu
        self.visible = False
        self.width = 350
        self.height = 500
        
        # Editör state
        self.editing_element_id: Optional[int] = None
        self.edit_buffer: Dict[str, Any] = {}
        self.has_unsaved_changes = False
        self.filter_type = "All"
        
        # Push/Pop sayacı (güvenlik için)
        self._push_count = 0

    def update_def_mgr(self, def_mgr):
        """Definition manager'ı güncelle (scene yüklendikten sonra)"""
        self.def_mgr = def_mgr
        logger.debug(f"PropertiesWindow def_mgr updated with sections: {list(def_mgr.sections.keys()) if def_mgr else 'None'}")
    
    def toggle(self):
        """Pencere görünürlüğünü değiştir"""
        self.visible = not self.visible
    
    def show(self):
        """Pencereyi göster"""
        self.visible = True
    
    def hide(self):
        """Pencereyi gizle"""
        self.visible = False
    
    def _push_style(self, color, *args):
        """Güvenli style push - sayaç tutar"""
        imgui.push_style_color(color, *args)
        self._push_count += 1
    
    def _pop_style(self, count=1):
        """Güvenli style pop - sayaçtan düşer"""
        for _ in range(min(count, self._push_count)):
            imgui.pop_style_color()
            self._push_count -= 1
    
    def _clear_styles(self):
        """Kalan tüm style'ları temizle"""
        while self._push_count > 0:
            imgui.pop_style_color()
            self._push_count -= 1
    
    def render(self):
        """Properties penceresini çiz"""
        if not self.visible:
            return
        
        imgui.set_next_window_size(self.width, self.height, imgui.FIRST_USE_EVER)
        
        opened, self.visible = imgui.begin("Properties", self.visible)
        if not opened:
            imgui.end()
            return
        
        try:
            elements = self.selection.get_selected()
            
            if not elements:
                imgui.text_disabled("No elements selected.")
                return
            
            # Seçim hash'i
            current_hash = hash(tuple(e.unique_id for e in elements))
            if self.editing_element_id != current_hash:
                self.editing_element_id = current_hash
                self.edit_buffer = {}
                self.has_unsaved_changes = False
            
            # Tip filtresi
            self._draw_type_filter(elements)
            
            imgui.separator()
            
            # Element özellikleri
            self._draw_properties(elements)
            
            # Apply/Discard butonları
            if self.has_unsaved_changes:
                imgui.separator()
                self._draw_action_buttons(elements)
        
        except Exception as e:
            logger.error(f"Properties window error: {e}")
            traceback.print_exc()
        finally:
            self._clear_styles()  # Her ihtimale karşı
            imgui.end()
    
    def _draw_type_filter(self, elements):
        """Tip filtresi combo box"""
        # Tip sayılarını hesapla
        type_counts = {}
        for e in elements:
            t_name = type(e).__name__
            type_counts[t_name] = type_counts.get(t_name, 0) + 1
        
        # Combo başlığı
        if self.filter_type != "All":
            count = type_counts.get(self.filter_type, 0)
            current_label = f"{self.filter_type} [{count}]"
        else:
            current_label = f"Show All ({len(elements)})"
        
        imgui.text_disabled("FILTER")
        imgui.push_item_width(-1)
        
        if imgui.begin_combo("##filter_combo", current_label):
            if imgui.selectable(f"Show All ({len(elements)})", self.filter_type == "All")[0]:
                self.filter_type = "All"
            
            imgui.separator()
            
            for t_name, count in type_counts.items():
                if imgui.selectable(f"{t_name} [{count}]", self.filter_type == t_name)[0]:
                    self.filter_type = t_name
            
            imgui.end_combo()
        
        imgui.pop_item_width()
        imgui.spacing()
    
    def _draw_restraint_editor(self, attr, elements):
        """Restraint editörü"""
        imgui.text_disabled("RESTRAINT")
        
        axes = ['ux', 'uy', 'uz', 'rx', 'ry', 'rz']
        labels = ['UX', 'UY', 'UZ', 'RX', 'RY', 'RZ']
        
        for i, (axis, label) in enumerate(zip(axes, labels)):
            path = f"{attr}.{axis}"
            
            # Ortak değer bul
            first_val = False
            common = True
            
            first_e = next((e for e in elements if hasattr(e, attr) and getattr(e, attr) is not None), None)
            if first_e:
                first_val = getattr(getattr(first_e, attr), axis, False)
                
                for e in elements[1:]:
                    if hasattr(e, attr) and getattr(e, attr) is not None:
                        if getattr(getattr(e, attr), axis, False) != first_val:
                            common = False
                            break
            
            # Ortak değilse gri yap
            if not common:
                self._push_style(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
            
            # Değeri al
            if path in self.edit_buffer:
                display_val = self.edit_buffer[path]
            else:
                display_val = first_val
            
            changed, new_val = imgui.checkbox(f"{label}##{path}", display_val)
            if changed:
                self.edit_buffer[path] = new_val
                self.has_unsaved_changes = True
            
            if not common:
                self._pop_style()
            
            if i % 3 != 2:
                imgui.same_line()
        
        # Restraint yoksa oluştur butonu
        has_restraint = any(hasattr(e, attr) and getattr(e, attr) is not None for e in elements)
        if not has_restraint and elements:
            imgui.text_colored("No restraints", 1.0, 1.0, 0.0, 1.0)
            if imgui.button("Create Restraint"):
                for e in elements:
                    e.restraint = Restraint()
                self.has_unsaved_changes = True
    
    def _draw_coord_editor(self, attr, elements, label):
        """Koordinat editörü"""
        # Ortak değer bul
        first_val = getattr(elements[0], attr)
        common = all(getattr(e, attr) == first_val for e in elements)
        
        if not common:
            self._push_style(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
        
        display_val = self.edit_buffer.get(attr, float(first_val))
        changed, new_val = imgui.input_float(f"{label}##{attr}", display_val)
        if changed:
            self.edit_buffer[attr] = new_val
            self.has_unsaved_changes = True
        
        if not common:
            self._pop_style()
    
    def _draw_float_editor(self, attr, elements, label):
        """Float editörü"""
        first_val = getattr(elements[0], attr)
        common = all(getattr(e, attr) == first_val for e in elements)
        
        if not common:
            self._push_style(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
        
        display_val = self.edit_buffer.get(attr, float(first_val))
        changed, new_val = imgui.input_float(f"{label}##{attr}", display_val)
        if changed:
            self.edit_buffer[attr] = new_val
            self.has_unsaved_changes = True
        
        if not common:
            self._pop_style()
    
    def _draw_text_editor(self, attr, elements, label):
        """Text editörü"""
        first_val = getattr(elements[0], attr)
        common = all(getattr(e, attr) == first_val for e in elements)
        
        if not common:
            self._push_style(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
        
        display_val = self.edit_buffer.get(attr, str(first_val))
        changed, new_val = imgui.input_text(f"{label}##{attr}", display_val, 256)
        if changed:
            self.edit_buffer[attr] = new_val
            self.has_unsaved_changes = True
        
        if not common:
            self._pop_style()
    
    def _draw_color_editor(self, attr, elements, label):
        """Renk editörü"""
        first_val = getattr(elements[0], attr)
        if isinstance(first_val, tuple):
            first_val = list(first_val)
        
        common = all(getattr(e, attr) == first_val for e in elements)
        
        if not common:
            self._push_style(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
        
        display_val = self.edit_buffer.get(attr, first_val[:3])
        changed, new_val = imgui.color_edit3(f"{label}##{attr}", *display_val)
        if changed:
            self.edit_buffer[attr] = list(new_val)
            self.has_unsaved_changes = True
        
        if not common:
            self._pop_style()
    
    def _draw_action_buttons(self, elements):
        """Apply/Discard butonları"""
        width = imgui.get_content_region_available_width()
        
        if imgui.button("Apply Changes", width=width):
            self._apply_changes(elements)
            self.has_unsaved_changes = False
            self.edit_buffer.clear()
        
        if imgui.button("Discard", width=width):
            self.editing_element_id = None
            self.edit_buffer.clear()
            self.has_unsaved_changes = False
    
    def _apply_changes(self, elements):
        """Değişiklikleri uygula - dirty flag ile"""
        for elem in elements:
            for path, value in self.edit_buffer.items():
                if '.' in path:
                    main, sub = path.split('.', 1)
                    if hasattr(elem, main):
                        target = getattr(elem, main)
                        if target is None and main == 'restraint':
                            target = Restraint()
                            setattr(elem, main, target)
                        if hasattr(target, sub):
                            setattr(target, sub, value)
                            elem.mark_dirty()  # Dirty işaretle
                else:
                    if hasattr(elem, path):
                        setattr(elem, path, value)
                        elem.mark_dirty()  # Dirty işaretle
        
        # Sadece dirty olanları güncelle
        if self.renderer:
            # Her renderer'a dirty güncelleme emri ver
            for renderer in [self.renderer.frame_r, self.renderer.node_r, 
                            self.renderer.area_r, self.renderer.link_r]:
                if renderer:
                    renderer.update_dirty()
        
        logger.info(f"Applied changes to {len(elements)} elements")
        self.has_unsaved_changes = False
        self.edit_buffer.clear()

    def _draw_properties(self, elements):
        """Element özelliklerini çiz - Section ve Material desteği ile"""
        # Filtre uygula
        if self.filter_type != "All":
            elements = [e for e in elements if type(e).__name__ == self.filter_type]
            if not elements:
                imgui.text_disabled("No elements match filter.")
                return
        
        # Ortak attribute'ları bul
        common_attrs = set(vars(elements[0]).keys())
        for e in elements[1:]:
            common_attrs &= set(vars(e).keys())
        
        # Siyah liste
        blacklist = {
            'element_id',
            'unique_id',
            'is_selected',
            '_id_counter',
            'needs_update',
            'dof_indices',
            'connected',
            '_node_cache',
            'guid',
            'profile_params',
            'pick_id'
        }
        
        # Her attribute için editor
        for attr in sorted(common_attrs):
            if attr in blacklist or attr.startswith('_'):
                continue
            
            # Değeri al
            val = getattr(elements[0], attr)
            
            # ===== ÖZEL EDITÖRLER =====
            if attr == 'restraint':
                self._draw_restraint_editor(attr, elements)
            
            elif attr == 'section':
                self._draw_section_editor(attr, elements)  # YENİ
            
            elif attr == 'material':
                self._draw_material_editor(attr, elements)  # YENİ
            
            elif attr == 'label':
                self._draw_text_editor(attr, elements, "Label")
            
            elif attr in ['x', 'y', 'z']:
                self._draw_coord_editor(attr, elements, attr.upper())
            
            elif attr == 'rotation_deg':
                self._draw_float_editor(attr, elements, "Rotation")
            
            elif attr == 'thickness':
                self._draw_float_editor(attr, elements, "Thickness")
            
            elif attr == 'propname':
                self._draw_text_editor(attr, elements, "Property")
            
            elif attr == 'color':
                self._draw_color_editor(attr, elements, "Color")
            
            elif attr == 'node_i' or attr == 'node_j':
                # Node referanslarını göster ama düzenlenemez
                if hasattr(val, 'label'):
                    imgui.text_disabled(f"{attr}: {val.label}")
            
            # ===== SAYISAL DEĞERLER =====
            elif isinstance(val, (int, float, np.number)):
                self._draw_float_editor(attr, elements, attr.capitalize())
            
            # ===== DİĞER NESNELER =====
            elif hasattr(val, 'name'):  # name attribute'u olan nesneler
                imgui.text_disabled(f"{attr}: {val.name}")
            
            elif isinstance(val, str):
                self._draw_text_editor(attr, elements, attr.capitalize())
            
            # ===== DİĞER (sadece göster) =====
            else:
                imgui.text(f"{attr}: {val}")

    def _draw_section_editor(self, attr, elements):
        """Section editörü - Frame'ler için"""
        imgui.text("Section")
        
        # Definition manager kontrolü
        if self.def_mgr is None:
            imgui.text_colored("def_mgr is None!", 1.0, 0.0, 0.0, 1.0)
            return
        
        # İsim-section eşlemesi oluştur
        name_to_section = {s.name: s for s in self.def_mgr.sections.values()}
        section_names = list(name_to_section.keys())
        
        if not section_names:
            imgui.text_colored("No sections defined", 1.0, 1.0, 0.0, 1.0)
            return
        
        # Ortak section kontrolü
        first_section = getattr(elements[0], attr, None)
        first_name = first_section.name if first_section else ""
        
        common = True
        for e in elements[1:]:
            s = getattr(e, attr, None)
            if (s is None and first_section is not None) or \
            (s is not None and s.name != first_name):
                common = False
                break
        
        # Combo box için hazırlık
        if not common:
            imgui.push_style_color(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
            current_idx = -1
            preview = "Multiple values"
        else:
            current_idx = section_names.index(first_name) if first_name in section_names else -1
            preview = first_name if first_name else "None"
        
        # Combo box'ı çiz
        imgui.push_item_width(-1)
        clicked, selected_idx = imgui.combo(
            f"##{attr}_combo",
            current_idx,
            section_names
        )
        imgui.pop_item_width()
        
        if not common:
            imgui.pop_style_color(1)
        
        # Seçim değiştiyse uygula
        if clicked and selected_idx != current_idx:
            selected_name = section_names[selected_idx]
            new_section = name_to_section[selected_name]  # İsimden section bul
            
            for e in elements:
                if hasattr(e, attr):
                    setattr(e, attr, new_section)
                    e.mark_dirty()
            
            self.has_unsaved_changes = True
            print(f"DEBUG: Section changed to {selected_name}")

    def _draw_material_editor(self, attr, elements):
        """Material editörü - Section'lar için"""
        imgui.text("Material")
        
        if self.def_mgr is None:
            imgui.text_colored("def_mgr is None!", 1.0, 0.0, 0.0, 1.0)
            return
        
        # İsim-material eşlemesi
        name_to_material = {m.name: m for m in self.def_mgr.materials.values()}
        material_names = list(name_to_material.keys())
        
        if not material_names:
            imgui.text_colored("No materials defined", 1.0, 1.0, 0.0, 1.0)
            return
        
        # Ortak material kontrolü
        first_mat = getattr(elements[0], attr, None)
        first_name = first_mat.name if first_mat else ""
        
        common = True
        for e in elements[1:]:
            m = getattr(e, attr, None)
            if (m is None and first_mat is not None) or \
            (m is not None and m.name != first_name):
                common = False
                break
        
        if not common:
            imgui.push_style_color(imgui.COLOR_TEXT, 0.5, 0.5, 0.5, 1.0)
            current_idx = -1
            preview = "Multiple values"
        else:
            current_idx = material_names.index(first_name) if first_name in material_names else -1
            preview = first_name if first_name else "None"
        
        imgui.push_item_width(-1)
        clicked, selected_idx = imgui.combo(
            f"##{attr}_combo",
            current_idx,
            material_names
        )
        imgui.pop_item_width()
        
        if not common:
            imgui.pop_style_color(1)
        
        if clicked and selected_idx != current_idx:
            selected_name = material_names[selected_idx]
            new_material = name_to_material[selected_name]
            
            for e in elements:
                if hasattr(e, attr):
                    setattr(e, attr, new_material)
                    e.mark_dirty()
            
            self.has_unsaved_changes = True