; Instalador do Lockscreen Agents (Inno Setup 6).
;
; Uso:  python build_exe.py
;       ISCC.exe /DMyAppVersion=0.1.0 installer.iss
; Gera build\installer\LockscreenAgents-Setup-<versão>.exe
;
; Instala só para o usuário atual (sem pedir administrador), porque o app é por usuário:
; configurações em %LOCALAPPDATA%\LockscreenAgents e início automático em HKCU.

#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif
#define MyAppName "Lockscreen Agents"
#define MyAppExe "LockscreenAgents.exe"

[Setup]
AppId={{9B4C4120-0924-4DC4-9E3E-4B4FEC14E28E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppName}
AppPublisherURL=https://github.com/andrrc/Lockscreen-Agents
AppSupportURL=https://github.com/andrrc/Lockscreen-Agents/issues
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=build\installer
OutputBaseFilename=LockscreenAgents-Setup-{#MyAppVersion}
SetupIconFile=build\logo.ico
UninstallDisplayIcon={app}\{#MyAppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=LICENSE

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "autostart"; Description: "{cm:AutoStart}"; GroupDescription: "{cm:AutoStartGroup}"

[CustomMessages]
brazilianportuguese.AutoStart=Iniciar o Lockscreen Agents com o Windows
brazilianportuguese.AutoStartGroup=Opções:
brazilianportuguese.RunNow=Abrir o Lockscreen Agents
english.AutoStart=Start Lockscreen Agents with Windows
english.AutoStartGroup=Options:
english.RunNow=Open Lockscreen Agents

[Files]
Source: "build\dist\LockscreenAgents\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
; mesmo nome que o app usa ao ligar o início automático nas configurações
Name: "{userstartup}\LockscreenAgents"; Filename: "{app}\{#MyAppExe}"; Tasks: autostart

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
  ValueName: "LockscreenAgents"; ValueData: """{app}\{#MyAppExe}"""; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "{cm:RunNow}"; Flags: nowait postinstall skipifsilent

[Code]
procedure StopApp();
var
  code: Integer;
begin
  { fecha a bandeja, a janela de configurações e o protetor para poder trocar os arquivos }
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM {#MyAppExe}', '', SW_HIDE, ewWaitUntilTerminated, code);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopApp();
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    StopApp();
end;
