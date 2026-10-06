"""通常のPython実行時と、PyInstallerで.exe化された時の両方で
正しいパスを解決するためのヘルパー。

- BASE_DIR: config/やdata/を置く場所。.exe化した場合は、exe本体と同じ
  フォルダに書き込めるならそこ(ポータブル運用。ユーザーが設定ファイルを
  直接編集したり、data/stock.json が永続化されたりする)。
  インストーラーで `C:\\Program Files\\Bikkurapon\\` に入れた場合のように
  書き込めないフォルダなら、ユーザーごとのデータフォルダ
  (Windowsは %LOCALAPPDATA%\\Bikkurapon)に置く。
- BUNDLE_DIR: templates/やstatic/を読む場所。.exe化した場合は
  PyInstallerが展開する一時フォルダ(sys._MEIPASS)を指す、
  読み取り専用の同梱リソース。
"""

import os
import sys
import tempfile
from pathlib import Path


def is_frozen():
    """PyInstallerなどで.exe化された状態で実行されているか。"""
    return getattr(sys, "frozen", False)


def is_writable_dir(path):
    """そのフォルダに実際にファイルを作れるか。

    os.access は Windows では権限(ACL)を正しく反映しないことがあるため、
    一時ファイルを作ってみて確かめる。
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=path):
            pass
        return True
    except OSError:
        return False


def get_user_data_dir():
    """exeの隣に書き込めないときの、ユーザーごとのデータ置き場。"""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Bikkurapon"
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data_home) if xdg_data_home else Path.home() / ".local" / "share"
    return base / "bikkurapon"


def choose_base_dir(exe_dir, fallback_dir, writable_check=is_writable_dir):
    """exeの隣に書き込めるならそこ、書き込めなければ fallback_dir を使う。"""
    if writable_check(exe_dir):
        return exe_dir
    return fallback_dir


def get_base_dir():
    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        return choose_base_dir(exe_dir, get_user_data_dir())
    return Path(__file__).resolve().parent.parent


def get_bundle_dir():
    if is_frozen():
        # PyInstallerの --onefile はこの一時フォルダに埋め込みリソースを展開する
        return Path(getattr(sys, "_MEIPASS", get_base_dir()))
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
BUNDLE_DIR = get_bundle_dir()
