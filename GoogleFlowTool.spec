# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('chrome_cache', 'chrome_cache')]
binaries = []
hiddenimports = ['selenium', 'webdriver_manager', 'tkinter', 'tkinter.ttk', 'tkinter.scrolledtext', 'tkinter.filedialog', 'tkinter.messagebox', 'threading', 'json', 'urllib.request', 'pathlib', 'os', 're', 'time', 'random']
tmp_ret = collect_all('selenium')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('webdriver_manager')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['flow_browser_tool.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
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
    icon=['logo.png'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GoogleFlowTool',
)
app = BUNDLE(
    coll,
    name='GoogleFlowTool.app',
    icon='logo.png',
    bundle_identifier=None,
)
