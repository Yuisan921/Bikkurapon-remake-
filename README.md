# びっくらポン(文化祭リメイク版)

回転寿司でおなじみの「びっくらポン」を文化祭のミニゲームとして再現するプロジェクトです。

コインを入れる → 画面で抽選演出 → 結果表示 → 当たりならサーボモーターでカプセルを排出、
という一連の流れを実装しています。

## 全体構成(役割分担)

本体は2つの機器に分かれています。

- **ノートPC**: 抽選ロジックとモニター表示画面を担当(このリポジトリのFlaskアプリ)。
  GPIOなどのハードウェアは一切触らない
- **Seeed XIAO ESP32-C3**: コインセンサーとカプセル排出用サーボモーターを直結し、
  コイン投入を検知したらWiFi経由でノートPCに通知するだけの小さなファームウェア
  (`firmware/xiao_esp32c3_coin_servo/`)を書き込んで使う

ノートPCとXIAO ESP32-C3は同じWiFiネットワークに接続する必要があります。
会場のWiFiが使えない/不安定な場合は、ノートPC側でモバイルホットスポットを立てて
ESP32をそこに接続させるのが手軽です。

### 通信の流れ

1. XIAO ESP32-C3がコインセンサーの投入を検知
2. ノートPCの `POST /api/insert_coin` にHTTPリクエストを送る
3. ノートPCが抽選を実行し、結果(景品名・サーボ角度など)をレスポンスJSONで返す
   と同時に、Socket.IOでブラウザ画面にも同じ結果を通知して演出を再生する
4. ESP32はレスポンスの `servo_angle` を見て、当選していればサーボモーターを動かして
   カプセルを排出する(はずれの場合は `servo_angle` が `null` なので何もしない)

サーバーからESP32への逆方向通信は発生しないので、ESP32側は待ち受けサーバーを
立てる必要がなく、ファームウェアがシンプルになっています。

## リポジトリの構成

- `run.py` … 起動エントリーポイント
- `app/server.py` … Flask + Socket.IO サーバー本体(ノートPCで動かす)
- `app/lottery.py` … 確率抽選と景品在庫の管理
- `config/prizes.json` … 景品の一覧・当選確率・初期在庫・サーボ角度
- `config/settings.json` … ポート番号やテスト用ボタンの表示設定
- `templates/`, `static/` … モニター表示画面(`/`)と在庫管理画面(`/admin`)
- `data/stock.json` … 実行時に自動生成される現在の在庫数(gitignore対象)
- `firmware/xiao_esp32c3_coin_servo/` … XIAO ESP32-C3用ファームウェア(Arduino)

## 必要なハードウェア

- ノートPC(モニター表示・抽選ロジック用)
- Seeed XIAO ESP32-C3
- コインセンサー(フォトインタラプタや簡易スイッチなど)
- カプセル排出用のサーボモーター(SG90など)
- カプセル排出機構(3Dプリント/レーザーカットで自作)
- 外部モニター(ノートPCの画面をそのまま使ってもOK、フルスクリーン表示推奨)

### 配線例(XIAO ESP32-C3、`firmware/.../xiao_esp32c3_coin_servo.ino` の初期値)

| 部品 | ピン |
| --- | --- |
| コインセンサー(入力、投入でLOW) | D0 |
| サーボモーター(信号線) | D1 |

## セットアップ

### ノートPC側(Flaskサーバー)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

起動後、ブラウザで `http://localhost:5000/` を開くとゲーム画面が表示されます。
画面右下の「コインを投入(テスト用)」ボタンでESP32なしでも動作確認できます
(本番当日は `config/settings.json` の `show_debug_button` を `false` にして、
来場者が誤ってタップできないようにしてください)。

他の端末(ESP32や別PC)からアクセスする場合は `ipconfig`(Windows)/
`ifconfig`(Mac/Linux)でノートPCのIPアドレスを確認してください。

### XIAO ESP32-C3側(ファームウェア)

1. Arduino IDEに以下をインストール
   - ボード: esp32(Espressif Systems)のボードパッケージから `XIAO_ESP32C3` を選択
   - ライブラリ: `ESP32Servo`、`ArduinoJson`
2. `firmware/xiao_esp32c3_coin_servo/xiao_esp32c3_coin_servo.ino` を開き、
   `WIFI_SSID` / `WIFI_PASSWORD` / `SERVER_URL`(ノートPCのIPアドレス)を書き換える
3. 書き込んでシリアルモニタで接続状況とコイン検知ログを確認する

## 景品・確率のカスタマイズ

`config/prizes.json` を編集します。

```json
{
  "id": "daiatari",
  "name": "大当たり",
  "probability": 0.05,
  "stock": 5,
  "servo_angle": 90
}
```

- `probability` … 各景品の当選確率(全景品の合計が1.0になるようにしてください)
- `stock` … 初期在庫数。`null` にすると無制限(はずれなど)
- `servo_angle` … 当選時にサーボを動かす角度。`null` ならカプセルを排出しない(はずれ用)

在庫が0になった景品は自動的に抽選対象から除外され、残りの景品の確率だけで再抽選されます。
はずれ(`stock: null`)を必ず1つ用意しておくことで、全景品が売り切れても抽選自体は成立します。

初期在庫を変更した場合は `data/stock.json` を削除してから再起動すると、
`prizes.json` の内容で作り直されます。

## 在庫管理画面

`http://<ノートPCのIP>:5000/admin` にアクセスすると、景品ごとの残数を確認・変更できます。
補充した分だけ数値を増やして「更新」を押すと即座に反映され、ゲーム画面側の抽選にも反映されます。

## テスト

抽選ロジック(`app/lottery.py`)の単体テストを用意しています。

```bash
pip install -r requirements-dev.txt
pytest
```

## 運用上の注意

- 実際の現金を投入させる形にすると景品交換を伴う抽選(いわゆる賭博)に該当するおそれがあるため、
  文化祭では現金の代わりに事前購入したメダル・チケットをコイン投入口に使う運用を推奨します。
- 演出の見た目(色・アニメーション)は `static/css/style.css` の
  `.state-daiatari` / `.state-atari` / `.state-hazure` を編集することで自由に追加・変更できます。
- 本番当日は `config/settings.json` の `show_debug_button` を `false` にしておくこと。
