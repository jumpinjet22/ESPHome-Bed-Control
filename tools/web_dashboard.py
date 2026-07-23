#!/usr/bin/env python3
"""
Live browser dashboard for the Keeson MC122SP bed sync bus, built on Flask.

A background thread polls the oscilloscope over a persistent SCPI
connection (same approach as scope_sweep.py / dashboard.py) and keeps the
latest CRC-valid packet in a shared, lock-protected state dict. The Flask
app serves a single page that polls /status.json every 200ms and updates
the DOM in place -- no page reloads. Field meanings are documented in the
"Protocol Findings" section of the top-level README.md; this only adds a
browser view on top of dashboard.py's terminal one, via bed_fields.py.

Usage:
    python3 web_dashboard.py <scope_ip> [--port 5000] [--interval 0.15]
"""
import argparse
import sys
import threading
import time

from flask import Flask, jsonify, render_template_string

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from scope_capture import scpi_connect, fetch_waveform, decode_9bit_uart, query_sample_rate, validate_packet  # noqa: E402
from bed_fields import decode_fields  # noqa: E402

app = Flask(__name__)

state_lock = threading.Lock()
state = {"connected": False, "error": None, "poll_hz": 0.0, "fields": None, "valid": False}


def poller(host, channel, interval):
    s = scpi_connect(host)
    sample_rate = query_sample_rate(s)
    poll_times = []
    while True:
        t0 = time.time()
        try:
            samples = fetch_waveform(s, channel)
        except Exception as e:
            with state_lock:
                state["connected"] = False
                state["error"] = str(e)
            try:
                s.close()
            except Exception:
                pass
            s = scpi_connect(host)
            sample_rate = query_sample_rate(s)
            continue

        frames = decode_9bit_uart(samples, sample_rate_hz=sample_rate)
        values = [fr["byte"] for fr in frames]
        ok, reason = validate_packet(frames)

        dt = time.time() - t0
        poll_times.append(dt)
        del poll_times[:-20]
        hz = 1.0 / (sum(poll_times) / len(poll_times)) if poll_times else 0.0

        with state_lock:
            state["connected"] = True
            state["error"] = None if ok else reason
            state["poll_hz"] = hz
            state["valid"] = ok
            if ok:
                state["fields"] = decode_fields(values)

        remaining = interval - dt
        if remaining > 0:
            time.sleep(remaining)


PAGE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Bed Status</title>
<style>
  body { background:#111; color:#eee; font-family: ui-monospace, monospace; padding: 2rem; }
  h1 { font-size: 1.1rem; color: #8fd; }
  .row { margin: 0.6rem 0; }
  .label { display:inline-block; width: 6rem; color:#9aa; }
  .barwrap { display:inline-block; width: 24rem; height: 1.1rem; background:#222; border:1px solid #444; vertical-align: middle; }
  .barfill { height: 100%; background:#4a8; }
  .pct { display:inline-block; width: 4rem; text-align:right; }
  .on { color:#4d8; font-weight:bold; }
  .off { color:#666; }
  .tag { display:inline-block; background:#245; color:#adf; padding: 0.1rem 0.5rem; margin: 0.15rem; border-radius: 0.3rem; font-size: 0.9rem; }
  .stale { color:#d55; }
  .raw { color:#777; font-size: 0.85rem; }
</style>
</head>
<body>
  <h1 id="title">KEESON MC122SP BED STATUS</h1>
  <div class="row" id="conn"></div>

  <div class="row"><span class="label">Head</span>
    <span class="barwrap"><span class="barfill" id="headbar" style="width:0%"></span></span>
    <span class="pct" id="headpct"></span> raw=<span id="headraw"></span> load=<span id="headload"></span>
  </div>
  <div class="row"><span class="label">Foot</span>
    <span class="barwrap"><span class="barfill" id="footbar" style="width:0%"></span></span>
    <span class="pct" id="footpct"></span> raw=<span id="footraw"></span> load=<span id="footload"></span>
  </div>

  <div class="row"><span class="label">Light</span><span id="light"></span></div>
  <div class="row"><span class="label">Traveling</span><span id="traveling"></span></div>
  <div class="row"><span class="label">Cancelling</span><span id="cancelling"></span></div>

  <div class="row"><span class="label">Directional</span><span id="directional"></span></div>
  <div class="row"><span class="label">Functions</span><span id="functions"></span></div>

  <div class="row raw" id="rawbytes"></div>

<script>
async function tick() {
  let r;
  try {
    r = await fetch("/status.json");
  } catch (e) {
    document.getElementById("conn").innerHTML = '<span class="stale">unreachable</span>';
    return;
  }
  const s = await r.json();
  const conn = document.getElementById("conn");
  if (!s.connected) {
    conn.innerHTML = '<span class="stale">disconnected: ' + (s.error || "") + '</span>';
    return;
  }
  conn.innerHTML = (s.valid ? '<span class="on">live</span>' : '<span class="stale">stale packet: ' + s.error + '</span>')
    + '  (~' + s.poll_hz.toFixed(1) + ' Hz)';

  const f = s.fields;
  if (!f) return;

  document.getElementById("headbar").style.width = f.head_pct + "%";
  document.getElementById("headpct").textContent = f.head_pct.toFixed(1) + "%";
  document.getElementById("headraw").textContent = f.head;
  document.getElementById("headload").textContent = f.head_load;

  document.getElementById("footbar").style.width = f.foot_pct + "%";
  document.getElementById("footpct").textContent = f.foot_pct.toFixed(1) + "%";
  document.getElementById("footraw").textContent = f.foot;
  document.getElementById("footload").textContent = f.foot_load;

  document.getElementById("light").innerHTML = f.light_on ? '<span class="on">ON</span>' : '<span class="off">off</span>';
  document.getElementById("traveling").innerHTML = f.traveling ? '<span class="on">YES -- heading to a preset</span>' : '<span class="off">no</span>';
  document.getElementById("cancelling").innerHTML = f.cancelling ? '<span class="on">YES -- preset just interrupted</span>' : '<span class="off">no</span>';

  document.getElementById("directional").innerHTML = f.directional.length
    ? f.directional.map(x => '<span class="tag">' + x + '</span>').join("")
    : '<span class="off">(none)</span>';
  document.getElementById("functions").innerHTML = f.function_bits.length
    ? f.function_bits.map(x => '<span class="tag">' + x + '</span>').join("")
    : '<span class="off">(none)</span>';

  document.getElementById("rawbytes").textContent =
    "byte#11 raw = 0x" + f.b11_raw.toString(16).padStart(2, "0") +
    "   byte#14 (massage, unconfirmed meaning) = 0x" + f.b14_raw.toString(16).padStart(2, "0");
}
setInterval(tick, 200);
tick();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE)


@app.route("/status.json")
def status_json():
    with state_lock:
        return jsonify(dict(state))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("host", help="Oscilloscope IP address")
    ap.add_argument("--channel", default="C1")
    ap.add_argument("--interval", type=float, default=0.15, help="minimum seconds between scope polls")
    ap.add_argument("--port", type=int, default=5000)
    ap.add_argument("--bind", default="127.0.0.1")
    args = ap.parse_args()

    t = threading.Thread(target=poller, args=(args.host, args.channel, args.interval), daemon=True)
    t.start()

    app.run(host=args.bind, port=args.port, debug=False)


if __name__ == "__main__":
    main()
