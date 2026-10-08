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

; Your data (employees, schedule, hours, tips) is in %APPDATA%\StamhadStaff and is
; NOT removed by the uninstaller.

[Run]
; normal install: offer to open the app at the end
Filename: "{app}\StamhadStaff.exe"; Description: "Open Stamhad Staff"; Flags: nowait postinstall skipifsilent
; in-app update (silent, started with /UPDATE=1): reopen the app by itself
Filename: "{app}\StamhadStaff.exe"; Flags: nowait; Check: IsAppUpdate

[Code]
function IsAppUpdate: Boolean;
begin
  Result := WizardSilent and (ExpandConstant('{param:UPDATE|0}') = '1');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultFile: String;
begin
  { tell the app the update worked (it reads this on the next start) }
  if CurStep = ssPostInstall then
  begin
    ResultFile := ExpandConstant('{param:RESULT|}');
    if ResultFile <> '' then
      SaveStringToFile(ResultFile, '{"to": "{#AppVer}", "status": "ok", "detail": ""}', False);
  end;
end;
