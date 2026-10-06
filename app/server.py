"""びっくらポン風カプセルゲームの本体サーバー(ノートPC側)。

コインセンサー/サーボモーターは XIAO ESP32-C3 側に直結し、ここでは
コイン投入通知を受けて抽選するだけ。当たり用・はずれ用それぞれに
専用のホッパー(サーボ)があり、抽選結果の "hopper" フィールド("a"/"b")
に応じてどちらを動かすかをUSBシリアル経由でESP32に伝える。
ESP32側はそれだけを見てサーボを動かせる(サーバー→ESP32への呼び出しは
発生しない)。

ESP32を接続しない場合(開発中など)は、ブラウザの「コインを投入(テスト用)」
ボタンから同じ抽選ロジックを呼べる。
"""

import json
import logging

from flask import Flask, abort, jsonify, make_response, render_template, request
from flask_socketio import SocketIO

from app.browser_launcher import open_windows_after_delay
from app.config_setup import ensure_config_dir
from app.lottery import Lottery, OutOfStock
from app.paths import BASE_DIR, BUNDLE_DIR
from app.serial_bridge import SerialBridge, find_serial_port

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
logger.info("設定フォルダ: %s / データフォルダ: %s", CONFIG_DIR, DATA_DIR)

# .exe化した初回起動時は、実行ファイルの隣にconfig/がまだ無いので、
# 同梱されているデフォルト設定をコピーして作る(以降はここを直接編集できる)。
# 既にある場合でも、旧バージョンの景品構成(大当たり等)のままなら
# 最新の既定値に差し替える(詳細はconfig_setup.pyのコメント参照)。
ensure_config_dir(CONFIG_DIR, BUNDLE_DIR / "config")

app = Flask(
    __name__,
    template_folder=str(BUNDLE_DIR / "templates"),
    static_folder=str(BUNDLE_DIR / "static"),
)
app.config["SECRET_KEY"] = "bikkurapon-remake"
socketio = SocketIO(app, cors_allowed_origins="*")

with open(CONFIG_DIR / "settings.json", encoding="utf-8") as f:
    settings = json.load(f)

lottery = Lottery(
    prizes_config_path=CONFIG_DIR / "prizes.json",
    stock_data_path=DATA_DIR / "stock.json",
)


def run_draw_and_broadcast():
    """抽選を1回実行し、ブラウザ画面に結果と在庫を通知する。

    全景品の在庫が尽きていて抽選できない場合は、演出画面に
    "out_of_stock"(巫女さんを呼ぶ画面)を通知して None を返す。
    この場合、在庫は減らさず、ホッパーも動かさない。
    """
    try:
        result = lottery.draw()
    except OutOfStock:
        logger.error("在庫がすべて尽きています。巫女さんを呼ぶ画面を表示します。")
        socketio.emit("out_of_stock", {})
        socketio.emit("stock_updated", lottery.get_status())
        return None

    logger.info("抽選結果: %s (残り %s)", result["name"], result["remaining"])
    socketio.emit("draw_result", result)
    socketio.emit("stock_updated", lottery.get_status())
    return result


def handle_coin_inserted_from_serial():
    """ESP32からUSBシリアルで "COIN" を受け取ったときに呼ばれる。
    戻り値は動かすべきホッパー記号("a"/"b"。どちらも使わない・在庫切れなら None)。
    """
    result = run_draw_and_broadcast()
    if result is None:
        return None
    return result.get("hopper")


def start_serial_bridge():
    port_setting = settings.get("serial_port")
    if not port_setting:
        logger.info("serial_port が未設定のため、USBシリアル連携は無効です。")
        return None

    port = find_serial_port() if port_setting == "auto" else port_setting
    if not port:
        logger.warning(
            "USBシリアルポートが見つかりませんでした。"
            "config/settings.json の serial_port で明示的に指定してください。"
        )
        return None

    bridge = SerialBridge(
        port=port,
        baudrate=settings.get("serial_baudrate", 115200),
        on_coin_inserted=handle_coin_inserted_from_serial,
        # "auto" のときは、USBを抜き差ししてポート名が変わっても探し直す
        port_finder=(lambda: find_serial_port(warn=False)) if port_setting == "auto" else None,
    )
    if bridge.start():
        return bridge
    return None


serial_bridge = start_serial_bridge()


# --- アクセス制限 -------------------------------------------------------
# 会場のWiFiには来場者もつながっているので、在庫・確率を書き換える管理系の
# 操作と、抽選を起動する /api/insert_coin は、既定ではこのPC自身(ローカル)
# からしか受け付けない。別端末(スマホの管理画面や、WiFi版ESP32)から使いたい
# 場合だけ、config/settings.json で明示的に許可する(README参照)。
_LOOPBACK_ADDRESSES = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}
_ADMIN_PATHS = {"/admin", "/api/restock", "/api/set_stock", "/api/set_probability"}


@app.before_request
def restrict_remote_access():
    if request.remote_addr in _LOOPBACK_ADDRESSES:
        return None
    if request.path in _ADMIN_PATHS and not settings.get("allow_remote_admin", False):
        abort(403)
    if request.path == "/api/insert_coin" and not settings.get(
        "allow_remote_insert_coin", False
    ):
        abort(403)
    return None


def _field(payload, key, cast):
    """JSONの項目を取り出して型変換する。無い・変換できない場合は400を返す。"""
    try:
        return cast(payload[key])
    except (KeyError, TypeError, ValueError):
        abort(make_response(jsonify({"error": f"invalid or missing field: {key}"}), 400))


def _json_payload():
    payload = request.get_json(force=True, silent=True)
    return payload if isinstance(payload, dict) else {}


@app.route("/")
def index():
    return render_template(
        "index.html", show_debug_button=settings.get("show_debug_button", True)
    )


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/api/status")
def api_status():
    return jsonify({"prizes": lottery.get_status()})


@app.route("/api/insert_coin", methods=["POST"])
def api_insert_coin():
    """ブラウザのテストボタンからコイン投入を通知するエンドポイント。"""
    result = run_draw_and_broadcast()
    if result is None:
        # 在庫切れ。WiFi版ESP32は200以外ならホッパーを動かさない。
        return jsonify({"error": "out_of_stock"}), 409
    return jsonify(result)


@app.route("/api/restock", methods=["POST"])
def api_restock():
    payload = _json_payload()
    prize_id = _field(payload, "prize_id", str)
    amount = _field(payload, "amount", int)
    try:
        remaining = lottery.restock(prize_id, amount)
    except KeyError as exc:
        return jsonify({"error": str(exc)}), 404
    socketio.emit("stock_updated", lottery.get_status())
    return jsonify({"prize_id": prize_id, "remaining": remaining})


@app.route("/api/set_stock", methods=["POST"])
def api_set_stock():
    payload = _json_payload()
    prize_id = _field(payload, "prize_id", str)
    amount = _field(payload, "amount", int)
    try:
        remaining = lottery.set_stock(prize_id, amount)
    except KeyError as exc:
        return jsonify({"error": str(exc)}), 404
    socketio.emit("stock_updated", lottery.get_status())
    return jsonify({"prize_id": prize_id, "remaining": remaining})


@app.route("/api/set_probability", methods=["POST"])
def api_set_probability():
    """景品の当選確率を変更する(config/prizes.jsonにも保存される)。"""
    payload = _json_payload()
    prize_id = _field(payload, "prize_id", str)
    new_probability = _field(payload, "probability", float)
    try:
        probability = lottery.set_probability(prize_id, new_probability)
    except KeyError as exc:
        return jsonify({"error": str(exc)}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    socketio.emit("stock_updated", lottery.get_status())
    return jsonify({"prize_id": prize_id, "probability": probability})


def main():
    port = settings.get("port", 5000)

    # サーバー起動が終わるのを少し待ってから、演出画面(キオスクモード)と
    # 管理画面を自動でブラウザで開く。config/settings.json の
    # auto_open_browser を false にすると無効化できる。
    open_windows_after_delay(f"http://localhost:{port}", settings)

    # 文化祭会場のローカルネットワーク内でのみ動かす前提の小規模キオスクアプリのため、
    # 開発用サーバーをそのまま使う(tty無しで起動されるケースに対応するため
    # allow_unsafe_werkzeug=True を指定)。
    # 既定ではこのPC自身からしか接続できない("127.0.0.1")。WiFi版ESP32や
    # 別端末の管理画面を使う場合だけ settings.json の host を "0.0.0.0" にする。
    socketio.run(
        app,
        host=settings.get("host", "127.0.0.1"),
        port=port,
        allow_unsafe_werkzeug=True,
    )


if __name__ == "__main__":
    main()
