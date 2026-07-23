#!/usr/bin/env python3
"""
Capture and decode the sync-bus signal from a Siglent SDS1000X-E oscilloscope
over its SCPI socket (port 5025), for reverse-engineering the Keeson MC122SP
sync protocol.

Findings so far (see README.md "Protocol Findings" for the full writeup):
  - Bit period: 26,000 ns (~38,461 baud -- close to but not exactly 38400)
  - Frame: 8E1 UART -- 1 start bit + 8 data bits + 1 even-parity bit + 1 stop
    bit = 11 unit intervals. This decoder reads the parity bit as if it were
    a 9th data bit (harmless -- it's masked off when returning the byte
    value), and reports it in the "header" field, but it's just parity, not
    a semantic marker as first assumed.
  - Frames are sent back-to-back with zero idle gap and zero jitter
    (286.00 us frame period, confirmed across dozens of captures).
  - Packet layout: byte 0 = payload length (total packet = length + 3),
    byte 1 = source address (0x07 = bed, 0x01 = commander), last byte = CRC
    (inverted 8-bit sum of every preceding byte -- sum of the whole packet
    including the CRC is always 0xFF mod 256). See validate_packet() and
    build_command_packet() below.

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


def fetch_waveform(sock, channel="C1", safety_timeout=10.0):
    """Fetch raw DAT2 waveform bytes for a channel, return numpy int8 array.

    Reads exactly the byte count the scope declares in the '#9<9-digit-length>'
    block header, instead of waiting for a socket timeout to signal end-of-data --
    that timeout wait was padding every capture regardless of actual transfer time.
    """
    sock.sendall(f"{channel}:WF? DAT2\n".encode())
    sock.settimeout(safety_timeout)
    raw = b""
    header_end = None
    n = None
    total_needed = None
    while total_needed is None or len(raw) < total_needed:
        chunk = sock.recv(1 << 20)
        if not chunk:
            break
        raw += chunk
        if total_needed is None and b"#9" in raw:
            hash_idx = raw.index(b"#9")
            if len(raw) >= hash_idx + 2 + 9:
                header_end = hash_idx + 2 + 9
                n = int(raw[hash_idx + 2:hash_idx + 2 + 9])
                total_needed = header_end + n

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


def validate_packet(frames):
    """Check a decoded frame list against the length/CRC rules.

    Returns (is_valid, reason). A truncated capture (missing a byte at
    either edge of the burst) will fail this even though every individual
    frame decoded with a good stop bit -- that's the point: it catches
    incomplete captures that per-frame stop-bit checking can't see.
    """
    if not frames:
        return False, "no frames"
    values = [f["byte"] for f in frames]
    length_field = values[0]
    expected_total = length_field + 3
    if len(values) != expected_total:
        return False, f"expected {expected_total} bytes (length byte={length_field}), got {len(values)}"
    checksum = sum(values) & 0xFF
    if checksum != 0xFF:
        return False, f"checksum mod 256 = 0x{checksum:02X}, expected 0xFF"
    return True, "ok"


def build_command_packet(payload_after_source, source=0x01):
    """Build a full command packet (length + source + payload + CRC) ready to transmit.

    payload_after_source is everything after the source-address byte, e.g.
    bytes([0x01, 0x00, 0x00, 0x00, 0x00]) for Head Up (button bitmask 0x01
    in the first payload byte). UNTESTED -- transmitting has not been tried
    yet; see the README's "Transmitting" section for the command table this
    was derived from and the open questions around bus safety.
    """
    payload_after_source = bytes(payload_after_source)
    length_field = len(payload_after_source)
    body = bytes([length_field, source]) + payload_after_source
    crc = (~sum(body)) & 0xFF
    return body + bytes([crc])


KNOWN_COMMANDS = {
    "full_stop": bytes([0x00, 0x00, 0x00, 0x00, 0x00]),
    "head_up": bytes([0x01, 0x00, 0x00, 0x00, 0x00]),
    "head_down": bytes([0x02, 0x00, 0x00, 0x00, 0x00]),
    "foot_up": bytes([0x04, 0x00, 0x00, 0x00, 0x00]),
    "foot_down": bytes([0x08, 0x00, 0x00, 0x00, 0x00]),
    "zero_gravity": bytes([0x00, 0x10, 0x00, 0x00, 0x00]),
    "flat": bytes([0x00, 0x00, 0x00, 0x08, 0x00]),
}


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
    valid, reason = validate_packet(frames)
    print(f"# {len(frames)} frames decoded, {bad} bad stop bits, packet {'VALID' if valid else 'INVALID: ' + reason}", file=sys.stderr)

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
