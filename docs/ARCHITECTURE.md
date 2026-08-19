# Architecture

## Four design principles

1. **Minimize compute.** The way to win is to burn fewer resources, not more.
2. **Random guessing is most efficient**, because we never coordinate over a network (reasoning below).
3. **Use almost no memory.** We do not accumulate a visited-set to avoid duplicates. A seed plus a counter is enough.
4. **Silence the network.** The win check is offline, and the only outbound call is one balance check per hour.

## Why random is "most efficient"

For a single searcher against a uniformly-placed target, sequential and random scanning have the same expected time. The difference appears when many people search without coordination.

- Sequential scanning makes everyone start at the bottom of the range and overlap the same water, wasting collective coverage.
- Random start points disperse each person into different regions and maximize the union of coverage, with no coordination and no shared server.
- This project's ethic is to use no network. So in an uncoordinated world the optimum is for each searcher to disperse from a different random seed, which is exactly the seed mechanism.

## The seed: one sentence becomes your own ocean

```
sentence  ──SHA-256──▶  seed (256-bit)  ──▶  PRNG(seed, counter)  ──▶  stream of random start points
"I will be the pirate king"    3f9a...e21     counter-mode SHA-256          points inside [2^(N-1), 2^N)
```

1. The user writes one meaningful sentence (a One Piece line, a personal motto, anything).
2. `seed = SHA-256(sentence)`, a deterministic 256-bit value.
3. That seed keys a counter-based PRNG (counter-mode SHA-256, so it stays in the standard library). Mapping the i-th output into the puzzle range gives the i-th random start point.
4. From each start point, scan only a short stride (a few million contiguous keys). Pure per-key randomness throws away the incremental elliptic-curve point-addition speedup and is slow. "Random start plus short sequential stride" captures both dispersion and speed. Stride length is configurable, small by default.

Same sentence means same seed and same stream, so it is fully reproducible and resumable. A different person means a different sentence and a different ocean. Collisions between people are astronomically rare and harmless anyway (it's a lottery).

## Lightweight state = seed + counter (no duplicates, near-zero memory)

This is the heart of "don't spend memory to avoid duplicate searching."

Remembering every visited point would take gigabytes and be pointless. Instead we use the fact that the stream is deterministic in (seed, counter).

- Advancing the counter monotonically guarantees you never revisit a point within your own run. No visited-set, no bloom filter.
- Resume means reloading the counter and continuing. The memory cost of dedup is zero.

The stored state is one tiny JSON (a few hundred bytes).

```json
{
  "puzzle": 71,
  "seed_hash": "3f9a...e21",
  "sentence_hint": "I will be the…",
  "counter": 500000,
  "keys_tried": 2000000000000,
  "started_at": "2026-08-20T03:00:00+09:00",
  "last_at":    "2026-08-20T05:00:00+09:00"
}
```

We also keep a local registry of previously-used seeds, so a new session does not accidentally reuse the same sentence and region, or can deliberately continue. That is what "the thing stored locally is basically your previously-searched seed" means.

Resume is triggered by the sentence, not by a separate flag. Typing the same sentence again produces the same `seed_hash`, which matches your local state file and picks the counter up exactly where it left off. A different sentence starts fresh in a new ocean.

## Search modes

- **Address-only** (#71 etc., public key hidden): brute force. From a start point, derive key, public key, and address hash, then compare offline to the target.
- **Public-key exposed** (140, 145, 150, 155, 160): Pollard's Kangaroo. When the public key is known and the key lies in a known interval, this finds it in about `2*sqrt(interval)` group operations instead of scanning the whole interval. It is a pseudorandom walk by nature, so it meshes cleanly with the "random jump" UX; the seed fixes each herd's jumps and starting offsets. Kangaroo does keep a bounded table of distinguished points: that memory is the algorithmic price of the sqrt speedup, not a duplicate-avoidance cache, and it is capped so memory stays bounded. (On the real intervals, 2^134 and up, it still never finishes. The odds are unchanged.)

## Network policy: the single outbound call

- The win check needs no network. Whether a generated key's address equals the target is a local comparison. Knowing the moment you find it costs zero internet.
- The only outbound call is the target address's balance, once per hour. It uses `mempool.space` by default and falls back to `blockstream.info`, then `blockchain.info`, on error or timeout (all keyless free APIs; see `data/puzzles.json` for the exact endpoints and how to read each one). Its purpose is not odds but "is there still a reason to keep running." If someone solved it first, or the creator withdrew, the balance goes to zero.
- Point it at your own node or Electrum and this tool opens zero outbound calls of its own (your node's own chain sync is separate).
- The interval may only be lengthened (quieter); a minimum interval is enforced, so it cannot be shortened.

## Dashboard grid

- Partition the keyspace `[2^(N-1), 2^N)` into `C` equal cells. Color only the cells your scanned start and stride fall into.
- No matter how long it runs, the screen stays almost entirely dark. It is a device to show that what we've searched is one drop in the ocean.
- Also shown: elapsed time, keys/sec, cumulative keys, "at this rate, X years to finish," and the last balance-check time.
- Served on `localhost` by polling the state file only (read-only, network-independent).

## Engine

- **Pure-Python standard library.** `git clone`, then `python3 -m onepiece …`. Nothing to compile, no dependencies, no API keys. It runs anywhere `python3` runs, which is the strongest form of the "leftover home PC" idea. Correctness is guarded by self-tests (`onepiece/crypto.py` reproduces puzzle #1's known address; `tests/test_found.py` recovers a planted key end to end).
- **Intensity = worker processes.** The 1-10 dial maps to how many CPU cores the hunt uses (leaving one free for you), via `multiprocessing`. Each worker searches its own seeded region so they never overlap.
- **Speed is deliberately not the point.** A native core (Rust, or GPU) would not change the odds, which are effectively zero. A faster path may be added later as an optional extra, never a requirement.
