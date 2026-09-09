# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    # win32print/win32api -- usados pra impressao termica direta (ver
    # services/impressora_termica_service.py); o PyInstaller as vezes
    # nao detecta esses modulos sozinho porque sao importados so dentro
    # de funcoes (import tardio de proposito, pra nao quebrar quem nao
    # tem pywin32 instalado e nunca usa o caminho USB)
    hiddenimports=['win32print', 'win32api', 'win32con', 'win32timezone'],
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
    name='VertexERP-Frontend',
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
    icon=['..\\icone.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='VertexERP-Frontend',
)
