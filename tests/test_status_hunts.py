"""list_hunts() must return hunt states only, never Kangaroo checkpoints.

Kangaroo checkpoints live in the same directory as hunt states but hold a
different shape (dp/ops/tame/wild, no "puzzle" or "seed_hash"). When they leak
into list_hunts(), `onepiece status` dies with KeyError: 'puzzle' on any
public-key-exposed hunt (140, 145, 150, 155, 160).
Run: python3 tests/test_status_hunts.py
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TMP = tempfile.mkdtemp(prefix="onepiece-status-")
os.environ["ONEPIECE_HOME"] = _TMP  # isolate BEFORE importing onepiece

from onepiece import state as statemod   # noqa: E402

SEED = "6873a1e8" + "0" * 56


def _hunt_state():
    return {"puzzle": 140, "seed_hash": SEED, "sentence_hint": "a sentence",
            "status": "running", "keys_tried": 21184512, "method": "kangaroo",
            "worker_counters": [0, 0], "started_at": "2026-08-20T00:00:00+0900"}


def _checkpoint():
    # The real shape written per worker: no "puzzle", no "seed_hash".
    return {"tame": [[1, 2]], "wild": [[3, 4]], "dp": {"5": 6}, "ops": 12345}


def main():
    try:
        statemod.save(statemod.state_path(140, SEED), _hunt_state())
        for w in (0, 1):
            statemod.save(statemod.kangaroo_ckpt_path(140, SEED, w), _checkpoint())

        # All three files are .json in HUNTS_DIR; only one is a hunt.
        on_disk = [n for n in os.listdir(statemod.HUNTS_DIR) if n.endswith(".json")]
        assert len(on_disk) == 3, on_disk

        hunts = statemod.list_hunts()
        assert len(hunts) == 1, f"checkpoints leaked into list_hunts(): {hunts}"

        # What cmd_status indexes directly must always be present.
        for st in hunts:
            assert "puzzle" in st, st
            assert "seed_hash" in st, st
        assert hunts[0]["puzzle"] == 140

        print("status/list_hunts checkpoint-filter test OK")
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)


if __name__ == "__main__":
    main()
