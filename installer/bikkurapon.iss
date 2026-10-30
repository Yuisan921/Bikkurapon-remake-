; びっくらポン Windowsインストーラー(Inno Setup用)
;
; 事前に `pyinstaller bikkurapon.spec` を実行して dist\bikkurapon.exe を
; 作っておいてから、このスクリプトをInno Setupでコンパイルしてください。
; (GitHub Actionsで自動ビルドする場合は .github/workflows/build-windows.yml
;  が両方まとめて実行します)
;
; 学校PCでも管理者パスワードなしで導入できるよう、現在のユーザー専用の
; LocalAppData\Programs にインストールする。

#define MyAppName "妖怪まつり びっくらぽん"
#define MyAppVersion "2.7.2"
#define MyAppExeName "bikkurapon.exe"

[Setup]
AppId={{6C2B7E3A-4B7B-4B77-9C1E-3E6E6B0A0B01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\Bikkurapon
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
UsePreviousAppDir=no
OutputDir=..\dist_installer
OutputBaseFilename=BikkurapoSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにアイコンを作成する"; GroupDescription: "追加のアイコン:"

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\videos\README.md"; DestDir: "{app}\videos"; Flags: onlyifdoesntexist
Source: "..\videos\atari\*"; DestDir: "{app}\videos\atari"; Flags: onlyifdoesntexist
Source: "..\videos\hazure\*"; DestDir: "{app}\videos\hazure"; Flags: onlyifdoesntexist

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName}を起動する"; Flags: postinstall nowait skipifsilent runasoriginaluser

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  { 旧版が画面を閉じた後もバックグラウンドに残っている場合があるため、
    ファイルを置き換える前に本アプリのプロセスだけを終了する。 }
  Exec(ExpandConstant('{cmd}'),
    '/C taskkill /F /IM bikkurapon.exe >nul 2>&1',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;
