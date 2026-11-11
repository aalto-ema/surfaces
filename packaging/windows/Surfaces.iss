#ifndef AppVersion
  #error AppVersion must be supplied by build.ps1
#endif

[Setup]
AppId={{7E30D930-864B-4C34-ACCC-877F3AB03D07}
AppName=Surfaces
AppVersion={#AppVersion}
AppPublisher=Surfaces contributors
AppPublisherURL=https://github.com/aalto-ema/surfaces
AppSupportURL=https://github.com/aalto-ema/surfaces/issues
DefaultDirName={localappdata}\Programs\Surfaces
DefaultGroupName=Surfaces
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\Surfaces.exe
SourceDir=..\..
OutputDir=dist\installer
OutputBaseFilename=Surfaces-{#AppVersion}-windows-x64-setup

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "dist\Surfaces\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Surfaces"; Filename: "{app}\Surfaces.exe"; WorkingDir: "{app}"
Name: "{group}\Third-party notices"; Filename: "{app}\THIRD-PARTY-NOTICES.txt"
Name: "{autodesktop}\Surfaces"; Filename: "{app}\Surfaces.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Surfaces.exe"; Description: "Launch Surfaces"; Flags: nowait postinstall skipifsilent
