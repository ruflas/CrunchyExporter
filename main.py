import sys
import ctypes
from pathlib import Path

_ROOT = Path(__file__).parent

# Project root on sys.path so both  "from src.*"  and  "from gui.*"  resolve
# to the bundled copies that ship with this project.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Tell Windows this is a standalone app so the taskbar shows the right icon
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        "CrunchyExporter"
    )
except Exception:
    pass

if __name__ == "__main__":
    from gui.app import App
    App().mainloop()
