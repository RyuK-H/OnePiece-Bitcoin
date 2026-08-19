"""Resume must survive a change in worker count.

Worker w searches the (seed, w)-derived stream, which does not depend on the
total worker count, so raising or lowering the count must keep each existing
worker's progress instead of restarting the whole hunt from zero.
Run: python3 tests/test_resume.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from onepiece.hunt import resume_counters   # noqa: E402

SEED = "a" * 64
OTHER = "b" * 64


def _state(counters, seed=SEED, keys=123, started="2026-08-20T00:00:00+0900"):
    return {"seed_hash": seed, "worker_counters": list(counters),
            "keys_tried": keys, "started_at": started}


def main():
    # Fresh hunt (no prior state) starts everyone at zero.
    start, extra, keys, started = resume_counters(None, SEED, 4)
    assert start == [0, 0, 0, 0] and extra == [] and keys == 0 and started is None

    # Same worker count: resume exactly.
    start, extra, keys, started = resume_counters(_state([10, 11, 12, 13]), SEED, 4)
    assert start == [10, 11, 12, 13] and extra == [] and keys == 123
    assert started == "2026-08-20T00:00:00+0900"

    # Grow 4 -> 9: keep the four, new workers start at zero, nothing preserved.
    start, extra, _, _ = resume_counters(_state([10, 11, 12, 13]), SEED, 9)
    assert start == [10, 11, 12, 13, 0, 0, 0, 0, 0], start
    assert extra == [], extra

    # Shrink 9 -> 4: keep the first four, preserve the rest for a later grow.
    start, extra, _, _ = resume_counters(_state([1, 2, 3, 4, 5, 6, 7, 8, 9]), SEED, 4)
    assert start == [1, 2, 3, 4], start
    assert extra == [5, 6, 7, 8, 9], extra

    # Shrink then grow round-trips: 9 -> 4 (preserve 5) -> 9 recovers all nine.
    shrunk = _state([1, 2, 3, 4], keys=200)
    shrunk["worker_counters"] = [1, 2, 3, 4] + [5, 6, 7, 8, 9]  # what the loop saved
    start, extra, _, _ = resume_counters(shrunk, SEED, 9)
    assert start == [1, 2, 3, 4, 5, 6, 7, 8, 9], start
    assert extra == []

    # A different sentence (different seed) is a different ocean: start fresh.
    start, extra, keys, started = resume_counters(_state([10, 11, 12, 13]), OTHER, 4)
    assert start == [0, 0, 0, 0] and extra == [] and keys == 0 and started is None

    print("resume-across-worker-count test OK")


if __name__ == "__main__":
    main()
