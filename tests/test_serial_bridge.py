import serial

from app import serial_bridge
from app.serial_bridge import SerialBridge


class FakeSerial:
    """readline()が決められた順に値を返すニセのシリアルポート。"""

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


def _plan(reservation_id="r1", hopper="a"):
    return {"reservation_id": reservation_id, "hopper": hopper}


def test_callback_error_replies_none_and_keeps_running():
    calls = []
    results = []

    def on_coin():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("想定外のエラー")
        return _plan("r2")

    bridge = SerialBridge(
        "COM_TEST",
        115200,
        on_coin,
        on_dispense_result=lambda reservation_id, success: results.append(
            (reservation_id, success)
        ),
        reconnect_interval=0,
        ack_timeout=0.1,
    )
    fake = FakeSerial([b"COIN:1\n", b"COIN:2\n", b"DONE:r2\n"], bridge._stop_event)
    bridge._serial = fake

    bridge._run()

    assert fake.written == ["NONE:1\n", "DISPENSE:2:r2:A\n"]
    assert results == [("r2", True)]


def test_initially_missing_device_is_detected_after_start(monkeypatch):
    bridge = SerialBridge(
        None,
        115200,
        lambda: _plan("r1"),
        on_dispense_result=lambda *_: None,
        port_finder=lambda: "COM9",
        reconnect_interval=0,
        ack_timeout=0.1,
    )
    connected = FakeSerial([b"COIN:7\n", b"DONE:r1\n"], bridge._stop_event)
    opened_ports = []

    def fake_serial_factory(port, baudrate, timeout):
        opened_ports.append(port)
        return connected

    monkeypatch.setattr(serial_bridge.serial, "Serial", fake_serial_factory)
    bridge._run()

    assert opened_ports == ["COM9"]
    assert connected.written == ["DISPENSE:7:r1:A\n"]


def test_reconnects_after_serial_error(monkeypatch):
    results = []
    bridge = SerialBridge(
        "COM3",
        115200,
        lambda: _plan("r2", "b"),
        on_dispense_result=lambda reservation_id, success: results.append(
            (reservation_id, success)
        ),
        port_finder=lambda: "COM9",
        reconnect_interval=0,
        ack_timeout=0.1,
    )
    first = FakeSerial([serial.SerialException("device disconnected")], bridge._stop_event)
    second = FakeSerial([b"COIN:2\n", b"DONE:r2\n"], bridge._stop_event)
    opened_ports = []

    def fake_serial_factory(port, baudrate, timeout):
        opened_ports.append(port)
        return second

    monkeypatch.setattr(serial_bridge.serial, "Serial", fake_serial_factory)
    bridge._serial = first
    bridge._run()

    assert opened_ports == ["COM9"]
    assert bridge.port == "COM9"
    assert second.written == ["DISPENSE:2:r2:B\n"]
    assert results == [("r2", True)]


def test_failed_ack_reports_failure():
    results = []
    bridge = SerialBridge(
        "COM3",
        115200,
        lambda: _plan("r3"),
        on_dispense_result=lambda reservation_id, success: results.append(
            (reservation_id, success)
        ),
        reconnect_interval=0,
        ack_timeout=0.1,
    )
    bridge._serial = FakeSerial([b"COIN:3\n", b"FAILED:r3\n"], bridge._stop_event)

    bridge._run()

    assert results == [("r3", False)]


def test_stop_during_reconnect_ends_the_loop(monkeypatch):
    bridge = SerialBridge(
        None,
        115200,
        lambda: None,
        port_finder=lambda: "COM3",
        reconnect_interval=0,
    )

    def always_fail(port, baudrate, timeout):
        bridge._stop_event.set()
        raise serial.SerialException("still gone")

    monkeypatch.setattr(serial_bridge.serial, "Serial", always_fail)
    bridge._run()
