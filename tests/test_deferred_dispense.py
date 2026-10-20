import json
import threading
from unittest import mock

import pytest

from app.lottery import Lottery
from app.presentation_gate import PresentationGate
from app.serial_bridge import SerialBridge


@pytest.fixture
def server(tmp_path, monkeypatch):
    from app import server

    prizes_path = tmp_path / "prizes.json"
    prizes_path.write_text(json.dumps([
        {"id": "atari", "name": "当たり", "probability": 1, "stock": 2, "hopper": "a"},
    ]), encoding="utf-8")
    monkeypatch.setattr(server, "lottery", Lottery(prizes_path, tmp_path / "stock.json"))
    monkeypatch.setattr(server, "presentation_gate", PresentationGate())
    monkeypatch.setattr(server, "last_admin_error", None)
    monkeypatch.setattr(server, "PRESENTATION_TIMEOUT_SECONDS", 2)
    monkeypatch.setattr(server, "serial_bridge", None)
    monkeypatch.setitem(server.settings, "servo_run_ms", {"a": 770, "b": 900})
    monkeypatch.setattr(server, "save_settings", mock.Mock())
    return server


class AckSerial:
    def __init__(self):
        self.written = []

    def write(self, message):
        self.written.append(message.decode())

    def readline(self):
        command = self.written[-1].split(":")
        assert command[0] == "DISPENSE"
        return f"DONE:{command[1]}\n".encode()


def make_bridge(server):
    bridge = SerialBridge(
        "COM_TEST", 115200,
        on_coin_inserted=server.handle_coin_inserted_from_serial,
        on_dispense_result=server.handle_serial_dispense_result,
        before_dispense=server.wait_for_presentation,
    )
    bridge._serial = AckSerial()
    return bridge


@pytest.mark.parametrize("coin_id", [None, "1"])
def test_only_dispenses_after_matching_animation_finishes(server, monkeypatch, coin_id):
    bridge = make_bridge(server)
    shown = threading.Event()
    events = []

    def emit(name, data):
        events.append((name, data))
        if name == "draw_result":
            shown.set()

    monkeypatch.setattr(server.socketio, "emit", emit)
    worker = threading.Thread(target=bridge._handle_coin, args=(coin_id,))
    worker.start()
    try:
        assert shown.wait(1)
        plan = next(data for name, data in events if name == "draw_result")
        assert plan["dispense_after_animation"] is True
        assert bridge._serial.written == (["NONE:1\n"] if coin_id else [])
        assert json.loads(server.lottery.stock_data_path.read_text())["atari"] == 2
        client = server.app.test_client()
        assert client.post("/api/demo_draw").status_code == 409
        assert client.post("/api/animation_finished", json={"reservation_id": "old"}).status_code == 409
        assert not any(line.startswith("DISPENSE:") for line in bridge._serial.written)
        assert client.post("/api/animation_finished", json={"reservation_id": plan["reservation_id"]}).status_code == 200
    finally:
        worker.join(3)
    assert not worker.is_alive()
    assert bridge._serial.written[-1] == f"DISPENSE:{plan['reservation_id']}~770:A\n"
    assert json.loads(server.lottery.stock_data_path.read_text())["atari"] == 1
    assert [name for name, _ in events].count("draw_result") == 1
    assert [name for name, _ in events].count("dispense_completed") == 1
    assert client.post("/api/animation_finished", json={"reservation_id": plan["reservation_id"]}).status_code == 409
    assert sum(line.startswith("DISPENSE:") for line in bridge._serial.written) == 1


def test_missing_animation_completion_cancels_without_dispensing(server, monkeypatch):
    monkeypatch.setattr(server, "PRESENTATION_TIMEOUT_SECONDS", 0)
    bridge = make_bridge(server)
    bridge._handle_coin("1")
    assert bridge._serial.written == ["NONE:1\n"]
    assert server.lottery.get_status()[0]["remaining"] == 2
    assert server.get_last_admin_error()["code"] == "presentation_timeout"


def test_remote_cannot_finish_animation_even_when_remote_admin_enabled(server, monkeypatch):
    monkeypatch.setitem(server.settings, "allow_remote_admin", True)
    response = server.app.test_client().post("/api/animation_finished", json={"reservation_id": "id"},
                                             environ_overrides={"REMOTE_ADDR": "192.168.1.50"})
    assert response.status_code == 403


def test_save_calibration_and_reject_invalid_duration(server):
    client = server.app.test_client()
    response = client.post("/api/set_servo_timing", json={"a": 800, "b": 750})
    assert response.status_code == 200
    assert server.servo_run_times() == {"a": 800, "b": 750}
    server.save_settings.assert_called_once()
    for bad in (0, 2001, True, "770", 770.5, None):
        assert client.post("/api/set_servo_timing", json={"a": bad, "b": 750}).status_code == 400
    assert server.servo_run_times() == {"a": 800, "b": 750}
