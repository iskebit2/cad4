# tools/s2k/__init__.py
"""S2K import katmanı — temiz public API."""
from tools.s2k.context import LoadContext

__all__ = ["LoadContext", "S2KLoader", "S2KParser"]


def __getattr__(name: str):
    if name == "S2KLoader":
        from tools.s2k.loader import S2KLoader

        return S2KLoader
    if name == "S2KParser":
        from tools.s2k.loader import S2KParser

        return S2KParser
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")