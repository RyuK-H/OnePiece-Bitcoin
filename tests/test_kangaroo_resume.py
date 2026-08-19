"""A Kangaroo hunt must RESUME its walk across restarts, not restart the herd
from the seed and reset progress to zero. Two checks:

  1. snapshot()/restore() round-trips the solver state exactly (deterministic
     continuation from a restored solver matches the original).
  2. Re-running the same sentence accumulates keys_tried (keys_before carried)
     and leaves a per-worker checkpoint file.

Run: python3 tests/test_kangaroo_resume.py
"""
import hashlib
import os
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="onepiece-kresume-")
os.environ["ONEPIECE_HOME"] = _TMP  # isolate BEFORE importing onepiece
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from onepiece import crypto                      # noqa: E402
from onepiece import kangaroo                    # noqa: E402
from onepiece import seed as seedmod             # noqa: E402
from onepiece import state as statemod           # noqa: E402
from onepiece import hunt as huntmod             # noqa: E402
from onepiece.puzzles import Puzzle              # noqa: E402


def test_snapshot_roundtrip():
    a, b = 1 << 24, 1 << 25
    Q = crypto.scalar_mul((1 << 24) + 0x9abc)
    seed = hashlib.sha256(b"roundtrip").digest()
    s1 = kangaroo.KangarooSolver(Q, a, b, seed)
    for _ in range(80):
        s1.step_batch(4096)
    snap = s1.snapshot()

    s2 = kangaroo.KangarooSolver(Q, a, b, seed)   # fresh, same seed
    s2.restore(snap)
    assert s2.ops == s1.ops
    assert [kg["pt"] for kg in s2.tame] == [kg["pt"] for kg in s1.tame]
    assert [kg["val"] for kg in s2.tame] == [kg["val"] for kg in s1.tame]
    assert [kg["pt"] for kg in s2.wild] == [kg["pt"] for kg in s1.wild]
    assert [kg["dist"] for kg in s2.wild] == [kg["dist"] for kg in s1.wild]
    assert s2.dp == s1.dp

    # A restored solver must continue identically to the original (determinism).
    s1.step_batch(4096)
    s2.step_batch(4096)
    assert [kg["pt"] for kg in s2.tame] == [kg["pt"] for kg in s1.tame]
    assert [kg["pt"] for kg in s2.wild] == [kg["pt"] for kg in s1.wild]
    print("kangaroo snapshot/restore round-trip OK")


def test_resume_accumulates():
    # Workers are spawned (fresh import), so patching the module constant won't
    # reach them — the worker reads this env var at runtime instead.
    os.environ["ONEPIECE_KANGAROO_CKPT_SECONDS"] = "0.4"

    # A pubkey-exposed puzzle in a window big enough NOT to solve in a 2s run
    # (2*sqrt(2^60) ≈ 2^31 ops needed) but that still routes through Kangaroo.
    a, b = 1 << 60, 1 << 61
    Q = crypto.scalar_mul((1 << 60) + 0x1234567)
    pub = bytes([0x02 if Q[1] % 2 == 0 else 0x03]) + Q[0].to_bytes(32, "big")
    addr = crypto.hash160_to_address(crypto.hash160(pub))
    pz = Puzzle(n=999, type="pubkey-exposed", address=addr, balance_btc=0.0,
                public_key=pub.hex(), keyspace_lo=a, keyspace_hi=b)

    st1 = huntmod.run_hunt(pz, sentence="kresume", intensity=1,
                           max_seconds=2, check_balance=False)
    assert st1["status"] != "found", "window too small; it solved instantly"
    k1 = st1["keys_tried"]
    assert k1 > 0

    seed_hex = seedmod.seed_hash_hex(seedmod.seed_from_sentence("kresume"))
    ckpt = statemod.kangaroo_ckpt_path(999, seed_hex, 0)
    assert os.path.exists(ckpt), "no checkpoint written — resume can't work"

    st2 = huntmod.run_hunt(pz, sentence="kresume", intensity=1,
                           max_seconds=2, check_balance=False)
    k2 = st2["keys_tried"]
    # Accumulated: run 2 starts from run 1's total and adds more, so k2 > k1.
    # Without resume, k2 would be only run 2's own ops (~k1-sized), not k1+more.
    assert k2 > k1, f"progress did not accumulate across restart: {k1} -> {k2}"
    print(f"kangaroo resume accumulates OK: {k1:,} -> {k2:,} keys, checkpoint present")


if __name__ == "__main__":
    test_snapshot_roundtrip()
    test_resume_accumulates()
