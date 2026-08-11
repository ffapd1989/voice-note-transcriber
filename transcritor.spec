# -*- mode: python ; coding: utf-8 -*-
# Spec portável do Transcritor de Áudio — sem caminhos absolutos.
# Build: pyinstaller transcritor.spec --noconfirm --clean  (ou .\build.ps1)

import os

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

datas = []
binaries = []
hiddenimports = ['requests']

# customtkinter e tkinterdnd2 carregam temas/JSONs e a DLL do tkdnd em runtime;
# collect_all resolve os caminhos sozinho, em qualquer máquina.
for pkg in ('customtkinter', 'tkinterdnd2'):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# pygame-ce já traz hook próprio de PyInstaller; basta garantir as DLLs.
binaries += collect_dynamic_libs('pygame')
hiddenimports += ['pygame']

# mutagen é Python puro — a análise de imports resolve, só reforçamos o pacote.
hiddenimports += ['mutagen']

# pyogg carrega ogg/vorbis/opus via ctypes; as DLLs vêm dentro do wheel.
binaries += collect_dynamic_libs('pyogg')
hiddenimports += ['pyogg']

# ffmpeg.exe (compactação de áudio >25MB): baixado por build.ps1 para um
# cache FORA do projeto (mesma razão do $WorkPath — Google Drive não deve
# sincronizar esse binário de ~110MB a cada build). build.ps1 exporta
# TRANSCRITOR_FFMPEG_PATH apontando pro cache; se ausente (build manual sem
# passar por build.ps1), cai para vendor/ffmpeg/ffmpeg.exe local (não
# versionado no git — ver .gitignore). Se nada for encontrado, o app segue
# funcionando, só sem a opção de compactação automática (ver _ffmpeg_path
# em transcricao_app.py, que resolve o binário em runtime do mesmo jeito).
_ffmpeg_bin = os.environ.get('TRANSCRITOR_FFMPEG_PATH') or os.path.join('vendor', 'ffmpeg', 'ffmpeg.exe')
if os.path.exists(_ffmpeg_bin):
    binaries.append((_ffmpeg_bin, '.'))

# Ícone: coloque um arquivo em assets/icone.ico e ele é usado automaticamente
# (no exe e também na janela do app — por isso entra em datas).
_icon = os.path.join('assets', 'icone.ico')
icon_path = _icon if os.path.exists(_icon) else None
if icon_path:
    datas.append((_icon, 'assets'))

# Módulos da stdlib/terceiros que o app não usa — enxugam o exe.
# NÃO excluir 'email': http.client (usado pelo requests) depende dele.
excludes = [
    'numpy',
    'PIL.ImageQt',
    'tkinter.test',
    'unittest',
    'pydoc',
    'doctest',
    'xmlrpc',
    'distutils',
    'setuptools',
    'pip',
]

a = Analysis(
    ['transcricao_app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    # Nome curto de propósito: o Application Control do Apex One (antivírus
    # corporativo) mantém regra de bloqueio pelo nome "Transcritor de Audio de
    # Zap.exe" — os MESMOS bytes rodam sob qualquer outro nome. O nome de
    # exibição do produto continua em version_info.txt e na janela do app.
    name='transcrizap',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX desativado de propósito: compressão UPX é gatilho clássico de
    # falso-positivo em antivírus/SmartScreen — péssimo para distribuir a amigos.
    upx=False,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
    version='version_info.txt',
)
