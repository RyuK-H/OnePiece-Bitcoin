"""Pollard's Kangaroo for the public-key-exposed puzzles (140, 145, 150, 155, 160).

When the public key Q = k*G is known and k lies in a known interval [a, b), the
discrete log can be attacked in ~2*sqrt(b-a) group operations instead of b-a.
Two herds of "kangaroos" (tame, starting from known scalars; wild, starting
from Q) take seeded pseudorandom jumps. When a tame and a wild kangaroo land on
the same distinguished point, their bookkeeping reveals k.

Honesty note: unlike the address-only brute force, Kangaroo DOES keep a table
of distinguished points — that memory is what buys the sqrt speedup, it is not
a duplicate-avoidance cache. The table is capped (max_dp) so memory stays
bounded; on the real puzzles the interval is so vast the search never finishes
anyway, which is the whole point.
"""

from __future__ import annotations
import hashlib
from math import isqrt

from . import crypto

G = (crypto.GX, crypto.GY)
N = crypto.N
P = crypto.P

# How many low bits of a kangaroo's point x-coordinate we surface for the
# dashboard to plot. The value is scattered uniformly over [0, 2^POSITION_BITS),
# so the dashboard can map it onto a grid cell independent of grid size. Kept
# under 63 so it fits an unsigned 64-bit shared-memory slot. hunt.py writes it,
# dashboard.py reads it — keep the two in sync via this constant.
POSITION_BITS = 62
_POSITION_MASK = (1 << POSITION_BITS) - 1


def _neg(pt):
    x, y = pt
    return (x, (P - y) % P)


def _seeded_jumps(seed: bytes, w: int):
    """Build r seeded jump sizes with mean ~ sqrt(w), and their point multiples."""
    r = max(8, w.bit_length() // 2)
    beta = max(2, isqrt(w))
    sizes, points = [], []
    for i in range(r):
        h = hashlib.sha256(seed + b"kjump" + i.to_bytes(2, "big")).digest()
        s = 1 + (int.from_bytes(h, "big") % (2 * beta))
        sizes.append(s)
        points.append(crypto.scalar_mul(s))
    return r, sizes, points


class KangarooSolver:
    def __init__(self, Q, a, b, seed: bytes,
                 tame_herd: int = 4, wild_herd: int = 4,
                 dp_bits: int | None = None, max_dp: int = 5_000_000):
        self.Q = Q
        self.a = a
        self.b = b
        self.w = b - a
        self.max_dp = max_dp
        self.r, self.sizes, self.jump_pts = _seeded_jumps(seed, self.w)
        if dp_bits is None:
            dp_bits = max(0, (self.w.bit_length() // 2) - 6)
        self.mask = (1 << dp_bits) - 1
        self.dp: dict[int, tuple[str, int]] = {}
        self.ops = 0

        # Reduce to m in [0, w): Q' = Q - a*G, so Q' = m*G.
        self.Qp = crypto.point_add(Q, _neg(crypto.scalar_mul(a)))

        # Tame herd: known scalars near the middle of the interval.
        self.tame = []
        for j in range(tame_herd):
            val = self.w // 2 + j
            self.tame.append({"pt": crypto.scalar_mul(val), "val": val})
        # Wild herd: start at Q' with small fixed offsets.
        self.wild = []
        for j in range(wild_herd):
            off = j
            pt = self.Qp if j == 0 else crypto.point_add(self.Qp, crypto.scalar_mul(j))
            self.wild.append({"pt": pt, "dist": 0, "off": off})

    def snapshot(self) -> dict:
        """Serializable state so a stopped hunt resumes its walk, not restarts.

        Saves each kangaroo's current point + accumulated scalar, the ops count,
        and the distinguished-point table (the traps that buy the sqrt speedup).
        The seed-derived jump table is NOT saved — it is rebuilt from the same
        sentence-seed on restore, so it must not change across restarts.
        """
        return {
            "ops": self.ops,
            "tame": [[kg["pt"][0], kg["pt"][1], kg["val"]] for kg in self.tame],
            "wild": [[kg["pt"][0], kg["pt"][1], kg["dist"], kg["off"]] for kg in self.wild],
            "dp": [[x, kind, val] for x, (kind, val) in self.dp.items()],
        }

    def restore(self, snap: dict) -> None:
        """Reload a snapshot() into this freshly-constructed solver in place.

        Herd sizes are whatever this instance was built with; only the overlap
        with the snapshot is restored, so a resume with fewer/more kangaroos
        keeps what it can (extra kangaroos just start from their seeded points).
        """
        try:
            self.ops = int(snap.get("ops", 0))
        except (TypeError, ValueError):
            self.ops = 0
        for i, row in enumerate(snap.get("tame", [])):
            if i < len(self.tame) and len(row) >= 3:
                self.tame[i]["pt"] = (int(row[0]), int(row[1]))
                self.tame[i]["val"] = int(row[2])
        for i, row in enumerate(snap.get("wild", [])):
            if i < len(self.wild) and len(row) >= 4:
                self.wild[i]["pt"] = (int(row[0]), int(row[1]))
                self.wild[i]["dist"] = int(row[2])
                self.wild[i]["off"] = int(row[3])
        for row in snap.get("dp", []):
            try:
                if len(row) >= 3 and len(self.dp) < self.max_dp:
                    self.dp[int(row[0])] = (row[1], int(row[2]))
            except (TypeError, ValueError):
                continue

    def herd_positions(self) -> list[int]:
        """Each kangaroo's current spot, as POSITION_BITS-wide scatter values.

        Tame herd first, then wild. Purely for visualization: the value is the
        low bits of the current point's x-coordinate, which moves every hop, so
        the dashboard can show the herd roaming the field.
        """
        return [(kg["pt"][0] & _POSITION_MASK) for kg in self.tame] + \
               [(kg["pt"][0] & _POSITION_MASK) for kg in self.wild]

    def _distinguished(self, x: int) -> bool:
        return (x & self.mask) == 0

    def _record(self, x: int, kind: str, value: int):
        if x in self.dp:
            k, v = self.dp[x]
            if k != kind:
                return v  # the other herd was here -> possible collision
            return None
        if len(self.dp) < self.max_dp:
            self.dp[x] = (kind, value)
        return None

    def _try_solve(self, tame_val: int, wild_total: int):
        m = (tame_val - wild_total) % N
        if 0 <= m < self.w and crypto.scalar_mul(self.a + m) == self.Q:
            return self.a + m
        return None

    def step_batch(self, n_ops: int):
        """Advance the herds for up to n_ops group operations.

        Returns (found_private_key or None, ops_done_this_call).
        """
        start = self.ops
        while self.ops - start < n_ops:
            for kg in self.tame:
                idx = kg["pt"][0] % self.r
                kg["pt"] = crypto.point_add(kg["pt"], self.jump_pts[idx])
                kg["val"] += self.sizes[idx]
                self.ops += 1
                x = kg["pt"][0]
                if self._distinguished(x):
                    other = self._record(x, "T", kg["val"])
                    if other is not None:
                        k = self._try_solve(kg["val"], other)
                        if k is not None:
                            return k, self.ops - start
            for kg in self.wild:
                idx = kg["pt"][0] % self.r
                kg["pt"] = crypto.point_add(kg["pt"], self.jump_pts[idx])
                kg["dist"] += self.sizes[idx]
                self.ops += 1
                x = kg["pt"][0]
                if self._distinguished(x):
                    total = kg["off"] + kg["dist"]
                    other = self._record(x, "W", total)
                    if other is not None:
                        k = self._try_solve(other, total)
                        if k is not None:
                            return k, self.ops - start
        return None, self.ops - start


def solve(Q, a, b, seed: bytes, max_ops: int | None = None, **kw):
    """Convenience: run until solved or max_ops reached. Returns k or None."""
    s = KangarooSolver(Q, a, b, seed, **kw)
    while max_ops is None or s.ops < max_ops:
        k, _ = s.step_batch(4096)
        if k is not None:
            return k
    return None


if __name__ == "__main__":
    # Self-test: plant a key in a small interval, expose its pubkey, recover it.
    secret = (1 << 24) + 0x123456  # in [2^24, 2^25)
    a, b = 1 << 24, 1 << 25
    Q = crypto.scalar_mul(secret)
    seed = hashlib.sha256(b"kangaroo test").digest()
    k = solve(Q, a, b, seed, max_ops=5_000_000)
    assert k == secret, f"expected {secret}, got {k}"
    print("kangaroo self-test OK: recovered", hex(k))
