"""確率抽選と景品在庫の管理。"""

import json
import random
import threading
from pathlib import Path


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
        with open(self.stock_data_path, "w", encoding="utf-8") as f:
            json.dump(initial, f, ensure_ascii=False, indent=2)

    def _read_stock(self):
        with open(self.stock_data_path, encoding="utf-8") as f:
            return json.load(f)

    def _write_stock(self, stock):
        with open(self.stock_data_path, "w", encoding="utf-8") as f:
            json.dump(stock, f, ensure_ascii=False, indent=2)

    def get_status(self):
        stock = self._read_stock()
        result = []
        for p in self._prizes:
            remaining = stock.get(p["id"]) if p["stock"] is not None else None
            result.append({**p, "remaining": remaining})
        return result

    def draw(self):
        """1回抽選する。在庫切れの景品は候補から除外し、残った候補の確率だけで
        再抽選する(はずれは stock=null=無制限なので候補が空になることはない)。
        """
        with self._lock:
            stock = self._read_stock()
            candidates = [
                p for p in self._prizes
                if p["stock"] is None or stock.get(p["id"], 0) > 0
            ]

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
