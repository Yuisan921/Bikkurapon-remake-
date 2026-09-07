"""通常のPython実行時と、PyInstallerで.exe化された時の両方で
正しいパスを解決するためのヘルパー。

- BASE_DIR: config/やdata/を置く場所。.exe化した場合はexe本体と同じ
  フォルダになるので、ユーザーが設定ファイルを直接編集したり、
  data/stock.json が永続化されたりする。
- BUNDLE_DIR: templates/やstatic/を読む場所。.exe化した場合は
  PyInstallerが展開する一時フォルダ(sys._MEIPASS)を指す、
  読み取り専用の同梱リソース。
"""

import sys
from pathlib import Path


def is_frozen():
    """PyInstallerなどで.exe化された状態で実行されているか。"""
    return getattr(sys, "frozen", False)


def get_base_dir():
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_bundle_dir():
    if is_frozen():
        # PyInstallerの --onefile はこの一時フォルダに埋め込みリソースを展開する
        return Path(getattr(sys, "_MEIPASS", get_base_dir()))
    return Path(__file__).resolve().parent.parent


BASE_DIR = get_base_dir()
BUNDLE_DIR = get_bundle_dir()
