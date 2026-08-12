# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

# firebase-admin (e o grpc/google-auth por baixo dele) usa import
# dinamico em varios submodulos -- o PyInstaller nao acha isso sozinho
# so olhando o codigo, precisa do collect_all pra nao faltar nada e o
# .exe empacotado quebrar so na hora de mandar notificacao de verdade.
datas_extra = []
binaries_extra = []
hidden_extra = []

for pacote in ('firebase_admin', 'grpc', 'google.auth', 'google.cloud.firestore'):
    d, b, h = collect_all(pacote)
    datas_extra += d
    binaries_extra += b
    hidden_extra += h

a = Analysis(
    ['backend_entry.py'],
    pathex=[],
    binaries=binaries_extra,
    datas=[('alembic.ini', '.'), ('migrations', 'migrations')] + datas_extra,
    hiddenimports=['uvicorn.loops.auto', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan.on', 'uvicorn.logging', 'psycopg', 'passlib.handlers.bcrypt', 'email_validator'] + hidden_extra,
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
    name='VertexERP-Backend',
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
    name='VertexERP-Backend',
)
