import sys
import ctypes
from pathlib import Path

_ROOT = Path(__file__).parent
_CLI  = _ROOT.parent / "CrunchyExporter-cli"

# sys.path setup — two-source strategy:
#
#   1. If CrunchyExporter-cli exists as a sibling folder (development),
#      add it FIRST so  "from src.*"  always resolves to the live CLI code.
#      Any update to the CLI is immediately reflected here — no manual copy.
#
#   2. Otherwise fall back to the bundled  src/  copy that ships with this
#      project (standalone / distribution installs where the CLI is absent).
#
# gui.* is always resolved from _ROOT regardless of which src/ is used.
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if _CLI.exists() and str(_CLI) not in sys.path:
    sys.path.insert(0, str(_CLI))   # takes precedence over bundled src/

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
