"""A tiny read-only localhost dashboard.

Serves one page that polls the hunt's state file. It shows the numbers and a
grid of the keyspace. The grid stays almost entirely dark on purpose: what you
have searched is one drop in the ocean, and this makes you see it.

Read-only and network-independent: it only reads the local state file.
"""

from __future__ import annotations
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import seed as seedmod
from . import state as statemod

GRID_COLS = 80
GRID_ROWS = 40
GRID_CELLS = GRID_COLS * GRID_ROWS

_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>OnePiece Bitcoin</title><style>
 body{background:#05070d;color:#c9d4e5;font-family:ui-monospace,Menlo,monospace;margin:0;padding:24px}
 h1{font-size:18px;margin:0 0 4px} .sub{color:#5b6b86;font-size:12px;margin-bottom:18px}
 .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:20px}
 .card{background:#0b1120;border:1px solid #16203a;border-radius:8px;padding:10px 12px}
 .k{color:#5b6b86;font-size:11px;text-transform:uppercase;letter-spacing:.04em} .v{font-size:16px;margin-top:3px}
 a{color:#4da3ff} .grid{display:grid;grid-template-columns:repeat(%COLS%,1fr);gap:1px;background:#0b1120;border:1px solid #16203a;border-radius:8px;padding:6px}
 .cell{width:100%;aspect-ratio:1;background:#0d1424;border-radius:1px} .cell.lit{background:#4da3ff;box-shadow:0 0 6px #4da3ff}
 .found{background:#123a1e;border-color:#1f7a3a;color:#7CFF9B} .empty{color:#ff7c7c}
 .foot{color:#5b6b86;font-size:11px;margin-top:14px}
</style></head><body>
<h1>&#127988; OnePiece Bitcoin</h1>
<div class="sub">The treasure exists. You find it, or you don't.</div>
<div id="app">loading&hellip;</div>
<div class="foot">Read-only view of your local hunt. This page makes no network calls of its own.</div>
<script>
function fmt(n){return n.toLocaleString()}
async function tick(){
 try{
  const s=await (await fetch('/api/state')).json();
  const app=document.getElementById('app');
  if(s.error){app.textContent=s.error;return;}
  const cov=s.coverage_fraction;
  const covStr = cov>0 ? (cov<1e-6 ? cov.toExponential(2) : (cov*100).toFixed(8)+'%') : '0%';
  let statusCard = '<div class="card"><div class="k">status</div><div class="v">'+s.status+'</div></div>';
  if(s.status==='found'){statusCard='<div class="card found"><div class="k">status</div><div class="v">KEY FOUND &mdash; move funds now, see '+ (s.found&&s.found.key_file||'') +'</div></div>';}
  if(s.status==='stopped-empty'){statusCard='<div class="card empty"><div class="k">status</div><div class="v">balance is 0 &mdash; solved or withdrawn, stopped</div></div>';}
  let cells='';
  const lit=new Set(s.lit_cells||[]);
  for(let i=0;i<%CELLS%;i++){cells+='<div class="cell'+(lit.has(i)?' lit':'')+'"></div>';}
  app.innerHTML =
   '<div class="stats">'+
   '<div class="card"><div class="k">puzzle</div><div class="v">#'+s.puzzle+' &middot; '+s.type+'</div></div>'+
   '<div class="card"><div class="k">target</div><div class="v"><a href="https://mempool.space/address/'+s.address+'" target="_blank">'+s.address.slice(0,10)+'&hellip;</a></div></div>'+
   '<div class="card"><div class="k">balance</div><div class="v">'+(s.last_balance?(s.last_balance.sat/1e8).toFixed(4)+' BTC':'&mdash;')+'</div></div>'+
   statusCard+
   '<div class="card"><div class="k">keys tried</div><div class="v">'+fmt(s.keys_tried)+'</div></div>'+
   '<div class="card"><div class="k">keys / sec</div><div class="v">'+fmt(Math.round(s.rate_per_sec||0))+'</div></div>'+
   '<div class="card"><div class="k">coverage</div><div class="v">'+covStr+'</div></div>'+
   '<div class="card"><div class="k">years to exhaust</div><div class="v">'+(isFinite(s.years_to_exhaust)?fmt(Math.round(s.years_to_exhaust)):'&infin;')+'</div></div>'+
   '<div class="card"><div class="k">workers</div><div class="v">'+s.workers+' (intensity '+s.intensity+')</div></div>'+
   '</div>'+
   '<div class="grid">'+cells+'</div>';
 }catch(e){}
}
tick();setInterval(tick,1000);
</script></body></html>""".replace("%COLS%", str(GRID_COLS)).replace("%CELLS%", str(GRID_CELLS))


def _lit_cells(st: dict) -> list[int]:
    """Recompute each worker's current start point and map it to a grid cell.

    The seed_hash IS the seed (sha256 of the sentence), so we can reproduce the
    start points from the state file alone.
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


def _augment(st: dict) -> dict:
    size = st.get("keyspace_hi", 0) - st.get("keyspace_lo", 0)
    st = dict(st)
    st["coverage_fraction"] = (st.get("keys_tried", 0) / size) if size else 0
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
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = _PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
    return Handler


def serve_in_thread(state_path: str, port: int = 7100):
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state_path))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd
