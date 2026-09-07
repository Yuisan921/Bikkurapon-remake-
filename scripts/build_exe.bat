@echo off
REM びっくらポン .exe ビルドスクリプト(Windows用)
REM Windows機で実行してください(.exeはビルドしたOS専用になります)。

cd /d "%~dp0\.."

if not exist venv_build (
  echo ビルド用の仮想環境を作成しています...
  python -m venv venv_build
)
call venv_build\Scripts\activate.bat
pip install -r requirements-build.txt

echo .exeをビルドしています...
pyinstaller bikkurapon.spec

echo.
echo 完了しました。dist\bikkurapon.exe を実行してください。
echo (初回起動時に dist\ 内へ config フォルダが自動生成されます)
