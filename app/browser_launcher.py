"""起動時にブラウザで演出画面・管理画面を自動的に開くための処理。

これまでは scripts/start_bikkurapon.bat がこの役割を持っていたが、
実行環境によっては(例: Windowsのユーザー名が非ASCII文字を含む場合)
バッチファイルの文字コード関連の不具合で正しく動かないことがあるため、
.exe自身がPythonの中でブラウザを起動する形に変更した。
"""

import logging
import shutil
import subprocess
import tempfile
import threading
import time
import webbrowser
from pathlib import Path

logger = logging.getLogger(__name__)

# Windowsでよくある Chrome のインストール先
_WINDOWS_CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_chrome():
    """Chrome/Chromiumの実行ファイルパスを探す。見つからなければNone。"""
    for name in ("chrome", "google-chrome", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path

    for candidate in _WINDOWS_CHROME_CANDIDATES:
        if Path(candidate).exists():
            return candidate

    return None


def _profile_dir(name):
    """演出画面/管理画面それぞれ専用のChromeプロファイル置き場。

    同じプロファイル(=同じChromeプロセス)を共有すると、Chromeが2つ目
    以降のウィンドウを「既存プロセスへの新規ウィンドウ要求」として扱い、
    --kioskや--window-sizeなどのウィンドウ固有フラグを無視したり、
    片方のフルスクリーン状態がもう片方にも伝染したりすることがある。
    プロファイルディレクトリを分けることで、2つを完全に別プロセスとして
    独立させ、それぞれが自分に指定したフラグどおりに開くようにする。
    """
    path = Path(tempfile.gettempdir()) / "bikkurapon-chrome-profile" / name
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def open_windows(base_url, settings):
    """演出画面と管理画面を、別々のウィンドウ(別プロセス)として開く。

    settings は config/settings.json の内容。auto_open_browser が false なら
    何もしない。

    - kiosk_mode が true の場合だけ、演出画面を枠なし(タイトルバーなし)の
      キオスクモードで開く。文化祭当日、外部モニターにフルスクリーン表示
      する時用。既定は false(普通のウィンドウ)で、これはタイトルバーが
      あるのでドラッグして動かせる。1台のモニターでテストする時は
      false のままの方が扱いやすい
    - kiosk_window_position("1920,0" のような文字列)が設定されていれば、
      演出画面をその座標(=外部モニター)に表示する。kiosk_mode が false でも
      通常ウィンドウの初期位置として使われる
    """
    if not settings.get("auto_open_browser", True):
        return

    chrome = find_chrome()
    admin_url = f"{base_url}/admin"
    display_url = f"{base_url}/"

    if not chrome:
        logger.warning(
            "Chrome/Chromiumが見つからなかったため、既定のブラウザで演出画面だけ開きます。"
            "管理画面は手動で %s を開いてください。",
            admin_url,
        )
        webbrowser.open(display_url)
        return

    display_args = [
        chrome,
        f"--user-data-dir={_profile_dir('display')}",
        "--new-window",
        "--no-first-run",
    ]
    if settings.get("kiosk_mode", False):
        display_args.append("--kiosk")
    else:
        display_args.append("--window-size=1000,700")
    position = settings.get("kiosk_window_position")
    if position:
        display_args.append(f"--window-position={position}")
    display_args.append(display_url)
    subprocess.Popen(display_args)

    admin_args = [
        chrome,
        f"--user-data-dir={_profile_dir('admin')}",
        "--new-window",
        "--no-first-run",
        "--window-size=900,700",
        admin_url,
    ]
    subprocess.Popen(admin_args)


def open_windows_after_delay(base_url, settings, delay_seconds=1.5):
    """サーバーが起動しきるのを少し待ってからブラウザを開く(別スレッドで実行)。"""

    def _run():
        time.sleep(delay_seconds)
        try:
            open_windows(base_url, settings)
        except Exception:  # noqa: BLE001 - ブラウザ起動失敗でサーバー自体は落とさない
            logger.exception("ブラウザの自動起動に失敗しました。手動で開いてください: %s", base_url)

    threading.Thread(target=_run, daemon=True).start()
