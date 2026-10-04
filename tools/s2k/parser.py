# tools/s2k/parser.py
"""S2K dosyasını tablo DataFrame'lerine ayırır."""
import re
from pathlib import Path
from typing import Dict, Optional

import pandas as pd

from logging_config import CadLogger
logger = CadLogger.get(__name__)


class S2KParser:
    """SAP2000 .s2k dosyası → tablo DataFrame'leri."""
    
    PAIR_PATTERN = re.compile(r'(\w+)=("[^"]*"|[^\s]+)')
    
    def __init__(self, file_path: Optional[str] = None):
        self.file_path = file_path
        self.tables: Dict[str, pd.DataFrame] = {}
        if self.file_path:
            self._parse(self.file_path)
    
    def _parse(self, file_path: str):
        path = Path(file_path)
        if not path.exists():
            logger.error(f"Dosya bulunamadı: {file_path}")
            return
        
        try:
            content = path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            logger.error(f"Dosya okuma hatası: {e}")
            return
        
        logger.info(f"[Parser] Dosya: {path.name}, boyut: {len(content)} bytes")
        
        # Satır devamı ( _\n ) birleştir
        content = re.sub(r' _\r?\n', ' ', content)
        
        # Tabloları ayır
        raw_tables = re.split(r'TABLE:\s*"*', content)
        logger.info(f"[Parser] {len(raw_tables)} potansiyel tablo")
        
        for raw in raw_tables:
            if not raw.strip():
                continue
            
            lines = raw.strip().split('\n')
            table_name = lines[0].strip().strip('"')
            rows = []
            
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                pairs = self.PAIR_PATTERN.findall(line)
                if pairs:
                    row = {}
                    for k, v in pairs:
                        if v.startswith('"') and v.endswith('"'):
                            v = v[1:-1]
                        row[k] = v
                    rows.append(row)
            
            if rows:
                self.tables[table_name] = pd.DataFrame(rows)
        
        logger.info(f"[Parser] {len(self.tables)} tablo yüklendi")
    
    def get_table(self, name: str) -> pd.DataFrame:
        return self.tables.get(name, pd.DataFrame())
    
    def get_all_tables(self) -> Dict[str, pd.DataFrame]:
        return self.tables