; Script generated by the Inno Script Studio Wizard.
; SEE THE DOCUMENTATION FOR DETAILS ON CREATING INNO SETUP SCRIPT FILES!

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
; Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)
AppId={{A395753D-3F91-47D4-8EF6-23FCAF0BC202}
AppName=AXBPS
AppVersion={{AXBPSVERSION}}
AppVerName=AXBPSv{{AXBPSVERSION}} 
AppPublisher=Casey Densmore
DefaultDirName={pf}\AXBPS
DefaultGroupName=AXBPS
OutputBaseFilename={{AXBPSINSTALLERFILENAME}}
SetupIconFile={{AXBPSPATH}}\lib\dropicon.ico
;Password=5309
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64 
LicenseFile={{AXBPSPATH}}\License_GNU_GPL_v3.txt
DisableDirPage=No

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 0,6.1

[Files]
Source: "{{AXBPSPATH}}\AXBPS.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{{AXBPSPATH}}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Specify pathway to Win10 x64bit driver .inf and .sys files
Source: "{{AXBPSPATH}}\data\Driver\Win10\WRG39WSB.inf"; DestDir: {app}\driver;
Source: "{{AXBPSPATH}}\data\Driver\Win10\WRG39WSB_XP64.sys"; DestDir: {app}\driver;
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{group}\AXBPS"; Filename: "{app}\AXBPS.exe";  IconFilename: "{app}\lib\dropicon.ico"
Name: "{group}\{cm:UninstallProgram,AXBPS}"; Filename: "{uninstallexe}";  IconFilename: "{app}\lib\dropicon.ico"
Name: "{commondesktop}\AXBPS"; Filename: "{app}\AXBPS.exe"; Tasks: desktopicon; IconFilename: "{app}\lib\dropicon.ico"
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\AXBPS"; Filename: "{app}\AXBPS.exe"; Tasks: quicklaunchicon; IconFilename: "{app}\lib\dropicon.ico"

[Run]
Filename: "{app}\AXBPS.exe"; Description: "{cm:LaunchProgram,AXBPS}"; Flags: nowait postinstall skipifsilent
; install driver using RUNDLL32.EXE (specify driver Win10 .inf file)
Filename: "{sys}\rundll32.exe"; Parameters: "setupapi,InstallHinfSection DefaultInstall 128 {app}\data\Driver\Win10\WRG39WSB.inf"; WorkingDir: "{app}\data\Driver\Win10";
