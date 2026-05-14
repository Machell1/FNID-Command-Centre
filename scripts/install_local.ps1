#Requires -Version 5.1
<#
.SYNOPSIS
    Install the FNID Command Centre to the current user's profile.

.DESCRIPTION
    No admin elevation required. Installs the PyInstaller bundle to
    %LOCALAPPDATA%\Programs\FNID Command Centre, creates Desktop and Start
    Menu shortcuts, registers an entry under Add/Remove Programs, and (with
    -Launch) starts the app.

.PARAMETER Source
    Path to the PyInstaller dist directory. Defaults to dist\FNID-Command-Centre
    relative to the repo root.

.PARAMETER Launch
    Start the app after installing.

.EXAMPLE
    .\scripts\install_local.ps1 -Launch
#>
param(
    [string]$Source = (Join-Path (Split-Path $PSScriptRoot -Parent) "dist\FNID-Command-Centre"),
    [switch]$Launch
)

$ErrorActionPreference = "Stop"

$AppName     = "FNID Command Centre"
$AppExeName  = "FNID-Command-Centre.exe"
$AppVersion  = "2.0.0"
$Publisher   = "Jamaica Constabulary Force - FNID Area 3"

$InstallDir  = Join-Path $env:LOCALAPPDATA "Programs\$AppName"
$AppExe      = Join-Path $InstallDir $AppExeName
$DesktopLnk  = Join-Path ([Environment]::GetFolderPath('Desktop')) "$AppName.lnk"
$StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\$AppName"
$StartLnk     = Join-Path $StartMenuDir "$AppName.lnk"
$DataLnk      = Join-Path $StartMenuDir "$AppName Data Folder.lnk"
$UninstallLnk = Join-Path $StartMenuDir "Uninstall $AppName.lnk"
$DataDir      = Join-Path $env:LOCALAPPDATA $AppName
$UninstallScript = Join-Path $InstallDir "uninstall.ps1"

function Write-Step($msg) {
    Write-Host "==> $msg" -ForegroundColor Cyan
}

if (-not (Test-Path $Source)) {
    throw "Source bundle not found at $Source. Run PyInstaller first."
}
if (-not (Test-Path (Join-Path $Source $AppExeName))) {
    throw "Bundle is missing $AppExeName"
}

# Stop a running instance, if any.
Write-Step "Stopping any running instance..."
Get-Process -Name "FNID-Command-Centre" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500

# Wipe an older install in the same place. Data dir is untouched.
if (Test-Path $InstallDir) {
    Write-Step "Removing previous install at $InstallDir..."
    Remove-Item -Recurse -Force $InstallDir
}

Write-Step "Copying bundle to $InstallDir..."
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item -Recurse -Force (Join-Path $Source "*") $InstallDir

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
}

# Write an uninstall script that removes the install dir, shortcuts, and
# Add/Remove Programs entry. Data dir is preserved.
Write-Step "Writing uninstaller..."
$uninstallContent = @'
$AppName = "FNID Command Centre"
$InstallDir   = Join-Path $env:LOCALAPPDATA "Programs\$AppName"
$DesktopLnk   = Join-Path ([Environment]::GetFolderPath('Desktop')) "$AppName.lnk"
$StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\$AppName"
$UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$AppName"

Get-Process -Name "FNID-Command-Centre" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500

Remove-Item -Recurse -Force $StartMenuDir -ErrorAction SilentlyContinue
Remove-Item -Force $DesktopLnk -ErrorAction SilentlyContinue
Remove-Item -Path $UninstallKey -Recurse -ErrorAction SilentlyContinue

# Last: remove the install dir itself.
Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue

Write-Host "FNID Command Centre uninstalled."
Write-Host "Your data is preserved at:"
Write-Host "  $(Join-Path $env:LOCALAPPDATA $AppName)"
Write-Host "Delete that folder manually if you also want to wipe case data."
'@
Set-Content -Path $UninstallScript -Value $uninstallContent -Encoding UTF8

# Helper to create a .lnk shortcut.
$shell = New-Object -ComObject WScript.Shell
function New-Shortcut($Path, $Target, [string]$WorkingDir = "", [string]$IconLocation = "", [string]$Description = "") {
    $sc = $shell.CreateShortcut($Path)
    $sc.TargetPath = $Target
    if ($WorkingDir) { $sc.WorkingDirectory = $WorkingDir }
    if ($IconLocation) { $sc.IconLocation = $IconLocation }
    if ($Description) { $sc.Description = $Description }
    $sc.Save()
}

Write-Step "Creating Start Menu folder..."
New-Item -ItemType Directory -Force -Path $StartMenuDir | Out-Null

New-Shortcut -Path $StartLnk -Target $AppExe -WorkingDir $InstallDir `
    -IconLocation $AppExe -Description "FNID Area 3 case management"

New-Shortcut -Path $DataLnk -Target $DataDir `
    -Description "Open the FNID Command Centre data folder (DB, logs, exports)"

# Uninstall shortcut points PowerShell at the uninstall script.
$psPath = (Get-Command powershell.exe).Source
$uninstArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$UninstallScript`""
$sc = $shell.CreateShortcut($UninstallLnk)
$sc.TargetPath = $psPath
$sc.Arguments  = $uninstArgs
$sc.WorkingDirectory = $InstallDir
$sc.IconLocation = $AppExe
$sc.Description = "Uninstall $AppName"
$sc.Save()

Write-Step "Creating Desktop shortcut..."
New-Shortcut -Path $DesktopLnk -Target $AppExe -WorkingDir $InstallDir `
    -IconLocation $AppExe -Description "FNID Area 3 case management"

# Register in Add/Remove Programs (per-user, no admin needed).
Write-Step "Registering with Add/Remove Programs..."
$uninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$AppName"
New-Item -Path $uninstallKey -Force | Out-Null
Set-ItemProperty -Path $uninstallKey -Name "DisplayName"      -Value $AppName
Set-ItemProperty -Path $uninstallKey -Name "DisplayVersion"   -Value $AppVersion
Set-ItemProperty -Path $uninstallKey -Name "Publisher"        -Value $Publisher
Set-ItemProperty -Path $uninstallKey -Name "DisplayIcon"      -Value $AppExe
Set-ItemProperty -Path $uninstallKey -Name "InstallLocation"  -Value $InstallDir
Set-ItemProperty -Path $uninstallKey -Name "UninstallString"  -Value "powershell.exe $uninstArgs"
Set-ItemProperty -Path $uninstallKey -Name "QuietUninstallString" -Value "powershell.exe $uninstArgs"
Set-ItemProperty -Path $uninstallKey -Name "NoModify"         -Value 1 -Type DWord
Set-ItemProperty -Path $uninstallKey -Name "NoRepair"         -Value 1 -Type DWord
$sizeKb = [int]((Get-ChildItem $InstallDir -Recurse | Measure-Object Length -Sum).Sum / 1024)
Set-ItemProperty -Path $uninstallKey -Name "EstimatedSize"    -Value $sizeKb -Type DWord

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host "  Installed:    $InstallDir"
Write-Host "  Data folder:  $DataDir"
Write-Host "  Desktop:      $DesktopLnk"
Write-Host "  Start Menu:   $StartMenuDir"
Write-Host "  Uninstall via Settings > Apps > Installed apps > '$AppName'"

if ($Launch) {
    Write-Host ""
    Write-Step "Launching $AppName..."
    Start-Process -FilePath $AppExe -WorkingDirectory $InstallDir
}
