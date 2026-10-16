from app.desktop_launcher import DesktopApi, _parse_position


class FakeWindow:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def record_call():
            self.calls.append(name)

        return record_call


def test_parses_external_monitor_position():
    assert _parse_position("1920, 0") == (1920, 0)


def test_invalid_monitor_position_is_ignored():
    assert _parse_position("right screen") == (None, None)
    assert _parse_position(None) == (None, None)


def test_show_admin_leaves_fullscreen_and_brings_admin_forward():
    api = DesktopApi()
    api.game_window = FakeWindow()
    api.admin_window = FakeWindow()
    api.game_fullscreen = True

    assert api.show_admin() is True
    assert api.game_fullscreen is False
    assert api.game_window.calls == ["toggle_fullscreen"]
    assert api.admin_window.calls == ["show", "restore"]


def test_fullscreen_toggle_returns_current_state():
    api = DesktopApi()
    api.game_window = FakeWindow()

    assert api.toggle_game_fullscreen() == {"fullscreen": True}
    assert api.toggle_game_fullscreen() == {"fullscreen": False}
    assert api.game_window.calls == ["toggle_fullscreen", "toggle_fullscreen"]


def test_hide_game_returns_to_admin_first():
    api = DesktopApi()
    api.game_window = FakeWindow()
    api.admin_window = FakeWindow()
    api.game_fullscreen = True

    assert api.hide_game() is True
    assert api.game_window.calls == ["toggle_fullscreen", "hide"]
    assert api.admin_window.calls == ["show", "restore"]


def test_close_app_destroys_both_windows():
    api = DesktopApi()
    api.game_window = FakeWindow()
    api.admin_window = FakeWindow()

    assert api.close_app() is True
    assert api.shutting_down is True
    assert api.game_window.calls == ["destroy"]
    assert api.admin_window.calls == ["destroy"]
