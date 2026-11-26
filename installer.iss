; Inno Setup 6 安裝程式腳本（由 GitHub Actions 呼叫 iscc 編譯）
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#define AppName "CRR"
#define AppExe "ChatRelationshipReport.exe"

[Setup]
AppId={{7E6C9B64-3A52-4F0B-9C1D-5B1E3D7A2C10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=johnsoncg06
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=ChatRelationshipReport-Setup-{#AppVersion}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Files]
Source: "dist\ChatRelationshipReport\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
