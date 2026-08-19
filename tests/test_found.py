"""Integration test: plant a known key in a small puzzle and confirm the full
found -> stop -> save path works end to end. Run: python3 tests/test_found.py
"""
import os
import sys
import tempfile

# Isolate state in a temp dir BEFORE importing onepiece (state reads env at import).
_TMP = tempfile.mkdtemp(prefix="onepiece-test-")
os.environ["ONEPIECE_HOME"] = _TMP
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from onepiece import crypto                    # noqa: E402
from onepiece.puzzles import Puzzle            # noqa: E402
from onepiece.hunt import run_hunt             # noqa: E402


def main():
    secret = 0x1234  # 4660, lies in [2^12, 2^13)
    addr = crypto.privkey_to_address(secret)
    puzzle = Puzzle(n=13, type="address-only", address=addr, balance_btc=0.0,
                    public_key=None, keyspace_lo=1 << 12, keyspace_hi=1 << 13)

    st = run_hunt(puzzle, sentence="find the planted key", intensity=1,
                  balance_interval=10 ** 9, max_seconds=60)

    assert st["status"] == "found", f"expected found, got {st['status']}"
    kf = st["found"]["key_file"]
    assert os.path.exists(kf), "key file missing"
    with open(kf) as f:
        body = f.read()
    assert addr in body and f"{secret:064x}" in body, "key file content wrong"
    mode = oct(os.stat(kf).st_mode & 0o777)
    assert mode == "0o600", f"key file should be 600, is {mode}"
    print("found-path integration test OK")
    print("  recovered address:", addr)
    print("  key file (600):", kf)


if __name__ == "__main__":
    main()
