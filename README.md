# びっくらポン(文化祭リメイク版)

回転寿司でおなじみの「びっくらポン」を文化祭のミニゲームとして再現するプロジェクトです。

コインを入れる → 画面で抽選演出 → 結果表示 → 当たりならサーボモーターでカプセルを排出、
という一連の流れを Raspberry Pi + Flask で実装しています。

## 全体構成

- `run.py` … 起動エントリーポイント
- `app/server.py` … Flask + Socket.IO サーバー本体
- `app/lottery.py` … 確率抽選と景品在庫の管理
- `app/hardware.py` … コインセンサー/サーボモーターの制御(GPIO)。実機がない環境では
  自動でモックモードにフォールバックし、ログ出力だけで動作確認できます
- `config/prizes.json` … 景品の一覧・当選確率・初期在庫・サーボ角度
- `config/settings.json` … GPIOピン番号やサーボの設定
- `templates/`, `static/` … モニター表示画面(`/`)と在庫管理画面(`/admin`)
- `data/stock.json` … 実行時に自動生成される現在の在庫数(gitignore対象)

## 必要なハードウェア(実機運用時)

- Raspberry Pi(Raspberry Pi OS)
- コインセレクター、またはコイン投入を検知する簡易スイッチ・光センサー
- カプセル排出用のサーボモーター(SG90など)
- モニター(HDMI接続、フルスクリーン表示推奨)

### 配線例(`config/settings.json` の初期値)

| 部品 | GPIO |
| --- | --- |
| コインセンサー(入力) | GPIO17 |
| サーボモーター(信号線) | GPIO18 |

ピン番号やサーボの角度・保持時間は `config/settings.json` で変更できます。

## セットアップ

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

起動後、ブラウザで `http://<RaspberryPiのIP>:5000/` を開くとゲーム画面が表示されます。

### ハードウェアなしで動作確認する(開発用PCなど)

`gpiozero` が実機GPIOを検知できない環境では、自動的に **モックモード** で起動します。
モックモード時はゲーム画面右下に「コインを投入(テスト用)」ボタンが表示されるので、
実機がなくても抽選〜演出〜在庫管理までブラウザだけで確認できます。

`config/settings.json` の `mock_mode` を `"force_mock"` にすると常にモックモードに、
`"force_real"` にすると実機GPIOが使えない場合にエラーで起動を止められます。

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

`http://<RaspberryPiのIP>:5000/admin` にアクセスすると、景品ごとの残数を確認・変更できます。
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
