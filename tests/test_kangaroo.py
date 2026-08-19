"""Integration test for the Kangaroo path: a synthetic public-key-exposed
puzzle in a small interval, solved end to end via run_hunt.
Run: python3 tests/test_kangaroo.py
"""
import os
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="onepiece-ktest-")
os.environ["ONEPIECE_HOME"] = _TMP
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from onepiece import crypto                    # noqa: E402
from onepiece.puzzles import Puzzle            # noqa: E402
from onepiece.hunt import run_hunt             # noqa: E402


def main():
    secret = (1 << 24) + 0xABCDE              # in [2^24, 2^25)
    addr = crypto.privkey_to_address(secret)
    pub = crypto.privkey_to_pubkey_compressed(secret).hex()
    puzzle = Puzzle(n=25, type="pubkey-exposed", address=addr, balance_btc=0.0,
                    public_key=pub, keyspace_lo=1 << 24, keyspace_hi=1 << 25)

    st = run_hunt(puzzle, sentence="kangaroo integration", intensity=1,
                  balance_interval=10 ** 9, max_seconds=90)

    assert st["method"] == "kangaroo", st.get("method")
    assert st["status"] == "found", f"expected found, got {st['status']}"
    kf = st["found"]["key_file"]
    assert os.path.exists(kf) and addr in open(kf).read()
    print("kangaroo found-path integration test OK")
    print("  recovered address:", addr)
    print("  key file:", kf)


if __name__ == "__main__":
    main()
