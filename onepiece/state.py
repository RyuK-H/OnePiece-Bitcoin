"""Tiny local state: seed + counters + progress. A few hundred bytes.

Everything lives under ONEPIECE_HOME (default ~/.onepiece):
    hunts/<puzzle>-<seedhash8>.json   one file per (puzzle, sentence) hunt
    found/puzzle-<n>-<ts>.txt         the private key, if you ever find one (mode 600)

The state file is the "status location": read it (or the dashboard) to see
where a hunt stands. It is deliberately small because resume only needs the
per-worker counters, never a record of visited keys.
"""

from __future__ import annotations
import json
import os
import time

HOME = os.environ.get("ONEPIECE_HOME", os.path.expanduser("~/.onepiece"))
HUNTS_DIR = os.path.join(HOME, "hunts")
FOUND_DIR = os.path.join(HOME, "found")


def _ensure_dirs() -> None:
    os.makedirs(HUNTS_DIR, exist_ok=True)
    os.makedirs(FOUND_DIR, exist_ok=True)


def now_iso() -> str:
    # Local time with offset, e.g. 2026-08-20T04:00:00+09:00
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def state_path(puzzle_n: int, seed_hash_hex: str) -> str:
    return os.path.join(HUNTS_DIR, f"{puzzle_n}-{seed_hash_hex[:8]}.json")


def load(path: str) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save(path: str, data: dict) -> None:
    _ensure_dirs()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)  # atomic


def list_hunts() -> list[dict]:
    if not os.path.isdir(HUNTS_DIR):
        return []
    out = []
    for name in sorted(os.listdir(HUNTS_DIR)):
        if name.endswith(".json"):
            d = load(os.path.join(HUNTS_DIR, name))
            if d:
                out.append(d)
    return out


def write_found(puzzle_n: int, private_key_int: int, address: str) -> str:
    """Persist a found private key locally (mode 600) with urgent guidance.

    Returns the file path. The key is NOT sent anywhere; moving the funds is a
    human decision (see the printed guidance and AGENTS.md).
    """
    _ensure_dirs()
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(FOUND_DIR, f"puzzle-{puzzle_n}-{ts}.txt")
    wif_hint = f"{private_key_int:064x}"
    body = (
        "OnePiece Bitcoin - FOUND KEY\n"
        "============================\n"
        f"puzzle:       #{puzzle_n}\n"
        f"address:      {address}\n"
        f"private key (hex, 32 bytes): {wif_hint}\n"
        f"private key (decimal):       {private_key_int}\n"
        f"found_at:     {now_iso()}\n\n"
        "URGENT, DO THIS FIRST:\n"
        "1. Do NOT paste this key into any website, chat, or remote service.\n"
        "2. Import it into a wallet YOU control and move the funds to your own\n"
        "   address immediately. Broadcasting late exposes it to mempool\n"
        "   front-running bots that can steal the prize.\n"
        "3. Keep this file offline. Anyone with this key owns the coins.\n"
    )
    # Create with restrictive permissions from the start.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(body)
    return path
