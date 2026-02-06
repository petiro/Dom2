# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for SuperAgent
Builds a standalone single-file executable
"""

import os
import sys

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        ('config/config.yaml', 'config'),
        ('ai', 'ai'),
        ('core', 'core'),
        ('ui', 'ui'),
        ('gateway', 'gateway'),
    ],
    hiddenimports=[
        'PySide6.QtWidgets',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'yaml',
        'requests',
        'PIL',
        'bs4',
        'sqlite_utils',
        'json',
        'logging',
        'ui.desktop_app',
        'ui.telegram_tab',
        'ai.vision_learner',
        'ai.rpa_healer',
        'ai.telegram_learner',
        'core.utils',
        'core.dom_executor_playwright',
        'gateway.telegram_parser_fixed',
        'gateway.pattern_memory',
        'gateway.telegram_listener_fixed',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'playwright',
        'telethon',
        'fastapi',
        'uvicorn',
        'openai',
        'cryptography',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Single-file executable (onefile mode)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SuperAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
