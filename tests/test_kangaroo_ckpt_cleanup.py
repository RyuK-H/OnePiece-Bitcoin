"""Kangaroo checkpoints are tidied up on a TERMINAL finish (key found /
balance zero) but PRESERVED on a pause (interrupt / timeout), so a paused
hunt still resumes. Run: python3 tests/test_kangaroo_ckpt_cleanup.py
"""
import glob
import os
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="onepiece-kclean-")
os.environ["ONEPIECE_HOME"] = _TMP  # isolate BEFORE importing onepiece
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from onepiece import crypto                      # noqa: E402
from onepiece import seed as seedmod             # noqa: E402
from onepiece import state as statemod           # noqa: E402
from onepiece import hunt as huntmod             # noqa: E402
from onepiece.puzzles import Puzzle              # noqa: E402


def _pubkey_puzzle(n, a, b, secret):
    Q = crypto.scalar_mul(secret)
    pub = bytes([0x02 if Q[1] % 2 == 0 else 0x03]) + Q[0].to_bytes(32, "big")
    addr = crypto.hash160_to_address(crypto.hash160(pub))
    return Puzzle(n=n, type="pubkey-exposed", address=addr, balance_btc=0.0,
                  public_key=pub.hex(), keyspace_lo=a, keyspace_hi=b)


def _ckpt_glob(n, sentence):
    seed_hex = seedmod.seed_hash_hex(seedmod.seed_from_sentence(sentence))
    return os.path.join(statemod.HUNTS_DIR, f"{n}-{seed_hex[:8]}.kang-w*.json")


def test_cleanup_on_found():
    # Tiny interval → Kangaroo solves fast → terminal "found".
    pz = _pubkey_puzzle(998, 1 << 20, 1 << 21, (1 << 20) + 0x2be)
    # Pre-plant a checkpoint (and an orphan from a "larger past run") that a
    # terminal finish must sweep away. Empty snapshot restores to a no-op.
    statemod._ensure_dirs()
    seed_hex = seedmod.seed_hash_hex(seedmod.seed_from_sentence("cleanup"))
    for w in (0, 7):
        statemod.save(statemod.kangaroo_ckpt_path(998, seed_hex, w),
                      {"ops": 0, "tame": [], "wild": [], "dp": []})
    assert len(glob.glob(_ckpt_glob(998, "cleanup"))) == 2

    st = huntmod.run_hunt(pz, sentence="cleanup", intensity=1,
                          max_seconds=30, check_balance=False)
    assert st["status"] == "found", f"expected found, got {st['status']}"
    left = glob.glob(_ckpt_glob(998, "cleanup"))
    assert left == [], f"checkpoints not cleaned on found: {left}"
    print("cleanup-on-found OK (swept planted + orphan checkpoints)")


def test_preserve_on_timeout():
    os.environ["ONEPIECE_KANGAROO_CKPT_SECONDS"] = "0.3"  # ensure one gets written
    # Big interval → won't solve in the run → "stopped-timeout" (a pause).
    pz = _pubkey_puzzle(997, 1 << 60, 1 << 61, (1 << 60) + 0x1234567)
    st = huntmod.run_hunt(pz, sentence="keepme", intensity=1,
                          max_seconds=2, check_balance=False)
    assert st["status"] == "stopped-timeout", f"expected timeout, got {st['status']}"
    left = glob.glob(_ckpt_glob(997, "keepme"))
    assert left, "checkpoint was wrongly deleted on a pause — resume would break"
    print(f"preserve-on-timeout OK ({len(left)} checkpoint kept for resume)")


if __name__ == "__main__":
    test_cleanup_on_found()
    test_preserve_on_timeout()
