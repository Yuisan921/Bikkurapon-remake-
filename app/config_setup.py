"""設定ファイル(config/)の初期化・移行を行うヘルパー。

.exeを新しいバージョンに入れ替えても、config/ フォルダは実行ファイルの
隣に前のバージョンが作ったものがそのまま残り続ける(インストーラーで
上書きインストールしても、アンインストールしても消えない)。そのため、
中身が「大当たり」があった頃の古い景品構成のままだと、新しいexeに
入れ替えても新しい既定値がずっと反映されない問題があった。

ここでは既知の古い形式(prizesの各要素に "hopper" フィールドが無い =
大当たり/servo_angle時代の形式)を検出したら、内容をバックアップした
上で最新の既定値に差し替える。
"""

import json
import logging
import shutil

logger = logging.getLogger(__name__)


def migrate_legacy_data(legacy_base_dir, base_dir):
    """旧版がexeの隣に保存した設定・在庫を新しい保存先へ一度だけコピーする。

    新しい保存先に同名ファイルがある場合は、現在のデータを優先して上書きしない。
    """
    if legacy_base_dir is None:
        return
    legacy_base_dir = legacy_base_dir.resolve()
    base_dir = base_dir.resolve()
    if legacy_base_dir == base_dir or not legacy_base_dir.exists():
        return

    relative_files = (
        ("config", "settings.json"),
        ("config", "prizes.json"),
        ("data", "stock.json"),
    )
    copied = []
    for directory, filename in relative_files:
        source = legacy_base_dir / directory / filename
        destination = base_dir / directory / filename
        if not source.is_file() or destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied.append(str(destination))

    if copied:
        logger.warning(
            "旧バージョンの設定・在庫を %s から新しい保存先へ移行しました: %s",
            legacy_base_dir,
            ", ".join(copied),
        )


def _prizes_need_migration(prizes_path):
    """prizes.json が hopper フィールドを持たない旧形式かどうか。"""
    try:
        with open(prizes_path, encoding="utf-8") as f:
            prizes = json.load(f)
    except (OSError, json.JSONDecodeError):
        return False
    return any("hopper" not in prize for prize in prizes)


def ensure_config_dir(config_dir, bundle_config_dir):
    """config_dir が無ければ同梱の既定値をコピーして作る。

    既にあるが景品構成が旧形式(大当たり/servo_angle時代)の場合は、
    prizes.json をバックアップしてから最新の既定値で上書きする。
    settings.json はフィールド追加のみで後方互換なので触らない。
    """
    if not config_dir.exists():
        shutil.copytree(bundle_config_dir, config_dir)
        return

    # 途中で削除・移行されたファイルだけを既定値から補う。既存の編集内容は
    # 上書きしない。
    for filename in ("settings.json", "prizes.json"):
        destination = config_dir / filename
        if not destination.exists():
            shutil.copy(bundle_config_dir / filename, destination)

    prizes_path = config_dir / "prizes.json"
    if _prizes_need_migration(prizes_path):
        backup_path = config_dir / "prizes.json.bak"
        logger.warning(
            "%s が旧バージョンの景品構成(大当たり等)のままだったため、"
            "%s にバックアップしてから最新の既定値(当たり/はずれの2ホッパー構成)"
            "に差し替えました。在庫を調整済みだった場合は %s の内容を見ながら"
            "管理画面から設定し直してください。",
            prizes_path,
            backup_path,
            backup_path,
        )
        shutil.copy(prizes_path, backup_path)
        shutil.copy(bundle_config_dir / "prizes.json", prizes_path)
