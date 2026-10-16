#!/bin/bash
# びっくらポン 起動スクリプト(Mac/Linux用、開発用)
# 演出画面・管理画面はアプリ専用ウィンドウで自動的に開きます。

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
