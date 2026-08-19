"""Orchestrates the hunt: N worker processes, live state, balance checks, and
the found-key handoff. This is what `onepiece hunt` and the wizard drive.

Two engines share the same orchestration:
- address-only puzzles: brute force (random start + short sequential stride)
- public-key-exposed puzzles: Pollard's Kangaroo (onepiece/kangaroo.py)

The number of workers is the "how much CPU" dial. Progress is a few counters we
persist so an address-only hunt can stop and resume without repeating. (A
Kangaroo hunt restarts its herd on resume; its walk is not checkpointed.)
"""

from __future__ import annotations
import multiprocessing as mp
import os
import time

from . import crypto, kangaroo, state as statemod
from . import seed as seedmod
from .search import scan_stride, intensity_to_workers
from .puzzles import Puzzle

STRIDE = 2000          # keys scanned per counter step, per brute-force worker
KANGAROO_BATCH = 4096  # group operations per step, per kangaroo worker


def _brute_worker(w, seed, target_h160, lo, size, stride,
                  start_counter, keys_tried, counters, found_evt, result_q):
    w_seed = seedmod.derive_worker_seed(seed, w)
    counter = start_counter
    while not found_evt.is_set():
        k, tried = scan_stride(w_seed, counter, target_h160, lo, size, stride)
        counter += 1
        counters[w] = counter
        with keys_tried.get_lock():
            keys_tried.value += tried
        if k is not None:
            result_q.put((w, k))
            found_evt.set()
            return


def _kangaroo_worker(w, Qx, Qy, a, b, seed, keys_tried, found_evt, result_q):
    w_seed = seedmod.derive_worker_seed(seed, w)
    solver = kangaroo.KangarooSolver((Qx, Qy), a, b, w_seed)
    while not found_evt.is_set():
        k, ops = solver.step_batch(KANGAROO_BATCH)
        with keys_tried.get_lock():
            keys_tried.value += ops
        if k is not None:
            result_q.put((w, k))
            found_evt.set()
            return


def years_to_exhaust(keyspace_size: int, rate_per_sec: float) -> float:
    if rate_per_sec <= 0:
        return float("inf")
    return keyspace_size / rate_per_sec / (3600 * 24 * 365)


def resume_counters(prev: dict | None, seed_hex: str, workers: int):
    """Decide each worker's start counter when (re)launching a brute-force hunt.

    Worker w searches the stream derived from (seed, w) alone — the total worker
    count never enters derive_worker_seed — so a worker's progress is valid no
    matter how many workers run alongside it. Therefore changing the worker
    count must NOT discard progress: resume every worker we have a counter for,
    start any newly added workers at 0, and preserve counters for workers beyond
    this run's count so that raising it again later resumes them too.

    Returns (start_counters, preserved_extra, keys_before, started_at_or_None).
    """
    if not prev or prev.get("seed_hash") != seed_hex:
        return [0] * workers, [], 0, None
    prev_counters = [int(c) for c in prev.get("worker_counters", [])]
    start_counters = [prev_counters[w] if w < len(prev_counters) else 0
                      for w in range(workers)]
    preserved_extra = prev_counters[workers:]
    return start_counters, preserved_extra, int(prev.get("keys_tried", 0)), prev.get("started_at")


def run_hunt(puzzle: Puzzle, sentence: str, intensity: int,
             balance_interval: int = 3600, max_seconds: float | None = None,
             on_status=None, check_balance: bool = True) -> dict:
    """Run the hunt until the key is found, interrupted, or max_seconds elapses.

    Dispatches to brute force or Kangaroo based on puzzle.type. Returns the
    final state dict.
    """
    seed = seedmod.seed_from_sentence(sentence)
    seed_hex = seedmod.seed_hash_hex(seed)
    lo, size = puzzle.keyspace_lo, puzzle.keyspace_size
    cpu = os.cpu_count() or 4
    workers = intensity_to_workers(intensity, cpu)
    is_kangaroo = puzzle.type == "pubkey-exposed"

    path = statemod.state_path(puzzle.n, seed_hex)

    ctx = mp.get_context("spawn")
    found_evt = ctx.Event()
    keys_tried = ctx.Value("Q", 0)
    result_q = ctx.Queue()

    counters = None
    keys_before = 0
    started_at = statemod.now_iso()
    preserved_extra: list[int] = []
    procs = []

    if is_kangaroo:
        Q = crypto.decompress_pubkey(puzzle.public_key)
        # sanity: the public key must hash to the puzzle's address
        pub = bytes([0x02 if Q[1] % 2 == 0 else 0x03]) + Q[0].to_bytes(32, "big")
        assert crypto.hash160_to_address(crypto.hash160(pub)) == puzzle.address, \
            "public key does not match the puzzle address"
        for w in range(workers):
            p = ctx.Process(target=_kangaroo_worker, args=(
                w, Q[0], Q[1], lo, puzzle.keyspace_hi, seed, keys_tried, found_evt, result_q))
            p.daemon = True
            p.start()
            procs.append(p)
        worker_counters = []
    else:
        target_h160 = crypto.address_to_hash160(puzzle.address)
        prev = statemod.load(path)
        start_counters, preserved_extra, prev_keys, prev_started = \
            resume_counters(prev, seed_hex, workers)
        keys_before = prev_keys
        if prev_started:
            started_at = prev_started
        counters = ctx.Array("Q", start_counters)
        for w in range(workers):
            p = ctx.Process(target=_brute_worker, args=(
                w, seed, target_h160, lo, size, STRIDE,
                start_counters[w], keys_tried, counters, found_evt, result_q))
            p.daemon = True
            p.start()
            procs.append(p)
        worker_counters = list(start_counters) + preserved_extra

    st = {
        "puzzle": puzzle.n,
        "address": puzzle.address,
        "type": puzzle.type,
        "method": "kangaroo" if is_kangaroo else "brute-force",
        "seed_hash": seed_hex,
        "sentence_hint": sentence[:12] + ("…" if len(sentence) > 12 else ""),
        "intensity": intensity,
        "workers": workers,
        "keyspace_lo": lo,
        "keyspace_hi": puzzle.keyspace_hi,
        "worker_counters": worker_counters,
        "keys_tried": keys_before,
        "started_at": started_at,
        "last_at": statemod.now_iso(),
        "status": "running",
        "found": None,
        "last_balance": None,
    }
    statemod.save(path, st)

    t0 = time.time()
    if check_balance:
        # First balance check ~2s in (so the dashboard shows it), then every interval.
        last_balance_t = t0 - balance_interval + 2.0
    else:
        last_balance_t = float("inf")
    found_key = None
    try:
        while True:
            if not result_q.empty():
                _, found_key = result_q.get()
                break
            if found_evt.is_set() and result_q.empty() and not any(p.is_alive() for p in procs):
                break

            now = time.time()
            elapsed = now - t0
            st["keys_tried"] = keys_before + keys_tried.value
            if counters is not None:
                st["worker_counters"] = list(counters) + preserved_extra
            st["last_at"] = statemod.now_iso()
            rate = (st["keys_tried"] - keys_before) / elapsed if elapsed > 0 else 0.0
            st["rate_per_sec"] = round(rate, 1)
            st["years_to_exhaust"] = years_to_exhaust(size, rate)

            if now - last_balance_t >= max(balance_interval, 1):
                last_balance_t = now
                try:
                    from .balance import check_balance_sats
                    sats, src = check_balance_sats(puzzle.address)
                    if sats is not None:
                        st["last_balance"] = {"sat": sats, "checked_at": statemod.now_iso(), "source": src}
                        if sats == 0:
                            st["status"] = "stopped-empty"
                            found_evt.set()
                except Exception:
                    pass

            statemod.save(path, st)
            if on_status:
                on_status(st)

            if max_seconds is not None and elapsed >= max_seconds:
                st["status"] = "stopped-timeout"
                found_evt.set()
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        st["status"] = "stopped-interrupt"
        found_evt.set()

    for p in procs:
        p.join(timeout=2)
        if p.is_alive():
            p.terminate()

    if found_key is not None:
        assert crypto.privkey_to_address(found_key) == puzzle.address
        found_path = statemod.write_found(puzzle.n, found_key, puzzle.address)
        st["status"] = "found"
        st["found"] = {
            "found_at": statemod.now_iso(),
            "address": puzzle.address,
            "key_file": found_path,
        }
    st["last_at"] = statemod.now_iso()
    statemod.save(path, st)
    return st
