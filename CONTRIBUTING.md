# Contributing

Thank you for wanting to sail with us. This project has an unusual goal, so it has unusual rules. Please read them before opening a PR.

## The prime directives

These are not style preferences. A PR that violates them will be declined no matter how clever it is.

**1. Minimize compute. The hunt is won by burning less.**

The odds do not improve with more work. Only the electricity bill does. Prefer changes that do the same search with fewer cycles. Micro-optimizations to the inner loop (batch EC additions, endianness tricks, avoiding allocations) are welcome. "Let's add a bigger thread pool to go faster" is not a feature, because the odds are unchanged and the concept is leftover power.

**2. Random is the strategy. Do not add coordination.**

Because we use no network, random dispersion from a per-user seed is the optimal collective strategy. Do not add pools, shared range servers, "claim a range" registries, or any phone-home coordination. If your idea needs the searchers to talk to each other, it belongs in a different project.

**3. Do not spend memory to avoid duplicates.**

Duplicate avoidance is already free. The `(seed, counter)` stream is deterministic and monotonic, so advancing the counter never revisits a point. Do not introduce visited-sets, bloom filters, on-disk indexes of tried keys, or anything whose memory grows with keys tried. State must stay a few hundred bytes. (The one allowed exception is the Kangaroo engine's distinguished-point table: that memory buys the algorithm's sqrt speedup on public-key-exposed puzzles and is capped. This rule is about not adding memory to the brute-force path.)

**4. Keep the network silent.**

The win check is offline. The only permitted outbound call is the once-per-hour balance check, and it must remain lengthenable to infinity, so own-node and fully-offline mode keep working. No telemetry, no analytics, no auto-update pings, no "anonymous stats." Ever.

## Honesty rule

This project never lies about the odds. Any copy, UI, or doc you add must not imply that this tool meaningfully improves your chance of winning, must not hide the creator-withdrawal risk, and must not dress up the lottery as an investment. The two-sided coin, you win or you don't, stays visible.

## Practical

- **Puzzle data (`data/puzzles.json`)**: addresses must be verified against at least two independent sources and confirmed to have a nonzero live balance (an unsolved puzzle). Cite your sources in the PR. Never commit an unverified or already-solved address.
- **No secrets, ever.** Do not commit keys, wallet files, or `.env`. If you happen to find a real key, that is yours to handle. It does not belong in a commit.
- Keep PRs focused. One idea per PR.
- Be kind. We are here for the hope, not the flame wars.

By contributing you agree your work is released under the project's [MIT License](LICENSE).
