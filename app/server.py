"""びっくらポン風カプセルゲームの本体サーバー。

コイン投入(GPIOまたはテスト用API)を受けると抽選し、結果をブラウザ画面へ
Socket.IO で通知、当選していればサーボモーターでカプセルを排出する。
"""

import json
import logging
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO

from app.hardware import HardwareController
from app.lottery import Lottery

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


def handle_coin_inserted():
    logger.info("コイン投入を検知。抽選を実行します。")
    result = lottery.draw()
    logger.info("抽選結果: %s (残り %s)", result["name"], result["remaining"])
    socketio.emit("draw_result", result)
    if result.get("servo_angle") is not None:
        hardware.dispense_capsule()
    socketio.emit("stock_updated", lottery.get_status())


hardware = HardwareController(settings, on_coin_inserted=handle_coin_inserted)


@app.route("/")
def index():
    return render_template("index.html", mock_mode=hardware.is_mock)


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/api/status")
def api_status():
    return jsonify({"prizes": lottery.get_status(), "mock_mode": hardware.is_mock})


@app.route("/api/insert_coin", methods=["POST"])
def api_insert_coin():
    if not hardware.is_mock:
        return jsonify({"error": "実機モードのためテスト投入は無効です"}), 403
    hardware.simulate_coin_insert()
    return jsonify({"ok": True})


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
    # 開発用サーバーをそのまま使う(systemd等ttyなしで起動されるケースに対応するため
    # allow_unsafe_werkzeug=True を指定)。
    socketio.run(
        app,
        host="0.0.0.0",
        port=settings.get("port", 5000),
        allow_unsafe_werkzeug=True,
    )


if __name__ == "__main__":
    main()
