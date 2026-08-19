"""Command line for OnePiece Bitcoin.

  onepiece list                       show the unsolved puzzles and pick one
  onepiece start                      friendly interactive wizard (non-developers)
  onepiece hunt --puzzle N --intensity K --sentence "..."   run a hunt
  onepiece status                     where things stand
  onepiece dashboard                  open the read-only local dashboard

The tool never lies about the odds: a single machine will almost certainly
never win. You run it for the hope and the hunt.
"""

from __future__ import annotations
import argparse
import os
import sys

from . import seed as seedmod
from . import state as statemod
from .puzzles import load_puzzles, get_puzzle
from .search import intensity_description, intensity_to_workers
from .hunt import run_hunt
from .dashboard import serve_in_thread

DEFAULT_PORT = 7100


def _status_location(state_path: str, port: int) -> str:
    return (f"  dashboard:  http://localhost:{port}\n"
            f"  state file: {state_path}")


def cmd_list(args):
    puzzles = load_puzzles()
    print("Unsolved Bitcoin Puzzles you can hunt:\n")
    print(f"  {'#':>4}  {'type':<15} {'prize(BTC)':>11}  difficulty")
    print("  " + "-" * 48)
    for p in puzzles:
        print(f"  {p.n:>4}  {p.type:<15} {p.balance_btc:>11.4f}  {p.difficulty_label()}")
    print("\nPick one. More money means harder AND more competitors hunting it,")
    print("but nothing stops it from being you who finds it. It probably won't be")
    print("(a single machine's odds are effectively zero) — that honesty is the point.")
    print('\nNot sure which to pick or how hard to run? Ask your own AI agent to')
    print("help you decide — that's encouraged.\n")


def _run(puzzle_n: int, sentence: str, intensity: int, port: int,
         max_seconds, no_dashboard: bool, balance_interval: int):
    try:
        p = get_puzzle(puzzle_n)
    except KeyError:
        print(f"Puzzle #{puzzle_n} is not in the unsolved list (it may be solved, or invalid).")
        print("Run  python3 -m onepiece list  to see the puzzles you can hunt.")
        return 1
    if not sentence or not sentence.strip():
        print("A meaningful sentence is required. It seeds your search region.")
        return 1
    if not (1 <= intensity <= 10):
        clamped = max(1, min(10, intensity))
        print(f"Intensity {intensity} is out of range; using {clamped} (valid range is 1-10).")
        intensity = clamped
    method = "Kangaroo" if p.type == "pubkey-exposed" else "brute force"
    seed_hex = seedmod.seed_hash_hex(seedmod.seed_from_sentence(sentence))
    path = statemod.state_path(p.n, seed_hex)
    cpu = os.cpu_count() or 4
    workers = intensity_to_workers(intensity, cpu)

    print(f"\n🏴 Hunting puzzle #{p.n} ({p.address}) via {method}")
    print(f"   {intensity_description(intensity, cpu)}")
    print(f"   your sentence seeds region {seed_hex[:16]}… (same sentence = resume)")
    if not no_dashboard:
        try:
            serve_in_thread(path, port)
            print(f"\n📺 Live status:\n{_status_location(path, port)}")
        except OSError as e:
            print(f"(dashboard could not start on port {port}: {e})")
    print("\nPress Ctrl-C to stop. Your progress is saved; the same sentence resumes.\n")

    def on_status(st):
        rate = st.get("rate_per_sec", 0)
        sys.stdout.write(
            f"\r  keys tried: {st['keys_tried']:>18,}   {rate:>10,.0f} keys/s   "
            f"workers: {st['workers']}   status: {st['status']}   ")
        sys.stdout.flush()

    st = run_hunt(p, sentence, intensity, balance_interval=balance_interval,
                  max_seconds=max_seconds, on_status=on_status)
    print()  # newline after the status line

    if st["status"] == "found":
        print("\n" + "=" * 60)
        print("  🎉 KEY FOUND. This is real. Act now, in this order:")
        print(f"  1. Open the key file (kept local, mode 600):\n     {st['found']['key_file']}")
        print("  2. Import the key into a wallet YOU control and move the funds")
        print("     to your own address IMMEDIATELY. Do not paste it anywhere online.")
        print("  3. Broadcasting late risks mempool front-running bots stealing it.")
        print("=" * 60)
    elif st["status"] == "stopped-empty":
        print("\nThe target balance is now 0 — it was solved or withdrawn. Stopped.")
    else:
        print(f"\nStopped ({st['status']}). Progress saved. Re-run with the same sentence to resume.")
        print(_status_location(path, port))
    return 0


def cmd_hunt(args):
    return _run(args.puzzle, args.sentence, args.intensity, args.port,
                args.max_seconds, args.no_dashboard, args.balance_interval)


def cmd_start(args):
    print("🏴 OnePiece Bitcoin — let's set up your hunt.\n")
    print("You are about to search for the private key of an unsolved Bitcoin")
    print("Puzzle address. Be clear-eyed: one machine's chance of winning is")
    print("effectively zero, the creator could withdraw the prize, and even a")
    print("find can be sniped when you broadcast. People do this for the hunt.\n")
    cmd_list(args)
    try:
        puzzle_n = int(input("Which puzzle number do you want to hunt? ").strip())
        cpu = os.cpu_count() or 4
        print("\nHow hard should your computer work? (this is spare power)")
        for i in (1, 3, 5, 8, 10):
            print(f"   {i:>2} = {intensity_description(i, cpu)}")
        intensity = int(input("Pick an intensity 1-10: ").strip())
        print("\nWrite one meaningful sentence. It becomes your secret starting point,")
        print("so no one else searches exactly where you do (a One Piece line, a motto…).")
        sentence = input("Your sentence: ").strip()
    except (ValueError, EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return 1
    if not sentence:
        print("A sentence is required.")
        return 1
    return _run(puzzle_n, sentence, intensity, args.port,
                None, args.no_dashboard, args.balance_interval)


def cmd_status(args):
    hunts = statemod.list_hunts()
    if not hunts:
        print("No hunts yet. Start one with:  onepiece start")
        return 0
    print("Your hunts:\n")
    for st in hunts:
        print(f"  #{st['puzzle']} [{st.get('status','?')}] "
              f"keys={st.get('keys_tried',0):,} "
              f"seed={st['seed_hash'][:8]} sentence=\"{st.get('sentence_hint','')}\"")
        if st.get("found"):
            print(f"     🎉 key file: {st['found']['key_file']}")
    print(f"\nState files live in: {statemod.HUNTS_DIR}")
    return 0


def cmd_dashboard(args):
    hunts = statemod.list_hunts()
    if not hunts:
        print("No hunt to show yet. Run:  onepiece start")
        return 0
    st = hunts[-1]
    path = statemod.state_path(st["puzzle"], st["seed_hash"])
    serve_in_thread(path, args.port)
    print(f"Dashboard for puzzle #{st['puzzle']}: http://localhost:{args.port}")
    print("Ctrl-C to stop the dashboard.")
    try:
        import time
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


def build_parser():
    ap = argparse.ArgumentParser(prog="onepiece", description="Local hunt for the unsolved Bitcoin Puzzle.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="show unsolved puzzles").set_defaults(func=cmd_list)

    s = sub.add_parser("start", help="friendly interactive wizard")
    s.add_argument("--port", type=int, default=DEFAULT_PORT)
    s.add_argument("--no-dashboard", action="store_true")
    s.add_argument("--balance-interval", type=int, default=3600)
    s.set_defaults(func=cmd_start)

    h = sub.add_parser("hunt", help="run a hunt non-interactively")
    h.add_argument("--puzzle", type=int, required=True)
    h.add_argument("--intensity", type=int, default=4)
    h.add_argument("--sentence", required=True)
    h.add_argument("--port", type=int, default=DEFAULT_PORT)
    h.add_argument("--no-dashboard", action="store_true")
    h.add_argument("--max-seconds", type=float, default=None)
    h.add_argument("--balance-interval", type=int, default=3600)
    h.set_defaults(func=cmd_hunt)

    st = sub.add_parser("status", help="show where hunts stand")
    st.set_defaults(func=cmd_status)

    d = sub.add_parser("dashboard", help="open the read-only local dashboard")
    d.add_argument("--port", type=int, default=DEFAULT_PORT)
    d.set_defaults(func=cmd_dashboard)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
