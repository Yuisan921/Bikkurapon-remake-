@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM 妖怪まつり びっくらぽん Windows起動スクリプト
REM 初回だけPython環境と必要ライブラリを自動で準備します。

cd /d "%~dp0\.."
if errorlevel 1 goto folder_error

set "LOG_FILE=%CD%\bikkurapon-startup.log"
echo [%date% %time%] 起動処理を開始しました。> "%LOG_FILE%"

echo.
echo ========================================
echo   妖怪まつり びっくらぽん
echo ========================================
echo.

if exist "dist\bikkurapon.exe" goto run_exe

REM 安定して動作するPythonを優先して探す。
set "PYTHON_CMD="
py -3.12 --version >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3.12"
if defined PYTHON_CMD goto python_found

py -3.11 --version >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3.11"
if defined PYTHON_CMD goto python_found

py -3.13 --version >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3.13"
if defined PYTHON_CMD goto python_found

python --version >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=python"
if not defined PYTHON_CMD goto python_missing

:python_found
echo 使用するPython: !PYTHON_CMD!
echo 使用するPython: !PYTHON_CMD!>> "%LOG_FILE%"

if exist "venv\Scripts\python.exe" goto environment_ready
if exist "venv" goto environment_broken

echo.
echo 初回セットアップを行っています。
echo 1/2 Python環境を作成中...
!PYTHON_CMD! -m venv venv >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto setup_error

echo 2/2 必要な部品をインストール中...
echo 数分かかることがあります。そのままお待ちください。
"venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto setup_error
goto run_app

:environment_ready
echo 必要な部品を確認しています...
"venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto setup_error

:run_app
echo.
echo アプリを起動しています...
echo ゲーム画面と管理画面が表示されるまで少しお待ちください。
"venv\Scripts\python.exe" run.py >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto app_error
exit /b 0

:run_exe
echo アプリを起動しています...
"dist\bikkurapon.exe" >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto app_error
exit /b 0

:python_missing
echo.
echo [エラー] Pythonが見つかりません。
echo Python 3.12をインストールしてから、もう一度このBATを実行してください。
echo インストール時に「Add python.exe to PATH」にチェックを入れてください。
echo.
echo ダウンロード先: https://www.python.org/downloads/windows/
echo Pythonが見つかりません。>> "%LOG_FILE%"
goto keep_open

:environment_broken
echo.
echo [エラー] 前回のセットアップが途中で止まっています。
echo このフォルダ内の「venv」フォルダだけを削除してから、もう一度実行してください。
echo Python仮想環境が壊れています。>> "%LOG_FILE%"
goto keep_open

:setup_error
echo.
echo [エラー] 初回セットアップに失敗しました。
echo ネット接続を確認してから、もう一度実行してください。
goto show_log

:app_error
echo.
echo [エラー] アプリを起動できませんでした。
goto show_log

:folder_error
echo.
echo [エラー] アプリのフォルダを開けませんでした。
goto keep_open

:show_log
echo.
echo ----- エラー詳細 -----
if exist "%LOG_FILE%" type "%LOG_FILE%"
echo ----- ここまで -----
echo.
echo エラー内容は「bikkurapon-startup.log」にも保存されています。

:keep_open
echo.
echo この画面は自動では閉じません。
echo 直らない場合は、この画面の写真を送ってください。
pause
exit /b 1
