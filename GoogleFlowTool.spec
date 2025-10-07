# -*- mode: python ; coding: utf-8 -*-

import os
import sys
import glob

# Discover Tcl/Tk directories from the base Python installation
_datas = []
try:
    _base = getattr(sys, 'base_prefix', sys.prefix)
    _tcl_root = os.path.join(_base, 'tcl')
    _tcl_dirs = []
    if os.path.isdir(_tcl_root):
        _tcl_dirs.extend(glob.glob(os.path.join(_tcl_root, 'tcl8*')))
        _tcl_dirs.extend(glob.glob(os.path.join(_tcl_root, 'tk8*')))
    # Fallbacks used by some embeddable installs
    _dlls = os.path.join(_base, 'DLLs')
    if not _tcl_dirs and os.path.isdir(_dlls):
        maybe = [os.path.join(_dlls, 'tcl8.6'), os.path.join(_dlls, 'tk8.6')]
        _tcl_dirs.extend([p for p in maybe if os.path.isdir(p)])
    for d in _tcl_dirs:
        name = os.path.basename(d)
        _datas.append((d, name))
except Exception:
    pass


a = Analysis(
    ['tool_launcher.py'],
    pathex=[],
    binaries=[],
    datas=_datas,
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.messagebox',
        'tkinter.filedialog',
        'tkinter.simpledialog',
        'tkinter.scrolledtext',
        '_tkinter',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['rth_tk.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# Onefile build: bundle everything into a single executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='GoogleFlowTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
