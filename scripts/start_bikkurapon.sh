#!/bin/bash
# びっくらポン 起動スクリプト(Mac/Linux用)
# サーバーを起動し、管理画面をノートPC本体に、演出画面を外部モニターに
# それぞれ別ウィンドウで開く。

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
python run.py &
SERVER_PID=$!
trap "kill $SERVER_PID 2>/dev/null" EXIT

sleep 3

find_chrome() {
  if [ "$(uname)" = "Darwin" ]; then
    echo "open -na 'Google Chrome' --args"
  elif command -v google-chrome > /dev/null; then
    echo "google-chrome"
  elif command -v chromium-browser > /dev/null; then
    echo "chromium-browser"
  elif command -v chromium > /dev/null; then
    echo "chromium"
  else
    echo ""
  fi
}

CHROME_CMD=$(find_chrome)
if [ -z "$CHROME_CMD" ]; then
  echo "Chrome/Chromiumが見つかりませんでした。手動でブラウザを開いてください:"
  echo "  管理画面: http://localhost:5000/admin"
  echo "  演出画面: http://localhost:5000/"
  wait $SERVER_PID
  exit 0
fi

# 管理画面: ノートPC本体の画面に普通のウィンドウで表示
eval "$CHROME_CMD --new-window \"http://localhost:5000/admin\"" &

# 演出画面: 外部モニターにフルスクリーン(キオスクモード)で表示
# --window-position の数値は外部モニターの左上座標に合わせて変更してください。
# 例: ノートPC画面が1920x1080で、外部モニターをその右側に拡張している場合は 1920,0
#     モニター配置が分からない場合は、いったんこの行を実行してから
#     ウィンドウをドラッグして外部モニターに移動 → フルスクリーンでもOK
eval "$CHROME_CMD --new-window --window-position=1920,0 --kiosk \"http://localhost:5000/\"" &

echo "起動しました。演出画面を閉じるには Cmd+Q (Mac) / Alt+F4 (Linux) を押してください。"

wait $SERVER_PID
