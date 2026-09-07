import json

from app.config_setup import ensure_config_dir


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
