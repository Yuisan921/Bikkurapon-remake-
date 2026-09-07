"""XIAO ESP32-C3とのUSBシリアル通信を担当するブリッジ。

ESP32から "COIN" という行を受け取ったらコールバックを呼び、その戻り値
(サーボ角度、なければNone)に応じて "DISPENSE:<角度>" または "NONE" を
1行返す。プロトコルはこれだけのシンプルなテキストベース。
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


def find_serial_port():
    """接続されていそうなESP32のシリアルポートを推測する。見つからなければNone。"""
    ports = list(serial.tools.list_ports.comports())

    for port in ports:
        if port.vid == _ESPRESSIF_USB_VID:
            return port.device

    for port in ports:
        description = (port.description or "").lower()
        if any(keyword in description for keyword in _KNOWN_DESCRIPTION_KEYWORDS):
            return port.device

    if ports:
        logger.warning(
            "ESP32らしきポートが見つかりませんでした。候補: %s",
            ", ".join(p.device for p in ports),
        )
    else:
        logger.warning("シリアルポートが1つも見つかりませんでした。")
    return None


class SerialBridge:
    def __init__(self, port, baudrate, on_coin_inserted):
        self.port = port
        self.baudrate = baudrate
        self.on_coin_inserted = on_coin_inserted
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
            except serial.SerialException as exc:
                logger.warning("シリアル読み取りエラー: %s", exc)
                break

            line = raw_line.decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            if line == "COIN":
                logger.info("USB経由でコイン投入を検知しました。")
                servo_angle = self.on_coin_inserted()
                self._respond(servo_angle)
            else:
                logger.debug("未知のシリアルメッセージ: %s", line)

    def _respond(self, servo_angle):
        message = "NONE\n" if servo_angle is None else f"DISPENSE:{servo_angle}\n"
        try:
            self._serial.write(message.encode("utf-8"))
        except serial.SerialException as exc:
            logger.warning("シリアル書き込みエラー: %s", exc)

    def stop(self):
        self._stop_event.set()
        if self._serial is not None:
            self._serial.close()
