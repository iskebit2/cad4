# tools/s2kloader.py

# --- Shiboken / PySide6 & six Python 3.12 Yama Bloğu ---
try:
    import six
    import sys
    for importer in sys.meta_path:
        if type(importer).__name__ == '_SixMetaPathImporter':
            if not hasattr(importer, '_path'):
                importer._path = []
except Exception:
    pass
# --------------------------------------------------------

import re
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging
from pathlib import Path
import sys
import ctypes
from ctypes import wintypes
from domain.element import Node, Frame, Area, Link, Section, SectionType
from domain.definition import Material, MatType
from domain.scene import Scene
from geometry.scenebuilder import SceneBuilder

logger = logging.getLogger(__name__)

def show_file_dialog() -> Optional[str]:
    """Show file dialog to select S2K file (Windows only)"""
    if sys.platform != 'win32':
        logger.warning("File dialog only supported on Windows")
        return None
    
    class OPENFILENAME(ctypes.Structure):
        _fields_ = [
            ("lStructSize", wintypes.DWORD),
            ("hwndOwner", wintypes.HWND),
            ("hInstance", wintypes.HINSTANCE),
            ("lpstrFilter", wintypes.LPCWSTR),
            ("lpstrCustomFilter", wintypes.LPWSTR),
            ("nMaxCustFilter", wintypes.DWORD),
            ("nFilterIndex", wintypes.DWORD),
            ("lpstrFile", wintypes.LPWSTR),
            ("nMaxFile", wintypes.DWORD),
            ("lpstrFileTitle", wintypes.LPWSTR),
            ("nMaxFileTitle", wintypes.DWORD),
            ("lpstrInitialDir", wintypes.LPCWSTR),
            ("lpstrTitle", wintypes.LPCWSTR),
            ("Flags", wintypes.DWORD),
            ("nFileOffset", wintypes.WORD),
            ("nFileExtension", wintypes.WORD),
            ("lpstrDefExt", wintypes.LPCWSTR),
            ("lCustData", wintypes.LPARAM),
            ("lpfnHook", ctypes.c_void_p),
            ("lpTemplateName", wintypes.LPCWSTR)
        ]
    
    buffer = ctypes.create_unicode_buffer(260)
    ofn = OPENFILENAME()
    ofn.lStructSize = ctypes.sizeof(OPENFILENAME)
    ofn.lpstrFilter = "S2K Files\0*.$2k;*.s2k\0All Files\0*.*\0"
    ofn.lpstrFile = ctypes.cast(buffer, wintypes.LPWSTR)
    ofn.nMaxFile = len(buffer)
    ofn.lpstrTitle = "Select S2K File"
    ofn.Flags = 0x00000800 | 0x00000004  # OFN_EXPLORER | OFN_HIDEREADONLY
    
    if ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn)):
        return buffer.value
    
    return None

class S2KParser:
    """SAP2000 s2k dosya okuma (UI Bağımsız Saf Parser)"""
    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path
        self.tables: Dict[str, pd.DataFrame] = {}
        self.points: Dict[str, np.ndarray] = {}
        
        # Eğer file_path verilmişse doğrudan yükle
        if self.file_path:
            self._load_and_parse(self.file_path)

    def _load_and_parse(self, file_: Optional[str] = None):
        """Load and parse S2K file"""
        # Parametre geldiyse dosya yolunu güncelle
        if file_:
            self.file_path = file_
            
        if not self.file_path:
            logger.warning("[S2KParser] No file path provided to parse.")
            return

        target_path = Path(self.file_path)
        if not target_path.exists():
            logger.error(f"[S2KParser] File '{self.file_path}' not found.")
            return

        try:
            with open(target_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            logger.info(f"[S2KParser] Loaded file: {self.file_path}, size: {len(content)} bytes")
        except Exception as e:
            logger.error(f"[S2KParser] Error reading file: {e}")
            return
        
        # Handle continuation lines
        content = re.sub(r' _\r?\n', ' ', content)
        
        # Split into tables
        raw_tables = re.split(r'TABLE:\s*"*', content)
        logger.info(f"[S2KParser] Found {len(raw_tables)} potential tables")
        
        table_count = 0
        for raw_table in raw_tables:
            if not raw_table.strip():
                continue
            
            lines = raw_table.strip().split('\n')
            if not lines:
                continue
            
            table_name = lines[0].strip().strip('"')
            data = []
            
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                
                # Parse key-value pairs
                pairs = re.findall(r'(\w+)=("[^"]*"|[^\s]+)', line)
                if pairs:
                    row_dict = {}
                    for key, value in pairs:
                        # Remove quotes
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        row_dict[key] = value
                    data.append(row_dict)
            
            if data:
                self.tables[table_name] = pd.DataFrame(data)
                table_count += 1
                logger.debug(f"  Loaded table: {table_name} ({len(data)} rows)")
        
        logger.info(f"[S2KParser] Loaded {table_count} tables")
    
    def get_table(self, table_name: str) -> pd.DataFrame:
        """Get table by name, return empty DataFrame if not found"""
        return self.tables.get(table_name, pd.DataFrame())


def map_sap_to_local_params(sap_row: pd.Series) -> Tuple[SectionType, Dict[str, float]]:
    """Convert SAP2000 parameters to our SectionParams format"""
    s_type = str(sap_row.get('Shape', 'Rectangle')).strip()
    
    try:
        if s_type == "I/Wide Flange" or s_type == "I":
            return SectionType.I, {
                "h": float(sap_row.get('t3', 200.0)),
                "b": float(sap_row.get('t2', 100.0)),
                "tw": float(sap_row.get('tw', 10.0)),
                "tf": float(sap_row.get('tf', 14.0))
            }
        elif s_type == "Rectangle" or s_type == "Rectangular":
            return SectionType.RECT, {
                "h": float(sap_row.get('t3', 200.0)),
                "b": float(sap_row.get('t2', 100.0))
            }
        elif s_type == "Pipe" or s_type == "Circular":
            t3 = float(sap_row.get('t3', 120.0))
            tw = float(sap_row.get('tw', 10.0))
            return SectionType.PIPE, {
                "ro": t3 / 2,
                "ri": max(0.1, (t3 - 2 * tw) / 2),
                "n": 24
            }
        elif s_type == "Channel" or s_type == "C":
            return SectionType.C, {
                "h": float(sap_row.get('t3', 100.0)),
                "b": float(sap_row.get('t2', 80.0)),
                "t": float(sap_row.get('tw', 6.0))
            }
        elif s_type == "Angle" or s_type == "L":
            return SectionType.L, {
                "h": float(sap_row.get('t3', 100.0)),
                "b": float(sap_row.get('t2', 80.0)),
                "t": float(sap_row.get('tw', 8.0))
            }
        elif s_type == "Tube" or s_type == "Box":
            return SectionType.TUBE, {
                "h": float(sap_row.get('t3', 200.0)),
                "b": float(sap_row.get('t2', 100.0)),
                "t": float(sap_row.get('tw', 10.0))
            }
        else:
            logger.debug(f"Warning: Unknown section type '{s_type}', using default rectangle")
            return SectionType.RECT, {"h": 200.0, "b": 100.0}
    except (ValueError, KeyError) as e:
        logger.debug(f"Error mapping section parameters for type '{s_type}': {e}")
        return SectionType.RECT, {"h": 200.0, "b": 100.0}


def get_color_from_string(color_str: str) -> Tuple[float, float, float]:
    """SAP2000 renk string'ini RGB tuple'a çevir"""
    color_map = {
        'Red': (1.0, 0.0, 0.0),
        'Green': (0.0, 1.0, 0.0),
        'Blue': (0.0, 0.0, 1.0),
        'Yellow': (1.0, 1.0, 0.0),
        'Cyan': (0.0, 1.0, 1.0),
        'Magenta': (1.0, 0.0, 1.0),
        'White': (1.0, 1.0, 1.0),
        'Black': (0.0, 0.0, 0.0),
        'Gray8Dark': (0.3, 0.3, 0.3),
        'Gray8Light': (0.7, 0.7, 0.7),
    }
    return color_map.get(color_str, (0.8, 0.8, 0.8))

def parse_sap_restraint(restraint_str: str) -> Optional[Dict[str, bool]]:
    """
    SAP2000 restraint string'ini sözlüğe çevir
    Örnek: "UX,UY,UZ,RX,RY,RZ" -> {'ux':True, 'uy':True, 'uz':True, 'rx':True, 'ry':True, 'rz':True}
    """
    if pd.isna(restraint_str) or not restraint_str:
        return None
    
    # DOF eşlemesi (SAP2000 isimleri -> bizim isimler)
    dof_map = {
        'UX': 'ux', 'UY': 'uy', 'UZ': 'uz',
        'RX': 'rx', 'RY': 'ry', 'RZ': 'rz'
    }
    
    restraint_dict = {}
    
    # SAP2000'de restraint string'i şöyle olabilir: "UX UY UZ" veya "UX,UY,UZ" veya "UX UY UZ RX RY RZ"
    # Önce virgülle ayır, sonra boşlukla ayır
    parts = []
    if ',' in restraint_str:
        parts = restraint_str.split(',')
    else:
        parts = restraint_str.split()
    
    for part in parts:
        part = part.strip().upper()
        if part in dof_map:
            restraint_dict[dof_map[part]] = True
            logger.debug(f"    Added restraint: {part} -> {dof_map[part]}")
    
    return restraint_dict if restraint_dict else None

class S2KLoader:
    """SAP2000 .$2k dosyasından model yükler"""
    
    def __init__(self, file_path: Optional[str] = None):
        # Dosya yolu dışarıdan geldiyse kullan, gelmediyse fallback diyaloğu dene
        self.file_path = file_path or show_file_dialog()
        
        if not self.file_path:
            logger.warning("[S2KLoader] Yüklenecek dosya seçilmedi veya yol geçersiz.")
            self.parser = None
            return

        self.parser = S2KParser(self.file_path)
        self.builder = SceneBuilder()
        self._sections: Dict[str, Section] = {}
        self._link_props: Dict[str, str] = {}
    
    def load(self) -> Scene:
        """Modeli yükle ve Scene döndür"""
        logger.info("[S2KLoader] Building model...")
        
        # 1. Tüm tabloları al
        df_j = self.parser.get_table("JOINT COORDINATES")
        df_j_rest = self.parser.get_table("JOINT RESTRAINT ASSIGNMENTS")  # YENİ
        df_f_conn = self.parser.get_table("CONNECTIVITY - FRAME")
        df_a_conn = self.parser.get_table("CONNECTIVITY - AREA")
        df_l_conn = self.parser.get_table("CONNECTIVITY - LINK")
        
        df_s = self.parser.get_table("FRAME SECTION PROPERTIES 01 - GENERAL")
        df_a_prop = self.parser.get_table("AREA SECTION PROPERTIES")
        df_l_prop = self.parser.get_table("LINK PROPERTY DEFINITIONS 01 - GENERAL")
        
        df_f_assign = self.parser.get_table("FRAME SECTION ASSIGNMENTS")
        df_a_assign = self.parser.get_table("AREA SECTION ASSIGNMENTS")
        df_l_assign = self.parser.get_table("LINK PROPERTY ASSIGNMENTS")
        
        if df_j.empty:
            logger.error("JOINT COORDINATES table not found!")
            return self.builder.scene
        
        # 2. Frame kesitlerini yükle
        sections_lib = {}
        if not df_s.empty:
            for _, row in df_s.iterrows():
                sect_name = row.get('SectionName', row.get('Section', 'DEFAULT'))
                s_type, s_params = map_sap_to_local_params(row)
                color = get_color_from_string(row.get('Color', 'Gray8Dark'))
                
                section = Section(
                    name=sect_name,
                    profile_type=s_type,
                    profile_params=s_params,
                    color=color
                )
                self._sections[sect_name] = section
                sections_lib[sect_name] = section
                self.builder.def_mgr.add_section(section)  # Definition manager'a ekle
        
        logger.info(f"  Loaded {len(self._sections)} frame sections")
        
        # 3. Area kalınlıklarını yükle
        area_thickness = {}
        if not df_a_prop.empty:
            for _, row in df_a_prop.iterrows():
                sect_name = row.get('Section', 'DEFAULT')
                thickness = float(row.get('Thickness', 100.0))
                area_thickness[sect_name] = thickness
        
        # 4. Link property'lerini yükle
        if not df_l_prop.empty:
            for _, row in df_l_prop.iterrows():
                link_id = row.get('Link', '')
                prop_name = row.get('LinkType', 'LINEAR')
                if link_id:
                    self._link_props[link_id] = prop_name
        
        # 5. Restraint bilgilerini hazırla (node -> restraint dict)
        restraint_map = {}
        if not df_j_rest.empty:
            logger.info(f"  Found {len(df_j_rest)} restraint rows")
            
            # DOF eşlemesi (SAP2000 kolon isimleri -> bizim isimler)
            dof_map = {
                'U1': 'ux',
                'U2': 'uy', 
                'U3': 'uz',
                'R1': 'rx',
                'R2': 'ry',
                'R3': 'rz'
            }
            
            for idx, row in df_j_rest.iterrows():
                joint_id = str(row.get('Joint', ''))
                
                # Her bir DOF için kontrol et
                restraint_dict = {}
                for sap_dof, our_dof in dof_map.items():
                    if sap_dof in row:
                        value = str(row[sap_dof]).strip().upper()
                        if value == 'YES':
                            restraint_dict[our_dof] = True
                            logger.debug(f"    Node {joint_id}: {sap_dof} -> {our_dof} = YES")
                
                if restraint_dict:
                    restraint_map[joint_id] = restraint_dict
                    logger.debug(f"    Node {joint_id} restraints: {restraint_dict}")
            
            logger.info(f"  Loaded {len(restraint_map)} node restraints")
        
        # 6. Noktaları oluştur (restraint ile)
        node_map = {}
        for _, row in df_j.iterrows():
            joint_id = str(row.get('Joint', ''))
            if not joint_id:
                continue
            
            x = float(row.get('XorR', row.get('X', 0)))
            y = float(row.get('Y', 0))
            z = float(row.get('Z', 0))
            
            # Restraint varsa al
            restraint_dict = restraint_map.get(joint_id)
            
            node = self.builder.create_node(
                x, y, z,
                label=f"N{joint_id}",
                restraint=restraint_dict  # Restraint sözlüğü doğrudan geç
            )
            node_map[joint_id] = node
        
        logger.info(f"  Loaded {len(node_map)} nodes")
        
        # 7. Frame'leri oluştur
        frame_count = 0
        if not df_f_conn.empty:
            for _, row in df_f_conn.iterrows():
                frame_id = str(row.get('Frame', ''))
                joint_i = str(row.get('JointI', ''))
                joint_j = str(row.get('JointJ', ''))
                
                if not frame_id or joint_i not in node_map or joint_j not in node_map:
                    continue
                
                # Kesit bilgisini bul
                section_name = "DEFAULT"
                rotation = 0.0
                
                if not df_f_assign.empty:
                    assign = df_f_assign[df_f_assign['Frame'] == frame_id]
                    if not assign.empty:
                        section_name = assign.iloc[0].get('AnalSect', assign.iloc[0].get('Section', 'DEFAULT'))
                        rotation = float(assign.iloc[0].get('Angle', 0.0))

                if section_name not in self.builder.def_mgr.sections:
                    # 2. Yoksa dosyadan yüklenen ilk kesiti yedek olarak al
                    if self._sections:
                        fallback_section = list(self._sections.values())[0]
                        section_name = fallback_section.name
                    else:
                        # 3. Dosyadan hiç kesit çıkmadıysa varsayılan bir kesit oluştur ve ekle
                        if "DEFAULT" not in self.builder.def_mgr.sections:
                            default_sec = Section(
                                name="DEFAULT",
                                profile_type=SectionType.RECT,
                                profile_params={"h": 200.0, "b": 100.0},
                                color=(0.5, 0.5, 0.5)
                            )
                            self.builder.def_mgr.add_section(default_sec)
                        section_name = "DEFAULT"
                        
                section = sections_lib.get(section_name)
                if not section and self._sections:
                    section = list(self._sections.values())[0]
                
                if section:
                    self.builder.create_frame(
                        node_map[joint_i],
                        node_map[joint_j],
                        section_name,  # section_name ile
                        rotation_deg=rotation,
                        label=f"F{frame_id}"
                    )
                    frame_count += 1
        
        logger.info(f"  Loaded {frame_count} frames")
        
        # 8. Area'ları oluştur
        area_count = 0
        if not df_a_conn.empty:
            for _, row in df_a_conn.iterrows():
                area_id = str(row.get('Area', ''))
                joints = []
                for i in range(1, 5):
                    joint = str(row.get(f'Joint{i}', ''))
                    if joint and joint in node_map:
                        joints.append(node_map[joint])
                
                if len(joints) < 3:
                    continue
                
                # Kalınlık bilgisini bul
                thickness = 100.0
                if not df_a_assign.empty:
                    assign = df_a_assign[df_a_assign['Area'] == area_id]
                    if not assign.empty:
                        sect_name = assign.iloc[0].get('Section', 'DEFAULT')
                        thickness = area_thickness.get(sect_name, 100.0)
                
                self.builder.create_area(
                    joints,
                    thickness,
                    label=f"A{area_id}"
                )
                area_count += 1
        
        logger.info(f"  Loaded {area_count} areas")
        
        # 9. Link'leri oluştur
        link_count = 0
        if not df_l_conn.empty:
            for _, row in df_l_conn.iterrows():
                link_id = str(row.get('Link', ''))
                joint_i = str(row.get('JointI', ''))
                joint_j = str(row.get('JointJ', ''))
                
                if not link_id or joint_i not in node_map or joint_j not in node_map:
                    continue
                
                prop_name = self._link_props.get(link_id, "LINK1")
                
                self.builder.create_link(
                    node_map[joint_i],
                    node_map[joint_j],
                    prop_name,
                    label=f"L{link_id}"
                )
                link_count += 1
        
        logger.info(f"  Loaded {link_count} links")
        
        return self.builder.scene