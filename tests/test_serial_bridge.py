import serial

from app import serial_bridge
from app.serial_bridge import SerialBridge


class FakeSerial:
    """readline() が決められた順に値を返し、尽きたら停止要求を出すニセのシリアルポート。"""

    def __init__(self, items, stop_event):
        self._items = list(items)
        self._stop_event = stop_event
        self.written = []

    def readline(self):
        if self._items:
            item = self._items.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        self._stop_event.set()
        return b""

    def write(self, data):
        self.written.append(data.decode("utf-8"))

    def close(self):
        pass


def test_callback_error_replies_none_and_keeps_running():
    calls = []

    def on_coin():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("想定外のエラー")
        return "a"

    bridge = SerialBridge("COM_TEST", 115200, on_coin, reconnect_interval=0)
    fake = FakeSerial([b"COIN\n", b"COIN\n"], bridge._stop_event)
    bridge._serial = fake

    bridge._run()

    # 1回目は例外 → NONE を返すが、スレッドは止まらず2回目も処理される
    assert fake.written == ["NONE\n", "DISPENSE:A\n"]


def test_reconnects_after_serial_error(monkeypatch):
    bridge = SerialBridge(
        "COM3",
        115200,
        lambda: "b",
        port_finder=lambda: "COM9",  # 抜き差しでポート名が変わった想定
        reconnect_interval=0,
    )
    first = FakeSerial([serial.SerialException("device disconnected")], bridge._stop_event)
    second = FakeSerial([b"COIN\n"], bridge._stop_event)
    opened_ports = []

    def fake_serial_factory(port, baudrate, timeout):
        opened_ports.append(port)
        return second

    monkeypatch.setattr(serial_bridge.serial, "Serial", fake_serial_factory)
    bridge._serial = first

    bridge._run()

    assert opened_ports == ["COM9"]
    assert bridge.port == "COM9"
    assert second.written == ["DISPENSE:B\n"]


def test_stop_during_reconnect_ends_the_loop(monkeypatch):
    bridge = SerialBridge("COM3", 115200, lambda: None, reconnect_interval=0)
    first = FakeSerial([serial.SerialException("gone")], bridge._stop_event)

    def always_fail(port, baudrate, timeout):
        bridge._stop_event.set()  # 再接続に失敗し続けている間に停止が要求された
        raise serial.SerialException("still gone")

    monkeypatch.setattr(serial_bridge.serial, "Serial", always_fail)
    bridge._serial = first

    bridge._run()  # 無限ループにならずに戻ってくること
