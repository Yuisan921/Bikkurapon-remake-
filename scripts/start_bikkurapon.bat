@echo off
REM びっくらポン 起動スクリプト(Windows用、開発用)
REM 演出画面・管理画面のブラウザ自動起動はexe/Python側(app/browser_launcher.py)
REM が行うので、このスクリプトはサーバーを起動するだけでよい。
REM
REM 日本語ユーザー名の環境ではこのbatが正しく動かないことがあります。
REM その場合はインストーラー版(README参照)を使ってください。

cd /d "%~dp0\.."

echo サーバーを起動しています...

if exist dist\bikkurapon.exe (
  REM .exeビルド済みならPython環境なしでそのまま起動できる
  dist\bikkurapon.exe
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
  python run.py
)
