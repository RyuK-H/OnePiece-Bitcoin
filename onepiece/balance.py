"""Once-per-hour balance check with keyless fallbacks.

This is the ONLY thing that touches the network. Its job is not to improve the
odds but to answer "is there still a reason to keep running?" If the balance
goes to zero, someone else solved it or the creator withdrew, so we can stop.

Endpoints and parsing come from data/puzzles.json (balance_apis), tried in
priority order, falling through on any error or timeout.
"""

from __future__ import annotations
import json
import urllib.request
from . import puzzles

MIN_INTERVAL_SECONDS = 3600  # may only be lengthened, never shortened


def _get_json(url: str, timeout: float = 15.0):
    req = urllib.request.Request(url, headers={"User-Agent": "OnePiece-Bitcoin/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_esplora(d: dict) -> int:
    c = d["chain_stats"]
    return c["funded_txo_sum"] - c["spent_txo_sum"]


def _parse_blockchain_info(d: dict, address: str) -> int:
    return d[address]["final_balance"]


def check_balance_sats(address: str):
    """Return (balance_sats, source_name) or (None, None) if every source failed."""
    for api in puzzles.balance_apis():
        url = api["url"].replace("{address}", address)
        try:
            d = _get_json(url)
            name = api.get("name", url)
            if "blockchain.info" in url:
                return _parse_blockchain_info(d, address), name
            return _parse_esplora(d), name
        except Exception:
            continue
    return None, None


if __name__ == "__main__":
    # Live check of puzzle #71 (should be nonzero while unsolved).
    addr = "1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU"
    sats, src = check_balance_sats(addr)
    if sats is None:
        print("all balance sources failed")
    else:
        print(f"{addr}: {sats/1e8:.8f} BTC via {src}")
