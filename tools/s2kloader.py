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
from logging_config import CadLogger
from pathlib import Path
import sys
import ctypes
from ctypes import wintypes
from domain.element import Node, Frame, Area, Link, Section, SectionType
from domain.definition import Material, MatType
from domain.scene import Scene
from geometry.scenebuilder import SceneBuilder

from logging_config import CadLogger

logger = CadLogger.get(__name__)

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
                # logger.debug(f"  Loaded table: {table_name} ({len(data)} rows)")
        
        logger.info(f"[S2KParser] Loaded {table_count} tables")
    
    def get_table(self, table_name: str) -> pd.DataFrame:
        """Get table by name, return empty DataFrame if not found"""
        return self.tables.get(table_name, pd.DataFrame())


def map_sap_to_local_params(sap_row: pd.Series) -> Tuple[SectionType, Dict[str, float]]:
    """Convert SAP2000 parameters to our SectionParams format while preserving 3D mesh geometry keys."""
    s_type = str(sap_row.get('Shape', 'Rectangle')).strip()
    
    # SAP2000'den gelen ham analiz ve statik verileri güvenli şekilde floata çevir
    def safe_float(key: str, default: float = 0.0, allow_zero: bool = True) -> float:
        val = sap_row.get(key)
        if val is None or str(val).strip() in ("", "None", "nan"):
            return default
        try:
            f_val = float(val)
            if not allow_zero and abs(f_val) < 1e-12:
                return default
            return f_val
        except (ValueError, TypeError):
            return default

    # GUID ve Notes HARİÇ S2K'daki tüm kesit parametreleri
    analysis_params = {
        'Area': safe_float('Area'),
        'J': safe_float('TorsConst'),        # TorsConst -> J
        'I33': safe_float('I33'),
        'I22': safe_float('I22'),
        'I23': safe_float('I23'),
        'AS2': safe_float('AS2'),
        'AS3': safe_float('AS3'),
        'S33Top': safe_float('S33Top'),
        'S33Bot': safe_float('S33Bot'),
        'S22Left': safe_float('S22Left'),
        'S22Right': safe_float('S22Right'),
        'Z33': safe_float('Z33'),
        'Z22': safe_float('Z22'),
        'R33': safe_float('R33'),
        'R22': safe_float('R22'),
        'CGOffset3': safe_float('CGOffset3'),
        'CGOffset2': safe_float('CGOffset2'),
        'EccV2': safe_float('EccV2'),
        'EccV3': safe_float('EccV3'),
        'Cw': safe_float('Cw'),
        'AMod': safe_float('AMod', 1.0),
        'A2Mod': safe_float('A2Mod', 1.0),
        'A3Mod': safe_float('A3Mod', 1.0),
        'JMod': safe_float('JMod', 1.0),
        'I2Mod': safe_float('I2Mod', 1.0),
        'I3Mod': safe_float('I3Mod', 1.0),
        'MMod': safe_float('MMod', 1.0),
        'WMod': safe_float('WMod', 1.0),
    }

    
    try:
        if s_type == "I/Wide Flange" or s_type == "I":
            params = {
                "h": safe_float('t3', 200.0),
                "b": safe_float('t2', 100.0),
                "tw": safe_float('tw', 10.0),
                "tf": safe_float('tf', 14.0)
            }
            params.update(analysis_params)
            return SectionType.I, params

        elif s_type == "Rectangle" or s_type == "Rectangular":
            params = {
                "h": safe_float('t3', 200.0),
                "b": safe_float('t2', 100.0)
            }
            params.update(analysis_params)
            return SectionType.RECT, params

        elif s_type == "Pipe" or s_type == "Circular" or s_type == "Circle":
            t3 = safe_float('t3', 120.0)
            tw = safe_float('tw', 10.0)
            params = {
                "ro": t3 / 2,
                "ri": max(0.1, (t3 - 2 * tw) / 2),
                "n": 24
            }
            params.update(analysis_params)
            return SectionType.PIPE, params

        elif s_type == "Channel" or s_type == "C":
            params = {
                "h": safe_float('t3', 100.0),
                "b": safe_float('t2', 80.0),
                "t": safe_float('tw', 6.0)
            }
            params.update(analysis_params)
            return SectionType.C, params

        elif s_type == "Angle" or s_type == "L":
            params = {
                "h": safe_float('t3', 100.0),
                "b": safe_float('t2', 80.0),
                "t": safe_float('tw', 8.0)
            }
            params.update(analysis_params)
            return SectionType.L, params

        elif s_type == "Tube" or s_type == "Box":
            params = {
                "h": safe_float('t3', 200.0),
                "b": safe_float('t2', 100.0),
                "t": safe_float('tw', 10.0)
            }
            params.update(analysis_params)
            return SectionType.TUBE, params

        else:
            # logger.debug(f"Warning: Unknown section type '{s_type}', using default rectangle")
            params = {"h": 200.0, "b": 100.0}
            params.update(analysis_params)
            return SectionType.RECT, params

    except (ValueError, KeyError) as e:
        # logger.debug(f"Error mapping section parameters for type '{s_type}': {e}")
        params = {"h": 200.0, "b": 100.0}
        params.update(analysis_params)
        return SectionType.RECT, params


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
            # logger.debug(f"    Added restraint: {part} -> {dof_map[part]}")
    
    return restraint_dict if restraint_dict else None

def parse_sap_mat_type(row: dict) -> MatType:
    """
    SAP2000'deki Type, Grade ve Material isimlerinden 
    güvenli bir şekilde MatType türetir.
    """
    raw_type = str(row.get('Type', '')).upper().strip()
    raw_grade = str(row.get('Grade', '')).upper().strip()
    raw_name = str(row.get('Material', '')).upper().strip()

    # 1. Doğrudan Tip Eşleşmeleri
    if raw_type == "STEEL":
        return MatType.STEEL
    elif raw_type == "CONCRETE":
        return MatType.CONCRETE
    elif raw_type == "REBAR":
        return MatType.REBAR
    elif raw_type == "TENDON":
        return MatType.TENDON
    elif raw_type == "ALUMINUM":
        return MatType.ALUMINUM
    elif raw_type == "COLDFORMED":
        return MatType.COLDFORMED

    # 2. Type "OTHER" ise Grade veya Name üzerinden akıllı tespit
    if raw_type == "OTHER":
        # Ahşap Kontrolü
        if "WOOD" in raw_grade or "TIMBER" in raw_grade or "OSB" in raw_grade or raw_name.startswith("C"):
            return getattr(MatType, 'TIMBER', MatType.NODESIGN)
        
        # Yığma / Taş Duvar Kontrolü
        if "TAS" in raw_name or "DUVAR" in raw_name or "MASONRY" in raw_name or "BRICK" in raw_name:
            return getattr(MatType, 'MASONRY', MatType.NODESIGN)

    # 3. Hiçbiri tutmazsa fallback
    return MatType.NODESIGN

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
        """
        S2K dosyasını yükle ve Scene döndür.
        
        Akış:
        1. Malzemeleri yükle
        2. Kesitleri yükle
        3. Area kalınlıklarını yükle
        4. Link property'lerini yükle
        5. Node restraint'larını yükle
        6. Node'ları oluştur
        7. Frame'leri oluştur (section atamalarıyla)
        8. Area'ları oluştur
        9. Link'leri oluştur
        """
        logger.info("[S2KLoader] Model oluşturuluyor...")
        
        # ============================================================
        # 1. Tabloları al
        # ============================================================


        df_joints      = self.parser.get_table("JOINT COORDINATES")
        df_joint_rest  = self.parser.get_table("JOINT RESTRAINT ASSIGNMENTS")
        df_frame_conn  = self.parser.get_table("CONNECTIVITY - FRAME")
        df_area_conn   = self.parser.get_table("CONNECTIVITY - AREA")
        df_link_conn   = self.parser.get_table("CONNECTIVITY - LINK")
        
        df_frame_props = self.parser.get_table("FRAME SECTION PROPERTIES 01 - GENERAL")
        df_area_props  = self.parser.get_table("AREA SECTION PROPERTIES")
        df_link_props  = self.parser.get_table("LINK PROPERTY DEFINITIONS 01 - GENERAL")
        
        df_frame_assign = self.parser.get_table("FRAME SECTION ASSIGNMENTS")
        df_area_assign  = self.parser.get_table("AREA SECTION ASSIGNMENTS")
        df_link_assign  = self.parser.get_table("LINK PROPERTY ASSIGNMENTS")
        
        df_mat_props = self.parser.get_table("MATERIAL PROPERTIES 01 - GENERAL")
        df_mat_mech  = self.parser.get_table("MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES")

        df_frame_release = self.parser.get_table("FRAME RELEASE ASSIGNMENTS 1 - GENERAL")
        
        if df_joints.empty:
            logger.error("JOINT COORDINATES tablosu bulunamadı!")
            return self.builder.scene
        
        # ============================================================
        # 2. Malzemeleri yükle
        # ============================================================
        materials = self._load_materials(df_mat_props, df_mat_mech)
        logger.info(f"  {len(materials)} malzeme yüklendi")
        
        # ============================================================
        # 3. Frame kesitlerini yükle
        # ============================================================
        sections = self._load_frame_sections(df_frame_props, materials)
        logger.info(f"  {len(sections)} frame kesiti yüklendi")
        
        # ============================================================
        # 4. Area kalınlıklarını yükle
        # ============================================================
        area_thickness = self._load_area_thicknesses(df_area_props)
        logger.info(f"  {len(area_thickness)} area kalınlığı yüklendi")
        
        # ============================================================
        # 5. Link property'lerini yükle
        # ============================================================
        link_props = self._load_link_properties(df_link_props)
        logger.info(f"  {len(link_props)} link property yüklendi")
        
        # ============================================================
        # 6. Node restraint'larını yükle
        # ============================================================
        restraints = self._load_node_restraints(df_joint_rest)
        logger.info(f"  {len(restraints)} node restraint yüklendi")
        
        # ============================================================
        # 7. Node'ları oluştur
        # ============================================================
        node_map = self._create_nodes(df_joints, restraints)
        logger.info(f"  {len(node_map)} node oluşturuldu")
        
        # ============================================================
        # 8. Frame'leri oluştur (section atamalarıyla)
        # ============================================================
        frame_count = self._create_frames(
            df_frame_conn, df_frame_assign, df_frame_release, node_map, sections
        )
        logger.info(f"  {frame_count} frame oluşturuldu")
        
        # ============================================================
        # 9. Area'ları oluştur
        # ============================================================
        area_count = self._create_areas(
            df_area_conn, df_area_assign, node_map, area_thickness
        )
        logger.info(f"  {area_count} area oluşturuldu")
        
        # ============================================================
        # 10. Link'leri oluştur
        # ============================================================
        link_count = self._create_links(
            df_link_conn, df_link_assign, node_map, link_props
        )
        logger.info(f"  {link_count} link oluşturuldu")
        
        return self.builder.scene


    # ================================================================
    # YARDIMCI METODLAR
    # ================================================================

    def _load_materials(self, df_props, df_mech) -> Dict[str, Material]:
        """Malzemeleri yükle ve döndür."""
        materials = {}
        
        if df_props.empty:
            return materials
        
        # Mekanik özellikleri indexle
        mech_index = {}
        if not df_mech.empty:
            mech_index = df_mech.set_index('Material').to_dict(orient='index')
        
        def safe_float(d, key, fallback):
            val = d.get(key)
            if val is None or str(val).strip() in ("", "None", "nan"):
                return fallback
            try:
                f_val = float(val)
                return f_val if f_val > 0 else fallback
            except (ValueError, TypeError):
                return fallback
        
        for _, row in df_props.iterrows():
            name = str(row.get('Material', '')).strip()
            if not name:
                continue
            
            mat_type = parse_sap_mat_type(row)
            color = get_color_from_string(row.get('Color', 'Gray8Dark'))
            mech = mech_index.get(name, {})
            
            e1 = safe_float(mech, 'E1', 2.0e8)
            
            material = Material(
                name=name,
                mat_type=mat_type,
                color=color,
                E1=e1,
                E2=safe_float(mech, 'E2', e1),
                E3=safe_float(mech, 'E3', e1),
                G12=safe_float(mech, 'G12', 7.7e7),
                G13=safe_float(mech, 'G13', 7.7e7),
                G23=safe_float(mech, 'G23', 7.7e7),
                nu12=safe_float(mech, 'U12', 0.3),
                nu13=safe_float(mech, 'U13', 0.3),
                nu23=safe_float(mech, 'U23', 0.3),
                density=safe_float(mech, 'UnitMass', 7.85e-9),
            )
            
            materials[name] = material
            self.builder.def_mgr.add_material(material)
        
        return materials


    def _load_frame_sections(self, df_props, materials) -> Dict[str, Section]:
        """Frame kesitlerini yükle. İsimle key'li dict döndür."""
        sections = {}
        
        if df_props.empty:
            return sections
        
        # SectionName kolonunu bul
        name_col = None
        for candidate in ('SectionName', 'Section', 'Name'):
            if candidate in df_props.columns:
                name_col = candidate
                break
        
        if name_col is None:
            logger.error("FRAME SECTION PROPERTIES tablosunda isim kolonu bulunamadı!")
            return sections
        
        for _, row in df_props.iterrows():
            sect_name = str(row.get(name_col, '')).strip()
            if not sect_name:
                continue
            
            s_type, s_params = map_sap_to_local_params(row)
            color = get_color_from_string(row.get('Color', 'Gray8Dark'))
            mat_name = str(row.get('Material', '')).strip()
            mat_obj = materials.get(mat_name)
            
            section = Section(
                name=sect_name,
                profile_type=s_type,
                profile_params=s_params,
                material=mat_obj,
                color=color,
            )
            
            sections[sect_name] = section
            self._sections[sect_name] = section
            self.builder.def_mgr.add_section(section)
        
        return sections


    def _load_area_thicknesses(self, df_props) -> Dict[str, float]:
        """Area section adı → kalınlık eşlemesi."""
        thicknesses = {}
        if df_props.empty:
            return thicknesses
        
        for _, row in df_props.iterrows():
            name = str(row.get('Section', '')).strip()
            if not name:
                continue
            try:
                thicknesses[name] = float(row.get('Thickness', 100.0))
            except (ValueError, TypeError):
                thicknesses[name] = 100.0
        
        return thicknesses


    def _load_link_properties(self, df_props) -> Dict[str, str]:
        """Link ID → property name eşlemesi."""
        props = {}
        if df_props.empty:
            return props
        
        for _, row in df_props.iterrows():
            link_id = str(row.get('Link', '')).strip()
            prop_name = str(row.get('LinkType', 'LINEAR')).strip()
            if link_id:
                props[link_id] = prop_name
                self._link_props[link_id] = prop_name
        
        return props


    def _load_node_restraints(self, df_rest) -> Dict[str, Dict[str, bool]]:
        """Node ID → restraint dict eşlemesi."""
        restraints = {}
        if df_rest.empty:
            return restraints
        
        dof_map = {'U1': 'ux', 'U2': 'uy', 'U3': 'uz',
                'R1': 'rx', 'R2': 'ry', 'R3': 'rz'}
        
        for _, row in df_rest.iterrows():
            joint_id = str(row.get('Joint', '')).strip()
            if not joint_id:
                continue
            
            restraint_dict = {}
            for sap_dof, our_dof in dof_map.items():
                value = str(row.get(sap_dof, '')).strip().upper()
                if value == 'YES':
                    restraint_dict[our_dof] = True
            
            if restraint_dict:
                restraints[joint_id] = restraint_dict
        
        return restraints


    def _create_nodes(self, df_joints, restraints) -> Dict[str, Node]:
        """Node'ları oluştur."""
        node_map = {}
        
        for _, row in df_joints.iterrows():
            joint_id = str(row.get('Joint', '')).strip()
            if not joint_id:
                continue
            
            try:
                x = float(row.get('XorR', row.get('X', 0)))
                y = float(row.get('Y', 0))
                z = float(row.get('Z', 0))
            except (ValueError, TypeError):
                logger.warning(f"Node {joint_id}: geçersiz koordinat")
                continue
            
            restraint = restraints.get(joint_id)
            
            node = self.builder.create_node(
                x, y, z,
                label=f"N{joint_id}",
                restraint=restraint,
            )
            node_map[joint_id] = node
        
        return node_map

    def _create_frames(self, df_conn, df_assign, df_release, node_map, sections) -> int:
        """Frame'leri oluştur. Her frame'e doğru section ve release bilgisi atanır."""
        if df_conn.empty:
            return 0
        
        # ---- Section atamaları ----
        frame_assign = {}
        if not df_assign.empty and 'Frame' in df_assign.columns:
            for _, row in df_assign.iterrows():
                frame_id = str(row.get('Frame', '')).strip()
                if not frame_id:
                    continue
                
                sect = str(row.get('AnalSect', '')).strip()
                if not sect or sect in ('', 'None', 'nan'):
                    sect = str(row.get('Section', '')).strip()
                
                try:
                    rotation = float(row.get('Angle', 0.0))
                except (ValueError, TypeError):
                    rotation = 0.0
                
                frame_assign[frame_id] = (sect, rotation)
        
        # ---- Release atamaları ----
        # SAP2000 kolonları:
        #   I ucu: PI, V2I, V3I, TI, M2I, M3I  →  R1..R6
        #   J ucu: PJ, V2J, V3J, TJ, M2J, M3J  →  R1..R6
        frame_release = {}   # {frame_id: {'i': {R1..R6}, 'j': {R1..R6}}}
        if not df_release.empty and 'Frame' in df_release.columns:
            i_cols = {'R1': 'PI',  'R2': 'V2I', 'R3': 'V3I',
                    'R4': 'TI',  'R5': 'M2I', 'R6': 'M3I'}
            j_cols = {'R1': 'PJ',  'R2': 'V2J', 'R3': 'V3J',
                    'R4': 'TJ',  'R5': 'M2J', 'R6': 'M3J'}
            
            for _, row in df_release.iterrows():
                frame_id = str(row.get('Frame', '')).strip()
                if not frame_id:
                    continue
                
                rel_i = {}
                rel_j = {}
                
                for code, col in i_cols.items():
                    rel_i[code] = str(row.get(col, 'No')).strip().upper() == 'YES'
                for code, col in j_cols.items():
                    rel_j[code] = str(row.get(col, 'No')).strip().upper() == 'YES'
                
                # Hiçbir release yoksa kayıt yapma
                if any(rel_i.values()) or any(rel_j.values()):
                    frame_release[frame_id] = {'i': rel_i, 'j': rel_j}
        
        # ---- Fallback section ----
        fallback_section_name = None
        if sections:
            fallback_section_name = list(sections.keys())[0]
        else:
            default_sec = Section(
                name="DEFAULT",
                profile_type=SectionType.RECT,
                profile_params={"h": 200.0, "b": 100.0},
                color=(0.5, 0.5, 0.5),
            )
            self.builder.def_mgr.add_section(default_sec)
            sections["DEFAULT"] = default_sec
            fallback_section_name = "DEFAULT"
        
        # ---- Frame oluştur ----
        count = 0
        for _, row in df_conn.iterrows():
            frame_id = str(row.get('Frame', '')).strip()
            joint_i = str(row.get('JointI', '')).strip()
            joint_j = str(row.get('JointJ', '')).strip()
            
            if not frame_id or joint_i not in node_map or joint_j not in node_map:
                continue
            
            sect_name, rotation = frame_assign.get(frame_id, ("", 0.0))
            
            if sect_name not in sections:
                if sect_name:
                    logger.warning(
                        f"Frame {frame_id}: section '{sect_name}' bulunamadı, "
                        f"fallback '{fallback_section_name}'"
                    )
                sect_name = fallback_section_name
            
            try:
                frame = self.builder.create_frame(
                    node_map[joint_i],
                    node_map[joint_j],
                    sect_name,
                    rotation_deg=rotation,
                    label=f"F{frame_id}",
                )
                
                # Release bilgisini Frame'e ata
                frame.release_i = None
                frame.release_j = None
                if frame_id in frame_release:
                    frame.release_i = frame_release[frame_id]['i']
                    frame.release_j = frame_release[frame_id]['j']
                
                count += 1
            except ValueError as e:
                logger.warning(f"Frame {frame_id}: {e}")
        
        release_count = len(frame_release)
        logger.info(f"  {release_count} frame'de release var")
        
        return count

    def _create_areas(self, df_conn, df_assign, node_map, thicknesses) -> int:
        """Area'ları oluştur."""
        if df_conn.empty:
            return 0
        
        # Area ID → (section_name, thickness) eşlemesi
        area_assign = {}
        if not df_assign.empty and 'Area' in df_assign.columns:
            for _, row in df_assign.iterrows():
                area_id = str(row.get('Area', '')).strip()
                if not area_id:
                    continue
                sect_name = str(row.get('Section', '')).strip()
                thickness = thicknesses.get(sect_name, 100.0)
                area_assign[area_id] = thickness
        
        count = 0
        for _, row in df_conn.iterrows():
            area_id = str(row.get('Area', '')).strip()
            
            # Joint'leri topla
            joints = []
            for i in range(1, 5):
                j = str(row.get(f'Joint{i}', '')).strip()
                if j and j in node_map:
                    joints.append(node_map[j])
            
            if len(joints) < 3:
                continue
            
            thickness = area_assign.get(area_id, 100.0)
            
            self.builder.create_area(
                joints,
                thickness=thickness,
                label=f"A{area_id}",
            )
            count += 1
        
        return count


    def _create_links(self, df_conn, df_assign, node_map, link_props) -> int:
        """Link'leri oluştur."""
        if df_conn.empty:
            return 0
        
        count = 0
        for _, row in df_conn.iterrows():
            link_id = str(row.get('Link', '')).strip()
            joint_i = str(row.get('JointI', '')).strip()
            joint_j = str(row.get('JointJ', '')).strip()
            
            if not link_id or joint_i not in node_map or joint_j not in node_map:
                continue
            
            prop_name = link_props.get(link_id, "LINK1")
            
            self.builder.create_link(
                node_map[joint_i],
                node_map[joint_j],
                prop_name=prop_name,
                label=f"L{link_id}",
            )
            count += 1
        
        return count