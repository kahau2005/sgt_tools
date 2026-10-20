# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/HAU/Internship/Task/Sub_Check/Sub_Check/main.py'],
    pathex=['C:/HAU/Internship/Task/Sub_Check/Sub_Check'],
    binaries=[],
    datas=[('C:/HAU/Internship/Task/Sub_Check/Sub_Check/geckodriver.exe', '.')],
    hiddenimports=['selenium.webdriver.firefox.webdriver', 'selenium.webdriver.firefox.options', 'selenium.webdriver.firefox.service'],
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
    name='GBSubmit',
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
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GBSubmit',
)
