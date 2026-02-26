# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 配置檔案
用於將 FinPack Flask 應用打包成 exe

使用方式：
    pyinstaller finpack.spec

輸出：
    dist/FinPack/FinPack.exe  (資料夾模式)
"""

import os
from PyInstaller.utils.hooks import collect_data_files

# 收集 yfinance 的數據檔案
yfinance_datas = collect_data_files('yfinance')

# 收集隱藏的模組導入（僅 requirements.txt 相關）
hidden_imports = [
    'flask',
    'werkzeug',
    'jinja2',
    'yfinance',
    'pandas',
    'numpy',
    'scipy',
    'requests',
    'urllib3',
    'certifi',
    'charset_normalizer',
    'idna',
]

# 專案根目錄
project_root = os.path.abspath('.')

a = Analysis(
    ['main.py'],
    pathex=[project_root],
    binaries=[],
    datas=[
        ('static', 'static'),
        ('templates', 'templates'),
        ('core', 'core'),
        ('backtest', 'backtest'),
        ('web', 'web'),
    ] + yfinance_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'PIL',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'IPython',
        'sphinx',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FinPack',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # True = 顯示命令列視窗，方便看 log
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可設定 icon='finpack.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FinPack',
)
