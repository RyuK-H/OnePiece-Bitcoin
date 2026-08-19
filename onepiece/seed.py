"""Seed mechanism: one meaningful sentence becomes your own search region.

    sentence --SHA-256--> seed (256-bit) --> counter-based PRNG --> random start points

The stream is deterministic in (seed, counter): advancing the counter never
revisits a point, so duplicate avoidance is free and costs no memory. Resume =
reload the counter. A different sentence => a different seed => a different ocean.

The PRNG is a counter-mode hash (SHA-256 of seed||counter) rather than ChaCha,
to stay in the standard library while remaining deterministic and well-mixed.
"""

from __future__ import annotations
import hashlib


def seed_from_sentence(sentence: str) -> bytes:
    return hashlib.sha256(sentence.encode("utf-8")).digest()


def seed_hash_hex(seed: bytes) -> str:
    return seed.hex()


def derive_worker_seed(seed: bytes, worker_index: int) -> bytes:
    """A distinct sub-seed per worker so parallel workers never overlap."""
    return hashlib.sha256(seed + b"worker" + worker_index.to_bytes(4, "big")).digest()


def start_point(seed: bytes, counter: int, lo: int, size: int) -> int:
    """The counter-th random start point inside [lo, lo+size)."""
    h = hashlib.sha256(seed + counter.to_bytes(8, "big")).digest()
    return lo + (int.from_bytes(h, "big") % size)
