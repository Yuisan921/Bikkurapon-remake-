import serial
from types import SimpleNamespace

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
        on_dispense_result=lambda reservation_id, success, error: results.append(
            (reservation_id, success, error)
        ),
        reconnect_interval=0,
        ack_timeout=0.1,
    )
    fake = FakeSerial([b"COIN:1\n", b"COIN:2\n", b"DONE:r2\n"], bridge._stop_event)
    bridge._serial = fake

    bridge._run()

    assert fake.written == ["NONE:1\n", "DISPENSE:2:r2:A\n"]
    assert results == [("r2", True, None)]


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
        on_dispense_result=lambda reservation_id, success, error: results.append(
            (reservation_id, success, error)
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
    assert results == [("r2", True, None)]


def test_failed_ack_reports_failure():
    results = []
    bridge = SerialBridge(
        "COM3",
        115200,
        lambda: _plan("r3"),
        on_dispense_result=lambda reservation_id, success, error: results.append(
            (reservation_id, success, error)
        ),
        reconnect_interval=0,
        ack_timeout=0.1,
    )
    bridge._serial = FakeSerial([b"COIN:3\n", b"FAILED:r3\n"], bridge._stop_event)

    bridge._run()

    assert results[0][0:2] == ("r3", False)
    assert results[0][2]["code"] == "arduino_reported_failure"


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


def test_auto_detects_genuine_arduino_uno(monkeypatch):
    ports = [
        SimpleNamespace(device="COM8", vid=0x2341, description="Arduino Uno"),
    ]
    monkeypatch.setattr(serial_bridge.serial.tools.list_ports, "comports", lambda: ports)

    assert serial_bridge.find_serial_port() == "COM8"


def test_auto_detects_ch340_compatible_uno(monkeypatch):
    ports = [
        SimpleNamespace(device="COM5", vid=0x1A86, description="USB-SERIAL CH340"),
    ]
    monkeypatch.setattr(serial_bridge.serial.tools.list_ports, "comports", lambda: ports)

    assert serial_bridge.find_serial_port() == "COM5"


def test_status_changes_when_bridge_stops():
    bridge = SerialBridge("COM3", 115200, lambda: None)
    bridge._serial = FakeSerial([], bridge._stop_event)

    assert bridge.get_status()["connected"] is True
    bridge.stop()
    assert bridge.get_status()["connected"] is False


def test_reports_cds_brightness_from_uno():
    bridge = SerialBridge("COM3", 115200, lambda: None)
    bridge._serial = FakeSerial([b"SENSOR:CDS:812\n"], bridge._stop_event)

    bridge._run()

    assert bridge.get_status()["sensor"] == {
        "type": "cds",
        "baseline": 812,
        "ok": True,
    }


def test_warns_when_cds_is_too_dark():
    bridge = SerialBridge("COM3", 115200, lambda: None)
    bridge._serial = FakeSerial([b"SENSOR:CDS:90\n"], bridge._stop_event)

    bridge._run()

    assert bridge.get_status()["sensor"]["ok"] is False


def test_reports_firmware_version_from_uno():
    bridge = SerialBridge("COM3", 115200, lambda: None)
    bridge._serial = FakeSerial([b"FIRMWARE:2.7.2\n"], bridge._stop_event)

    bridge._run()

    assert bridge.get_status()["firmware_version"] == "2.7.2"


def test_reports_arduino_restart_during_dispense_as_power_problem():
    results = []
    bridge = SerialBridge(
        "COM3",
        115200,
        lambda: _plan("reset-during-servo", "b"),
        on_dispense_result=lambda reservation_id, success, error: results.append(
            (reservation_id, success, error)
        ),
        ack_timeout=0.1,
    )
    bridge._serial = FakeSerial(
        [b"COIN:4\n", b"FIRMWARE:2.7.2\n"], bridge._stop_event
    )

    bridge._run()

    assert results[0][0:2] == ("reset-during-servo", False)
    assert results[0][2]["code"] == "arduino_restarted_during_dispense"
    assert "外部5V電源" in results[0][2]["detail"]


def test_manual_servo_runs_only_while_control_is_active():
    bridge = SerialBridge("COM3", 115200, lambda: None)
    fake = FakeSerial([], bridge._stop_event)
    bridge._serial = fake

    assert bridge.set_manual_servo("a", True) is True
    assert bridge.get_status()["manual_hopper"] == "a"
    assert bridge.get_status()["busy"] is True
    assert bridge.request_hardware_test() is False
    assert bridge.set_manual_servo("a", True) is True  # keepalive
    assert bridge.set_manual_servo("a", False) is True

    assert bridge.get_status()["manual_hopper"] is None
    assert fake.written == [
        "MANUAL:A:START\n",
        "MANUAL:A:START\n",
        "MANUAL:A:STOP\n",
    ]


def test_manual_servo_automatically_stops_when_keepalive_expires():
    bridge = SerialBridge("COM3", 115200, lambda: None)
    fake = FakeSerial([], bridge._stop_event)
    bridge._serial = fake
    assert bridge.set_manual_servo("b", True) is True
    bridge._manual_deadline = 0

    bridge._stop_expired_manual_control()

    assert bridge.get_status()["manual_hopper"] is None
    assert fake.written[-1] == "MANUAL:B:STOP\n"


def test_hardware_test_uses_same_dispense_flow_as_coin():
    results = []
    bridge = SerialBridge(
        "COM3",
        115200,
        lambda: _plan("test-reservation", "b"),
        on_dispense_result=lambda reservation_id, success, error: results.append(
            (reservation_id, success, error)
        ),
        ack_timeout=0.1,
    )
    fake = FakeSerial([b"DONE:test-reservation\n"], bridge._stop_event)
    bridge._serial = fake

    assert bridge.request_hardware_test() is True
    bridge._run()

    assert fake.written == ["DISPENSE:test-reservation:B\n"]
    assert results == [("test-reservation", True, None)]
