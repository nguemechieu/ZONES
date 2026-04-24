#define MyAppName "ZONES"
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef ReleaseRoot
  #define ReleaseRoot "..\dist\ZONES-v" + AppVersion
#endif

#define AppExeName "ZONES.exe"
#define AppSourceDir ReleaseRoot + "\app\ZONES"
#define DocsSourceDir ReleaseRoot + "\docs"
#define Mt4SourceDir ReleaseRoot + "\MQL4"
#define InstallerOutputDir ReleaseRoot + "\installer"

[Setup]
AppId={{D8D7B3A0-1F12-4D7F-8BF4-17B4AC4A8A5D}}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppPublisher=Sopotek Corporation
AppPublisherURL=https://github.com/nguemechieu/ZONES
AppSupportURL=https://github.com/nguemechieu/ZONES/issues
AppUpdatesURL=https://github.com/nguemechieu/ZONES/releases
DefaultDirName={autopf}\ZONES
DefaultGroupName=ZONES
DisableProgramGroupPage=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
Compression=lzma
SolidCompression=yes
WizardStyle=modern
OutputDir={#InstallerOutputDir}
OutputBaseFilename=ZONES-Setup-{#AppVersion}
SetupIconFile=..\app\src\assets\Zones.png
UninstallDisplayIcon={app}\{#AppExeName}
LicenseFile=..\LICENSE.md
ChangesAssociations=no
ChangesEnvironment=no
UsePreviousAppDir=yes
VersionInfoVersion={#AppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Dirs]
Name: "{commonappdata}\ZONES"; Permissions: users-modify
Name: "{commonappdata}\ZONES\data"; Permissions: users-modify
Name: "{commonappdata}\ZONES\logs"; Permissions: users-modify
Name: "{commonappdata}\ZONES\config"; Permissions: users-modify

[Files]
Source: "{#AppSourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#DocsSourceDir}\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist
Source: "{#Mt4SourceDir}\*"; DestDir: "{app}\MQL4"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

[Icons]
Name: "{group}\ZONES"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; WorkingDir: "{commonappdata}\ZONES"
Name: "{group}\Documentation"; Filename: "{app}\docs"; WorkingDir: "{app}\docs"
Name: "{commondesktop}\ZONES"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; WorkingDir: "{commonappdata}\ZONES"; Tasks: desktopicon
[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch ZONES"; Flags: nowait postinstall skipifsilent; WorkingDir: "{commonappdata}\ZONES"