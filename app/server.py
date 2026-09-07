"""びっくらポン風カプセルゲームの本体サーバー(ノートPC側)。

コインセンサー/サーボモーターは XIAO ESP32-C3 側に直結し、ここでは
コイン投入通知を受けて抽選するだけ。抽選結果(サーボ角度含む)は
USBシリアル経由でESP32に返すので、ESP32側はそれだけを見てサーボを
動かすかどうかを判断できる(サーバー→ESP32への呼び出しは発生しない)。

ESP32を接続しない場合(開発中など)は、ブラウザの「コインを投入(テスト用)」
ボタンから同じ抽選ロジックを呼べる。
"""

import json
import logging
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO

from app.lottery import Lottery
from app.serial_bridge import SerialBridge, find_serial_port

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
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
    """抽選を1回実行し、ブラウザ画面に結果と在庫を通知する。"""
    result = lottery.draw()
    logger.info("抽選結果: %s (残り %s)", result["name"], result["remaining"])
    socketio.emit("draw_result", result)
    socketio.emit("stock_updated", lottery.get_status())
    return result


def handle_coin_inserted_from_serial():
    """ESP32からUSBシリアルで "COIN" を受け取ったときに呼ばれる。
    戻り値はサーボを動かすべき角度(はずれなら None)。
    """
    result = run_draw_and_broadcast()
    return result.get("servo_angle")


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
    )
    if bridge.start():
        return bridge
    return None


serial_bridge = start_serial_bridge()


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
    return jsonify(result)


@app.route("/api/restock", methods=["POST"])
def api_restock():
    payload = request.get_json(force=True)
    try:
        remaining = lottery.restock(payload["prize_id"], int(payload["amount"]))
    except KeyError as exc:
        return jsonify({"error": str(exc)}), 404
    socketio.emit("stock_updated", lottery.get_status())
    return jsonify({"prize_id": payload["prize_id"], "remaining": remaining})


@app.route("/api/set_stock", methods=["POST"])
def api_set_stock():
    payload = request.get_json(force=True)
    try:
        remaining = lottery.set_stock(payload["prize_id"], int(payload["amount"]))
    except KeyError as exc:
        return jsonify({"error": str(exc)}), 404
    socketio.emit("stock_updated", lottery.get_status())
    return jsonify({"prize_id": payload["prize_id"], "remaining": remaining})


def main():
    # 文化祭会場のローカルネットワーク内でのみ動かす前提の小規模キオスクアプリのため、
    # 開発用サーバーをそのまま使う(tty無しで起動されるケースに対応するため
    # allow_unsafe_werkzeug=True を指定)。
    socketio.run(
        app,
        host="0.0.0.0",
        port=settings.get("port", 5000),
        allow_unsafe_werkzeug=True,
    )


if __name__ == "__main__":
    main()
