import json

from app.config_setup import ensure_config_dir, migrate_legacy_data


def _write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _make_bundle_config(tmp_path):
    bundle_config = tmp_path / "bundle_config"
    bundle_config.mkdir()
    _write_json(
        bundle_config / "prizes.json",
        [
            {"id": "atari", "name": "当たり", "probability": 0.2, "stock": 30, "hopper": "a"},
            {"id": "hazure", "name": "はずれ", "probability": 0.8, "stock": 60, "hopper": "b"},
        ],
    )
    _write_json(bundle_config / "settings.json", {"port": 5000})
    return bundle_config


def test_creates_config_dir_when_missing(tmp_path):
    bundle_config = _make_bundle_config(tmp_path)
    config_dir = tmp_path / "config"

    ensure_config_dir(config_dir, bundle_config)

    prizes = json.loads((config_dir / "prizes.json").read_text(encoding="utf-8"))
    assert [p["id"] for p in prizes] == ["atari", "hazure"]


def test_migrates_legacy_prizes_without_hopper_field(tmp_path):
    bundle_config = _make_bundle_config(tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    legacy_prizes_path = config_dir / "prizes.json"
    _write_json(
        legacy_prizes_path,
        [
            {"id": "daiatari", "name": "大当たり", "probability": 0.05, "stock": 5, "servo_angle": 0},
            {"id": "atari", "name": "当たり", "probability": 0.2, "stock": 30, "servo_angle": 90},
            {"id": "hazure", "name": "はずれ", "probability": 0.75, "stock": None, "servo_angle": None},
        ],
    )
    _write_json(config_dir / "settings.json", {"port": 5000})

    ensure_config_dir(config_dir, bundle_config)

    prizes = json.loads(legacy_prizes_path.read_text(encoding="utf-8"))
    assert [p["id"] for p in prizes] == ["atari", "hazure"]
    assert all("hopper" in p for p in prizes)

    backup = json.loads((config_dir / "prizes.json.bak").read_text(encoding="utf-8"))
    assert [p["id"] for p in backup] == ["daiatari", "atari", "hazure"]


def test_leaves_current_format_prizes_untouched(tmp_path):
    bundle_config = _make_bundle_config(tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    prizes_path = config_dir / "prizes.json"
    _write_json(
        prizes_path,
        [
            {"id": "atari", "name": "当たり", "probability": 0.5, "stock": 3, "hopper": "a"},
            {"id": "hazure", "name": "はずれ", "probability": 0.5, "stock": None, "hopper": "b"},
        ],
    )
    _write_json(config_dir / "settings.json", {"port": 5000})

    ensure_config_dir(config_dir, bundle_config)

    prizes = json.loads(prizes_path.read_text(encoding="utf-8"))
    assert prizes[0]["stock"] == 3
    assert not (config_dir / "prizes.json.bak").exists()


def test_migrates_legacy_settings_prizes_and_stock_without_overwriting(tmp_path):
    legacy = tmp_path / "program_files"
    target = tmp_path / "local_app_data"
    (legacy / "config").mkdir(parents=True)
    (legacy / "data").mkdir()
    _write_json(legacy / "config" / "settings.json", {"port": 7777})
    _write_json(legacy / "config" / "prizes.json", [{"id": "old"}])
    _write_json(legacy / "data" / "stock.json", {"old": 4})
    (target / "config").mkdir(parents=True)
    _write_json(target / "config" / "settings.json", {"port": 5000})

    migrate_legacy_data(legacy, target)

    assert json.loads((target / "config" / "settings.json").read_text()) == {"port": 5000}
    assert json.loads((target / "config" / "prizes.json").read_text()) == [{"id": "old"}]
    assert json.loads((target / "data" / "stock.json").read_text()) == {"old": 4}


def test_ensure_config_repairs_missing_default_file(tmp_path):
    bundle_config = _make_bundle_config(tmp_path)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    _write_json(config_dir / "settings.json", {"port": 6000})

    ensure_config_dir(config_dir, bundle_config)

    assert json.loads((config_dir / "settings.json").read_text())["port"] == 6000
    assert (config_dir / "prizes.json").exists()
