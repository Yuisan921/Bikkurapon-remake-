# 妖怪まつり びっくらぽん

文化祭向けのカプセル抽選ゲームです。

コインが赤外線センサーを通ると抽選が始まり、Arduino Uno R3が「当たり」または「参加賞」のホッパーを動かします。PCにはゲーム画面と管理画面がEdgeのアプリ表示（タブ・アドレスバーなし）で開くため、サーバーやブラウザーを操作する必要はありません。

## インストール

1. [BikkurapoSetup.exe](https://github.com/Yuisan921/Bikkurapon-remake-/releases/latest/download/BikkurapoSetup.exe) をダウンロードする
2. ダウンロードしたファイルをダブルクリックしてインストールする
3. デスクトップの「妖怪まつり びっくらぽん」を起動する

Python、CMD、BATファイルの操作は不要です。

## 普段の使い方

1. Arduino Uno R3とPCをUSBでつなぐ
2. デスクトップの「びっくらぽん」をダブルクリックする
3. 管理画面の「Arduino Uno」が緑色の「接続済み」になるのを待つ
4. 管理画面でホッパーに入れたカプセル数を入力する
5. コインを1枚通して動作を確認する

起動すると次の2画面が自動で開きます。

- **ゲーム画面**：お客さんが見る抽選演出
- **管理画面**：Arduino接続、在庫、確率、画面テスト

「画面演出をテスト」は在庫を減らさず、サーボも動かしません。

## 必要なもの

- Windows 10またはWindows 11のPC
- Arduino Uno R3またはUno互換機
- デジタル出力付き赤外線センサーモジュール
- サーボモーター2個
- カプセル用ホッパー2台（当たり用・参加賞用）
- Arduino用USBケーブル
- サーボ用の外部5V電源

## 配線

| 部品 | Arduino Uno R3 |
|---|---|
| 赤外線センサー OUT | D2 |
| 赤外線センサー VCC | 5V |
| 赤外線センサー GND | GND |
| 当たり用サーボ 信号線 | D9 |
| 参加賞用サーボ 信号線 | D10 |

サーボの電源はArduinoの5Vピンから取らず、十分な電流を出せる外部5V電源を使ってください。外部電源のGNDとArduinoのGNDは必ず共通にします。配線中は電源を切ってください。

## Arduinoへ最初の1回だけ書き込む

1. Arduino IDEをインストールする
2. `firmware/arduino_uno_usb_serial/arduino_uno_usb_serial.ino` を開く
3. 「ツール」→「ボード」で `Arduino Uno` を選ぶ
4. 「ツール」→「ポート」で接続したUnoを選ぶ
5. 「書き込み」を押す

赤外線センサーの多くは、物体で遮られるとOUTがLOWになります。センサーが逆に反応する場合は、ファームウェア先頭付近の次の行だけ変更します。

```cpp
const int COIN_DETECTED_LEVEL = HIGH;
```

サーボの動く向きや角度が合わない場合は、次の値を実機に合わせて変更します。

```cpp
const int SERVO_A_REST_ANGLE = 0;
const int SERVO_A_DISPENSE_ANGLE = 90;
const int SERVO_B_REST_ANGLE = 0;
const int SERVO_B_DISPENSE_ANGLE = 90;
```

## 管理画面

### Arduino Uno

USBポートは自動検出されます。起動後につないでも数秒で再接続します。

### 在庫

各ホッパーへ実際に入れたカプセル数を入力して「在庫を保存」を押します。正常に排出されたときだけ1個減ります。USBが抜けた場合や排出完了を確認できなかった場合は減りません。

### 当たりやすさ

スライダーまたは数字で確率を決め、「確率を保存」を押します。景品が2種類の場合は、もう一方が自動的に調整され、合計100%になります。

### 全画面表示

ゲーム画面上部の操作バー、または管理画面の「ゲーム画面を全画面にする」を押すと、ゲーム画面だけを全画面にできます。全画面中も上部バーから「管理画面」「全画面をやめる」「画面を隠す」「アプリ終了」を選べます。外部モニターへゲーム画面を移動してから全画面にすると、PC側に管理画面を残せます。

## 困ったとき

### Arduinoが「未接続」のまま

1. USBケーブルが充電専用ではなく、データ通信対応か確認する
2. WindowsのデバイスマネージャーでCOMポートが表示されるか確認する
3. Arduino IDEを閉じる（シリアルモニターがポートを使用している場合があります）
4. Uno互換機の場合はCH340ドライバーを確認する

### センサーが反応しない

1. センサーの電源ランプを確認する
2. OUTがD2につながっているか確認する
3. センサー基板の感度調整ネジを少しずつ回す
4. `COIN_DETECTED_LEVEL` をLOW/HIGHで切り替える

### サーボが動くとArduinoが再起動する

電源不足の可能性が高いです。サーボへ外部5V電源を使い、GNDをArduinoと共通にしてください。

### カプセルは出たのにエラー画面になる

UnoからPCへの排出完了通知が届いていません。USBケーブル、電源、Arduinoへ書き込んだファームウェアを確認してください。

## 開発する場合

Python 3.11以降を推奨します。

```bash
python -m venv .venv
```

Windows:

```bat
.venv\Scripts\activate
pip install -r requirements-dev.txt
python run.py
```

通常は `scripts/start_bikkurapon.bat` をダブルクリックするだけで起動できます。起動に失敗した場合はCMD画面を閉じずに原因を表示し、プロジェクト直下の `bikkurapon-startup.log` に詳細を保存します。

macOS / Linux:

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
python run.py
```

テスト:

```bash
pytest -q
```

Windows用インストーラーはGitHub Actionsの「Build Windows installer」を実行すると生成できます。ローカルで作る場合は `scripts/build_exe.bat` を実行します。

## 内部構成

利用時に意識する必要はありませんが、アプリ内部ではローカル通信を使ってゲーム画面と制御処理を同期しています。外部インターネットは不要です。初期設定ではこのPC以外から管理操作できません。

- `app/`：抽選、在庫、USB通信、アプリ起動
- `templates/`、`static/`：ゲーム画面と管理画面
- `firmware/arduino_uno_usb_serial/`：Uno R3用プログラム
- `config/`：初期設定
- `cad/`：筐体・ホッパー用データ
