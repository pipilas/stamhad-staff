; Stamhad Staff — Windows installer (Inno Setup 6)
; Built by GitHub Actions:  iscc /DAppVer=0.7.1 installer\windows.iss
; Installs for the current user (no admin password), so the app can update itself.

#ifndef AppVer
  #define AppVer "0.0.0"
#endif

[Setup]
AppId={{6B1F7C2E-3D4A-4E8B-9C5D-7A2E1F0B3C48}
AppName=Stamhad Staff
AppVersion={#AppVer}
AppVerName=Stamhad Staff {#AppVer}
AppPublisher=Stamhad Software
AppPublisherURL=https://github.com/pipilas/stamhad-staff
AppSupportURL=https://github.com/pipilas/stamhad-staff/releases
DefaultDirName={localappdata}\Programs\Stamhad Staff
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\out
OutputBaseFilename=StamhadStaff-Setup
SetupIconFile=..\icons\icon.ico
UninstallDisplayIcon={app}\StamhadStaff.exe
UninstallDisplayName=Stamhad Staff
VersionInfoVersion={#AppVer}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\StamhadStaff\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Stamhad Staff"; Filename: "{app}\StamhadStaff.exe"
Name: "{autodesktop}\Stamhad Staff"; Filename: "{app}\StamhadStaff.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\StamhadStaff.exe"; Description: "Open Stamhad Staff"; Flags: nowait postinstall skipifsilent

; Your data (employees, schedule, hours, tips) is in %APPDATA%\StamhadStaff and is
; NOT removed by the uninstaller.
