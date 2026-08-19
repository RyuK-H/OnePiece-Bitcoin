"""Orchestrates the hunt: N worker processes, live state, balance checks, and
the found-key handoff. This is what `onepiece hunt` and the wizard drive.

The number of workers is the "how much CPU" dial. Each worker searches its own
seeded region so they never overlap, and progress is a few counters we persist
so you can stop and resume without ever repeating.
"""

from __future__ import annotations
import multiprocessing as mp
import os
import time

from . import crypto, state as statemod
from . import seed as seedmod
from .search import scan_stride, intensity_to_workers
from .puzzles import Puzzle

STRIDE = 2000  # keys scanned per counter step, per worker


def _worker(w, seed, target_h160, lo, size, stride,
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


def years_to_exhaust(keyspace_size: int, rate_per_sec: float) -> float:
    if rate_per_sec <= 0:
        return float("inf")
    return keyspace_size / rate_per_sec / (3600 * 24 * 365)


def run_hunt(puzzle: Puzzle, sentence: str, intensity: int,
             balance_interval: int = 3600, max_seconds: float | None = None,
             on_status=None) -> dict:
    """Run the hunt until the key is found, interrupted, or max_seconds elapses.

    Returns the final state dict. Pure address-only brute force for now;
    public-key-exposed puzzles will get a Kangaroo path later.
    """
    seed = seedmod.seed_from_sentence(sentence)
    seed_hex = seedmod.seed_hash_hex(seed)
    target_h160 = crypto.address_to_hash160(puzzle.address)
    lo, size = puzzle.keyspace_lo, puzzle.keyspace_size
    cpu = os.cpu_count() or 4
    workers = intensity_to_workers(intensity, cpu)

    path = statemod.state_path(puzzle.n, seed_hex)
    prev = statemod.load(path)
    if prev and prev.get("seed_hash") == seed_hex and len(prev.get("worker_counters", [])) == workers:
        start_counters = list(prev["worker_counters"])
        keys_before = int(prev.get("keys_tried", 0))
        started_at = prev.get("started_at", statemod.now_iso())
    else:
        start_counters = [0] * workers
        keys_before = 0
        started_at = statemod.now_iso()

    ctx = mp.get_context("spawn")
    found_evt = ctx.Event()
    keys_tried = ctx.Value("Q", 0)
    counters = ctx.Array("Q", start_counters)
    result_q = ctx.Queue()

    procs = []
    for w in range(workers):
        p = ctx.Process(target=_worker, args=(
            w, seed, target_h160, lo, size, STRIDE,
            start_counters[w], keys_tried, counters, found_evt, result_q))
        p.daemon = True
        p.start()
        procs.append(p)

    st = {
        "puzzle": puzzle.n,
        "address": puzzle.address,
        "type": puzzle.type,
        "seed_hash": seed_hex,
        "sentence_hint": sentence[:12] + ("…" if len(sentence) > 12 else ""),
        "intensity": intensity,
        "workers": workers,
        "keyspace_lo": lo,
        "keyspace_hi": puzzle.keyspace_hi,
        "worker_counters": list(start_counters),
        "keys_tried": keys_before,
        "started_at": started_at,
        "last_at": statemod.now_iso(),
        "status": "running",
        "found": None,
        "last_balance": None,
    }
    statemod.save(path, st)

    t0 = time.time()
    last_balance_t = t0  # first balance check happens after one interval, not at t=0
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
            st["worker_counters"] = list(counters)
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
        # Verify before celebrating.
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
