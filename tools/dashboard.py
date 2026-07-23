#!/usr/bin/env python3
"""
Live terminal dashboard for the Keeson MC122SP bed sync bus.

Polls the oscilloscope over a persistent SCPI connection (same approach as
scope_sweep.py) and redraws a plain-ANSI status view from the last
CRC-valid packet on every cycle. Field meanings are documented in the
"Protocol Findings" section of the top-level README.md -- this is just a
live view of them, nothing decoded here is new.

Usage:
    python3 dashboard.py <scope_ip> [--interval 0.15]
"""
import argparse
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from scope_capture import scpi_connect, fetch_waveform, decode_9bit_uart, query_sample_rate, validate_packet  # noqa: E402

# Empirically measured full-travel endpoints (headup_series.txt / footup_series.txt,
# each driven to its mechanical limit) -- see README.md "Protocol Findings".
HEAD_MAX = 12698
FOOT_MAX = 10816

CLEAR = "\033[2J\033[H"


def bar(pct, width=30):
    pct = max(0.0, min(1.0, pct))
    filled = int(round(pct * width))
    return "[" + "#" * filled + "-" * (width - filled) + f"] {pct * 100:5.1f}%"


def decode_fields(values):
    b2, b3, b4, b5, b11 = values[2], values[3], values[4], values[5], values[11]
    head = values[18] | (values[19] << 8)
    foot = values[20] | (values[21] << 8)
    head_load = values[22] | (values[23] << 8)
    foot_load = values[24] | (values[25] << 8)

    directional = []
    if b2 & 0x01:
        directional.append("HEAD UP")
    if b2 & 0x02:
        directional.append("HEAD DOWN")
    if b2 & 0x04:
        directional.append("FOOT UP")
    if b2 & 0x08:
        directional.append("FOOT DOWN")

    function_bits = []
    if b3 & 0x02:
        function_bits.append("TIMER")
    if b3 & 0x04:
        function_bits.append("MASSAGE RIGHT")
    if b3 & 0x08:
        function_bits.append("MASSAGE LEFT")
    if b3 & 0x10:
        function_bits.append("ZERO-G (trigger)")
    if b3 & 0x20:
        function_bits.append("MEMORY AMBER? (trigger, unconfirmed)")
    if b3 & 0x40:
        function_bits.append("MEMORY GREEN (trigger)")
    if b4 & 0x01:
        function_bits.append("MEMORY RED (trigger)")
    if b4 & 0x02:
        function_bits.append("LIGHT (held)")
    if b5 & 0x08:
        function_bits.append("FLAT (trigger)")

    return {
        "head": head, "foot": foot,
        "head_load": head_load, "foot_load": foot_load,
        "directional": directional, "function_bits": function_bits,
        "light_on": bool(b11 & 0x01),
        "cancelling": bool(b11 & 0x02),
        "traveling": bool(b11 & 0x04),
        "b11_raw": b11, "b14_raw": values[14],
    }


def render(values, is_valid, reason, poll_hz):
    f = decode_fields(values)
    lines = [
        "=" * 62,
        " KEESON MC122SP BED STATUS  (live, ~%.1f Hz)" % poll_hz,
        "=" * 62,
        f"last packet: {'VALID' if is_valid else 'stale -- last good packet shown (INVALID: ' + reason + ')'}",
        "",
        f"Head : {bar(f['head'] / HEAD_MAX)}  raw={f['head']:5d}  load={f['head_load']}",
        f"Foot : {bar(f['foot'] / FOOT_MAX)}  raw={f['foot']:5d}  load={f['foot_load']}",
        "",
        f"Light        : {'ON' if f['light_on'] else 'off'}",
        f"Traveling    : {'YES -- heading to a preset' if f['traveling'] else 'no'}",
        f"Cancelling   : {'YES -- preset just interrupted' if f['cancelling'] else 'no'}",
        "",
        f"Directional held : {', '.join(f['directional']) or '(none)'}",
        f"Active function bits: {', '.join(f['function_bits']) or '(none)'}",
        "",
        f"byte#11 raw = {f['b11_raw']:#04x}   byte#14 (massage, unconfirmed meaning) = {f['b14_raw']:#04x}",
        "=" * 62,
        "Ctrl-C to quit",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("host", help="Oscilloscope IP address")
    ap.add_argument("--channel", default="C1")
    ap.add_argument("--interval", type=float, default=0.15, help="minimum seconds between polls")
    args = ap.parse_args()

    s = scpi_connect(args.host)
    sample_rate = query_sample_rate(s)

    last_ok = None
    poll_times = []
    try:
        while True:
            t0 = time.time()
            try:
                samples = fetch_waveform(s, args.channel)
            except Exception as e:
                sys.stdout.write(f"{CLEAR}capture failed: {e}, reconnecting...\n")
                sys.stdout.flush()
                s.close()
                s = scpi_connect(args.host)
                sample_rate = query_sample_rate(s)
                continue

            frames = decode_9bit_uart(samples, sample_rate_hz=sample_rate)
            values = [fr["byte"] for fr in frames]
            ok, reason = validate_packet(frames)
            if ok:
                last_ok = values

            dt = time.time() - t0
            poll_times.append(dt)
            poll_times = poll_times[-20:]
            hz = 1.0 / (sum(poll_times) / len(poll_times)) if poll_times else 0.0

            if last_ok is not None:
                sys.stdout.write(CLEAR + render(last_ok, ok, reason, hz) + "\n")
                sys.stdout.flush()

            remaining = args.interval - dt
            if remaining > 0:
                time.sleep(remaining)
    except KeyboardInterrupt:
        pass
    finally:
        s.close()


if __name__ == "__main__":
    main()
