# Build a portable .zip distribution for users who can't run the .exe installer
# (e.g. limited-permission Windows accounts where Inno Setup's elevation isn't
# possible).
#
# Run from the repo root in PowerShell:
#   .\scripts\build_portable_zip.ps1
#
# Output:
#   installer\Output\FNID-Command-Centre-Portable-<version>.zip
#
# Users extract the zip anywhere and double-click FNID-Command-Centre.exe.
# No install, no admin rights, no Python required.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$bundle = "dist\FNID-Command-Centre"
if (-not (Test-Path "$bundle\FNID-Command-Centre.exe")) {
    Write-Host "Bundle missing. Running PyInstaller first..." -ForegroundColor Yellow
    & ".\.venv\Scripts\python.exe" -m PyInstaller fnid_command_centre.spec --clean --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
}

# Read version from the Inno Setup script
$iss = Get-Content installer\fnid.iss -Raw
if ($iss -match '#define MyAppVersion\s+"([^"]+)"') {
    $version = $matches[1]
} else {
    $version = "2.0.0"
}

$outDir  = "installer\Output"
$outZip  = "$outDir\FNID-Command-Centre-Portable-$version.zip"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
Remove-Item $outZip -Force -ErrorAction SilentlyContinue

# Write a README into the bundle that explains the portable launch.
$readmePath = "$bundle\README-FIRST.txt"
@"
FNID Command Centre - Portable Edition
=======================================

How to launch:
  1. Double-click FNID-Command-Centre.exe.
  2. A tray icon appears (navy/gold "FN") and the default browser opens
     at http://127.0.0.1:5000.
  3. On first launch, your initial password is written to:
     %LOCALAPPDATA%\FNID Command Centre\_initial_credentials.txt
     Sign in as badge "ADMIN", change your password, then delete that file.

User data location:
  %LOCALAPPDATA%\FNID Command Centre\
  (DB, uploads, exports, logs - preserved across upgrades)

To uninstall:
  Delete this folder. To also wipe data, delete the LOCALAPPDATA folder above.

Support: README.md / docs\BUILD.md in the source repository.
"@ | Out-File -Encoding utf8 $readmePath

Write-Host "Compressing bundle to $outZip..." -ForegroundColor Cyan
Compress-Archive -Path "$bundle\*" -DestinationPath $outZip -CompressionLevel Optimal

$info = Get-Item $outZip
Write-Host "Done." -ForegroundColor Green
Write-Host "Portable zip: $($info.FullName)" -ForegroundColor Green
Write-Host "Size:         $([math]::Round($info.Length / 1MB, 1)) MB" -ForegroundColor Green
