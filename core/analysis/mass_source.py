# core/analysis/mass_source.py
"""
SAP2000 mass source tablolarını oku.
"""
from logging_config import CadLogger

from logging_config import CadLogger

logger = CadLogger.get(__name__)


def read_mass_source(parser):
    """
    Parser'dan mass source kurallarını oku.
    
    Returns
    -------
    dict
        {
            'multipliers': {pattern: float},
            'self_weight_mults': {pattern: float},
            'elements': bool,
            'loads': bool,
        }
    """
    # ---- MASS SOURCE tablosu ----
    df_mass = parser.get_table("MASS SOURCE")
    multipliers = {}
    elements_flag = False
    loads_flag = False
    
    if not df_mass.empty:
        for _, row in df_mass.iterrows():
            pattern = str(row.get('LoadPat', '')).strip()
            mult = row.get('Multiplier')
            
            # Elements/Loads flag'leri (ilk satırda)
            if 'Elements' in row.index:
                elements_flag = str(row.get('Elements', '')).strip().upper() == 'YES'
            if 'Loads' in row.index:
                loads_flag = str(row.get('Loads', '')).strip().upper() == 'YES'
            
            if pattern and mult is not None:
                try:
                    multipliers[pattern] = float(mult)
                except (ValueError, TypeError):
                    pass
    
    # ---- LOAD PATTERN DEFINITIONS tablosu ----
    df_lp = parser.get_table("LOAD PATTERN DEFINITIONS")
    self_wt = {}
    
    if not df_lp.empty:
        for _, row in df_lp.iterrows():
            pattern = str(row.get('LoadPat', '')).strip()
            swm = row.get('SelfWtMult', 0.0)
            if pattern:
                try:
                    self_wt[pattern] = float(swm)
                except (ValueError, TypeError):
                    self_wt[pattern] = 0.0
    
    return {
        'multipliers': multipliers,
        'self_weight_mults': self_wt,
        'elements': elements_flag,
        'loads': loads_flag,
    }


def read_frame_loads(parser):
    """
    FRAME LOADS - DISTRIBUTED tablosunu oku.
    
    Returns
    -------
    dict
        {frame_id: [{'pattern': str, 'direction': str, 'value': float}, ...]}
    """
    df = parser.get_table("FRAME LOADS - DISTRIBUTED")
    loads = {}
    
    if df.empty:
        return loads
    
    for _, row in df.iterrows():
        frame_id = str(row.get('Frame', '')).strip()
        pattern = str(row.get('LoadPat', '')).strip()
        direction = str(row.get('Dir', '')).strip()
        
        foverA = row.get('FOverLA')
        
        try:
            value = float(foverA) if foverA is not None and str(foverA) != 'nan' else 0.0
        except (ValueError, TypeError):
            value = 0.0
        
        if frame_id and pattern:
            loads.setdefault(frame_id, []).append({
                'pattern': pattern,
                'direction': direction,
                'value': value,
            })
    
    return loads