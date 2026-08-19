<!-- Thanks for wanting to sail with us. Keep PRs focused: one idea per PR. -->

## What this changes

<!-- A short description of the change and why. -->

## Checklist

- [ ] It respects the four prime directives (minimize compute, random-only, near-zero memory on the brute path, silent network). See `CONTRIBUTING.md`.
- [ ] It respects the honesty rule (does not imply the tool improves the odds, hide the creator-withdrawal risk, or dress the lottery up as an investment).
- [ ] No secrets, keys, or wallet files are committed.
- [ ] If puzzle data changed, addresses are verified against at least two independent sources and have a nonzero live balance.
- [ ] Self-tests pass locally (`python3 -m onepiece.crypto`, `python3 -m onepiece.kangaroo`, `python3 tests/test_found.py`, `python3 tests/test_kangaroo.py`).
