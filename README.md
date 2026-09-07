# びっくらポン(文化祭リメイク版)

回転寿司でおなじみの「びっくらポン」を文化祭のミニゲームとして再現するプロジェクトです。

コインを入れる → 画面で抽選演出 → 結果表示 → 当たりならサーボモーターでカプセルを排出、
という一連の流れを実装しています。

## 全体構成(役割分担)

本体は2つの機器に分かれています。

- **ノートPC**: 抽選ロジックとモニター表示画面を担当(このリポジトリのFlaskアプリ)。
  GPIOなどのハードウェアは一切触らない
- **Seeed XIAO ESP32-C3**: コインセンサーとカプセル排出用サーボモーターを直結し、
  コイン投入を検知したらノートPCに通知するだけの小さなファームウェアを書き込んで使う

ESP32とノートPCの接続方法は **USBケーブル(推奨)** と **WiFi** の2通りを用意しています。

| 接続方法 | ファームウェア | 特徴 |
| --- | --- | --- |
| USB(推奨) | `firmware/xiao_esp32c3_usb_serial/` | ケーブル1本で完結。会場のWiFi環境に左右されず安定動作 |
| WiFi | `firmware/xiao_esp32c3_wifi_http/` | ESP32を離れた場所に置きたい場合向け。会場WiFiかノートPCのモバイルホットスポットが必要 |

### 通信の流れ(USB版)

1. XIAO ESP32-C3がコインセンサーの投入を検知し、USBシリアルで `COIN` という1行を送る
2. ノートPCがそれを受け取って抽選を実行し、
   - 当選なら `DISPENSE:<角度>`
   - はずれなら `NONE`
   を1行返す。同時にSocket.IOでブラウザ画面にも結果を通知して演出を再生する
3. ESP32は返ってきた行を見て、当選していればサーボモーターを動かしてカプセルを排出する

WiFi版もレスポンスの中身(サーバー→ESP32への逆方向通信が不要な設計)は同じで、
HTTP経由でJSONをやり取りする点だけが異なります。詳しくは
`firmware/xiao_esp32c3_wifi_http/xiao_esp32c3_wifi_http.ino` 冒頭のコメントを参照してください。

## カプセル排出機構(CAD)

`cad/capsule_dispenser.scad` に、回転ゲート式のカプセルディスペンサーの
パラメトリックモデル(OpenSCAD)があります。当たり用・はずれ用(弱景品)で
同じものを2セット印刷して使う想定です。

- 無料の [OpenSCAD](https://openscad.org/) で開いてください
- ファイル冒頭の `PART` 変数を `"throat_adapter"` / `"gate_disc"` / `"base"` に
  切り替えて、それぞれ File > Export > Export as STL でパーツごとに出力します
  (`"assembly"` は組み立てイメージのプレビュー用で、STL出力の対象ではありません)
- `capsule_diameter`(カプセル直径)や `servo_*`(サーボの寸法)は実物に
  合わせて数値を調整してから出力してください
- レンダリング時にコンソールへ各パーツの高さ・直径が出力されるので、
  お使いの3Dプリンタの造形サイズ(`printer_bed_x/y/z`)に収まっているか
  確認してください(既定値は200x200x170mm)
- FusionなどのCADで外側の筐体(装飾込みの本体ケース)を作る場合は、
  この機構部分だけOpenSCADでSTLを出力し、そのSTLをメッシュとして
  Fusion側のプロジェクトに取り込んで組み合わせる形がおすすめです

### カプセルを貯める部分(ホッパー)は3Dプリントしない

カプセルをまとめて貯めておく背の高い部分は、3Dプリンタの造形サイズに
左右されないよう、あえてOpenSCAD側では作っていません。代わりに
`throat_adapter` パーツ上部の「襟」(`funnel_collar_outer_d` で直径を調整)に、
市販の透明アクリルパイプや、いらないペットボトル・クリアな容器などを
接着 or はめ込みで取り付けて使ってください。中のカプセルが見える方が
本物のガチャガチャらしくもあります。使う容器の口の直径に合わせて
`funnel_collar_outer_d` を調整してから `throat_adapter` を出力してください。

## リポジトリの構成

- `run.py` … 起動エントリーポイント
- `app/server.py` … Flask + Socket.IO サーバー本体(ノートPCで動かす)
- `app/lottery.py` … 確率抽選と景品在庫の管理
- `app/serial_bridge.py` … XIAO ESP32-C3とのUSBシリアル通信(コイン投入受信・結果送信)
- `config/prizes.json` … 景品の一覧・当選確率・初期在庫・サーボ角度
- `config/settings.json` … ポート番号・USBシリアルポート・テスト用ボタンの表示設定
- `templates/`, `static/` … モニター表示画面(`/`)と在庫管理画面(`/admin`)
- `data/stock.json` … 実行時に自動生成される現在の在庫数(gitignore対象)
- `firmware/xiao_esp32c3_usb_serial/` … XIAO ESP32-C3用ファームウェア(USB接続版・推奨)
- `firmware/xiao_esp32c3_wifi_http/` … XIAO ESP32-C3用ファームウェア(WiFi接続版)
- `cad/capsule_dispenser.scad` … カプセル排出機構のパラメトリックCAD(OpenSCAD)
- `scripts/` … 当日の起動を1コマンドでまとめて行うスクリプト(Windows/Mac/Linux)

## 必要なハードウェア

- ノートPC(モニター表示・抽選ロジック用)
- Seeed XIAO ESP32-C3
- コインセンサー(フォトインタラプタや簡易スイッチなど)
- カプセル排出用のサーボモーター(SG90など)
- カプセル排出機構(3Dプリント/レーザーカットで自作)
- 外部モニター(ノートPCの画面をそのまま使ってもOK、フルスクリーン表示推奨)
- USBケーブル(XIAO ESP32-C3をノートPCに接続する用)

### 配線例(XIAO ESP32-C3共通)

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

起動時のログに `USBシリアルブリッジを開始しました` と出ていればESP32を自動検出できています。
出ていない場合はESP32が接続されていないか自動検出に失敗しているので、
`config/settings.json` の `serial_port` に手動でポート名(例: `/dev/ttyACM0` や `COM3`)を
指定してください。ESP32を接続しない状態でも、ブラウザの
「コインを投入(テスト用)」ボタンで動作確認できます(本番当日は
`show_debug_button` を `false` にして、来場者が誤ってタップできないようにしてください)。

起動後、ブラウザで `http://localhost:5000/` を開くとゲーム画面が表示されます。

### 当日の起動を1コマンドで(起動スクリプト)

`scripts/` に、サーバー起動から「演出画面(外部モニターにフルスクリーン)」
「管理画面(ノートPC本体に通常ウィンドウ)」を2つ同時に開くスクリプトを用意しています。

- Windows: `scripts\start_bikkurapon.bat` をダブルクリック
- Mac/Linux: `bash scripts/start_bikkurapon.sh`

スクリプト内の `--window-position=1920,0` は外部モニターの左上座標です。
ノートPC画面の解像度や、外部モニターをどちら側に拡張しているかによって
数値を合わせて書き換えてください(分からない場合は、いったんそのまま実行して
表示されたウィンドウを手動でモニター間ドラッグしてもOKです)。
Chrome/Chromiumが見つからない場合は自動起動せず、URLをターミナルに表示するので
手動でブラウザを開いてください。

### XIAO ESP32-C3側(ファームウェア、USB接続版)

1. Arduino IDEに以下をインストール
   - ボード: esp32(Espressif Systems)のボードパッケージから `XIAO_ESP32C3` を選択
   - Tools > USB CDC On Boot を `Enabled` にする(USB経由のシリアル通信に必須)
   - ライブラリ: `ESP32Servo`
2. `firmware/xiao_esp32c3_usb_serial/xiao_esp32c3_usb_serial.ino` を書き込む
   (WIFI設定などは不要。ピン番号を変える場合だけ冒頭の定数を編集)
3. USBケーブルでノートPCに接続する。シリアルモニタでコイン検知ログを確認できます

WiFi接続版を使う場合は `firmware/xiao_esp32c3_wifi_http/` の手順(ファイル冒頭のコメント)
に従ってWiFi情報とノートPCのIPアドレスを設定してください。

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
