from app import browser_launcher


def test_opens_edge_app_windows_without_browser_navigation(monkeypatch, tmp_path):
    launched = []
    monkeypatch.setattr(browser_launcher, "find_app_browser", lambda: "msedge.exe")
    monkeypatch.setattr(browser_launcher, "_profile_dir", lambda name: str(tmp_path / name))
    monkeypatch.setattr(
        browser_launcher.subprocess,
        "Popen",
        lambda args: launched.append(args),
    )

    browser_launcher.open_windows(
        "http://127.0.0.1:5000",
        {"auto_open_browser": True, "kiosk_mode": False},
    )

    assert len(launched) == 2
    assert "--app=http://127.0.0.1:5000/" in launched[0]
    assert "--autoplay-policy=no-user-gesture-required" in launched[0]
    assert "--app=http://127.0.0.1:5000/admin" in launched[1]
    assert "--autoplay-policy=no-user-gesture-required" not in launched[1]
    assert "--new-window" not in launched[0]


def test_kiosk_and_monitor_position_are_preserved(monkeypatch, tmp_path):
    launched = []
    monkeypatch.setattr(browser_launcher, "find_app_browser", lambda: "msedge.exe")
    monkeypatch.setattr(browser_launcher, "_profile_dir", lambda name: str(tmp_path / name))
    monkeypatch.setattr(
        browser_launcher.subprocess,
        "Popen",
        lambda args: launched.append(args),
    )

    browser_launcher.open_windows(
        "http://127.0.0.1:5000",
        {
            "auto_open_browser": True,
            "kiosk_mode": True,
            "kiosk_window_position": "1920,0",
        },
    )

    assert "--kiosk" in launched[0]
    assert "--window-position=1920,0" in launched[0]
