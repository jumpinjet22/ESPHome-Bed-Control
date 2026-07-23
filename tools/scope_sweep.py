#!/usr/bin/env python3
"""
Fast repeated-capture sweep against the scope over a single persistent SCPI
connection, for correlating remote button presses with packet contents.

Unlike scope_capture.py invoked in a loop (which pays Python/numpy startup
cost -- ~6-7s -- on every iteration), this keeps one connection and one
process alive for the whole sweep, so each sample only costs the actual
SCPI round-trip + decode time (typically well under 1s).

Usage:
    python3 scope_sweep.py <scope_ip> --duration 75 --interval 0.3 --out sweep.txt
"""
import argparse
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from scope_capture import scpi_connect, fetch_waveform, decode_9bit_uart, query_sample_rate  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("host")
    ap.add_argument("--channel", default="C1")
    ap.add_argument("--duration", type=float, default=75.0)
    ap.add_argument("--interval", type=float, default=0.3, help="minimum gap between samples")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out = open(args.out, "w") if args.out else sys.stdout

    s = scpi_connect(args.host)
    sample_rate = query_sample_rate(s)
    print(f"# sample rate: {sample_rate/1e6:.2f} MSa/s", file=sys.stderr)
    start = time.time()
    n = 0
    while time.time() - start < args.duration:
        t0 = time.time()
        try:
            samples = fetch_waveform(s, args.channel)
        except Exception as e:
            print(f"# capture failed: {e}", file=sys.stderr)
            s.close()
            s = scpi_connect(args.host)
            sample_rate = query_sample_rate(s)
            continue
        n += 1
        elapsed = time.time() - start
        frames = decode_9bit_uart(samples, sample_rate_hz=sample_rate)
        out.write(f"=== capture {n} at t+{elapsed:.2f}s ===\n")
        for f in frames:
            marker = "HDR" if f["header"] else "   "
            out.write(f"0x{f['byte']:02X} {marker}\n")
        out.flush()
        dt = time.time() - t0
        print(f"# sample {n} at t+{elapsed:.2f}s ({dt:.2f}s/capture, {len(frames)} frames)", file=sys.stderr)
        remaining = args.interval - dt
        if remaining > 0:
            time.sleep(remaining)

    s.close()
    print(f"# done: {n} samples over {time.time()-start:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
