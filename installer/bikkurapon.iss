; びっくらポン Windowsインストーラー(Inno Setup用)
;
; 事前に `pyinstaller bikkurapon.spec` を実行して dist\bikkurapon.exe を
; 作っておいてから、このスクリプトをInno Setupでコンパイルしてください。
; (GitHub Actionsで自動ビルドする場合は .github/workflows/build-windows.yml
;  が両方まとめて実行します)
;
; インストール先はユーザー名を含まない共通のプログラムフォルダ
; ({autopf}\Bikkurapon)なので、Windowsのユーザー名に日本語(非ASCII文字)が
; 含まれていて発生する不具合を避けられる。

#define MyAppName "びっくらポン"
#define MyAppVersion "1.0"
#define MyAppExeName "bikkurapon.exe"

[Setup]
AppId={{6C2B7E3A-4B7B-4B77-9C1E-3E6E6B0A0B01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\Bikkurapon
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist_installer
OutputBaseFilename=BikkurapoSetup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
WizardStyle=modern

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Tasks]
Name: "desktopicon"; Description: "デスクトップにアイコンを作成する"; GroupDescription: "追加のアイコン:"

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{#MyAppName}を起動する"; Flags: postinstall nowait skipifsilent
