import os
import sys

# This runtime hook adjusts TCL/TK environment paths for frozen apps
try:
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS  # unpacked temp dir for onefile
        # Common names we used when bundling datas (tcl8.x, tk8.x)
        candidates = []
        for name in os.listdir(base):
            low = name.lower()
            if low.startswith('tcl8') or low.startswith('tk8'):
                candidates.append(os.path.join(base, name))

        # Prefer exact tcl path for TCL_LIBRARY
        tcl_dir = next((p for p in candidates if os.path.basename(p).lower().startswith('tcl8')), None)
        tk_dir = next((p for p in candidates if os.path.basename(p).lower().startswith('tk8')), None)

        if tcl_dir and os.path.isdir(tcl_dir):
            os.environ.setdefault('TCL_LIBRARY', tcl_dir)
        if tk_dir and os.path.isdir(tk_dir):
            os.environ.setdefault('TK_LIBRARY', tk_dir)
except Exception:
    # Best-effort only; tkinter may still work without envs
    pass


