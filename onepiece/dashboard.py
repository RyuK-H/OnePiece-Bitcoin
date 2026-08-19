"""A tiny read-only localhost dashboard.

Serves one page that polls the hunt's state file. It shows the numbers and a
grid of the keyspace. The grid stays almost entirely dark on purpose: what you
have searched is one drop in the ocean, and this makes you see it.

Read-only and network-independent: it only reads the local state file.
"""

from __future__ import annotations
import base64
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import seed as seedmod
from . import state as statemod

GRID_COLS = 80
GRID_ROWS = 40
GRID_CELLS = GRID_COLS * GRID_ROWS

_ASSET = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "assets", "gol-d-roger.webp")
try:
    with open(_ASSET, "rb") as _f:
        _BG_B64 = base64.b64encode(_f.read()).decode("ascii")
except OSError:
    _BG_B64 = ""

_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>OnePiece Bitcoin</title><style>
 :root{--green:#3ddc84;--red:#ff4d4d;--amber:#ff9f43;--gray:#8aa0c6}
 *{box-sizing:border-box}
 body{background:#05070d;color:#c9d4e5;font-family:ui-monospace,Menlo,monospace;margin:0;padding:24px;position:relative;min-height:100vh}
 body::before{content:"";position:fixed;inset:0;background:url(data:image/webp;base64,%BG%) center/contain no-repeat;opacity:.06;pointer-events:none;z-index:0}
 .wrap{position:relative;z-index:1}
 h1{font-size:18px;margin:0 0 4px} .sub{color:#5b6b86;font-size:12px;margin-bottom:18px}
 .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:20px}
 .card{background:rgba(11,17,32,.82);border:1px solid #16203a;border-radius:8px;padding:10px 12px}
 .k{color:#5b6b86;font-size:11px;text-transform:uppercase;letter-spacing:.04em} .v{font-size:16px;margin-top:3px;word-break:break-word}
 .v.small{font-size:12px;line-height:1.35} a{color:#4da3ff}
 .status .v{font-weight:700}
 .grid{display:grid;grid-template-columns:repeat(%COLS%,1fr);gap:1px;background:rgba(11,17,32,.82);border:1px solid #16203a;border-radius:8px;padding:6px}
 .cell{width:100%;aspect-ratio:1;background:#0d1424;border-radius:1px} .cell.lit{background:#4da3ff;box-shadow:0 0 6px #4da3ff}
 .foot{color:#5b6b86;font-size:11px;margin-top:14px}
</style></head><body><div class="wrap">
<h1>&#127988; OnePiece Bitcoin</h1>
<div class="sub">The treasure exists. You find it, or you don't.</div>
<div id="app">loading&hellip;</div>
<div class="foot">Read-only view of your local hunt. This page makes no network calls of its own.</div>
</div>
<script>
const COLORS={running:'var(--green)',found:'var(--red)','stopped-empty':'var(--amber)','stopped-timeout':'var(--gray)','stopped-interrupt':'var(--gray)'};
function fmt(n){return Number(n).toLocaleString()}
async function tick(){
 try{
  const s=await (await fetch('/api/state')).json();
  const app=document.getElementById('app');
  if(s.error){app.textContent=s.error;return;}
  const kang = s.method==='kangaroo';
  const rateLabel = kang?'group ops / sec':'keys tested / sec';
  const triedLabel = kang?'group ops done':'keys tested';
  const col = COLORS[s.status]||'var(--gray)';
  let statusText = s.status;
  if(s.status==='found') statusText='KEY FOUND — move funds now';
  if(s.status==='stopped-empty') statusText='balance 0 — solved/withdrawn';
  const lit=new Set(s.lit_cells||[]);
  let cells='';for(let i=0;i<%CELLS%;i++){cells+='<div class="cell'+(lit.has(i)?' lit':'')+'"></div>';}
  app.innerHTML =
   '<div class="stats">'+
   '<div class="card"><div class="k">puzzle</div><div class="v">#'+s.puzzle+' &middot; '+s.type+'</div></div>'+
   '<div class="card"><div class="k">target</div><div class="v small"><a href="https://mempool.space/address/'+s.address+'" target="_blank">'+s.address+'</a></div></div>'+
   '<div class="card"><div class="k">balance (live, hourly)</div><div class="v">'+(s.last_balance?(s.last_balance.sat/1e8).toFixed(4)+' BTC':'checking…')+'</div></div>'+
   '<div class="card status" style="border-color:'+col+'"><div class="k">status</div><div class="v" style="color:'+col+'">'+statusText+'</div></div>'+
   '<div class="card"><div class="k">'+triedLabel+'</div><div class="v">'+fmt(s.keys_tried)+'</div></div>'+
   '<div class="card"><div class="k">'+rateLabel+'</div><div class="v">'+fmt(Math.round(s.rate_per_sec||0))+'</div></div>'+
   '<div class="card"><div class="k">total keyspace (2^'+s.keyspace_pow+')</div><div class="v small">'+s.keyspace_full+'</div></div>'+
   '<div class="card"><div class="k">how far you are</div><div class="v small">'+(s.one_in_str?('you have searched 1 in '+s.one_in_str+'<br>of all keys — a drop in the ocean'):'—')+'</div></div>'+
   '<div class="card"><div class="k">workers</div><div class="v">'+s.workers+' (intensity '+s.intensity+')</div></div>'+
   '</div>'+
   '<div class="grid">'+cells+'</div>';
 }catch(e){}
}
tick();setInterval(tick,1000);
</script></body></html>""".replace("%COLS%", str(GRID_COLS)).replace("%CELLS%", str(GRID_CELLS)).replace("%BG%", _BG_B64)


def _lit_cells(st: dict) -> list[int]:
    """Recompute each worker's current start point and map it to a grid cell.

    The seed_hash IS the seed (sha256 of the sentence), so we can reproduce the
    start points from the state file alone. (Only meaningful for brute force,
    which tracks worker_counters; Kangaroo has none and shows an empty grid.)
    """
    try:
        seed = bytes.fromhex(st["seed_hash"])
        lo = st["keyspace_lo"]
        size = st["keyspace_hi"] - lo
        cells = set()
        for w, counter in enumerate(st.get("worker_counters", [])):
            w_seed = seedmod.derive_worker_seed(seed, w)
            sp = seedmod.start_point(w_seed, max(0, counter - 1), lo, size)
            cell = int((sp - lo) * GRID_CELLS // size)
            cells.add(min(GRID_CELLS - 1, max(0, cell)))
        return sorted(cells)
    except Exception:
        return []


def _sci(n: int) -> str:
    return f"{n:.2e}".replace("e+0", "e").replace("e+", "e")


def _augment(st: dict) -> dict:
    lo = st.get("keyspace_lo", 0)
    hi = st.get("keyspace_hi", 0)
    size = hi - lo
    st = dict(st)
    tried = st.get("keys_tried", 0)
    st["keyspace_size"] = size
    # size is a power of two (2^(n-1)); show that exponent so the label and the
    # full number agree (the search WIDTH, not the upper bound 2^n).
    st["keyspace_pow"] = (size.bit_length() - 1) if size else 0
    st["keyspace_full"] = f"{size:,}"
    st["one_in_str"] = _sci(size // tried) if tried > 0 else None
    st["lit_cells"] = _lit_cells(st)
    return st


def make_handler(state_path: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass  # quiet

        def do_GET(self):
            if self.path.startswith("/api/state"):
                st = statemod.load(state_path)
                payload = _augment(st) if st else {"error": "no active hunt yet"}
                body = json.dumps(payload).encode("utf-8")
                ctype = "application/json"
            else:
                body = _PAGE.encode("utf-8")
                ctype = "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    return Handler


def serve_in_thread(state_path: str, port: int = 7100):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state_path))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd
