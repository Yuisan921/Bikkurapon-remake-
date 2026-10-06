"""確率抽選と景品在庫の管理。"""

import json
import os
import random
import threading
from pathlib import Path


class OutOfStock(Exception):
    """抽選できる景品が1つも残っていない(全景品の在庫が0)ときに投げる。

    はずれにも在庫(stock)を設定している場合、使い切ると候補が空になる。
    その場合は黙って別の結果を返さず、呼び出し側(サーバー)で
    「巫女さんを呼んでください」画面を出すなどの対応をしてもらう。
    """


def _write_json_atomic(path, data):
    """JSONを一時ファイルに書いてから置き換える。

    直接上書きすると、書き込み中の停電・強制終了・並行読み込みで
    ファイルが途中までの壊れた状態になることがある。os.replace は
    置き換えが一瞬(原子的)なので、読む側は常に「古い完全版」か
    「新しい完全版」のどちらかしか見ない。
    """
    path = Path(path)
    tmp_path = path.with_name(path.name + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)


class Lottery:
    def __init__(self, prizes_config_path, stock_data_path):
        self.prizes_config_path = Path(prizes_config_path)
        self.stock_data_path = Path(stock_data_path)
        self._lock = threading.Lock()
        self._prizes = self._load_prizes()
        self._ensure_stock_file()

    def _load_prizes(self):
        with open(self.prizes_config_path, encoding="utf-8") as f:
            return json.load(f)

    def _ensure_stock_file(self):
        if self.stock_data_path.exists():
            return
        initial = {p["id"]: p["stock"] for p in self._prizes if p["stock"] is not None}
        self.stock_data_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json_atomic(self.stock_data_path, initial)

    def _read_stock(self):
        with open(self.stock_data_path, encoding="utf-8") as f:
            return json.load(f)

    def _write_stock(self, stock):
        _write_json_atomic(self.stock_data_path, stock)

    def _write_prizes(self):
        _write_json_atomic(self.prizes_config_path, self._prizes)

    def has_stock(self):
        """抽選できる景品が1つでも残っているか。"""
        with self._lock:
            return bool(self._candidates(self._read_stock()))

    def _candidates(self, stock):
        return [
            p for p in self._prizes
            if p["stock"] is None or stock.get(p["id"], 0) > 0
        ]

    def get_status(self):
        with self._lock:
            stock = self._read_stock()
            result = []
            for p in self._prizes:
                remaining = stock.get(p["id"]) if p["stock"] is not None else None
                result.append({**p, "remaining": remaining})
            return result

    def draw(self):
        """1回抽選する。在庫切れの景品は候補から除外し、残った候補の確率だけで
        再抽選する。全景品の在庫が0で候補が空なら OutOfStock を投げる
        (この場合、在庫は減らさず、何も排出しない)。
        """
        with self._lock:
            stock = self._read_stock()
            candidates = self._candidates(stock)
            if not candidates:
                raise OutOfStock("抽選できる景品の在庫がありません")

            weights = [p["probability"] for p in candidates]
            if sum(weights) <= 0:
                # 残った候補の確率が合計0(設定ミスやテスト用データ)の場合は
                # クラッシュさせず均等な確率で選ぶ
                weights = [1] * len(candidates)
            chosen = random.choices(candidates, weights=weights, k=1)[0]

            if chosen["stock"] is not None:
                stock[chosen["id"]] -= 1
                self._write_stock(stock)

            remaining = stock.get(chosen["id"]) if chosen["stock"] is not None else None
            return {**chosen, "remaining": remaining}

    def restock(self, prize_id, amount):
        with self._lock:
            stock = self._read_stock()
            if prize_id not in stock:
                raise KeyError(f"unknown prize id: {prize_id}")
            stock[prize_id] = max(0, stock[prize_id] + amount)
            self._write_stock(stock)
            return stock[prize_id]

    def set_stock(self, prize_id, amount):
        with self._lock:
            stock = self._read_stock()
            if prize_id not in stock:
                raise KeyError(f"unknown prize id: {prize_id}")
            stock[prize_id] = max(0, amount)
            self._write_stock(stock)
            return stock[prize_id]

    def set_probability(self, prize_id, probability):
        """景品の当選確率を変更し、config/prizes.json にも書き戻す(再起動後も
        反映される)。管理画面から「在庫に合わせて確率を調整する」「テスト用に
        わざと確率を偏らせる」といった用途で使う想定。
        """
        with self._lock:
            prize = next((p for p in self._prizes if p["id"] == prize_id), None)
            if prize is None:
                raise KeyError(f"unknown prize id: {prize_id}")
            if probability < 0 or probability != probability or probability == float("inf"):
                raise ValueError("probability must be a finite number, 0 or greater")
            prize["probability"] = probability
            self._write_prizes()
            return prize["probability"]
