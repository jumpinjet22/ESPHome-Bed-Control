#!/usr/bin/env python3
"""
Capture and decode the sync-bus signal from a Siglent SDS1000X-E oscilloscope
over its SCPI socket (port 5025), for reverse-engineering the Keeson MC122SP
sync protocol.

Findings so far (idle-line capture, 2026-07-18):
  - Bit period: 26,000 ns (~38,461 baud -- close to but not exactly 38400)
  - Frame: 1 start bit + 9 data bits + 1 stop bit = 11 unit intervals
  - Frames are sent back-to-back with zero idle gap and zero jitter
    (286.00 us frame period, confirmed across 46 consecutive frames)
  - Bit 9 (the 9th/last data bit) looks like an address/header marker,
    matching the classic 9-bit multiprocessor-UART scheme: header bytes
    (bit9=1) are followed by one or more payload bytes (bit9=0) until the
    next header.

Usage:
    python3 scope_capture.py [scope_ip] [--channel C1] [--out capture.bin]

Requires: numpy (pip install --user numpy)
"""
import argparse
import os
import socket
import sys
import time

import numpy as np

CAPTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "captures", "raw")

BIT_NS = 26000.0  # measured unit interval; see module docstring
FRAME_UI = 11      # 1 start + 9 data + 1 stop


def scpi_connect(host, port=5025, timeout=5):
    return socket.create_connection((host, port), timeout=timeout)


def scpi_query_text(sock, cmd, idle_timeout=0.5):
    sock.sendall((cmd + "\n").encode())
    time.sleep(0.1)
    sock.settimeout(idle_timeout)
    data = b""
    try:
        while True:
            chunk = sock.recv(1 << 16)
            if not chunk:
                break
            data += chunk
    except socket.timeout:
        pass
    return data.decode(errors="replace").strip()


def query_sample_rate(sock):
    """Query the scope's actual sample rate (Sa/s) -- varies with memory depth/timebase."""
    text = scpi_query_text(sock, "SARA?")
    return float(text)


def fetch_waveform(sock, channel="C1"):
    """Fetch raw DAT2 waveform bytes for a channel, return numpy int8 array."""
    sock.sendall(f"{channel}:WF? DAT2\n".encode())
    time.sleep(0.2)
    sock.settimeout(3.0)
    raw = b""
    try:
        while True:
            chunk = sock.recv(1 << 20)
            if not chunk:
                break
            raw += chunk
    except socket.timeout:
        pass

    hash_idx = raw.index(b"#9")
    header_end = hash_idx + 2 + 9
    n = int(raw[hash_idx + 2:hash_idx + 2 + 9])
    payload = raw[header_end:header_end + n]
    return np.frombuffer(payload, dtype=np.int8).astype(np.int32)


def decode_9bit_uart(samples, sample_rate_hz=1e9, bit_ns=BIT_NS):
    """Decode a 1-start/9-data/1-stop UART bitstream from a digitized analog trace.

    bit_ns is a real-world duration; it's converted to samples using sample_rate_hz,
    since capture memory depth (and therefore effective sample rate) can vary.
    """
    ns_per_sample = 1e9 / sample_rate_hz
    bit_samples = bit_ns / ns_per_sample

    mid = (int(samples.min()) + int(samples.max())) / 2.0
    above = samples > mid
    N = len(above)

    def is_high(idx):
        if idx < 0 or idx >= N:
            return True
        return bool(above[idx])

    pos = 0
    frames = []
    while pos < N - int(13 * bit_samples):
        if is_high(pos) or not is_high(pos - 1):
            pos += 1
            continue
        start = pos
        bits = [1 if is_high(round(start + (1.5 + k) * bit_samples)) else 0 for k in range(9)]
        stop_ok = is_high(round(start + 10.5 * bit_samples))
        header = bits[8]
        byte = 0
        for i, b in enumerate(bits[:8]):
            byte |= (b << i)
        frames.append({
            "t_ns": start * ns_per_sample,
            "byte": byte,
            "header": header,
            "stop_ok": stop_ok,
        })
        pos = start + int((FRAME_UI - 1) * bit_samples)
    return frames


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("host", help="Oscilloscope IP address")
    ap.add_argument("--channel", default="C1")
    ap.add_argument("--out", default=None, help="Path to save raw waveform bytes (default: auto-named file under captures/raw/)")
    ap.add_argument("--no-save", action="store_true", help="Don't save the raw waveform at all")
    ap.add_argument("--single", action="store_true", help="Arm a single-shot trigger before capturing")
    args = ap.parse_args()

    s = scpi_connect(args.host)
    idn = scpi_query_text(s, "*IDN?")
    print(f"# {idn}", file=sys.stderr)

    if args.single:
        s.sendall(b"TRMD SINGLE\n")
        print("# Armed for single trigger -- waveform will be fetched on next call", file=sys.stderr)
        s.close()
        return

    sample_rate = query_sample_rate(s)
    samples = fetch_waveform(s, args.channel)
    s.close()

    if not args.no_save:
        out_path = args.out
        if out_path is None:
            os.makedirs(CAPTURES_DIR, exist_ok=True)
            stamp = time.strftime("%Y%m%d_%H%M%S")
            out_path = os.path.join(CAPTURES_DIR, f"scope_{args.channel}_{stamp}_{sample_rate/1e6:.2f}MSas.bin")
        samples.astype(np.int8).tofile(out_path)
        print(f"# saved raw waveform to {out_path}", file=sys.stderr)

    frames = decode_9bit_uart(samples, sample_rate_hz=sample_rate)
    bad = sum(1 for f in frames if not f["stop_ok"])
    print(f"# {len(frames)} frames decoded, {bad} bad stop bits", file=sys.stderr)

    prev_t = None
    for f in frames:
        t_us = f["t_ns"] / 1000.0
        gap = "" if prev_t is None else f"  (+{t_us - prev_t:.2f}us)"
        marker = "HDR" if f["header"] else "   "
        flag = "" if f["stop_ok"] else "  <-- BAD STOP"
        print(f"t={t_us:9.2f}us  {marker}  0x{f['byte']:02X}{gap}{flag}")
        prev_t = t_us


if __name__ == "__main__":
    main()
