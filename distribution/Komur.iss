#define AppName "Kömür"
#define AppVersion "2.3.0"
#define AppPublisher "Kömür"

[Setup]
AppId={{75B09D94-55C4-4E19-A912-67A92498C094}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\Komur
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
MinVersion=10.0
OutputDir=..\dist-installer
OutputBaseFilename=Komur-Setup-{#AppVersion}-x64
ArchitecturesInstallIn64BitMode=x64os
ArchitecturesAllowed=x64os
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=no
UninstallDisplayName={#AppName}
SetupLogging=yes
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol oluştur"; GroupDescription: "Ek seçenekler:"; Flags: unchecked

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Files]
Source: "..\dist\Komur.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "THIRD-PARTY-NOTICES.txt"; DestDir: "{app}\licenses"; Flags: ignoreversion

[Icons]
Name: "{group}\Kömür"; Filename: "{app}\Komur.exe"
Name: "{group}\Kömür'ü kaldır"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Kömür"; Filename: "{app}\Komur.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Komur.exe"; Description: "Kömür'ü aç"; Flags: postinstall nowait skipifsilent unchecked

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  RunValue, InstalledCommand: string;
begin
  if CurUninstallStep = usUninstall then
  begin
    if RegQueryStringValue(HKCU,
      'Software\Microsoft\Windows\CurrentVersion\Run', 'Komur', RunValue) then
    begin
      InstalledCommand := '"' + ExpandConstant('{app}\Komur.exe') + '"';
      if CompareText(RunValue, InstalledCommand) = 0 then
        RegDeleteValue(HKCU,
          'Software\Microsoft\Windows\CurrentVersion\Run', 'Komur');
    end;
  end;
end;
