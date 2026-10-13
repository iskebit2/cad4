# domain/serialization.py
import json
from enum import Enum
from dataclasses import is_dataclass, asdict


class DomainJSONEncoder(json.JSONEncoder):
    """Domain nesnelerini JSON'a çevirir."""
    
    def default(self, obj):
        # Enum → isim (veya değer)
        if isinstance(obj, Enum):
            return obj.name   # "STEEL" gibi okunabilir isim
        
        # dataclass → dict (genelde to_dict kullanacağız ama emniyet için)
        if is_dataclass(obj) and not isinstance(obj, type):
            return asdict(obj)
        
        # set → list
        if isinstance(obj, (set, frozenset)):
            return list(obj)
        
        # tuple → list (json zaten list'e çevirir ama açık olsun)
        if isinstance(obj, tuple):
            return list(obj)
        
        # bytes → str
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        
        # numpy scalar → python scalar (varsa)
        try:
            import numpy as np
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
        except ImportError:
            pass
        
        return super().default(obj)


def dumps_pretty(obj, **kw) -> str:
    """Proje için standart JSON yazımı."""
    kw.setdefault("indent", 2)
    kw.setdefault("ensure_ascii", False)
    return json.dumps(obj, cls=DomainJSONEncoder, **kw)