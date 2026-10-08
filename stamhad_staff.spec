# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for Stamhad Staff.
Windows -> dist/StamhadStaff.exe (one file, portable)
           set STAMHAD_ONEDIR=1 -> dist/StamhadStaff/ (program folder, used by the installer)
macOS   -> dist/Stamhad Staff.app
Build:  pyinstaller stamhad_staff.spec --clean --noconfirm
"""
import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
VERSION = open(os.path.join(SPEC_DIR, "version.txt")).read().strip()

datas = [(os.path.join(SPEC_DIR, "version.txt"), "."),
         (os.path.join(SPEC_DIR, "icons"), "icons")]
binaries, hidden = [], []
# paramiko (Toast download) pulls in compiled crypto libraries; collect them fully
for pkg in ("paramiko", "nacl", "bcrypt", "cryptography", "cffi", "certifi"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hidden += h
    except Exception as e:
        print(f"[spec] {pkg}: {e}")
hidden += collect_submodules("reportlab")
# app modules (pages are imported lazily, so list them all)
hidden += ["core", "store", "ui", "toast", "quick", "inventory", "exports", "applog", "updater",
           "update_ui", "sharing", "account", "account_ui", "page_help", "page_home", "page_day", "page_schedule", "page_week",
           "page_inventory", "page_setup"]

a = Analysis(
    [os.path.join(SPEC_DIR, "app.py")],
    pathex=[SPEC_DIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    excludes=["matplotlib", "numpy", "pandas", "PyQt5", "PySide6", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)

ONEDIR = os.environ.get("STAMHAD_ONEDIR") == "1"

if sys.platform == "win32" and ONEDIR:
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="StamhadStaff",
        console=False,
        upx=False,
        icon=os.path.join(SPEC_DIR, "icons", "icon.ico"),
    )
    coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="StamhadStaff")
elif sys.platform == "win32":
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name="StamhadStaff",
        console=False,
        upx=False,                      # UPX makes antivirus programs suspicious
        icon=os.path.join(SPEC_DIR, "icons", "icon.ico"),
        version=None,
    )
else:
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="StamhadStaff",
        console=False,
        upx=False,
        argv_emulation=False,
    )
    coll = COLLECT(exe, a.binaries, a.datas, upx=False, name="StamhadStaff")
    app = BUNDLE(
        coll,
        name="Stamhad Staff.app",
        icon=os.path.join(SPEC_DIR, "icons", "icon.icns"),
        bundle_identifier="com.stamhad.staff",
        info_plist={
            "CFBundleName": "Stamhad Staff",
            "CFBundleDisplayName": "Stamhad Staff",
            "CFBundleVersion": VERSION,
            "CFBundleShortVersionString": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
