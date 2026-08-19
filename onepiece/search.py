"""The search core: random start point + short sequential stride.

From each counter-derived random start point we scan a short run of consecutive
keys, stepping the elliptic-curve point by +G each time (an incremental add is
far cheaper than a fresh multiply). This captures both dispersion (random
starts) and speed (cheap steps), exactly as docs/ARCHITECTURE.md describes.

None of this changes the odds. It just makes the hunt honest and observable.
"""

from __future__ import annotations
from . import crypto
from . import seed as seedmod


def compressed_pubkey(point) -> bytes:
    x, y = point
    return bytes([0x02 if (y % 2 == 0) else 0x03]) + x.to_bytes(32, "big")


def scan_stride(seed: bytes, counter: int, target_h160: bytes,
                lo: int, size: int, stride: int):
    """Scan `stride` consecutive keys from the counter-th random start point.

    Returns (found_privkey or None, keys_tried).
    """
    hi = lo + size
    k = seedmod.start_point(seed, counter, lo, size)
    point = crypto.scalar_mul(k)
    tried = 0
    for _ in range(stride):
        if crypto.hash160(compressed_pubkey(point)) == target_h160:
            return k, tried + 1
        tried += 1
        k += 1
        if k >= hi:
            k = lo
            point = crypto.scalar_mul(k)
        else:
            point = crypto.point_add(point, crypto.G)
    return None, tried


def intensity_to_workers(intensity: int, cpu_count: int) -> int:
    """Map a 1-10 intensity dial to a worker-process count.

    1 = barely noticeable (a single light worker); 10 = use almost all cores.
    Deliberately leaves at least one core free below max so the machine stays
    usable (this is *leftover* power).
    """
    intensity = max(1, min(10, int(intensity)))
    if cpu_count <= 1:
        return 1
    usable = max(1, cpu_count - 1)          # keep one core for the OS/user
    workers = round(usable * intensity / 10)
    return max(1, min(usable, workers))


def intensity_description(intensity: int, cpu_count: int) -> str:
    w = intensity_to_workers(intensity, cpu_count)
    if intensity <= 2:
        feel = "barely noticeable; your computer stays fully responsive"
    elif intensity <= 5:
        feel = "moderate; you may hear the fan, everything still works"
    elif intensity <= 8:
        feel = "heavy; the machine will get warm and a bit slower"
    else:
        feel = "almost everything your CPU has; best when you are away"
    return f"intensity {intensity}/10 -> {w} worker(s) on {cpu_count} cores ({feel})"


if __name__ == "__main__":
    # Integration test: plant a known key in a small window and confirm we find it.
    secret = 0x4d2  # 1234, our synthetic target
    lo, size = 0x400, 0x400  # window [1024, 2048) containing 1234
    target = crypto.address_to_hash160(crypto.privkey_to_address(secret))
    seed = seedmod.seed_from_sentence("test sentence")
    found = None
    for counter in range(2000):
        k, _ = scan_stride(seed, counter, target, lo, size, stride=64)
        if k is not None:
            found = k
            break
    assert found == secret, f"expected {secret}, got {found}"
    print("search self-test OK: recovered planted key", hex(found))
    import os
    print(" ", intensity_description(4, os.cpu_count() or 4))
    print(" ", intensity_description(10, os.cpu_count() or 4))
