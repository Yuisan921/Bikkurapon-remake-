#!/bin/bash
# びっくらポン 起動スクリプト(Mac/Linux用、開発用)
# 演出画面・管理画面のブラウザ自動起動はPython側(app/browser_launcher.py)が
# 行うので、このスクリプトは環境構築とサーバー起動だけを行う。

set -e
cd "$(dirname "$0")/.."

if [ ! -d venv ]; then
  echo "初回セットアップ中..."
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
else
  source venv/bin/activate
fi

echo "サーバーを起動しています..."
python run.py
