"""
Path helpers for frozen (PyInstaller) vs script execution.

  resource_root()  →  bundled files: locales/, src/, images
                       sys._MEIPASS when frozen, project root when script

  data_root()      →  user files: config.yaml, data/
                       directory next to the exe when frozen,
                       project root when script
"""

import sys
from pathlib import Path


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)           # type: ignore[attr-defined]
    return Path(__file__).parent.parent


def data_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent  # next to CrunchyExporter.exe
    return Path(__file__).parent.parent
