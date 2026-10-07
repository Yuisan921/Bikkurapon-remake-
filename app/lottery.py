"""確率抽選と景品在庫の管理。"""

import json
import os
import random
import threading
import time
import uuid
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
    def __init__(
        self,
        prizes_config_path,
        stock_data_path,
        reservation_timeout=30.0,
        clock=time.monotonic,
    ):
        self.prizes_config_path = Path(prizes_config_path)
        self.stock_data_path = Path(stock_data_path)
        self._lock = threading.Lock()
        self._reservation_timeout = reservation_timeout
        self._clock = clock
        self._reservations = {}
        self._reserved_counts = {}
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

    def _release_reservation_locked(self, reservation):
        prize_id = reservation["prize"]["id"]
        if reservation["prize"]["stock"] is None:
            return
        remaining = self._reserved_counts.get(prize_id, 0) - 1
        if remaining > 0:
            self._reserved_counts[prize_id] = remaining
        else:
            self._reserved_counts.pop(prize_id, None)

    def _prune_expired_reservations_locked(self):
        now = self._clock()
        expired_ids = [
            reservation_id
            for reservation_id, reservation in self._reservations.items()
            if now - reservation["created_at"] >= self._reservation_timeout
        ]
        for reservation_id in expired_ids:
            reservation = self._reservations.pop(reservation_id)
            self._release_reservation_locked(reservation)

    def _remaining_available(self, prize, stock):
        if prize["stock"] is None:
            return None
        return max(
            0,
            stock.get(prize["id"], 0) - self._reserved_counts.get(prize["id"], 0),
        )

    def has_stock(self):
        """抽選できる景品が1つでも残っているか。"""
        with self._lock:
            self._prune_expired_reservations_locked()
            return bool(self._candidates(self._read_stock()))

    def _candidates(self, stock):
        return [
            p for p in self._prizes
            if p["stock"] is None or self._remaining_available(p, stock) > 0
        ]

    def get_status(self):
        with self._lock:
            self._prune_expired_reservations_locked()
            stock = self._read_stock()
            result = []
            for p in self._prizes:
                remaining = self._remaining_available(p, stock)
                result.append({**p, "remaining": remaining})
            return result

    def reserve_draw(self):
        """景品を1個予約するが、在庫ファイルはまだ減らさない。

        実物の排出が成功したら commit_draw()、失敗したら cancel_draw() を呼ぶ。
        予約中の個数は次の抽選候補から除外されるため、並行した投入でも同じ
        最後の1個を二重に割り当てない。確認応答が失われた予約は一定時間後に
        自動解放する。
        """
        with self._lock:
            self._prune_expired_reservations_locked()
            stock = self._read_stock()
            candidates = self._candidates(stock)
            if not candidates:
                raise OutOfStock("抽選できる景品の在庫がありません")

            weights = [p["probability"] for p in candidates]
            if sum(weights) <= 0:
                weights = [1] * len(candidates)
            chosen = random.choices(candidates, weights=weights, k=1)[0]

            reservation_id = uuid.uuid4().hex
            if chosen["stock"] is not None:
                self._reserved_counts[chosen["id"]] = (
                    self._reserved_counts.get(chosen["id"], 0) + 1
                )
            reservation = {
                "prize": dict(chosen),
                "created_at": self._clock(),
            }
            self._reservations[reservation_id] = reservation
            remaining = self._remaining_available(chosen, stock)
            return {**chosen, "remaining": remaining, "reservation_id": reservation_id}

    def commit_draw(self, reservation_id):
        """排出成功が確認できた予約だけを在庫へ反映する。"""
        with self._lock:
            reservation = self._reservations.pop(reservation_id, None)
            if reservation is None:
                raise KeyError(f"unknown or expired reservation: {reservation_id}")

            chosen = reservation["prize"]
            stock = self._read_stock()
            if chosen["stock"] is not None:
                if stock.get(chosen["id"], 0) <= 0:
                    self._release_reservation_locked(reservation)
                    raise OutOfStock("予約した景品の在庫がありません")
                stock[chosen["id"]] -= 1
                self._write_stock(stock)
            self._release_reservation_locked(reservation)
            remaining = self._remaining_available(chosen, stock)
            return {**chosen, "remaining": remaining}

    def cancel_draw(self, reservation_id):
        """排出できなかった予約を解放する。在庫ファイルは変更しない。"""
        with self._lock:
            reservation = self._reservations.pop(reservation_id, None)
            if reservation is None:
                return False
            self._release_reservation_locked(reservation)
            return True

    def draw(self):
        """1回抽選する。在庫切れの景品は候補から除外し、残った候補の確率だけで
        再抽選する。全景品の在庫が0で候補が空なら OutOfStock を投げる
        (この場合、在庫は減らさず、何も排出しない)。
        """
        reservation = self.reserve_draw()
        return self.commit_draw(reservation["reservation_id"])

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
            self._prune_expired_reservations_locked()
            stock = self._read_stock()
            if prize_id not in stock:
                raise KeyError(f"unknown prize id: {prize_id}")
            # 排出中の予約分は物理的にはまだ筐体内にあるため、それ未満へは
            # 変更させない。ACK後に予約分が正しく1個減る。
            stock[prize_id] = max(
                self._reserved_counts.get(prize_id, 0),
                max(0, amount),
            )
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
