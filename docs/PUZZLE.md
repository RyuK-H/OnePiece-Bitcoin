# The Puzzle: history, intent, and risks

## What this is

The **Bitcoin Puzzle** (a.k.a. the "1000 BTC Challenge") is a real on-chain bounty created on **15 January 2015** by an anonymous author. The rule is brutally simple.

- The private key for puzzle `N` is a single number in exactly `[2^(N-1), 2^N)`.
- So puzzle 1 has a single candidate key (instant), puzzle 71's key lies in a 2⁷⁰-wide range, and puzzle 160's in a 2¹⁵⁹-wide range.
- Each puzzle maps to one Bitcoin address, and whoever finds that address's private key first takes the prize.

Keys are understood to be placed randomly within their range. The low numbers were all solved long ago (minutes to hours on a laptop). Each higher number doubles the space until it hits a wall that all of humanity's compute cannot touch. That staircase is a living benchmark of "how many bits are crackable with today's technology."

## Current state (verified 2026-08-20)

- **83 of 160 solved, 77 unsolved**, holding **~903 BTC** in total. Every unsolved address was re-checked on-chain on this date.
- Lowest unsolved address-only target **#71 (~7.1 BTC, 2⁷⁰)**. Measured in mid-2026, a public community pool had scanned well under 1% of the keyspace (about 0.9% by its own telemetry), and at that speed the whole pool combined would need on the order of centuries to finish (a commonly cited figure is ~**421 years**). These are rough projections of effort, not predictions that it gets solved on any date, and they shift with assumed pool speed.
- These numbers move. Check each address's live balance yourself via the explorer links in the [README fleet table](../README.md#the-unsolved-fleet).

## The creator's intent (documented facts vs. common understanding)

**Documented facts**

- At creation in 2015, each address held only a small amount (roughly `N × 0.001 BTC` for puzzle N).
- Later, notably a large top-up in 2019, the prizes grew dramatically (the concentrated puzzles reaching roughly `N/10 BTC`). These top-up transactions themselves prove the creator can move the funds.
- Spending from some addresses exposed their public keys. That is why a few unsolved puzzles (for example 140, 145, 150, 155, 160) have visible public keys, making Kangaroo viable, while re-funded, untouched addresses like #71 show only the address hash.

**Widely understood** (the creator's exact words are limited, so this is the gist only)

- It is not a scam but a demonstration of Bitcoin keyspace security, proving with money that "low bits are findable, high bits are effectively impossible."
- Keys are random within range, and there is no bit-targeted trap or backdoor known.

> Note: we paraphrase the intent rather than quote the creator. Verified original messages (with sources) are welcome as contributions.

## Risks: all of them, stated plainly

This project's ethic is to never lie about the odds, so it hides no risk.

1. **The creator can withdraw the funds at any time.** As the 2019 top-up shows, the author (or key holder) has already demonstrated the ability to move these outputs. If the prize goes to zero one day, no one can stop it.
2. **Splitting the search space does not meaningfully raise your odds.** 2⁷⁰ is a speck you could scratch at for a lifetime and barely dent. This tool's "region splitting" is a visualization device, not an odds device.
3. **Even a find might not pay out.** Broadcasting a transaction signed with the winning key exposes it to mempool front-running bots, which can replace it (RBF/sniping) with a higher fee and steal the same output. This is a known, real threat in the puzzle community.
4. **In the end the probability is "50%."** A joke that is also true. You win, or you don't. That two-sided coin is this project's identity.

## So why do it

For the same reason a solo miner still dreams every ten minutes against million-year odds. This is not about the money. It is the emotional reward of hope and challenge. OnePiece Bitcoin makes that hope local, honest, and visible. Just as Gol D. declared the One Piece is real before anyone had found it, the treasure exists. All that's left is whether you find it.

---

<sub>This project is an unofficial, fan-made homage and is not affiliated with, endorsed by, or associated with Shueisha, Toei Animation, or Eiichiro Oda. "One Piece" and related names are trademarks of their respective owners. All artwork in this repository is original.</sub>
