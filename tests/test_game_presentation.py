"""Browser-to-serial regression checks (run when Playwright/Chromium is installed)."""

import shutil
import threading
import time
import json
from unittest import mock

import pytest
from flask_socketio import SocketIO
from werkzeug.serving import make_server

from app.lottery import Lottery
from app.presentation_gate import PresentationGate
from tests.test_deferred_dispense import make_bridge


@pytest.fixture
def presentation_server(tmp_path, monkeypatch):
    from app import server

    prizes_path = tmp_path / "prizes.json"
    prizes_path.write_text(json.dumps([
        {"id": "atari", "name": "当たり", "probability": 1, "stock": 2, "hopper": "a"},
    ]), encoding="utf-8")
    monkeypatch.setattr(server, "lottery", Lottery(prizes_path, tmp_path / "stock.json"))
    monkeypatch.setattr(server, "presentation_gate", PresentationGate())
    monkeypatch.setattr(server, "last_admin_error", None)
    monkeypatch.setattr(server, "PRESENTATION_TIMEOUT_SECONDS", 20)
    monkeypatch.setattr(server, "serial_bridge", None)
    monkeypatch.setitem(server.settings, "servo_run_ms", {"a": 770, "b": 900})
    monkeypatch.setattr(server, "save_settings", mock.Mock())
    # Use a fresh event bus so in-process API clients from other test modules
    # cannot affect delivery to the real Chromium client.
    monkeypatch.setattr(server, "socketio", SocketIO(server.app, cors_allowed_origins="*"))
    return server


@pytest.fixture
def display(presentation_server, monkeypatch):
    server = presentation_server
    playwright = pytest.importorskip("playwright.sync_api")
    chromium = shutil.which("chromium")
    if not chromium:
        pytest.skip("Chromium browser is not installed")
    bridge = make_bridge(server)
    monkeypatch.setattr(server, "PRESENTATION_TIMEOUT_SECONDS", 20)
    monkeypatch.setattr(server, "serial_bridge", bridge)
    http = make_server("127.0.0.1", 0, server.app, threaded=True)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chromium, args=["--no-sandbox"])
        page = browser.new_page()
        page.goto(f"http://127.0.0.1:{http.server_port}/", wait_until="networkidle")
        yield page, bridge
        browser.close()
    http.shutdown()
    thread.join(2)


def test_fallback_result_finishes_before_hopper_moves(display):
    page, bridge = display
    worker = threading.Thread(target=bridge._handle_coin, daemon=True)
    worker.start()
    page.locator("#playing-screen").wait_for(state="visible")
    assert bridge._serial.written == []
    page.locator("#result-screen").wait_for(state="visible")
    assert bridge._serial.written == []
    page.wait_for_function("document.getElementById('result-message').textContent === 'カプセルを受け取ってね！'", timeout=15000)
    worker.join(2)
    assert sum(line.startswith("DISPENSE:") for line in bridge._serial.written) == 1


def test_video_end_event_triggers_dispense_only_once(presentation_server, display):
    server = presentation_server
    page, bridge = display
    server.lottery._prizes[0]["video"] = "/test-video.mp4"
    # Model a playing video whose duration exceeds the standard result timer.
    page.evaluate("""() => {
      const video = document.getElementById('result-video');
      video.load = () => {};
      video.play = () => Promise.resolve();
      video.pause = () => {};
      video.setAttribute = () => {};
      Object.defineProperty(video, 'src', {set: () => {}});
    }""")
    started_at = time.monotonic()
    worker = threading.Thread(target=bridge._handle_coin, daemon=True)
    worker.start()
    page.locator("#video-screen").wait_for(state="visible", timeout=1500)
    assert time.monotonic() - started_at < 1.5
    page.wait_for_timeout(5500)
    assert bridge._serial.written == []
    page.evaluate("document.getElementById('result-video').dispatchEvent(new Event('ended'))")
    page.wait_for_function("document.getElementById('result-message').textContent === 'カプセルを受け取ってね！'")
    page.evaluate("document.getElementById('result-video').dispatchEvent(new Event('ended'))")
    worker.join(2)
    assert sum(line.startswith("DISPENSE:") for line in bridge._serial.written) == 1
