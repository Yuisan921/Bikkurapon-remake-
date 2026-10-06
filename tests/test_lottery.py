import json

import pytest

from app.lottery import Lottery, OutOfStock


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


@pytest.fixture
def limited_lottery(tmp_path):
    """既定の設定と同じく、はずれにも在庫がある(=全部使い切ると候補が空になる)構成。"""
    prizes = [
        {"id": "atari", "name": "当たり", "probability": 0.2, "stock": 1, "hopper": "a"},
        {"id": "hazure", "name": "はずれ", "probability": 0.8, "stock": 2, "hopper": "b"},
    ]
    prizes_path = tmp_path / "prizes.json"
    prizes_path.write_text(json.dumps(prizes), encoding="utf-8")
    return Lottery(prizes_path, tmp_path / "stock.json")


def test_raises_out_of_stock_when_every_prize_is_exhausted(limited_lottery):
    for _ in range(3):
        limited_lottery.draw()

    assert limited_lottery.has_stock() is False
    with pytest.raises(OutOfStock):
        limited_lottery.draw()


def test_out_of_stock_does_not_change_stock(limited_lottery):
    for _ in range(3):
        limited_lottery.draw()
    before = limited_lottery.stock_data_path.read_text(encoding="utf-8")

    with pytest.raises(OutOfStock):
        limited_lottery.draw()

    assert limited_lottery.stock_data_path.read_text(encoding="utf-8") == before


def test_restock_after_out_of_stock_allows_drawing_again(limited_lottery):
    for _ in range(3):
        limited_lottery.draw()

    limited_lottery.set_stock("hazure", 1)

    assert limited_lottery.has_stock() is True
    assert limited_lottery.draw()["id"] == "hazure"


def test_has_stock_is_true_with_unlimited_prize(lottery):
    lottery.draw()
    lottery.draw()
    assert lottery.has_stock() is True  # はずれは stock=None(無制限)


def test_writes_leave_no_temp_files_and_valid_json(limited_lottery):
    limited_lottery.draw()
    limited_lottery.set_probability("atari", 0.5)

    leftovers = [p.name for p in limited_lottery.stock_data_path.parent.iterdir()
                 if p.name.endswith(".tmp")]
    assert leftovers == []
    json.loads(limited_lottery.stock_data_path.read_text(encoding="utf-8"))
    json.loads(limited_lottery.prizes_config_path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0])
def test_set_probability_rejects_non_finite_or_negative(lottery, bad):
    with pytest.raises(ValueError):
        lottery.set_probability("atari", bad)
