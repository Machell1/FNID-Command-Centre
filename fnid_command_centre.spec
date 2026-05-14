# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the FNID Command Centre Windows installer build.

Build:
    pyinstaller fnid_command_centre.spec --clean --noconfirm

Output: dist/FNID-Command-Centre/  (one-directory bundle).
The Inno Setup script (installer/fnid.iss) wraps this directory into a
single .exe installer that drops shortcuts and the uninstaller.
"""
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

ROOT = Path(SPECPATH)
PORTAL = ROOT / "fnid_portal"

# All Jinja templates and static files must travel with the bundle.
datas = []
datas += [(str(PORTAL / "templates"), "fnid_portal/templates")]
datas += [(str(PORTAL / "static"), "fnid_portal/static")]

# xhtml2pdf / reportlab ship data files that PyInstaller needs to detect.
datas += collect_data_files("xhtml2pdf")
datas += collect_data_files("reportlab")
datas += collect_data_files("pyhanko")
datas += collect_data_files("pyhanko_certvalidator")

# Hidden imports: flask blueprints loaded by string, optional integrations,
# and parts of waitress / openpyxl / pillow / xhtml2pdf the static analyser
# cannot reach through pure imports.
hiddenimports = []
hiddenimports += collect_submodules("fnid_portal")
hiddenimports += collect_submodules("waitress")
hiddenimports += collect_submodules("openpyxl")
hiddenimports += [
    "xhtml2pdf",
    "xhtml2pdf.pisa",
    "reportlab.graphics.barcode",
    "reportlab.graphics.barcode.code39",
    "reportlab.graphics.barcode.code93",
    "reportlab.graphics.barcode.code128",
    "reportlab.graphics.barcode.usps",
    "reportlab.graphics.barcode.usps4s",
    "reportlab.graphics.barcode.qr",
    "reportlab.graphics.barcode.eanbc",
    "reportlab.graphics.barcode.fourstate",
    "reportlab.graphics.barcode.lto",
    "reportlab.graphics.barcode.dmtx",
    "reportlab.graphics.barcode.ecc200datamatrix",
    "PIL.Image",
    "PIL.ImageDraw",
    "PIL.ImageFont",
    "PIL._tkinter_finder",
    "pystray",
    "pystray._win32",
    "engineio.async_drivers.threading",
    "_cffi_backend",
]


a = Analysis(
    [str(ROOT / "launcher.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Pull out test/dev-only deps to shrink the bundle
        "pytest",
        "pytest_flask",
        "ruff",
        "tkinter",
        "test",
        "unittest",
        "tomllib",
        "psycopg2",
        "psycopg2-binary",
        "sqlalchemy",
        "flask_sqlalchemy",
        "flask_migrate",
        "alembic",
        "celery",
        "kombu",
        "amqp",
        "billiard",
        "vine",
        "redis",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="FNID-Command-Centre",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                # UPX confuses some AV scanners; skip for now.
    console=False,            # windowed app (no cmd window)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / "installer" / "fnid.ico") if (ROOT / "installer" / "fnid.ico").exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="FNID-Command-Centre",
)
