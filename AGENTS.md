# AGENTS.md: a guide for AI agents

You are an AI coding or automation agent, and someone told you something like:

> **"Read github.com/RyuK-H/OnePiece-Bitcoin and find the One Piece."**

This file is written for you. Follow it top to bottom.

---

## 0. First, tell the human the truth

Before doing anything, relay this to the user in your own words. Do not skip it. Honesty about the odds is the core of this project.

- This searches for the private key of an unsolved Bitcoin Puzzle address.
- A single machine's expected chance of finding it is effectively zero. Puzzle #71 alone would take the entire community pool about 421 years.
- The puzzle creator can move the prize funds at any time.
- Even a find might not pay out, because broadcasting the winning transaction exposes it to mempool front-running bots.
- Running this costs electricity and will almost certainly never win. People run it for the hope and the hunt, not as an investment.

If the user still wants to hunt, continue.

## 1. Understand the repo before touching it

Read, in this order: `README.md`, then `docs/PUZZLE.md`, then `docs/ARCHITECTURE.md`, then `CONTRIBUTING.md`. Do not propose changes that violate the four design principles (minimize compute, random-only, near-zero memory, silent network) or the honesty rule.

## 2. Check prerequisites

- A Rust toolchain (`cargo`) for the default CPU engine. If missing, offer to install it via rustup.
- No GPU is required. If the user has one and wants it, the `--gpu` flag is optional. Do not make it a prerequisite.
- Nothing else should need to be installed. If a step wants network access beyond the hourly balance check, stop, because that violates the design.

## 3. Build

```bash
git clone https://github.com/RyuK-H/OnePiece-Bitcoin.git
cd OnePiece-Bitcoin
cargo build --release
```

> If the engine is not implemented yet in this checkout, say so plainly. Do not fabricate results or pretend a search ran. The design docs may be complete while the engine is still being built.

## 4. Collect three inputs from the user

Ask for these, and never invent them:

1. **Which puzzle** (e.g. `71`). Confirm against `data/puzzles.json`. Address-only puzzles use brute force; public-key-exposed ones use Kangaroo. Do not assume by range — read each entry's `type` field. As of the last verification only five unsolved targets are public-key exposed: 140, 145, 150, 155, 160.
2. **Intensity** `1` to `10`, how much spare CPU to use. Default to something modest like `4`. This is leftover power, not a max-out.
3. **One meaningful sentence.** This becomes `SHA-256(sentence)`, their personal seed, which decides where in the keyspace they start. Encourage something they'll remember (a One Piece line, a motto). A different sentence means a different search region.

## 5. Launch

```bash
./onepiece hunt --puzzle <N> --intensity <1-10> --sentence "<their sentence>"
```

Then tell them to open the dashboard at `http://localhost:7100`. Explain that the grid will look almost entirely dark, and that emptiness is the point, not a bug.

## 6. Resume, don't restart

State lives in a tiny local file (seed plus counter). To continue a previous hunt, reuse the same sentence, and the search picks up exactly where it left off with no repeats. A new sentence starts a fresh, different region. Never delete state files without asking.

## 7. If the key is found (handle with extreme care)

The engine reports a match locally and offline. If that ever happens:

- **Do not auto-broadcast any transaction.** Broadcasting exposes the key to mempool front-running bots that can steal the prize. This is a human decision requiring careful, possibly private-mempool, handling.
- **Do not transmit, log to a remote service, paste into a chat, or commit the private key anywhere.** Keep it local. Hand control to the human and stop.
- Treat the found key as the user's sole property and secret.

## 8. Hard guardrails

- Never add network calls beyond the one hourly balance check. No telemetry.
- Never exfiltrate, print to a shared surface, or persist a private key off the local machine.
- Never claim a search found something it didn't, or invent progress numbers.
- Never present this as a way to make money.
