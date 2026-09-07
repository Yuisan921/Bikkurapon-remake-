import json

import pytest

from app.lottery import Lottery


@pytest.fixture
def lottery(tmp_path):
    prizes = [
        {"id": "atari", "name": "当たり", "probability": 1.0, "stock": 2, "hopper": "a"},
        {"id": "hazure", "name": "はずれ", "probability": 0.0, "stock": None, "hopper": "b"},
    ]
    prizes_path = tmp_path / "prizes.json"
    prizes_path.write_text(json.dumps(prizes), encoding="utf-8")
    stock_path = tmp_path / "stock.json"
    return Lottery(prizes_path, stock_path)


def test_draw_decrements_stock(lottery):
    result = lottery.draw()
    assert result["id"] == "atari"
    assert result["remaining"] == 1


def test_falls_back_to_unlimited_prize_when_stock_exhausted(lottery):
    lottery.draw()
    lottery.draw()
    result = lottery.draw()
    assert result["id"] == "hazure"


def test_set_stock_and_restock(lottery):
    lottery.set_stock("atari", 10)
    assert lottery.restock("atari", 5) == 15


def test_unknown_prize_id_raises(lottery):
    with pytest.raises(KeyError):
        lottery.restock("unknown", 1)


def test_set_probability_updates_draw_behavior_and_persists(lottery):
    lottery.set_probability("atari", 0.0)
    lottery.set_probability("hazure", 1.0)

    result = lottery.draw()
    assert result["id"] == "hazure"

    # prizes.json にも書き戻されていること
    saved = json.loads(lottery.prizes_config_path.read_text(encoding="utf-8"))
    saved_by_id = {p["id"]: p for p in saved}
    assert saved_by_id["atari"]["probability"] == 0.0
    assert saved_by_id["hazure"]["probability"] == 1.0


def test_set_probability_rejects_negative(lottery):
    with pytest.raises(ValueError):
        lottery.set_probability("atari", -0.1)


def test_set_probability_unknown_prize_raises(lottery):
    with pytest.raises(KeyError):
        lottery.set_probability("unknown", 0.5)
