# tools/s2k/dialog.py
"""Windows dosya dialog'u."""
import sys
import ctypes
from ctypes import wintypes
from typing import Optional


def show_file_dialog() -> Optional[str]:
    if sys.platform != 'win32':
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
            ("lpTemplateName", wintypes.LPCWSTR),
        ]
    
    buffer = ctypes.create_unicode_buffer(260)
    ofn = OPENFILENAME()
    ofn.lStructSize = ctypes.sizeof(OPENFILENAME)
    ofn.lpstrFilter = "S2K Files\0*.$2k;*.s2k\0All Files\0*.*\0"
    ofn.lpstrFile = ctypes.cast(buffer, wintypes.LPWSTR)
    ofn.nMaxFile = len(buffer)
    ofn.lpstrTitle = "Select S2K File"
    ofn.Flags = 0x00000800 | 0x00000004
    
    if ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn)):
        return buffer.value
    return None