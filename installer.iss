; --- Basic Installer Settings ---
[Setup]
AppName=Ledger App
AppVersion=1.0
DefaultDirName={localappdata}\LedgerApp
DefaultGroupName=Ledger App
OutputBaseFilename=LedgerAppInstaller
Compression=lzma
SolidCompression=yes
DisableWelcomePage=no
SetupIconFile=icon.ico

; --- Files to Include ---
[Files]
Source: "dist\LedgerOnlineOff.v1.0.1.exe"; DestDir: "{app}"; Flags: ignoreversion


; --- Shortcuts ---
[Icons]
Name: "{group}\Ledger App"; Filename: "{app}\LedgerOnlineOff.v1.0.1.exe"
Name: "{commondesktop}\Ledger App"; Filename: "{app}\LedgerOnlineOff.v1.0.1.exe"; Tasks: desktopicon


; --- Uninstaller Behavior ---
[UninstallDelete]
Name: "{app}"; Type: filesandordirs



; --- Tasks (Optional Checkbox for Desktop Icon) ---
[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\LedgerOnlineOff.v1.0.1.exe"; Description: "Launch Ledger App"; Flags: nowait postinstall skipifsilent
