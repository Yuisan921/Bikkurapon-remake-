"""びっくらポン風カプセルゲームの本体サーバー(ノートPC側)。

コインセンサー/サーボモーターは Arduino Uno R3 側に直結し、ここでは
コイン投入通知を受けて抽選するだけ。当たり用・はずれ用それぞれに
専用のホッパー(サーボ)があり、抽選結果の "hopper" フィールド("a"/"b")
に応じてどちらを動かすかをUSBシリアル経由でUnoに伝える。
Uno側はそれだけを見てサーボを動かせる(サーバー→Unoへの呼び出しは
発生しない)。

Unoを接続しない場合でも、管理画面から在庫を減らさない画面演出テストを行える。
"""

import json
import hmac
import logging
import socket
import urllib.error
import urllib.request
from logging.handlers import RotatingFileHandler

from flask import Flask, abort, jsonify, make_response, render_template, request
from flask_socketio import SocketIO

from app.browser_launcher import open_windows, open_windows_after_delay
from app.config_setup import ensure_config_dir, migrate_legacy_data
from app.lottery import Lottery, OutOfStock
from app.paths import BASE_DIR, BUNDLE_DIR, LEGACY_BASE_DIR
from app.serial_bridge import SerialBridge, find_serial_port

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# GUI版ではコンソールを表示しないため、起動失敗も確認できるログを保存する。
# 1ファイル1MB・3世代に制限し、文化祭のPCで容量が増え続けないようにする。
try:
    file_handler = RotatingFileHandler(
        DATA_DIR / "bikkurapon.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logging.getLogger().addHandler(file_handler)
except OSError:
    logger.exception("ログファイルを作成できませんでした。")

logger.info("設定フォルダ: %s / データフォルダ: %s", CONFIG_DIR, DATA_DIR)

# .exe化した初回起動時は、実行ファイルの隣にconfig/がまだ無いので、
# 同梱されているデフォルト設定をコピーして作る(以降はここを直接編集できる)。
# 既にある場合でも、旧バージョンの景品構成(大当たり等)のままなら
# 最新の既定値に差し替える(詳細はconfig_setup.pyのコメント参照)。
migrate_legacy_data(LEGACY_BASE_DIR, BASE_DIR)
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


def _broadcast_result(result):
    logger.info("抽選結果: %s (残り %s)", result["name"], result["remaining"])
    socketio.emit("draw_result", result)
    socketio.emit("stock_updated", lottery.get_status())


def run_draw_and_broadcast():
    """抽選を1回実行し、ゲーム画面に結果と在庫を通知する。

    全景品の在庫が尽きていて抽選できない場合は、演出画面に
    "out_of_stock"(巫女さんを呼ぶ画面)を通知して None を返す。
    この場合、在庫は減らさず、ホッパーも動かさない。
    """
    try:
        plan = lottery.reserve_draw()
    except OutOfStock:
        logger.error("在庫がすべて尽きています。巫女さんを呼ぶ画面を表示します。")
        socketio.emit("out_of_stock", {})
        socketio.emit("stock_updated", lottery.get_status())
        return None

    socketio.emit("draw_started", {})
    result = lottery.commit_draw(plan["reservation_id"])
    _broadcast_result(result)
    return result


def prepare_hardware_draw():
    """実物の排出用に抽選結果を予約する。在庫確定と表示はACK後に行う。"""
    try:
        plan = lottery.reserve_draw()
    except OutOfStock:
        logger.error("在庫がすべて尽きています。巫女さんを呼ぶ画面を表示します。")
        socketio.emit("out_of_stock", {})
        socketio.emit("stock_updated", lottery.get_status())
        return None

    socketio.emit("draw_started", {})

    # カプセルを出さない完全ハズレは物理ACKが不要なので即時確定する。
    if plan.get("hopper") is None:
        result = lottery.commit_draw(plan["reservation_id"])
        _broadcast_result(result)
        return {**result, "reservation_id": None}
    return plan


def finish_hardware_draw(reservation_id, success):
    """制御基板の排出完了応答を受け、成功時だけ在庫と表示を確定する。"""
    if not success:
        lottery.cancel_draw(reservation_id)
        socketio.emit("draw_cancelled", {})
        socketio.emit("stock_updated", lottery.get_status())
        logger.error("カプセル排出を確認できなかったため抽選を取り消しました。")
        return None
    try:
        result = lottery.commit_draw(reservation_id)
    except (KeyError, OutOfStock) as exc:
        logger.error("排出済み抽選を確定できませんでした: %s", exc)
        return None
    _broadcast_result(result)
    return result


def handle_coin_inserted_from_serial():
    """UnoからUSBシリアルで "COIN" を受け取ったときに呼ばれる。
    戻り値は動かすべきホッパー記号("a"/"b"。どちらも使わない・在庫切れなら None)。
    """
    return prepare_hardware_draw()


def handle_serial_dispense_result(reservation_id, success):
    finish_hardware_draw(reservation_id, success)


def start_serial_bridge():
    port_setting = settings.get("serial_port")
    if not port_setting:
        logger.info("serial_port が未設定のため、USBシリアル連携は無効です。")
        return None

    port = find_serial_port() if port_setting == "auto" else port_setting
    if not port:
        logger.info("USBシリアルポートはまだ見つかりません。接続を待機します。")

    bridge = SerialBridge(
        port=port,
        baudrate=settings.get("serial_baudrate", 115200),
        on_coin_inserted=handle_coin_inserted_from_serial,
        on_dispense_result=handle_serial_dispense_result,
        # "auto" のときは、USBを抜き差ししてポート名が変わっても探し直す
        port_finder=(lambda: find_serial_port(warn=False)) if port_setting == "auto" else None,
    )
    if bridge.start():
        return bridge
    return None


serial_bridge = None


def is_bikkurapon_server_running(base_url, timeout_seconds=0.6):
    """同じPCですでに起動している本アプリのサーバーか確認する。"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"{base_url}/api/status", timeout=timeout_seconds) as response:
            payload = json.load(response)
        return response.status == 200 and isinstance(payload.get("prizes"), list)
    except (OSError, ValueError, urllib.error.URLError):
        return False


def find_available_port(host, preferred_port, attempts=20):
    """既定ポートが旧プロセス等に使われていても起動できるポートを返す。"""
    bind_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    for port in range(preferred_port, preferred_port + attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind((bind_host, port))
            return port
        except OSError:
            continue
    return None


# --- アクセス制限 -------------------------------------------------------
# 会場のWiFiには来場者もつながっているので、在庫・確率を書き換える管理系の
# 操作と、抽選を起動する /api/insert_coin は、既定ではこのPC自身(ローカル)
# からしか受け付けない。別端末(スマホの管理画面や、WiFi版ESP32)から使いたい
# 場合だけ、config/settings.json で明示的に許可する(README参照)。
_LOOPBACK_ADDRESSES = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}
_ADMIN_PATHS = {
    "/admin",
    "/api/system_status",
    "/api/preview_result",
    "/api/restock",
    "/api/set_stock",
    "/api/set_probability",
}
_DEVICE_PATHS = {"/api/insert_coin", "/api/dispense_ack"}


def _valid_device_token():
    configured = settings.get("device_token")
    provided = request.headers.get("X-Bikkurapon-Token", "")
    return (
        isinstance(configured, str)
        and len(configured) >= 16
        and hmac.compare_digest(provided, configured)
    )


@app.before_request
def restrict_remote_access():
    if request.remote_addr in _LOOPBACK_ADDRESSES:
        return None
    if request.path in _ADMIN_PATHS and not settings.get("allow_remote_admin", False):
        abort(403)
    if request.path in _DEVICE_PATHS:
        if not settings.get("allow_remote_insert_coin", False):
            abort(403)
        if not _valid_device_token():
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
    return render_template("index.html")


@app.route("/admin")
def admin():
    return render_template("admin.html")


@app.route("/api/status")
def api_status():
    return jsonify({"prizes": lottery.get_status()})


@app.route("/api/system_status")
def api_system_status():
    """管理画面用。USB接続とゲームの準備状態を分かりやすく返す。"""
    if serial_bridge is not None:
        hardware = serial_bridge.get_status()
    else:
        port_setting = settings.get("serial_port")
        hardware = {
            "enabled": bool(port_setting),
            "connected": False,
            "port": None if port_setting == "auto" else port_setting,
        }
    return jsonify({"hardware": hardware, "ready": lottery.has_stock()})


@app.route("/api/preview_result", methods=["POST"])
def api_preview_result():
    """在庫やホッパーを動かさず、選んだ結果の画面演出だけを確認する。"""
    prize_id = _field(_json_payload(), "prize_id", str)
    prize = next((item for item in lottery.get_status() if item["id"] == prize_id), None)
    if prize is None:
        return jsonify({"error": "unknown prize"}), 404
    socketio.emit("draw_started", {"preview": True})
    socketio.emit("draw_result", {**prize, "preview": True})
    return jsonify({"ok": True})


@app.route("/api/insert_coin", methods=["POST"])
def api_insert_coin():
    """ローカルテストまたはWi-Fi制御基板からコイン投入を通知する。"""
    # ローカルのテストボタンは実物を動かさないので即時確定する。
    if request.remote_addr in _LOOPBACK_ADDRESSES:
        result = run_draw_and_broadcast()
    else:
        # WiFi版ESP32は排出完了後に /api/dispense_ack を送る。ACKまでは
        # 在庫ファイルも演出画面も確定しない。
        result = prepare_hardware_draw()
    if result is None:
        # 在庫切れ。WiFi版ESP32は200以外ならホッパーを動かさない。
        return jsonify({"error": "out_of_stock"}), 409
    return jsonify(result)


@app.route("/api/dispense_ack", methods=["POST"])
def api_dispense_ack():
    payload = _json_payload()
    reservation_id = _field(payload, "reservation_id", str)
    success = payload.get("success")
    if not isinstance(success, bool):
        abort(make_response(jsonify({"error": "invalid or missing field: success"}), 400))
    result = finish_hardware_draw(reservation_id, success)
    if result is None:
        return jsonify({"error": "unknown_or_cancelled_reservation"}), 409
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
    global serial_bridge
    host = settings.get("host", "127.0.0.1")
    preferred_port = int(settings.get("port", 5000))

    preferred_url = f"http://127.0.0.1:{preferred_port}"
    if is_bikkurapon_server_running(preferred_url):
        logger.info("すでに起動中のびっくらぽん画面を開きます。")
        open_windows(preferred_url, settings)
        return

    port = find_available_port(host, preferred_port)
    if port is None:
        logger.error("利用できる通信ポートが見つからないため起動できません。")
        if serial_bridge is not None:
            serial_bridge.stop()
        return
    if port != preferred_port:
        logger.warning("ポート%dが使用中のため、ポート%dで起動します。", preferred_port, port)

    serial_bridge = start_serial_bridge()

    def run_server():
        # 既定ではこのPC自身からしか接続できない。Wi-Fi版の機器や別端末を
        # 明示的に使う場合だけ settings.json の host を変更する。
        socketio.run(
            app,
            host=host,
            port=port,
            allow_unsafe_werkzeug=True,
            use_reloader=False,
        )

    base_url = f"http://127.0.0.1:{port}"

    # Edgeの「アプリとして表示」を使うため、タブやアドレスバーは出ない。
    # 画面は別プロセスに任せ、サーバーをメインスレッドで動かすことで、
    # Windows環境でウィンドウ表示後に応答しなくなる問題を避ける。
    open_windows_after_delay(base_url, settings, delay_seconds=0.8)
    try:
        run_server()
    finally:
        if serial_bridge is not None:
            serial_bridge.stop()


if __name__ == "__main__":
    main()
