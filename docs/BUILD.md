# Building the FNID Command Centre Windows installer

## Overview

The build produces a single Windows installer:

```
installer\Output\FNID-Command-Centre-Setup-<version>.exe
```

End users double-click it, click through the wizard, and get a fully
self-contained installation with no Python required.

The build pipeline has two stages:

1. **PyInstaller** — bundles the Flask app, the Waitress server, the launcher,
   all Python dependencies, the Jinja templates, and the static assets into a
   single directory: `dist\FNID-Command-Centre\`.
2. **Inno Setup** — wraps that directory into a polished single-file installer
   that creates shortcuts, registers with Add/Remove Programs, and supports
   silent install.

## Prerequisites

| Tool | Version | Source |
|------|---------|--------|
| Python | 3.11 - 3.13 (x64) | https://www.python.org/downloads/ |
| Inno Setup | 6.x | https://jrsoftware.org/isdl.php |
| Git (optional) | any | https://git-scm.com/download/win |

PyInstaller and the runtime dependencies are installed automatically by the
build script into a local `.venv`.

## One-command build

From PowerShell, in the repo root:

```powershell
.\scripts\build_installer.ps1
```

What it does:

1. Verifies Python is on PATH
2. Creates `.venv` if missing and upgrades pip
3. Installs `requirements.txt` + `pyinstaller`
4. Generates `installer\fnid.ico` if missing (`scripts\make_icon.py`)
5. Runs the smoke tests (`tests\_smoke_routes_full.py`, `tests\_smoke_post.py`)
6. Cleans `build\` and `dist\`
7. Runs PyInstaller against `fnid_command_centre.spec`
8. Looks for `ISCC.exe` in the standard Inno Setup install locations
9. Compiles `installer\fnid.iss`
10. Prints the path and size of the produced installer

Skip Inno Setup if you only need the PyInstaller bundle (for testing) — the
launcher in `dist\FNID-Command-Centre\FNID-Command-Centre.exe` is fully
functional standalone.

## Manual build (step-by-step)

For diagnosing problems, run the steps individually:

```powershell
# 1. venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install pyinstaller

# 2. icon
python scripts\make_icon.py

# 3. smoke tests
python tests\_smoke_routes_full.py
python tests\_smoke_post.py

# 4. bundle
pyinstaller fnid_command_centre.spec --clean --noconfirm

# 5. installer
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\fnid.iss
```

PyInstaller takes 5-15 minutes on first run (downloads + analyzes ~80 deps).
Subsequent builds reuse the analysis cache and finish in ~1 minute.

## Build artefacts

| Path | Purpose | Tracked? |
|------|---------|----------|
| `build\` | PyInstaller intermediate workspace | ignored |
| `dist\FNID-Command-Centre\` | One-directory bundle (~250 MB) | ignored |
| `installer\Output\` | Inno Setup installer .exe | ignored |
| `installer\fnid.ico` | App icon | tracked |
| `installer\fnid.iss` | Inno Setup script | tracked |
| `fnid_command_centre.spec` | PyInstaller spec | tracked |

## Smoke testing the bundle before shipping

```powershell
# Run the bundled exe directly (no install)
.\dist\FNID-Command-Centre\FNID-Command-Centre.exe
```

Expected:
- A tray icon appears (navy/gold "FN")
- The default browser opens to `http://127.0.0.1:5000/login`
- The data dir `%LOCALAPPDATA%\FNID Command Centre\` is populated
- `_initial_credentials.txt` is written with the auto-generated ADMIN password

To run headless (for CI):

```powershell
$env:FNID_NO_BROWSER = "1"
$env:FNID_NO_TRAY = "1"
.\dist\FNID-Command-Centre\FNID-Command-Centre.exe
```

## Versioning

Bump the version in two places before tagging a release:

- `installer\fnid.iss` → `#define MyAppVersion "..."`
- `fnid_portal\__init__.py` docstring (informational)

Then:

```powershell
.\scripts\build_installer.ps1
git tag v<version>
git push --tags
```

## Common build issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `ModuleNotFoundError` at runtime in the bundle | Hidden import missed | Add to `hiddenimports` in `fnid_command_centre.spec` |
| TemplateNotFound in the bundle | Templates path not collected | Verify `datas` in the spec covers `fnid_portal/templates` |
| `ISCC.exe not found` | Inno Setup not installed | Install Inno Setup 6 from the link above |
| Bundle .exe blocked by Windows Defender | Unsigned binary | Sign with a code-signing cert (see below) |
| App crashes immediately when launched | `console=False` hides errors | Temporarily set `console=True` in the spec |

## Code signing (optional, recommended for distribution)

Without a code-signing certificate, Windows shows a SmartScreen warning on
first run. To remove it:

1. Buy an EV or OV code-signing certificate (DigiCert, Sectigo, etc.)
2. After PyInstaller produces `dist\FNID-Command-Centre\FNID-Command-Centre.exe`,
   sign it:

   ```powershell
   signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 `
       /f cert.pfx /p <password> dist\FNID-Command-Centre\FNID-Command-Centre.exe
   ```

3. Run Inno Setup. Then sign the installer too:

   ```powershell
   signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 `
       /f cert.pfx /p <password> installer\Output\FNID-Command-Centre-Setup-*.exe
   ```

Inno Setup also supports `[Setup] SignTool=` to do this automatically.
