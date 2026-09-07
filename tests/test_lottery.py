import json

import pytest

from app.lottery import Lottery


@pytest.fixture
def lottery(tmp_path):
    prizes = [
        {"id": "atari", "name": "当たり", "probability": 1.0, "stock": 2, "servo_angle": 90},
        {"id": "hazure", "name": "はずれ", "probability": 0.0, "stock": None, "servo_angle": None},
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
