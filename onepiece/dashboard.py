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
from math import isqrt
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import seed as seedmod
from . import state as statemod
from .kangaroo import POSITION_BITS

GRID_COLS = 80
GRID_ROWS = 34          # the grid flex-grows to fill the viewport; rows keep cells ~square
GRID_CELLS = GRID_COLS * GRID_ROWS

_ASSET = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "assets", "gol-d.png")
try:
    with open(_ASSET, "rb") as _f:
        _BG_B64 = base64.b64encode(_f.read()).decode("ascii")
except OSError:
    _BG_B64 = ""

_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>OnePiece Bitcoin</title><style>
 /* palette borrowed from ryuology.com — warm paper + forest green, dark = ink + mint */
 :root{
  --bg:#f4f5f1;--fg:#17191a;--muted:#5b6455;--faint:#8a9382;
  --accent:#1d7a44;--amber:#8a5a12;--danger:#b23b2e;--border:#dadfd4;--panel:#e9ece4;
  --scan:rgba(0,0,0,.015);--cell:#dde1d7;--cell-lit:var(--accent)}
 @media(prefers-color-scheme:dark){:root{
  --bg:#0c0f0d;--fg:#e4e8e0;--muted:#8b9484;--faint:#545e4d;
  --accent:#7dff9b;--amber:#e7b45a;--danger:#ff6b6b;--border:#1e251b;--panel:#12160f;
  --scan:rgba(255,255,255,.012);--cell:#171d14;--cell-lit:var(--accent)}}
 *{box-sizing:border-box}
 html,body{height:100%}
 body{background:var(--bg);color:var(--fg);margin:0;padding:26px 22px 18px;position:relative;
  min-height:100vh;display:flex;flex-direction:column;
  font-family:ui-monospace,SFMono-Regular,Menlo,"Cascadia Code",monospace;font-size:13px;
  -webkit-font-smoothing:antialiased;
  background-image:repeating-linear-gradient(0deg,transparent 0 3px,var(--scan) 3px 4px)}
 body::after{content:"";position:fixed;inset:0;background:url(data:image/png;base64,%BG%) center/contain no-repeat;
  opacity:.04;pointer-events:none;z-index:0}
 .wrap{position:relative;z-index:1;max-width:1080px;margin:0 auto;width:100%;flex:1;
  display:flex;flex-direction:column}
 #app{flex:1;display:flex;flex-direction:column;min-height:0}
 .head{display:flex;align-items:baseline;gap:14px;margin-bottom:24px}
 h1{font-family:Pretendard,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  font-size:17px;margin:0;letter-spacing:.01em;font-weight:800}
 .tag{color:var(--faint);font-size:11.5px}
 .hero{display:grid;grid-template-columns:1.05fr 1.5fr 1.1fr;gap:16px;margin-bottom:16px;flex:0 0 auto}
 .bar{display:flex;flex-wrap:wrap;gap:16px;margin-bottom:16px;flex:0 0 auto}
 .bar .card{flex:1 1 130px;min-width:120px}
 @media(max-width:720px){.hero{grid-template-columns:1fr}}
 .card{background:var(--panel);border:1px solid var(--border);border-radius:5px;padding:11px 13px}
 .k{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.09em;font-weight:700}
 .v{font-size:15px;margin-top:5px;line-height:1.25;word-break:break-word}
 .v.xl{font-size:23px;letter-spacing:.01em;font-weight:700}
 .v.small{font-size:12px}
 .cap{color:var(--faint);font-size:10.5px;margin-top:5px;line-height:1.45}
 a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
 .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px;vertical-align:middle;
  box-shadow:0 0 7px currentColor}
 .pow{font-size:26px;font-weight:700;letter-spacing:.01em;margin-top:5px}
 .pow sup{font-size:.58em;font-weight:700;vertical-align:super;margin-left:.42em}
 .mapwrap{padding:10px 12px;flex:1 1 auto;display:flex;flex-direction:column;min-height:120px}
 .maphd{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:8px;flex:0 0 auto}
 .maphd .k,.maphd .cap{margin:0}
 .grid{flex:1;display:grid;grid-template-columns:repeat(%COLS%,1fr);grid-template-rows:repeat(%ROWS%,1fr);
  gap:2px;min-height:0}
 .cell{background:var(--cell);border-radius:1px;min-height:0}
 .cell.lit{background:var(--cell-lit);box-shadow:0 0 6px var(--cell-lit)}
 .foot{color:var(--faint);font-size:10.5px;margin-top:12px;flex:0 0 auto}
</style></head><body><div class="wrap">
<div class="head"><h1>&#127988; OnePiece Bitcoin</h1><span class="tag">The treasure exists. You find it, or you don&rsquo;t.</span></div>
<div id="app">loading&hellip;</div>
<div class="foot">Read-only view of your local hunt &middot; this page makes no network calls of its own.</div>
</div>
<script>
const COLORS={running:'var(--accent)',found:'var(--danger)','stopped-empty':'var(--amber)','stopped-timeout':'var(--muted)','stopped-interrupt':'var(--muted)'};
function fmt(n){return Number(n).toLocaleString()}
function esc(s){return String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function shortAddr(a){return a.length>16?a.slice(0,7)+'…'+a.slice(-6):a}
function ordinal(n){const t=n%100,u=n%10;return n+((t>=11&&t<=13)?'th':u===1?'st':u===2?'nd':u===3?'rd':'th')}
async function tick(){
 try{
  const s=await (await fetch('/api/state')).json();
  const app=document.getElementById('app');
  if(s.error){app.textContent=s.error;return;}
  const kang = s.method==='kangaroo';
  const rateLabel = kang?'group ops / sec':'keys / sec';
  const triedLabel = kang?'group ops done':'keys tested';
  const col = COLORS[s.status]||'var(--muted)';
  let statusText = s.status;
  if(s.status==='found') statusText='KEY FOUND';
  if(s.status==='stopped-empty') statusText='balance 0';
  const lit=new Set(s.lit_cells||[]);
  let cells='';for(let i=0;i<%CELLS%;i++){cells+='<div class="cell'+(lit.has(i)?' lit':'')+'"></div>';}
  const workNoun = kang ? 'the group ops Kangaroo expects' : 'all keys';
  const far = s.voyage_sailed
   ? '<div class="v xl">sailed '+esc(s.voyage_sailed)+'</div>'+
     '<div class="cap">of the ~150-million-km trip from Earth to the Sun, if the whole search were that far</div>'+
     '<div class="cap">1 part in '+esc(s.one_in_words)+' of '+workNoun+' &mdash; the more you search, the smaller that gets</div>'
   : '<div class="v xl">just cast off</div><div class="cap">the first '+(kang?'hops are':'keys are')+' being tested&hellip;</div>';
  // Kangaroo leads with the EFFECTIVE difficulty (~2^70), not the raw 2^139
  // interval — the exposed public key is exactly what makes the real number
  // the square-root one. Brute force has no such gap: keyspace == difficulty.
  const kcard = kang
   ? '<div class="card"><div class="k">work to crack</div>'+
     '<div class="pow">2<sup>'+s.difficulty_pow+'</sup></div>'+
     '<div class="cap">~that many group ops &mdash; Kangaroo (&radic; speedup)</div>'+
     '<div class="cap">the key sits in a 2<sup>'+s.keyspace_pow+'</sup> interval; the exposed public key cuts the work to this</div></div>'
   : '<div class="card"><div class="k">total keyspace</div>'+
     '<div class="pow">2<sup>'+s.keyspace_pow+'</sup></div>'+
     '<div class="cap">two to the '+ordinal(s.keyspace_pow)+' power</div>'+
     '<div class="cap">'+s.keyspace_full+' keys</div></div>';
  app.innerHTML =
   '<div class="hero">'+
    '<div class="card status" style="border-color:'+col+'"><div class="k">status</div>'+
     '<div class="v xl" style="color:'+col+'"><span class="dot" style="background:'+col+'"></span>'+statusText+'</div>'+
     '<div class="cap">'+s.workers+' worker'+(s.workers==1?'':'s')+' &middot; '+fmt(Math.round(s.rate_per_sec||0))+' '+rateLabel+'</div></div>'+
    '<div class="card"><div class="k">how far you are</div>'+far+'</div>'+
    kcard+
   '</div>'+
   '<div class="bar">'+
   '<div class="card"><div class="k">puzzle</div><div class="v">#'+s.puzzle+'</div><div class="cap">'+esc(s.type)+'</div></div>'+
   '<div class="card"><div class="k">target</div><div class="v small"><a href="https://mempool.space/address/'+esc(s.address)+'" target="_blank" rel="noopener">'+esc(shortAddr(s.address))+'</a></div><div class="cap">live balance ↗</div></div>'+
   '<div class="card"><div class="k">balance</div><div class="v">'+(s.last_balance?(s.last_balance.sat/1e8).toFixed(4)+' BTC':'checking…')+'</div><div class="cap">hourly, on-chain</div></div>'+
   '<div class="card"><div class="k">'+triedLabel+'</div><div class="v">'+fmt(s.keys_tried)+'</div></div>'+
   '<div class="card"><div class="k">'+rateLabel+'</div><div class="v">'+fmt(Math.round(s.rate_per_sec||0))+'</div></div>'+
   '<div class="card"><div class="k">cpu workers</div><div class="v">'+s.workers+'</div><div class="cap">of '+s.cores+' cores &middot; intensity '+s.intensity+'/10</div></div>'+
   '</div>'+
   '<div class="card mapwrap"><div class="maphd"><div class="k">keyspace map</div><div class="cap">'+lit.size+' of '+%CELLS%+' cells lit &middot; the dark is the point</div></div>'+
   '<div class="grid">'+cells+'</div></div>';
 }catch(e){}
}
tick();setInterval(tick,1000);
</script></body></html>""".replace("%COLS%", str(GRID_COLS)).replace("%ROWS%", str(GRID_ROWS)).replace("%CELLS%", str(GRID_CELLS)).replace("%BG%", _BG_B64)


def _lit_cells(st: dict) -> list[int]:
    """Map the live search's current spots to grid cells.

    Kangaroo: each kangaroo reports POSITION_BITS-wide scatter values (low bits
    of its point's x-coordinate); scale each onto the grid. Brute force: the
    seed_hash IS the seed, so we reproduce each RUNNING worker's current start
    point from the state file. Only workers running this session are lit —
    worker_counters may also hold preserved counters for workers from a larger
    past run, and those are not moving, so lighting them would misrepresent it.
    """
    try:
        if st.get("method") == "kangaroo":
            cells = set()
            for pos in st.get("kangaroo_positions", []):
                try:
                    p = int(pos)
                except (TypeError, ValueError):
                    continue  # skip a bad entry, keep the good ones (don't blank)
                if p:  # 0 = a slot not yet written by its worker
                    cells.add(min(GRID_CELLS - 1, (p * GRID_CELLS) >> POSITION_BITS))
            return sorted(cells)
        seed = bytes.fromhex(st["seed_hash"])
        lo = st["keyspace_lo"]
        size = st["keyspace_hi"] - lo
        counters = st.get("worker_counters", [])
        active = int(st.get("workers") or len(counters))
        cells = set()
        for w, counter in enumerate(counters[:active]):
            w_seed = seedmod.derive_worker_seed(seed, w)
            sp = seedmod.start_point(w_seed, max(0, counter - 1), lo, size)
            cell = int((sp - lo) * GRID_CELLS // size)
            cells.add(min(GRID_CELLS - 1, max(0, cell)))
        return sorted(cells)
    except Exception:
        return []


EARTH_SUN_M = 1.496e11  # one astronomical unit, the "voyage" the progress line maps onto

_SCALES = (
    (1e3, "thousand"), (1e6, "million"), (1e9, "billion"),
    (1e12, "trillion"), (1e15, "quadrillion"), (1e18, "quintillion"),
)


def _one_in_words(n: int) -> str:
    """1 in N, in words a human can hold: '11.3 trillion', not '1.13e13'.

    Past quintillions the names stop meaning anything, so switch to digit
    count, which stays visceral ('a 44-digit number').
    """
    if n < 1000:
        return f"{n:,}"
    for base, name in _SCALES:
        v = n / base
        if v < 999.5:  # would render as 4 digits — promote to the next scale
            return f"{v:.3g} {name}"
    return f"a {len(str(n))}-digit number"


def _voyage_dist(fraction: float) -> str:
    """How far along an Earth→Sun voyage the searched fraction takes you.

    Returns just the distance phrase (e.g. '1.7 cm', '0.31 µm · thinner than a
    hair'); the page frames it. This number GROWS as you search, unlike the
    coverage ratio which shrinks, so it reads as forward progress.
    """
    m = EARTH_SUN_M * fraction
    if m >= 1000:
        return f"{m / 1000:,.1f} km"
    if m >= 1:
        return f"{m:,.1f} m"
    if m >= 0.01:
        return f"{m * 100:.1f} cm"
    if m >= 1e-3:
        return f"{m * 1000:.2f} mm"
    if m >= 1e-6:
        um = m * 1e6
        # a human hair is ~17–180 µm; only claim "thinner than a hair" when it
        # is safely below that, not across the whole 1–999 µm bucket.
        return f"{um:.2f} µm" + (" · thinner than a hair" if um < 15 else "")
    if m >= 1e-9:
        return f"{m * 1e9:.2f} nm · molecular scale"
    if m >= 1e-12:
        return f"{m * 1e12:.2f} pm · atomic scale"
    return "not yet a single atom's width"


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
    st["cores"] = os.cpu_count() or st.get("workers", 1)

    # Effective work to expect a solve. Brute force must scan the whole interval
    # width; Kangaroo (public-key exposed) solves in ~2*sqrt(width) group ops —
    # that square-root speedup is the whole reason those puzzles are attackable,
    # so progress must be measured against THAT, not the raw 2^139 interval.
    # (Measuring against 2^139 understated progress by ~20 orders of magnitude.)
    if st.get("method") == "kangaroo" and size > 0:
        difficulty = 2 * isqrt(size)
        st["difficulty_pow"] = difficulty.bit_length() - 1
    else:
        difficulty = size
        st["difficulty_pow"] = None

    if tried > 0 and difficulty > 0:
        st["one_in_words"] = _one_in_words(max(1, difficulty // tried))
        st["voyage_sailed"] = _voyage_dist(min(1.0, tried / difficulty))
    else:
        st["one_in_words"] = None
        st["voyage_sailed"] = None
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
