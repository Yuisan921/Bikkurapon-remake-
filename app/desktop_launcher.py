"""びっくらぽんをブラウザーではなくデスクトップアプリとして表示する。"""

import logging

logger = logging.getLogger(__name__)


def desktop_available():
    """pywebview を利用できるかを返す。

    開発環境などで未導入の場合は従来のブラウザー表示へ安全に戻せるよう、
    import はこのモジュールの読み込み時ではなく実行時に行う。
    """
    try:
        import webview  # noqa: F401
    except ImportError:
        return False
    return True


def _parse_position(value):
    """設定の ``"1920,0"`` を pywebview 用の座標へ変換する。"""
    if not isinstance(value, str):
        return None, None
    try:
        x, y = (int(part.strip()) for part in value.split(",", 1))
    except (TypeError, ValueError):
        return None, None
    return x, y


class DesktopApi:
    """画面内のナビゲーションから2つのウィンドウを操作するAPI。"""

    def __init__(self):
        self.game_window = None
        self.admin_window = None
        self.game_fullscreen = False
        self.shutting_down = False

    def _leave_game_fullscreen(self):
        if self.game_window is not None and self.game_fullscreen:
            self.game_window.toggle_fullscreen()
            self.game_fullscreen = False

    def show_game(self):
        if self.game_window is None:
            return False
        self.game_window.show()
        self.game_window.restore()
        return True

    def show_admin(self):
        if self.admin_window is None:
            return False
        # 管理画面がゲーム画面の裏へ隠れないよう、先に全画面を解除する。
        self._leave_game_fullscreen()
        self.admin_window.show()
        self.admin_window.restore()
        return True

    def toggle_game_fullscreen(self):
        if self.game_window is None:
            return {"fullscreen": False}
        self.game_window.toggle_fullscreen()
        self.game_fullscreen = not self.game_fullscreen
        return {"fullscreen": self.game_fullscreen}

    def get_window_state(self):
        return {"fullscreen": self.game_fullscreen}

    def hide_game(self):
        if self.game_window is None:
            return False
        self._leave_game_fullscreen()
        self.show_admin()
        self.game_window.hide()
        return True

    def close_app(self):
        """確認操作後に呼ばれ、ゲームと管理の両方を終了する。"""
        self.shutting_down = True
        if self.game_window is not None:
            self.game_window.destroy()
        if self.admin_window is not None:
            self.admin_window.destroy()
        return True


def launch_desktop_windows(base_url, settings):
    """ゲーム画面と管理画面を専用ウィンドウで開き、終了まで待つ。"""
    import webview

    api = DesktopApi()
    x, y = _parse_position(settings.get("kiosk_window_position"))

    # 最初に作ったウィンドウがアプリの親になるため、管理画面を先に作る。
    # 管理画面を閉じたときだけアプリ全体が終了する、分かりやすい動作になる。
    admin_window = webview.create_window(
        "びっくらぽん 管理",
        f"{base_url}/admin",
        width=1080,
        height=800,
        min_size=(760, 620),
        background_color="#f7f1e4",
        js_api=api,
    )
    api.admin_window = admin_window

    game_window = webview.create_window(
        "妖怪まつり びっくらぽん",
        base_url,
        width=1280,
        height=720,
        x=x,
        y=y,
        min_size=(800, 450),
        background_color="#073c43",
        js_api=api,
    )
    api.game_window = game_window

    def hide_game_instead_of_closing():
        # ゲーム画面を×で閉じても管理画面のボタンから戻せるようにする。
        if api.shutting_down:
            return None
        game_window.hide()
        return False

    def close_game_with_admin():
        api.shutting_down = True
        game_window.destroy()

    game_window.events.closing += hide_game_instead_of_closing
    admin_window.events.closing += close_game_with_admin

    def apply_startup_window_state():
        # kiosk_mode は旧設定との互換用。新規設定では game_fullscreen を使う。
        if settings.get("game_fullscreen", settings.get("kiosk_mode", False)):
            game_window.toggle_fullscreen()
            api.game_fullscreen = True

    logger.info("デスクトップ用のゲーム画面と管理画面を開きます。")
    webview.start(apply_startup_window_state, debug=False, private_mode=False)

