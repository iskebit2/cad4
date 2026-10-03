# core/analysis/spectrum.py
"""TBDY 2018 spektrum ve spektral analiz."""
import numpy as np
from logging_config import CadLogger

from logging_config import CadLogger

logger = CadLogger.get(__name__)


class TBDYSpectrum:
    """
    TBDY 2018 yatay elastik tasarım spektrumu.
    
    Kullanım:
        spec = TBDYSpectrum(Ss=0.905, S1=0.254, Fs=1.138, F1=2.092,
                            R=4.0, D=2.5, I=1.2, TL=6.0)
        Sa = spec.S_ra(T=1.0)  # g cinsinden
    """
    
    def __init__(self, Ss, S1, Fs, F1, R, D, I, TL=6.0):
        # Tasarım spektral ivmeleri
        self.S_DS = Ss * Fs
        self.S_D1 = S1 * F1
        
        # Köşe periyotları
        self.T_B = self.S_D1 / self.S_DS
        self.T_A = 0.2 * self.T_B
        self.T_L = TL
        
        # Katsayılar
        self.R = R
        self.D = D
        self.I = I
    
    def S_ae(self, T):
        """Yatay elastik spektral ivme (g)."""
        if T <= 0:
            T = 1e-6
        
        if T <= self.T_A:
            return (0.4 + 0.6 * T / self.T_A) * self.S_DS
        elif T <= self.T_B:
            return self.S_DS
        elif T <= self.T_L:
            return self.S_D1 / T
        else:
            return self.S_D1 * self.T_L / (T * T)
    
    def R_a(self, T):
        """Deprem yükü azaltma katsayısı."""
        if T <= self.T_B:
            return self.D + (self.R / self.I - self.D) * T / self.T_B
        else:
            return self.R / self.I
    
    def S_ra(self, T):
        """Azaltılmış tasarım spektral ivmesi (g)."""
        return self.S_ae(T) / self.R_a(T)
    
    def info(self):
        return (
            f"S_DS={self.S_DS:.4f}  S_D1={self.S_D1:.4f}\n"
            f"T_A={self.T_A:.4f}  T_B={self.T_B:.4f}  T_L={self.T_L:.1f}\n"
            f"R={self.R:.1f}  D={self.D:.1f}  I={self.I:.1f}"
        )


def read_spectrum_from_parser(parser):
    """S2K tablolarından spektrum parametrelerini oku."""
    df = parser.get_table("AUTO SEISMIC - TSC-2018")
    
    defaults = {
        'Ss': 0.905, 'S1': 0.254,
        'Fs': 1.138, 'F1': 2.092,
        'R': 4.0, 'D': 2.5, 'I': 1.2, 'TL': 6.0,
    }
    
    if df.empty:
        return defaults
    
    row = df.iloc[0]
    for key in defaults.keys():
        if key in row.index:
            try:
                defaults[key] = float(row[key])
            except (ValueError, TypeError):
                pass
    
    return defaults