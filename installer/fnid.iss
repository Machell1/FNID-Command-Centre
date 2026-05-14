; ============================================================================
; FNID Command Centre - Windows Installer (Inno Setup script)
; ============================================================================
; Build prerequisites:
;   1. Run `pyinstaller fnid_command_centre.spec --clean --noconfirm` so that
;      dist/FNID-Command-Centre/ exists with FNID-Command-Centre.exe inside.
;   2. Install Inno Setup 6 from https://jrsoftware.org/isdl.php.
;   3. Compile this script with the Inno Setup compiler (or `iscc.exe fnid.iss`).
;
; Output: installer/Output/FNID-Command-Centre-Setup-X.Y.Z.exe
; ============================================================================

#define MyAppName        "FNID Command Centre"
#define MyAppVersion     "2.0.0"
#define MyAppPublisher   "Jamaica Constabulary Force - FNID Area 3"
#define MyAppExeName     "FNID-Command-Centre.exe"
#define MyAppDataDirName "FNID Command Centre"

[Setup]
; AppId uniquely identifies the install for upgrades / uninstallation.
AppId={{C46F4C4B-3A2C-4F84-94B2-FNID000COMMAND}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppCopyright=Copyright (c) 2026 Jamaica Constabulary Force - FNID Area 3
VersionInfoVersion={#MyAppVersion}
VersionInfoProductName={#MyAppName}

; Default install to Program Files\FNID Command Centre
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableDirPage=auto
DisableProgramGroupPage=auto
AllowNoIcons=yes

; UI assets
SetupIconFile=fnid.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
WizardSizePercent=120

; Output
OutputDir=Output
OutputBaseFilename=FNID-Command-Centre-Setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes

; Per-machine install with admin elevation. The app's user data still lives
; in %LOCALAPPDATA% so each Windows account has its own database.
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog commandline

; Don't bother with 32-bit installs; Python 3.13 + xhtml2pdf wheels are x64.
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

MinVersion=10.0.17763
; Windows 10 1809+ / Windows 11

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &Desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "quicklaunchicon"; Description: "Create a &Quick Launch shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "startwithwindows"; Description: "Launch &FNID Command Centre when I sign in to Windows"; GroupDescription: "Auto-start:"; Flags: unchecked

[Files]
; The PyInstaller --onedir bundle. Source path is relative to this .iss file.
Source: "..\dist\FNID-Command-Centre\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{group}\Open FNID Data Folder"; Filename: "{userappdata}\..\Local\{#MyAppDataDirName}"; Comment: "Opens the user data folder containing the database, logs, exports."
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Registry]
; Optional: auto-start on login (per-user). Only created if the task was checked.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; \
    Flags: uninsdeletevalue; Tasks: startwithwindows

[Run]
; Launch immediately after install finishes (optional; user can untick).
Filename: "{app}\{#MyAppExeName}"; \
    Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; The PyInstaller bundle directory may have created caches/temp at runtime;
; sweep them on uninstall. User data in LOCALAPPDATA is preserved by design.
Type: filesandordirs; Name: "{app}"

[Code]
function InitializeSetup(): Boolean;
begin
  // Stop any running instance before installing/upgrading.
  Exec('taskkill.exe', '/F /IM FNID-Command-Centre.exe', '', SW_HIDE,
       ewWaitUntilTerminated, ResultCode := 0);
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // No-op for now; reserved for post-install hooks (e.g. firewall rule).
  end;
end;

function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  // Stop any running instance before uninstalling.
  Exec('taskkill.exe', '/F /IM FNID-Command-Centre.exe', '', SW_HIDE,
       ewWaitUntilTerminated, ResultCode);
  Result := True;
end;
