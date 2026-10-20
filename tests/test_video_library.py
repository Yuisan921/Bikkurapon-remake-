from urllib.parse import unquote

from tests.test_server import server, server_module  # noqa: F401 - shared isolated fixtures


def make_video_folders(root):
    (root / "atari").mkdir()
    (root / "hazure").mkdir()


def test_selects_only_supported_video_from_matching_result_folder(server, tmp_path, monkeypatch):
    make_video_folders(tmp_path)
    (tmp_path / "atari" / "one.mp4").write_bytes(b"one")
    (tmp_path / "atari" / "当たり二.webm").write_bytes(b"two")
    (tmp_path / "atari" / "ignore.txt").write_text("ignore", encoding="utf-8")
    (tmp_path / "hazure" / "lose.mp4").write_bytes(b"lose")
    monkeypatch.setattr(server, "VIDEO_DIR", tmp_path)
    monkeypatch.setattr(server.random, "choice", lambda candidates: candidates[-1])

    winner = server.select_result_video({"id": "atari", "hopper": "a", "video": "/old.mp4"})
    loser = server.select_result_video({"id": "hazure", "hopper": "b", "video": "/old.mp4"})

    assert unquote(winner["video"]) == "/media/atari/当たり二.webm"
    assert unquote(loser["video"]) == "/media/hazure/lose.mp4"
    assert server.video_library_status() == {
        "path": str(tmp_path),
        "atari": 2,
        "hazure": 1,
    }


def test_keeps_existing_single_video_setting_when_folder_is_empty(server, tmp_path, monkeypatch):
    make_video_folders(tmp_path)
    monkeypatch.setattr(server, "VIDEO_DIR", tmp_path)

    result = server.select_result_video({
        "id": "atari",
        "hopper": "a",
        "video": "/media/atari.mp4",
    })

    assert result["video"] == "/media/atari.mp4"


def test_preview_uses_requested_result_folder(server, tmp_path, monkeypatch):
    make_video_folders(tmp_path)
    (tmp_path / "atari" / "winner.mp4").write_bytes(b"winner")
    (tmp_path / "hazure" / "loser.mp4").write_bytes(b"loser")
    monkeypatch.setattr(server, "VIDEO_DIR", tmp_path)
    socket_client = server.socketio.test_client(server.app)
    socket_client.get_received()

    response = server.app.test_client().post("/api/preview_result", json={"prize_id": "hazure"})

    assert response.status_code == 200
    event = next(item for item in socket_client.get_received() if item["name"] == "draw_result")
    assert event["args"][0]["video"] == "/media/hazure/loser.mp4"


def test_open_video_folder_is_local_only(server, tmp_path, monkeypatch):
    make_video_folders(tmp_path)
    monkeypatch.setattr(server, "VIDEO_DIR", tmp_path)
    launched = []
    monkeypatch.setattr(server.sys, "platform", "linux")
    monkeypatch.setattr(server.subprocess, "Popen", lambda command: launched.append(command))
    monkeypatch.setitem(server.settings, "allow_remote_admin", True)
    client = server.app.test_client()

    assert client.post("/api/open_video_folder").status_code == 200
    assert launched == [["xdg-open", str(tmp_path)]]
    remote = client.post(
        "/api/open_video_folder",
        environ_overrides={"REMOTE_ADDR": "192.168.1.50"},
    )
    assert remote.status_code == 403
