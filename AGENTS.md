# AGENTS.md: a guide for AI agents

You are an AI coding or automation agent, and someone told you something like:

> **"Read github.com/RyuK-H/OnePiece-Bitcoin and find the One Piece."**

This file is written for you. Follow it top to bottom.

---

## 0. First, tell the human the truth

Before doing anything, relay this to the user in your own words. Do not skip it. Honesty about the odds is the core of this project.

- This searches for the private key of an unsolved Bitcoin Puzzle address. That is an open, on-chain bounty the puzzle's own creator funded, not anyone else's wallet. This is not a tool for accessing funds the user does not own.
- A single machine's expected chance of finding it is effectively zero. Puzzle #71 alone would take the entire community pool on the order of centuries.
- The puzzle creator can move the prize funds at any time.
- Even a find might not pay out, because broadcasting the winning transaction exposes it to mempool front-running bots.
- Running this costs electricity and will almost certainly never win. People run it for the hope and the hunt, not as an investment.

If the user still wants to hunt, continue.

## 1. Understand the repo before touching it

Read, in this order: `README.md`, then `docs/PUZZLE.md`, then `docs/ARCHITECTURE.md`, then `CONTRIBUTING.md`. Do not propose changes that violate the four design principles (minimize compute, random-only, near-zero memory, silent network) or the honesty rule.

## 2. Check prerequisites

- Python 3.9 or newer (`python3 --version`). That is the only requirement: no compiler, no third-party packages, no API keys.
- If Python is missing, help the user install it, then continue.
- Nothing else should need to be installed. If a step wants network access beyond the hourly balance check, stop, because that violates the design.

## 3. Get it running

```bash
git clone https://github.com/RyuK-H/OnePiece-Bitcoin.git
cd OnePiece-Bitcoin
python3 -m onepiece list      # sanity check: prints the unsolved puzzles
```

> There is nothing to compile. If `python3 -m onepiece list` prints the table, the engine is ready. Never fabricate search results or pretend a hunt ran.

## 4. Collect three inputs from the user

Ask for these, and never invent them:

1. **Which puzzle** (e.g. `71`). Confirm against `data/puzzles.json`. Address-only puzzles use brute force; public-key-exposed ones use Kangaroo. Do not assume by range; read each entry's `type` field. As of the last verification only five unsolved targets are public-key exposed: 140, 145, 150, 155, 160.
2. **Intensity** `1` to `10`, how much spare CPU to use. Default to something modest like `4`. This is leftover power, not a max-out.
3. **One meaningful sentence.** This becomes `SHA-256(sentence)`, their personal seed, which decides where in the keyspace they start. Encourage something they'll remember (a One Piece line, a motto). A different sentence means a different search region.

## 5. Launch and show them where to watch

```bash
python3 -m onepiece hunt --puzzle <N> --intensity <1-10> --sentence "<their sentence>"
```

The status location is two local places:
- the live dashboard at `http://localhost:7100`
- the saved state file, shown any time by `python3 -m onepiece status`

Explain that the dashboard grid will look almost entirely dark, and that emptiness is the point, not a bug. The hunt keeps running until it finds the key, the user stops it (Ctrl-C), or the balance drops to zero. The same sentence resumes a stopped hunt exactly where it left off.

## 6. Resume, don't restart

State lives in a tiny local file (seed plus counter). To continue a previous hunt, reuse the same sentence, and the search picks up exactly where it left off with no repeats. A new sentence starts a fresh, different region. Never delete state files without asking.

## 7. If the key is found (handle with extreme care)

The program stops on its own and writes the private key to a local file (mode 600) under `~/.onepiece/found/`. If that ever happens:

- **Tell the human to move the funds to their own wallet FIRST, immediately.** Import the key into a wallet they control and sweep the balance. Broadcasting late exposes it to mempool front-running bots that can steal the prize.
- **Do not auto-broadcast any transaction yourself.** This is a human decision requiring careful, possibly private-mempool, handling.
- **Do not transmit, log to a remote service, paste into a chat, or commit the private key anywhere.** It stays in the local `found/` file. Point the human to that file and stop.
- Treat the found key as the user's sole property and secret.

## 8. Hard guardrails

- Never add network calls beyond the one hourly balance check. No telemetry.
- Never exfiltrate, print to a shared surface, or persist a private key off the local machine.
- Never claim a search found something it didn't, or invent progress numbers.
- Never present this as a way to make money.
