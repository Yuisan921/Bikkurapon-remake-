"""XIAO ESP32-C3とのUSBシリアル通信を担当するブリッジ。

ESP32から "COIN" という行を受け取ったらコールバックを呼び、その戻り値
(景品が使うホッパー記号 "a"/"b"、どちらも使わないなら None)に応じて
"DISPENSE:A" / "DISPENSE:B" または "NONE" を1行返す。
サーボの角度自体はESP32ファームウェア側の固定値で、サーバーは
「どちらのホッパーを動かすか」だけを伝える。プロトコルはこれだけの
シンプルなテキストベース。
"""

import logging
import threading

import serial
import serial.tools.list_ports

logger = logging.getLogger(__name__)

# XIAO ESP32-C3のUSB CDC(ネイティブUSBシリアル)によく見られる特徴。
# 環境によって表示のされ方が違うため、複数の手がかりで探す。
_ESPRESSIF_USB_VID = 0x303A
_KNOWN_DESCRIPTION_KEYWORDS = ("cp210", "ch340", "ch9102", "usb serial", "esp32")


def find_serial_port(warn=True):
    """接続されていそうなESP32のシリアルポートを推測する。見つからなければNone。

    warn=False にすると、見つからなかったときの警告ログを出さない
    (再接続の待機中に何度も呼ぶ場合にログが埋まらないようにするため)。
    """
    ports = list(serial.tools.list_ports.comports())

    for port in ports:
        if port.vid == _ESPRESSIF_USB_VID:
            return port.device

    for port in ports:
        description = (port.description or "").lower()
        if any(keyword in description for keyword in _KNOWN_DESCRIPTION_KEYWORDS):
            return port.device

    if warn:
        if ports:
            logger.warning(
                "ESP32らしきポートが見つかりませんでした。候補: %s",
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
        port_finder=None,
        reconnect_interval=2.0,
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
        self.port_finder = port_finder
        self.reconnect_interval = reconnect_interval
        self._serial = None
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        try:
            self._serial = serial.Serial(self.port, self.baudrate, timeout=1)
        except serial.SerialException as exc:
            logger.warning("シリアルポート %s を開けませんでした: %s", self.port, exc)
            return False

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("USBシリアルブリッジを開始しました(port=%s, baudrate=%s)", self.port, self.baudrate)
        return True

    def _run(self):
        while not self._stop_event.is_set():
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

            if line == "COIN":
                self._handle_coin()
            else:
                logger.debug("未知のシリアルメッセージ: %s", line)

    def _handle_coin(self):
        logger.info("USB経由でコイン投入を検知しました。")
        try:
            hopper = self.on_coin_inserted()
        except Exception:  # noqa: BLE001 - 想定外のエラーでも受信スレッドは止めない
            logger.exception(
                "コイン投入の処理中にエラーが発生しました(ホッパーは動かしません)。"
            )
            hopper = None
        self._respond(hopper)

    def _reconnect(self):
        """シリアルポートを開き直す。接続できたら True、停止要求で止まったら False。"""
        try:
            self._serial.close()
        except (serial.SerialException, OSError):
            pass

        while not self._stop_event.is_set():
            # stop() が呼ばれたらすぐ抜けられるよう、sleep ではなく wait で待つ
            if self._stop_event.wait(self.reconnect_interval):
                return False

            port = (self.port_finder() if self.port_finder else None) or self.port
            try:
                self._serial = serial.Serial(port, self.baudrate, timeout=1)
            except (serial.SerialException, OSError) as exc:
                logger.debug("再接続に失敗しました(%s): %s", port, exc)
                continue

            self.port = port
            logger.info("USBシリアルに再接続しました(port=%s)", port)
            return True
        return False

    def _respond(self, hopper):
        message = "NONE\n" if hopper is None else f"DISPENSE:{hopper.upper()}\n"
        try:
            self._serial.write(message.encode("utf-8"))
        except (serial.SerialException, OSError) as exc:
            logger.warning("シリアル書き込みエラー: %s", exc)

    def stop(self):
        self._stop_event.set()
        if self._serial is not None:
            self._serial.close()
