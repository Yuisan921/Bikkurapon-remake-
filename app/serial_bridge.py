"""Arduino Uno / XIAO ESP32-C3とのUSBシリアル通信を担当するブリッジ。

ESP32から "COIN" という行を受け取ったらコールバックを呼び、その戻り値
(景品が使うホッパー記号 "a"/"b"、どちらも使わないなら None)に応じて
"DISPENSE:A" / "DISPENSE:B" または "NONE" を1行返す。
サーボの角度自体はESP32ファームウェア側の固定値で、サーバーは
「どちらのホッパーを動かすか」だけを伝える。プロトコルはこれだけの
シンプルなテキストベース。
"""

import logging
import threading
import time

import serial
import serial.tools.list_ports

logger = logging.getLogger(__name__)

# Arduino Uno R3、互換機、XIAO ESP32-C3によく見られる特徴。
# 純正Unoと互換UnoではUSBチップが異なるため、複数の手がかりで探す。
_KNOWN_USB_VIDS = {0x2341, 0x2A03, 0x303A}
_KNOWN_DESCRIPTION_KEYWORDS = (
    "arduino",
    "usb serial",
    "usb-serial",
    "cp210",
    "ch340",
    "ch9102",
    "esp32",
)


def find_serial_port(warn=True):
    """接続されていそうな制御基板のポートを推測する。見つからなければNone。

    warn=False にすると、見つからなかったときの警告ログを出さない
    (再接続の待機中に何度も呼ぶ場合にログが埋まらないようにするため)。
    """
    ports = list(serial.tools.list_ports.comports())

    for port in ports:
        if port.vid in _KNOWN_USB_VIDS:
            return port.device

    for port in ports:
        description = (port.description or "").lower()
        if any(keyword in description for keyword in _KNOWN_DESCRIPTION_KEYWORDS):
            return port.device

    if warn:
        if ports:
            logger.warning(
                "Arduino/ESP32らしきポートが見つかりませんでした。候補: %s",
                ", ".join(p.device for p in ports),
            )
        else:
            logger.warning("シリアルポートが1つも見つかりませんでした。")
    return None


class SerialBridge:
    def __init__(
        self,
        port,
        baudrate,
        on_coin_inserted,
        on_dispense_result=None,
        port_finder=None,
        reconnect_interval=2.0,
        ack_timeout=5.0,
    ):
        """
        port_finder: 再接続のときにポートを探し直す関数(任意)。USBを抜き差しすると
            COM3 → COM4 のようにポート名が変わることがあるため。見つからなければ
            元の port で再試行する。
        reconnect_interval: 再接続を試す間隔(秒)。
        """
        self.port = port
        self.baudrate = baudrate
        self.on_coin_inserted = on_coin_inserted
        self.on_dispense_result = on_dispense_result
        self.port_finder = port_finder
        self.reconnect_interval = reconnect_interval
        self.ack_timeout = ack_timeout
        self._serial = None
        self._stop_event = threading.Event()
        self._test_requested = threading.Event()
        self._draw_in_progress = threading.Event()
        self._thread = None

    def get_status(self):
        """管理画面に表示するUSB接続状態を返す。"""
        return {
            "enabled": True,
            "connected": self._serial is not None,
            "port": self.port,
            "busy": self._draw_in_progress.is_set() or self._test_requested.is_set(),
        }

    def start(self):
        if self.port:
            try:
                self._serial = serial.Serial(self.port, self.baudrate, timeout=1)
            except (serial.SerialException, OSError) as exc:
                logger.warning(
                    "シリアルポート %s を開けませんでした: %s。接続を待ちます。",
                    self.port,
                    exc,
                )
                self._serial = None
        else:
            logger.info("ESP32のUSB接続を待っています。後から挿しても自動認識します。")

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if self._serial is not None:
            logger.info(
                "USBシリアルブリッジを開始しました(port=%s, baudrate=%s)",
                self.port,
                self.baudrate,
            )
        return True

    def _run(self):
        while not self._stop_event.is_set():
            if self._serial is None:
                if not self._reconnect():
                    break
                continue
            if self._test_requested.is_set():
                self._draw_in_progress.set()
                self._test_requested.clear()
                try:
                    self._handle_coin()
                finally:
                    self._draw_in_progress.clear()
                continue
            try:
                raw_line = self._serial.readline()
            except (serial.SerialException, OSError) as exc:
                # USBケーブルが一瞬抜けた等。スレッドを終わらせず、つなぎ直す。
                logger.warning("シリアル読み取りエラー: %s。再接続を試みます。", exc)
                if not self._reconnect():
                    break
                continue

            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            if line == "COIN" or line.startswith("COIN:"):
                coin_id = line.partition(":")[2] or None
                self._draw_in_progress.set()
                try:
                    self._handle_coin(coin_id)
                finally:
                    self._draw_in_progress.clear()
            else:
                logger.debug("未知のシリアルメッセージ: %s", line)

    def request_hardware_test(self):
        """管理画面から、本物のコイン投入と同じ排出処理を1回予約する。"""
        if self._serial is None or self._stop_event.is_set():
            return False
        if self._test_requested.is_set() or self._draw_in_progress.is_set():
            return False
        self._test_requested.set()
        return True

    def _handle_coin(self, coin_id=None):
        logger.info("USB経由でコイン投入を検知しました。")
        try:
            plan = self.on_coin_inserted()
        except Exception:  # noqa: BLE001 - 想定外のエラーでも受信スレッドは止めない
            logger.exception(
                "コイン投入の処理中にエラーが発生しました(ホッパーは動かしません)。"
            )
            plan = None

        if not plan or not plan.get("hopper"):
            self._write_response(f"NONE:{coin_id}\n" if coin_id else "NONE\n")
            return

        reservation_id = plan["reservation_id"]
        hopper = str(plan["hopper"]).upper()
        if coin_id:
            message = f"DISPENSE:{coin_id}:{reservation_id}:{hopper}\n"
        else:
            message = f"DISPENSE:{reservation_id}:{hopper}\n"

        if not self._write_response(message):
            self._finish_dispense(
                reservation_id,
                False,
                {
                    "code": "usb_write_failed",
                    "title": "Arduinoへ命令を送れませんでした",
                    "detail": f"ホッパー{hopper}の排出命令を送信できませんでした。USBケーブルとCOMポートを確認してください。",
                },
            )
            self._serial = None
            return

        success, error = self._wait_for_ack(reservation_id, hopper)
        self._finish_dispense(reservation_id, success, error)
        if not success and self._serial is None:
            logger.warning("排出確認中にUSB接続が切れました。再接続を待ちます。")

    def _finish_dispense(self, reservation_id, success, error=None):
        if self.on_dispense_result is None:
            return
        try:
            self.on_dispense_result(reservation_id, success, error)
        except Exception:  # noqa: BLE001 - ACK処理失敗で受信スレッドを止めない
            logger.exception("排出結果の確定処理に失敗しました(reservation=%s)", reservation_id)

    def _wait_for_ack(self, reservation_id, hopper):
        """Unoがサーボを動かし終えるまで待ち、失敗時は管理者向け理由も返す。"""
        deadline = time.monotonic() + self.ack_timeout
        expected_done = f"DONE:{reservation_id}"
        expected_failed = f"FAILED:{reservation_id}"
        while not self._stop_event.is_set() and time.monotonic() < deadline:
            try:
                line = self._serial.readline().decode("utf-8", errors="ignore").strip()
            except (serial.SerialException, OSError) as exc:
                logger.warning("排出確認中のシリアルエラー: %s", exc)
                self._serial = None
                return False, {
                    "code": "usb_disconnected",
                    "title": "排出中にUSB接続が切れました",
                    "detail": f"ホッパー{hopper}の動作完了を待っている途中でArduinoとの通信が切れました。USBケーブルとサーボ電源を確認してください。",
                }
            if line == expected_done:
                return True, None
            if line == expected_failed:
                return False, {
                    "code": "arduino_reported_failure",
                    "title": "Arduinoが排出失敗を通知しました",
                    "detail": f"ホッパー{hopper}を正常に動かせませんでした。カプセル詰まり、サーボ配線、外部5V電源を確認してください。",
                }
            if line:
                logger.debug("排出確認中のメッセージ: %s", line)
        logger.warning("ESP32から排出完了ACKが届きませんでした(reservation=%s)", reservation_id)
        return False, {
            "code": "ack_timeout",
            "title": "排出完了を確認できませんでした",
            "detail": f"ホッパー{hopper}へ命令を送りましたが、{self.ack_timeout:g}秒以内にArduinoから完了通知が届きませんでした。USB接続、サーボ電源、カプセル詰まりを確認してください。",
        }

    def _reconnect(self):
        """シリアルポートを開き直す。接続できたら True、停止要求で止まったら False。"""
        if self._serial is not None:
            try:
                self._serial.close()
            except (serial.SerialException, OSError):
                pass
        self._serial = None

        while not self._stop_event.is_set():
            try:
                discovered_port = self.port_finder() if self.port_finder else None
            except (OSError, serial.SerialException) as exc:
                logger.debug("シリアルポート探索に失敗しました: %s", exc)
                discovered_port = None
            port = discovered_port or self.port
            if not port:
                if self._stop_event.wait(self.reconnect_interval):
                    return False
                continue
            try:
                self._serial = serial.Serial(port, self.baudrate, timeout=1)
            except (serial.SerialException, OSError) as exc:
                logger.debug("再接続に失敗しました(%s): %s", port, exc)
                if self._stop_event.wait(self.reconnect_interval):
                    return False
                continue

            self.port = port
            logger.info("USBシリアルに再接続しました(port=%s)", port)
            return True
        return False

    def _write_response(self, message):
        try:
            self._serial.write(message.encode("utf-8"))
            return True
        except (serial.SerialException, OSError) as exc:
            logger.warning("シリアル書き込みエラー: %s", exc)
            return False

    def stop(self):
        self._stop_event.set()
        if self._serial is not None:
            try:
                self._serial.close()
            except (serial.SerialException, OSError):
                pass
            self._serial = None
