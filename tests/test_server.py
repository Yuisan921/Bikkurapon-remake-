import json
import socket
from unittest import mock

import pytest

from app.lottery import Lottery


@pytest.fixture(scope="module")
def server_module():
    # 実機のESP32をつないだPCでテストしても触らないよう、検出を無効にする
    with mock.patch("app.serial_bridge.find_serial_port", return_value=None):
        from app import server

        return server


def _make_lottery(tmp_path, prizes):
    prizes_path = tmp_path / "prizes.json"
    prizes_path.write_text(json.dumps(prizes), encoding="utf-8")
    return Lottery(prizes_path, tmp_path / "stock.json")


@pytest.fixture
def server(server_module, tmp_path, monkeypatch):
    prizes = [
        {"id": "atari", "name": "当たり", "probability": 0.2, "stock": 1, "hopper": "a"},
        {"id": "hazure", "name": "はずれ", "probability": 0.8, "stock": 1, "hopper": "b"},
    ]
    monkeypatch.setattr(server_module, "lottery", _make_lottery(tmp_path, prizes))
    monkeypatch.setitem(server_module.settings, "allow_remote_admin", False)
    monkeypatch.setitem(server_module.settings, "allow_remote_insert_coin", False)
    monkeypatch.setitem(server_module.settings, "device_token", "test-device-token-1234")
    monkeypatch.setitem(server_module.settings, "auto_probability_by_stock", False)
    return server_module


def _event_names(socket_client):
    return [event["name"] for event in socket_client.get_received()]


def _use_up_stock(server):
    server.lottery.draw()
    server.lottery.draw()


def test_out_of_stock_returns_409_and_notifies_display(server):
    _use_up_stock(server)
    socket_client = server.socketio.test_client(server.app)
    socket_client.get_received()  # 接続直後のイベントを捨てる

    response = server.app.test_client().post("/api/insert_coin")

    assert response.status_code == 409
    assert response.get_json() == {"error": "out_of_stock"}
    names = _event_names(socket_client)
    assert "out_of_stock" in names
    assert "draw_result" not in names


def test_serial_coin_when_out_of_stock_moves_no_hopper(server):
    _use_up_stock(server)

    assert server.handle_coin_inserted_from_serial() is None


def test_serial_coin_commits_only_after_successful_ack(server):
    socket_client = server.socketio.test_client(server.app)
    socket_client.get_received()

    plan = server.handle_coin_inserted_from_serial()

    assert plan["hopper"] in ("a", "b")
    assert "draw_result" not in _event_names(socket_client)
    persisted_before = json.loads(server.lottery.stock_data_path.read_text(encoding="utf-8"))
    assert sum(persisted_before.values()) == 2

    result = server.finish_hardware_draw(plan["reservation_id"], True)

    assert result is not None
    assert "draw_result" in _event_names(socket_client)
    persisted_after = json.loads(server.lottery.stock_data_path.read_text(encoding="utf-8"))
    assert sum(persisted_after.values()) == 1


def test_serial_failed_ack_cancels_without_decrement(server):
    plan = server.handle_coin_inserted_from_serial()

    assert server.finish_hardware_draw(plan["reservation_id"], False) is None
    persisted = json.loads(server.lottery.stock_data_path.read_text(encoding="utf-8"))
    assert sum(persisted.values()) == 2


def test_normal_draw_broadcasts_result(server):
    socket_client = server.socketio.test_client(server.app)
    socket_client.get_received()

    response = server.app.test_client().post("/api/insert_coin")

    assert response.status_code == 200
    names = _event_names(socket_client)
    assert "draw_started" in names
    assert "draw_result" in names


def test_preview_result_does_not_change_stock(server):
    socket_client = server.socketio.test_client(server.app)
    socket_client.get_received()
    before = server.lottery.get_status()

    response = server.app.test_client().post(
        "/api/preview_result", json={"prize_id": "atari"}
    )

    assert response.status_code == 200
    assert server.lottery.get_status() == before
    names = _event_names(socket_client)
    assert "draw_started" in names
    assert "draw_result" in names


def test_demo_draw_uses_probability_without_stock_or_hardware(server):
    socket_client = server.socketio.test_client(server.app)
    socket_client.get_received()
    before = server.lottery.stock_data_path.read_text(encoding="utf-8")

    response = server.app.test_client().post("/api/demo_draw")

    assert response.status_code == 200
    assert response.get_json()["preview"] is True
    assert server.lottery.stock_data_path.read_text(encoding="utf-8") == before
    names = _event_names(socket_client)
    assert "draw_started" in names
    assert "draw_result" in names
    assert "stock_updated" not in names


def test_system_status_reports_hardware_connection(server, monkeypatch):
    bridge = mock.Mock()
    bridge.get_status.return_value = {
        "enabled": True,
        "connected": True,
        "port": "COM4",
    }
    monkeypatch.setattr(server, "serial_bridge", bridge)

    response = server.app.test_client().get("/api/system_status")

    assert response.status_code == 200
    assert response.get_json()["hardware"]["port"] == "COM4"
    assert response.get_json()["hardware"]["connected"] is True
    assert response.get_json()["auto_probability_by_stock"] is False


def test_hardware_test_requires_connection(server, monkeypatch):
    monkeypatch.setattr(server, "serial_bridge", None)

    response = server.app.test_client().post("/api/hardware_test")

    assert response.status_code == 409
    assert "Arduino" in response.get_json()["error"]


def test_hardware_test_requests_real_dispense(server, monkeypatch):
    bridge = mock.Mock()
    bridge.get_status.return_value = {"connected": True}
    bridge.request_hardware_test.return_value = True
    monkeypatch.setattr(server, "serial_bridge", bridge)

    response = server.app.test_client().post("/api/hardware_test")

    assert response.status_code == 202
    bridge.request_hardware_test.assert_called_once_with()


def test_auto_probability_toggle_updates_probabilities(server, monkeypatch):
    monkeypatch.setattr(server, "save_settings", mock.Mock())

    response = server.app.test_client().post(
        "/api/set_auto_probability", json={"enabled": True}
    )

    assert response.status_code == 200
    assert response.get_json()["enabled"] is True
    assert [item["probability"] for item in response.get_json()["prizes"]] == [0.5, 0.5]
    assert server.settings["auto_probability_by_stock"] is True


REMOTE = {"REMOTE_ADDR": "192.168.0.50"}


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/set_stock", {"prize_id": "atari", "amount": 99}),
        ("/api/restock", {"prize_id": "atari", "amount": 1}),
        ("/api/set_probability", {"prize_id": "atari", "probability": 1.0}),
        ("/api/set_auto_probability", {"enabled": True}),
    ],
)
def test_remote_cannot_change_stock_or_probability_by_default(server, path, body):
    response = server.app.test_client().post(path, json=body, environ_overrides=REMOTE)

    assert response.status_code == 403
    assert server.lottery.get_status()[0]["remaining"] == 1  # 変更されていない


def test_remote_cannot_open_admin_page_or_insert_coin_by_default(server):
    client = server.app.test_client()

    assert client.get("/admin", environ_overrides=REMOTE).status_code == 403
    assert client.post("/api/insert_coin", environ_overrides=REMOTE).status_code == 403
    assert server.lottery.get_status()[0]["remaining"] == 1  # 抽選も走っていない


@pytest.mark.parametrize(
    "path", ["/api/system_status", "/api/preview_result", "/api/demo_draw", "/api/hardware_test"]
)
def test_remote_cannot_use_new_admin_endpoints_by_default(server, path):
    client = server.app.test_client()
    response = (
        client.get(path, environ_overrides=REMOTE)
        if path.endswith("system_status")
        else client.post(path, json={"prize_id": "atari"}, environ_overrides=REMOTE)
    )
    assert response.status_code == 403


def test_remote_can_still_read_status_and_view_display(server):
    client = server.app.test_client()

    assert client.get("/api/status", environ_overrides=REMOTE).status_code == 200
    assert client.get("/", environ_overrides=REMOTE).status_code == 200


def test_pages_load_socket_io_from_local_static_asset(server):
    client = server.app.test_client()

    index_html = client.get("/").get_data(as_text=True)
    admin_html = client.get("/admin").get_data(as_text=True)

    assert "cdn.socket.io" not in index_html
    assert "cdn.socket.io" not in admin_html
    assert "/static/vendor/socket.io.min.js" in index_html
    assert client.get("/static/vendor/socket.io.min.js").status_code == 200


def test_remote_admin_allowed_when_enabled(server, monkeypatch):
    monkeypatch.setitem(server.settings, "allow_remote_admin", True)

    response = server.app.test_client().post(
        "/api/set_stock", json={"prize_id": "atari", "amount": 5}, environ_overrides=REMOTE
    )

    assert response.status_code == 200
    assert response.get_json()["remaining"] == 5


def test_remote_insert_coin_requires_device_token(server, monkeypatch):
    monkeypatch.setitem(server.settings, "allow_remote_insert_coin", True)
    client = server.app.test_client()

    assert client.post("/api/insert_coin", environ_overrides=REMOTE).status_code == 403
    assert client.post(
        "/api/insert_coin",
        headers={"X-Bikkurapon-Token": "wrong-device-token"},
        environ_overrides=REMOTE,
    ).status_code == 403


def test_remote_wifi_draw_commits_only_after_authenticated_ack(server, monkeypatch):
    monkeypatch.setitem(server.settings, "allow_remote_insert_coin", True)
    headers = {"X-Bikkurapon-Token": "test-device-token-1234"}
    socket_client = server.socketio.test_client(server.app)
    socket_client.get_received()

    response = server.app.test_client().post(
        "/api/insert_coin", headers=headers, environ_overrides=REMOTE
    )

    assert response.status_code == 200
    plan = response.get_json()
    assert plan["reservation_id"]
    assert "draw_result" not in _event_names(socket_client)

    ack = server.app.test_client().post(
        "/api/dispense_ack",
        json={"reservation_id": plan["reservation_id"], "success": True},
        headers=headers,
        environ_overrides=REMOTE,
    )

    assert ack.status_code == 200
    assert "draw_result" in _event_names(socket_client)


def test_remote_failed_dispense_ack_does_not_decrement(server, monkeypatch):
    monkeypatch.setitem(server.settings, "allow_remote_insert_coin", True)
    headers = {"X-Bikkurapon-Token": "test-device-token-1234"}
    client = server.app.test_client()
    plan = client.post(
        "/api/insert_coin", headers=headers, environ_overrides=REMOTE
    ).get_json()

    response = client.post(
        "/api/dispense_ack",
        json={"reservation_id": plan["reservation_id"], "success": False},
        headers=headers,
        environ_overrides=REMOTE,
    )

    assert response.status_code == 409
    persisted = json.loads(server.lottery.stock_data_path.read_text(encoding="utf-8"))
    assert sum(persisted.values()) == 2


def test_local_requests_always_allowed(server):
    client = server.app.test_client()  # 既定の接続元は 127.0.0.1

    assert client.get("/admin").status_code == 200
    response = client.post("/api/set_stock", json={"prize_id": "atari", "amount": 3})
    assert response.status_code == 200


@pytest.mark.parametrize(
    "path,body",
    [
        ("/api/set_stock", {"prize_id": "atari", "amount": "たくさん"}),
        ("/api/set_stock", {"prize_id": "atari"}),
        ("/api/restock", {"amount": 1}),
        ("/api/set_probability", {"prize_id": "atari", "probability": "abc"}),
        ("/api/set_probability", {"prize_id": "atari", "probability": -1}),
    ],
)
def test_invalid_input_returns_400_not_500(server, path, body):
    response = server.app.test_client().post(path, json=body)

    assert response.status_code == 400


def test_unknown_prize_returns_404(server):
    response = server.app.test_client().post(
        "/api/set_stock", json={"prize_id": "nope", "amount": 1}
    )

    assert response.status_code == 404


def test_finds_another_port_when_preferred_port_is_in_use(server_module):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", 0))
        preferred_port = occupied.getsockname()[1]

        selected = server_module.find_available_port(
            "127.0.0.1", preferred_port, attempts=20
        )

    assert selected is not None
    assert selected != preferred_port
