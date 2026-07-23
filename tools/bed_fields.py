#!/usr/bin/env python3
"""
Shared field decoding for a validated packet's byte list, used by both
dashboard.py (terminal) and web_dashboard.py (Flask). Field meanings are
documented in the "Protocol Findings" section of the top-level README.md --
nothing here decodes anything new.
"""

# Empirically measured full-travel endpoints (headup_series.txt / footup_series.txt,
# each driven to its mechanical limit) -- see README.md "Protocol Findings".
HEAD_MAX = 12698
FOOT_MAX = 10816


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
        "head_pct": round(100.0 * head / HEAD_MAX, 1),
        "foot_pct": round(100.0 * foot / FOOT_MAX, 1),
        "head_load": head_load, "foot_load": foot_load,
        "directional": directional, "function_bits": function_bits,
        "light_on": bool(b11 & 0x01),
        "cancelling": bool(b11 & 0x02),
        "traveling": bool(b11 & 0x04),
        "b11_raw": b11, "b14_raw": values[14],
    }
