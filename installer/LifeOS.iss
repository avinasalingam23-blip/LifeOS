; Packages the complete verified PyInstaller folder. Never installs user data.
#ifndef PayloadDir
  #error Pass /DPayloadDir=<verified application folder>
#endif
#ifndef NoticesDir
  #error Pass /DNoticesDir=<prepared dependency notices folder>
#endif
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{02C71D19-97DA-4094-80F3-5D2348B5975C}
AppName=LifeOS
AppVersion={#AppVersion}
AppPublisher=LifeOS
DefaultDirName={autopf}\LifeOS
DefaultGroupName=LifeOS
AllowNoIcons=yes
PrivilegesRequired=admin
; Default remains Program Files/all users. This explicit CLI override also lets
; the exact installer be verified in a user-owned isolated directory, without UAC.
PrivilegesRequiredOverridesAllowed=commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
Compression=lzma2/normal
SolidCompression=yes
OutputBaseFilename=LifeOS-Setup
SetupIconFile={#PayloadDir}\_internal\lifeos\assets\lifeos-monochrome.ico
UninstallDisplayIcon={app}\LifeOS.exe
UninstallDisplayName=LifeOS
Uninstallable=yes
CreateUninstallRegKey=yes
UninstallFilesDir={app}
CloseApplications=no
RestartApplications=no
SetupMutex=LifeOS.Setup.02C71D19-97DA-4094-80F3-5D2348B5975C

[Languages]
Name: english; MessagesFile: compiler:Default.isl

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#NoticesDir}\*"; DestDir: "{app}\ThirdParty-Notices"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\LifeOS"; Filename: "{app}\LifeOS.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\LifeOS"; Filename: "{app}\LifeOS.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\LifeOS.exe"; Description: "Launch LifeOS"; Flags: postinstall nowait skipifsilent unchecked runasoriginaluser

; Intentionally no Registry, InstallDelete, UninstallDelete, user-profile Dirs,
; database payload, data migration, or uninstall code. Inno's normal uninstall
; removes only its managed files/shortcuts/registration; user data stays outside.
