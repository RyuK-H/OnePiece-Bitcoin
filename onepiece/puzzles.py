"""Load and query the verified unsolved-puzzle dataset (data/puzzles.json)."""

from __future__ import annotations
import json
import os
from dataclasses import dataclass

_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "puzzles.json")


@dataclass(frozen=True)
class Puzzle:
    n: int
    type: str            # "address-only" | "pubkey-exposed"
    address: str
    balance_btc: float
    public_key: str | None
    keyspace_lo: int     # inclusive, 2^(n-1)
    keyspace_hi: int     # exclusive, 2^n

    @property
    def keyspace_size(self) -> int:
        return self.keyspace_hi - self.keyspace_lo

    @property
    def bits(self) -> int:
        return self.n

    def difficulty_label(self) -> str:
        # Purely descriptive; every unsolved puzzle is astronomically hard.
        if self.n <= 75:
            return "hardest-reachable"
        if self.n <= 110:
            return "astronomical"
        return "beyond astronomical"


def _load_raw() -> dict:
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_puzzles() -> list[Puzzle]:
    raw = _load_raw()
    out = []
    for p in raw["puzzles"]:
        n = p["n"]
        out.append(Puzzle(
            n=n,
            type=p["type"],
            address=p["address"],
            balance_btc=p["balance_btc"],
            public_key=p.get("public_key"),
            keyspace_lo=1 << (n - 1),
            keyspace_hi=1 << n,
        ))
    return out


def get_puzzle(n: int) -> Puzzle:
    for p in load_puzzles():
        if p.n == n:
            return p
    raise KeyError(f"puzzle #{n} is not in the unsolved list (it may be solved, or invalid)")


def balance_apis() -> list[dict]:
    return sorted(_load_raw().get("balance_apis", []), key=lambda a: a.get("priority", 99))


def totals() -> dict:
    return _load_raw().get("counts", {})
