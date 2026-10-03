
import numpy as np
from enum import Enum
import math
from typing import List, Tuple, Optional, Dict, Any
import pandas as pd
import re
from logging_config import CadLogger
from logging_config import CadLogger

logger = CadLogger.get(__name__)

# ==================== SOLID GEOMETRY DATACLASS ====================

class SectionType(Enum):
    """
    FEA çubuk kesit tipleri
    """
    RECT = "RECT"
    CIRCLE = "CIRCLE"
    I = "I"
    L = "L"
    T = "T"
    PIPE = "PIPE"
    TUBE = "TUBE"
    C = "C"

def normalize(v: np.ndarray) -> np.ndarray:
    """Normalize vector with safe division."""
    norm = np.linalg.norm(v)
    if norm < 1e-10:
        return v
    return v / norm

def get_profile_2d(section_type: SectionType, params: dict) -> List[Tuple[float, float]]:
    """Get 2D profile points in local 2-3 plane (centroid at origin)"""
    params = params.copy()  # Avoid modifying original
    
    if section_type == SectionType.RECT:
        b = params.get("b", 100.0)  # width along 2-axis
        h = params.get("h", 200.0)  # depth along 3-axis
        return [
            (-b/2, -h/2),
            (b/2, -h/2),
            (b/2, h/2),
            (-b/2, h/2)
        ]
    
    elif section_type == SectionType.CIRCLE:
        r = params.get("r", 50.0)
        n = max(3, int(params.get("n", 16)))  # At least 3 segments
        return [
            (r * math.cos(a), r * math.sin(a))
            for a in np.linspace(0, 2*math.pi, n, endpoint=False)
        ]
    
    elif section_type == SectionType.I:
        b = params.get("b", 100.0)
        h = params.get("h", 200.0)
        tw = max(0.1, params.get("tw", 10.0))   # web thickness
        tf = max(0.1, params.get("tf", 14.0))   # flange thickness
        return [
            (-b/2, h/2),
            (b/2, h/2),
            (b/2, h/2 - tf),
            (tw/2, h/2 - tf),
            (tw/2, -h/2 + tf),
            (b/2, -h/2 + tf),
            (b/2, -h/2),
            (-b/2, -h/2),
            (-b/2, -h/2 + tf),
            (-tw/2, -h/2 + tf),
            (-tw/2, h/2 - tf),
            (-b/2, h/2 - tf),
        ]
    
    elif section_type == SectionType.L:
        b = params.get("b", 80.0)
        h = params.get("h", 100.0)
        t = max(0.1, params.get("t", 8.0))
        return [
            (0, 0),
            (t, 0),
            (t, h - t),
            (b, h - t),
            (b, h),
            (0, h)
        ]
    
    elif section_type == SectionType.T:
        b = params.get("b", 120.0)
        h = params.get("h", 150.0)
        tw = max(0.1, params.get("tw", 10.0))
        tf = max(0.1, params.get("tf", 15.0))
        return [
            (-b/2, h/2),
            (b/2, h/2),
            (b/2, h/2 - tf),
            (tw/2, h/2 - tf),
            (tw/2, -h/2),
            (-tw/2, -h/2),
            (-tw/2, h/2 - tf),
            (-b/2, h/2 - tf),
        ]
    
    elif section_type == SectionType.PIPE:
        ro = params.get("ro", 60.0)
        ri = min(ro - 0.1, params.get("ri", 50.0))
        n = max(3, int(params.get("n", 24)))
        # Outer circle (counter-clockwise)
        outer = [
            (ro * math.cos(a), ro * math.sin(a))
            for a in np.linspace(0, 2*math.pi, n, endpoint=False)
        ]
        # Inner circle (clockwise)
        inner = [
            (ri * math.cos(a), ri * math.sin(a))
            for a in np.linspace(2*math.pi, 0, n, endpoint=False)
        ]
        return outer + inner
    
    elif section_type == SectionType.TUBE:
        # Tube is typically rectangular hollow section
        b = params.get("b", 100.0)
        h = params.get("h", 200.0)
        t = max(0.1, params.get("t", 10.0))
        return [
            (-b/2, -h/2),  # Outer rectangle
            (b/2, -h/2),
            (b/2, h/2),
            (-b/2, h/2),
            (-b/2 + t, -h/2 + t),  # Inner rectangle (reverse order)
            (-b/2 + t, h/2 - t),
            (b/2 - t, h/2 - t),
            (b/2 - t, -h/2 + t),
        ]
    
    elif section_type == SectionType.C:
        b = params.get("b", 80.0)
        h = params.get("h", 100.0)
        t = max(0.1, params.get("t", 6.0))
        return [
            (0, 0),
            (t, 0),
            (t, h),
            (b, h),
            (b, h - t),
            (2*t, h - t),
            (2*t, t),
            (b, t),
            (b, 0)
        ]
    
    else:
        # Default rectangle
        return [
            (-50, -50),
            (50, -50),
            (50, 50),
            (-50, 50)
        ]

# ==================== S2K PARSER ====================

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
            # Default to rectangle
            # logger.debug(f"Warning: Unknown section type '{s_type}', using default rectangle")
            return SectionType.RECT, {"h": 200.0, "b": 100.0}
    except (ValueError, KeyError) as e:
        # logger.debug(f"Error mapping section parameters for type '{s_type}': {e}")
        return SectionType.RECT, {"h": 200.0, "b": 100.0}

class S2KParser:
    """
    sap2000 s2k dosya okuma
    """
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.tables: Dict[str, pd.DataFrame] = {}
        self.points: Dict[str, np.ndarray] = {}
        self._load_and_parse()
    
    def _load_and_parse(self):
        """Load and parse S2K file"""
        try:
            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except FileNotFoundError:
            # logger.debug(f"Error: File '{self.file_path}' not found")
            return
        except Exception as e:
            # logger.debug(f"Error reading file: {e}")
            return
        
        # Handle continuation lines
        content = re.sub(r' _\r?\n', ' ', content)
        
        # Split into tables
        raw_tables = re.split(r'TABLE:\s*"*', content)
        
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
    
    def get_table(self, table_name: str) -> pd.DataFrame:
        """Get table by name, return empty DataFrame if not found"""
        return self.tables.get(table_name, pd.DataFrame())
    
    def add_point_with_id(self, point_id: str, position: List[float]):
        """Add point with ID"""
        self.points[point_id] = np.array(position, dtype=np.float32)
    
    def build_model(self):
        """Tablolardan gelen ham veriyi SolidElement objelerine dönüştürür"""
        # 1. Tabloları güvenli bir şekilde al
        df_j = self.get_table("JOINT COORDINATES")
        df_f = self.get_table("CONNECTIVITY - FRAME")
        df_s = self.get_table("FRAME SECTION PROPERTIES")
        df_a = self.get_table("FRAME SECTION ASSIGNMENTS")

        if df_j.empty or df_f.empty:
            # logger.debug("Hata: Temel tablolar (Joint veya Frame) bulunamadı!")
            return

        # 2. Önce Noktaları (Joints) oluştur
        for _, row in df_j.iterrows():
            # SAP2000 bazen XorR, bazen X kullanır; ikisini de kontrol et
            x = float(row.get('XorR', row.get('X', 0)))
            y = float(row.get('Y', 0))
            z = float(row.get('Z', 0))
            self.add_point_with_id(str(row['Joint']), [x, y, z])

        # 3. Kesit Kütüphanesini önbelleğe al (Hız için)
        sections_lib = {}
        if not df_s.empty:
            for _, row in df_s.iterrows():
                sections_lib[row['Section']] = map_sap_to_local_params(row)

        # 4. Frame'leri (Çubukları) oluştur ve bağla
        for _, row in df_f.iterrows():
            f_id = str(row['Frame'])
            j_a, j_b = str(row['JointI']), str(row['JointJ'])
            
            # Koordinatları çek
            if j_a not in self.points or j_b not in self.points:
                continue # Eksik nokta varsa atla
                
            p0 = self.points[j_a]
            p1 = self.points[j_b]
            
            # Kesit ismini ve Angle (Dönü) bilgisini Assignment tablosundan bul
            # Not: Query kullanarak hızlandırıyoruz
            assign = df_a[df_a['Frame'] == f_id]
            
            if not assign.empty:
                s_name = assign.iloc[0].get('Section', 'Default')
                angle = float(assign.iloc[0].get('Angle', 0.0))
            else:
                s_name = "Default"
                angle = 0.0
            
            # Kesit tipi ve parametrelerini belirle
            s_type, s_params = sections_lib.get(s_name, (SectionType.RECT, {"h": 200.0, "b": 100.0}))
            
            # SolidElement objesini oluştur
            element_data = {
                "id": f_id,
                "p0": p0,
                "p1": p1,
                "angle": angle,
                "section": {"type": s_type, "params": s_params},
                "material": {"color": [0.6, 0.6, 0.7], "roughness": 0.5} # İstersen S2K'dan renk de çekebilirsin
            }
            

        # logger.debug(f"Model başarıyla inşa edildi: {len(self.solids)} adet Frame elemanı oluşturuldu.")

    