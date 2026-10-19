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
import threading
import time
import urllib.error
import urllib.request
from logging.handlers import RotatingFileHandler

from flask import Flask, abort, jsonify, make_response, render_template, request, send_from_directory
from flask_socketio import SocketIO

from app.browser_launcher import open_default_windows, open_windows
from app.config_setup import ensure_config_dir, migrate_legacy_data
from app.lottery import Lottery, OutOfStock, _write_json_atomic
from app.paths import BASE_DIR, BUNDLE_DIR, LEGACY_BASE_DIR
from app.serial_bridge import SerialBridge, find_serial_port

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "data"
VIDEO_DIR = BASE_DIR / "videos"
DATA_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

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
    auto_probability_by_stock=settings.get("auto_probability_by_stock", False),
)
settings_lock = threading.Lock()


def save_settings():
    """管理画面から変更した設定を、次回起動にも残す。"""
    with settings_lock:
        _write_json_atomic(CONFIG_DIR / "settings.json", settings)


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


last_admin_error = None
admin_error_lock = threading.Lock()


def report_admin_error(error):
    """客側には出さない詳しいエラーを管理画面へ保存・通知する。"""
    global last_admin_error
    normalized = {
        "code": error.get("code", "hardware_error"),
        "title": error.get("title", "実機の動作でエラーが発生しました"),
        "detail": error.get("detail", "Arduino、USBケーブル、サーボ電源を確認してください。"),
        "occurred_at": time.time(),
    }
    with admin_error_lock:
        last_admin_error = normalized
    socketio.emit("admin_error", normalized)
    return normalized


def get_last_admin_error():
    with admin_error_lock:
        return dict(last_admin_error) if last_admin_error else None


def finish_hardware_draw(reservation_id, success, error=None):
    """制御基板の排出完了応答を受け、成功時だけ在庫と表示を確定する。"""
    if not success:
        lottery.cancel_draw(reservation_id)
        socketio.emit("draw_cancelled", {})
        socketio.emit("stock_updated", lottery.get_status())
        reported = report_admin_error(error or {
            "code": "dispense_failed",
            "title": "カプセルを排出できませんでした",
            "detail": "Arduinoから正常な排出完了を確認できませんでした。USB接続、サーボ電源、カプセル詰まりを確認してください。",
        })
        logger.error("カプセル排出を確認できず抽選を取り消しました: %s", reported["detail"])
        return None
    try:
        result = lottery.commit_draw(reservation_id)
    except (KeyError, OutOfStock) as exc:
        socketio.emit("draw_cancelled", {})
        report_admin_error({
            "code": "inventory_commit_failed",
            "title": "排出後の在庫更新に失敗しました",
            "detail": f"カプセルは排出されましたが、在庫データを更新できませんでした。管理画面で実在庫を確認してください（{exc}）。",
        })
        logger.error("排出済み抽選を確定できませんでした: %s", exc)
        return None
    _broadcast_result(result)
    return result


def handle_coin_inserted_from_serial():
    """UnoからUSBシリアルで "COIN" を受け取ったときに呼ばれる。
    戻り値は動かすべきホッパー記号("a"/"b"。どちらも使わない・在庫切れなら None)。
    """
    return prepare_hardware_draw()


def handle_serial_dispense_result(reservation_id, success, error=None):
    finish_hardware_draw(reservation_id, success, error)


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
ui_connected = threading.Event()


def is_bikkurapon_server_running(base_url, timeout_seconds=0.6):
    """同じPCですでに起動している本アプリのサーバーか確認する。"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"{base_url}/api/status", timeout=timeout_seconds) as response:
            status = response.status
            payload = json.load(response)
        return (
            status == 200
            and isinstance(payload, dict)
            and isinstance(payload.get("prizes"), list)
        )
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


def wait_until_server_ready(base_url, timeout_seconds=15):
    """内部サーバーの応答を確認してから画面を開く。"""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if is_bikkurapon_server_running(base_url, timeout_seconds=0.4):
            return True
        time.sleep(0.1)
    return False


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
    "/api/demo_draw",
    "/api/hardware_test",
    "/api/clear_admin_error",
    "/api/restock",
    "/api/set_stock",
    "/api/set_probability",
    "/api/set_auto_probability",
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
    ui_connected.set()
    return render_template("index.html")


@app.route("/admin")
def admin():
    ui_connected.set()
    return render_template("admin.html")


@app.route("/media/<path:filename>")
def media_file(filename):
    """利用者が後から差し替える当たり・ハズレ動画を返す。"""
    return send_from_directory(VIDEO_DIR, filename)


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
    return jsonify({
        "hardware": hardware,
        "ready": lottery.has_stock(),
        "auto_probability_by_stock": lottery.auto_probability_by_stock,
        "last_error": get_last_admin_error(),
    })


@app.route("/api/clear_admin_error", methods=["POST"])
def api_clear_admin_error():
    """管理者が確認したエラー表示を消す。"""
    global last_admin_error
    with admin_error_lock:
        last_admin_error = None
    socketio.emit("admin_error_cleared", {})
    return jsonify({"ok": True})


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


@app.route("/api/demo_draw", methods=["POST"])
def api_demo_draw():
    """設定中の確率で1回試す。在庫・Arduino・ホッパーには触れない。"""
    try:
        result = lottery.preview_draw()
    except OutOfStock:
        return jsonify({"error": "no_prizes"}), 409
    socketio.emit("draw_started", {"preview": True})
    socketio.emit("draw_result", result)
    return jsonify(result)


@app.route("/api/hardware_test", methods=["POST"])
def api_hardware_test():
    """Arduino・ホッパー・在庫を含む、本番と同じ抽選を1回開始する。"""
    if serial_bridge is None or not serial_bridge.get_status().get("connected"):
        return jsonify({"error": "Arduinoが接続されていません"}), 409
    if not serial_bridge.request_hardware_test():
        return jsonify({"error": "実機テストを開始できません。少し待って再度お試しください"}), 409
    return jsonify({"ok": True}), 202


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
    supplied_error = payload.get("error")
    error = None
    if not success and isinstance(supplied_error, str) and supplied_error.strip():
        error = {
            "code": "device_reported_failure",
            "title": "制御基板が排出失敗を通知しました",
            "detail": supplied_error.strip(),
        }
    result = finish_hardware_draw(reservation_id, success, error)
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


@app.route("/api/set_auto_probability", methods=["POST"])
def api_set_auto_probability():
    """在庫残数の比率をそのまま抽選確率にする機能を切り替える。"""
    payload = _json_payload()
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        abort(make_response(jsonify({"error": "invalid or missing field: enabled"}), 400))
    try:
        lottery.set_auto_probability_by_stock(enabled)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    settings["auto_probability_by_stock"] = enabled
    save_settings()
    prizes = lottery.get_status()
    socketio.emit("stock_updated", prizes)
    return jsonify({"enabled": enabled, "prizes": prizes})


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

    # サーバーを先に確実に起動し、それから通常ユーザーのEdgeを開く。
    # 内蔵WebViewは使わないため、画面側がサーバーを止めることもない。
    ui_connected.clear()
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    if not wait_until_server_ready(base_url):
        logger.error("内部サーバーの起動を確認できませんでした。")
        if serial_bridge is not None:
            serial_bridge.stop()
        return

    try:
        open_windows(base_url, settings)
    except OSError:
        logger.exception("Edgeのアプリ画面を開けなかったため通常表示へ切り替えます。")
        open_default_windows(base_url)

    def ensure_visible_window():
        # Edgeが起動要求を受け取ってもウィンドウを作らない環境がある。
        # 画面URLへのアクセスが無ければ、既定ブラウザーで確実に開き直す。
        if not ui_connected.wait(timeout=6):
            logger.warning("専用画面を確認できないため通常ブラウザーで開きます。")
            open_default_windows(base_url)

    threading.Thread(target=ensure_visible_window, daemon=True).start()
    try:
        server_thread.join()
    finally:
        if serial_bridge is not None:
            serial_bridge.stop()


if __name__ == "__main__":
    main()
