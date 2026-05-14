# Build the FNID Command Centre one-click Windows installer.
# Run from the repo root in PowerShell:
#   .\scripts\build_installer.ps1
#
# Prerequisites:
#   - Python 3.11+ on PATH
#   - Inno Setup 6 installed (https://jrsoftware.org/isdl.php)
#   - Internet access for the first run (pip install)
#
# Output:
#   installer\Output\FNID-Command-Centre-Setup-<version>.exe

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "==> Verifying Python..." -ForegroundColor Cyan
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { throw "python.exe not found on PATH" }
& $py --version

Write-Host "`n==> Ensuring virtual environment..." -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    & $py -m venv .venv
}
$venvPy = ".\.venv\Scripts\python.exe"
& $venvPy -m pip install --upgrade pip --quiet

Write-Host "`n==> Installing dependencies..." -ForegroundColor Cyan
& $venvPy -m pip install -r requirements.txt --quiet
& $venvPy -m pip install pyinstaller --quiet

Write-Host "`n==> Generating icon if needed..." -ForegroundColor Cyan
if (-not (Test-Path "installer\fnid.ico")) {
    & $venvPy scripts\make_icon.py
}

Write-Host "`n==> Running smoke tests..." -ForegroundColor Cyan
& $venvPy tests\_smoke_routes_full.py
if ($LASTEXITCODE -ne 0) { throw "Smoke test failed" }
& $venvPy tests\_smoke_post.py
if ($LASTEXITCODE -ne 0) { throw "POST smoke test failed" }

Write-Host "`n==> Cleaning previous build artifacts..." -ForegroundColor Cyan
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

Write-Host "`n==> Running PyInstaller (this takes 2-4 minutes)..." -ForegroundColor Cyan
& $venvPy -m PyInstaller fnid_command_centre.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

if (-not (Test-Path "dist\FNID-Command-Centre\FNID-Command-Centre.exe")) {
    throw "PyInstaller did not produce the expected executable"
}

Write-Host "`n==> Searching for Inno Setup compiler..." -ForegroundColor Cyan
$isccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    Write-Warning "Inno Setup not found. PyInstaller bundle is in dist\FNID-Command-Centre\."
    Write-Warning "Install Inno Setup 6 from https://jrsoftware.org/isdl.php and re-run, "
    Write-Warning "or compile installer\fnid.iss manually."
    exit 0
}

Write-Host "Using $iscc"
Write-Host "`n==> Compiling installer with Inno Setup..." -ForegroundColor Cyan
& $iscc installer\fnid.iss
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed" }

$installer = Get-ChildItem installer\Output\*.exe | Select-Object -First 1
if ($installer) {
    Write-Host "`nDone." -ForegroundColor Green
    Write-Host "Installer: $($installer.FullName)" -ForegroundColor Green
    Write-Host "Size:      $([math]::Round($installer.Length / 1MB, 1)) MB" -ForegroundColor Green
} else {
    throw "Installer .exe was not produced in installer\Output"
}
