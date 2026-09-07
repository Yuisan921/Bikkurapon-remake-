@echo off
REM びっくらポン 起動スクリプト(Windows用)
REM サーバーを起動し、管理画面をノートPC本体に、演出画面を外部モニターに
REM それぞれ別ウィンドウで開く。

cd /d "%~dp0\.."

echo サーバーを起動しています...

if exist dist\bikkurapon.exe (
  REM .exeビルド済みならPython環境なしでそのまま起動できる
  start "bikkurapon-server" cmd /c dist\bikkurapon.exe
) else (
  REM .exe未ビルドの場合はPythonで直接起動する(開発用)
  if not exist venv (
    echo 初回セットアップ中...
    python -m venv venv
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
  ) else (
    call venv\Scripts\activate.bat
  )
  start "bikkurapon-server" cmd /c python run.py
)

timeout /t 3 /nobreak > nul

REM 管理画面: ノートPC本体の画面に普通のウィンドウで表示
start chrome --new-window "http://localhost:5000/admin"

REM 演出画面: 外部モニターにフルスクリーン(キオスクモード)で表示
REM --window-position の数値は外部モニターの左上座標に合わせて変更してください。
REM 例: ノートPC画面が1920x1080で、外部モニターをその右側に拡張している場合は 1920,0
REM     モニター配置が分からない場合は、いったんこの行を実行してから
REM     ウィンドウをドラッグして外部モニターに移動 → フルスクリーン(F11)でもOK
start chrome --new-window --window-position=1920,0 --kiosk "http://localhost:5000/"

echo 起動しました。演出画面を閉じるには Alt+F4 を押してください。
