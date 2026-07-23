# ESPHome-Bed-Control
 ___Adjustable Bed Base Integration with Home Assistant___

## Overview
I've been working on integrating my adjustable bed base into Home Assistant. While I have a plan of action, I am reaching the limits of my technical knowledge and venturing into uncharted waters.

## Project Description
This project involves an adjustable base that uses a Keeson MC122SP controller. Through research and forum discussions, I discovered that this base is equipped with an nRF51802 from Nordic Semiconductor. The controller features several multipurpose ports, one of which is intended for syncing two bases. I am attempting to use this port to control the bed.

## Progress
I used a sync cable, which I modified by cutting off the end, to test the signals using a multimeter and an oscilloscope. The signals I captured appear to be digital, and I suspect they might be UART, although I am not entirely certain.

I think I have made steps forward. I noticed that certain bits turned to 1 when I pressed different buttons on the remote. I believe I have found the primary signaling for the remote, but I'm still unsure if this is UART or some proprietary protocol they developed. The question I am asking myself is, would they use a standard that already exists or create their own signaling to communicate between bases?

## Screenshots of Signal
Here are some screenshots I took of the signal:

***no interaction***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00001.png)

***massage head***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00002.png)

***massage timer***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00003.png)

***massage foot***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00004.png)

***Head up***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00005.png)

***Light***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00006.png)

***Foot Up***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00007.png)

***Head Down***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00008.png)

***Zero G***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00009.png)

***Foot Down***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00010.png)

***Preset one***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00011.png)

***Preset two***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00012.png)

***Preset three***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00013.png)

***Unkoown***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00014.png)

***Flatten***

![photo](https://raw.githubusercontent.com/jumpinjet22/ESPHome-Bed-Control/main/Remote%20Signals/SDS00015.png)

## Protocol Findings (2026-07-18 – 2026-07-19)
The oscilloscope used above (a Siglent SDS1202X-E) exposes a SCPI socket on the network, so instead of reading screenshots by eye, the raw waveform samples were pulled directly and decoded in software. See [`tools/scope_capture.py`](tools/scope_capture.py) — point it at the scope's IP and it fetches and decodes channel 1.

Independently reverse-engineered from scratch, then cross-checked against an existing [Home Assistant community write-up](https://community.home-assistant.io/t/guide-ergomotion-serta-tempur-ghostbed-askona-adjustable-beds-keeson-mc120pr-mc122sp-uart-protocol-full-breakdown/1018253) covering the same Keeson MC120PR/MC122SP family — our independently-found button bitmask and head/foot position byte offsets matched that write-up exactly, which is good mutual validation. A few things it corrected in our own understanding are noted below.

- **Bit timing:** 26,000 ns per bit (~38,461 baud — close to, but not exactly, the standard 38400 baud rate).
- **Framing is 8 data bits + even parity + 1 stop bit (8E1)**, not a 9-bit data field as first assumed. Total frame is still 11 unit intervals (1 start + 8 data + 1 parity + 1 stop), which is why our original "9-bit" decoder — which just treated that 9th bit as an extra data bit — worked and gave 0 framing errors; it just mislabeled what that bit *means*. Checked against our own logs: `0x2C` has three 1-bits (odd) so parity=1, matching every "HDR" flag logged for that byte; `0xFF` has eight 1-bits (even) so parity=0, matching every unflagged `FF`. The underlying data byte values we decoded are unaffected — only the "9th bit = header marker" interpretation was wrong.
- **Cadence:** frames run back-to-back with zero idle gap, at a rock-steady 286.00 µs/byte (~3,496 bytes/sec) — confirmed with zero jitter across every capture taken. The whole bed unit broadcasts a full status packet roughly every 139 ms (we measured 120-150ms).
- **Packet structure** (offsets below match the community write-up, and our own independent captures line up with these exactly for the fields we tested):

  | Offset | Field | Notes |
  |---|---|---|
  | 0 | Packet length | We consistently saw `0x2C` (44) here |
  | 1 | Source address | `0x07` = bed unit (constant in every capture); `0x01` = command transmitter |
  | 2 | Directional button bitmask | See table below — confirmed independently tonight |
  | 3 | Zero Gravity button | `0x10` = pressed (momentary; we didn't happen to catch this bit live) |
  | 5 | Flat button | `0x08` = pressed (momentary; same caveat) |
  | 18–19 | Head position | Little-endian 16-bit — confirmed independently tonight, see below |
  | 20–21 | Foot position | Little-endian 16-bit — confirmed independently tonight, see below |
  | 22–23 | Head load/current | Little-endian, raw units (supersedes our earlier weaker byte #27 guess) |
  | 24–25 | Foot load/current | Little-endian, raw units |
  | last byte | CRC | Inverted 8-bit sum (1's complement) of all preceding bytes; summing every byte *including* the CRC should equal `0xFF`. This explains the "unexplained noisy last byte" we kept seeing and could never pin down. |

  Bytes in between (roughly #26–43, excluding the load/CRC fields above) are still unaccounted for by either source — likely padding/reserved, not yet confirmed either way.

- **Directional button bitmask (byte #2)**, confirmed by holding each button individually and watching the byte change live, then revert to `0x00` on release:

  | Bit | Value | Button |
  |---|---|---|
  | 0 | `0x01` | Head Up |
  | 1 | `0x02` | Head Down |
  | 2 | `0x04` | Foot Up |
  | 3 | `0x08` | Foot Down |

  Because it's a real bitmask (not a sequential code), it should support simultaneous combinations, e.g. Head Up + Foot Up held together should read `0x05`.
- **Momentary/preset buttons behave differently:** Zero G and Flatten did *not* set byte #2 while held. Matches the community write-up: they're one-shot triggers (byte #3 = `0x10` for Zero G, byte #5 = `0x08` for Flat) rather than continuous-hold signals like the directional buttons.
- **Bytes #18–19 and #20–21 are live head/foot position telemetry**, independently confirmed tonight before finding the matching community write-up. Taking several captures in a row *during a single continuous button hold* (rather than one snapshot per button) showed:
  - While holding Head Up, bytes #18–19 changed capture-to-capture, then froze the instant the motor hit its mechanical travel limit (confirmed against real-time "it stopped" feedback while still holding the button).
  - While holding Foot Up, bytes #18–19 stayed **exactly** at the value they'd frozen at during the Head Up test (carried over correctly since the head wasn't touched), while bytes #20–21 did the same drift-then-freeze dance instead.
  - Confirmed further with a momentary Flatten press, sampled 8 times over the run: both #18–19 and #20–21 were still drifting in the first two samples, then **landed on exactly `0x0000` simultaneously** and held there once the base finished flattening — `0` is the flat/home reference for both axes.
  - Per the community write-up, these positions are **purely virtual/estimated** (no physical position sensor) — the controller infers them from motor run time and load, so they can drift and need periodic recalibration via the Flat button or by holding a direction button after bottoming out.
- **Byte #4 is a second, separate status byte for the Light button** (distinct from the directional bitmask at #2): `0x00` idle/released, `0x02` (parity bit set) while Light is being pressed, confirmed clean across 6 alternating held/released rounds with zero exceptions. Like the directional buttons, this only reflects "button currently pressed," not the bulb's actual on/off state. Not covered by the community write-up — this one's ours.
- **Byte #11 is a small status/flags byte with two confirmed bits:**
  - **Bit 0 (`0x01`) = light on/off.** Confirmed with 4 samples of the light physically on and 4 of it physically off (spread across a full on/off/on/off/on/off sequence): reads exactly `0x21` every time the light is on, exactly `0x20` every time it's off — zero variation within either group, zero overlap.
  - **Bit 2 (`0x04`) = "traveling to a preset," not "any motor active."** Live-tested repeatedly: firing Memory Red/Green sets it for the whole travel and clears the instant the base stops (confirmed in real time, checked live between messages). Critically, it does **not** get set by directly holding a directional button — checked against the earlier `headup_series.txt`/`footup_series.txt` captures (4 samples each): byte #11 stayed at base `0x20` the entire time even though the motor was clearly running (byte #2 nonzero, position visibly drifting). So this bit specifically distinguishes autonomous preset-driven movement from direct held-button movement, not motor activity in general. Manually pushing the bed by hand (no motor engaged at all) also leaves it at `0`, as expected since there's no real position sensor to detect that.
  - Not covered by the community write-up — both bits are ours.
- **Byte #3 is a second bitmask, for "special function" buttons** (separate from the directional bitmask at byte #2), confirmed by holding/tapping each button and watching the byte change:

  | Value | Button |
  |---|---|
  | `0x02` | Timer (the clock-icon button between the massage zone buttons — cycles 10/20/30 min with repeated taps, not 3 separate buttons) |
  | `0x04` | Massage — right zone (held steady the whole press, doesn't pulse) |
  | `0x08` | Massage — left zone (confirmed while cycling through massage modes — same value on every tap) |
  | `0x10` | Zero Gravity (matches the community write-up exactly) |

  Massage-left and Timer showed the value appearing in short repeated blips rather than one sustained block — that's the user tapping through multiple modes/durations on the same button, not the protocol itself pulsing.
- **Timer triggers active massage, not just a flag.** Once a massage motor is running, byte #14 (and correlated bytes #15, #22, #24, #26, #30, #46) continuously ramp — byte #14 counts smoothly down and then wraps and keeps descending again (`...0x0F → 0x00 → 0xE4 → 0xD7...`), a repeating sawtooth rather than a one-shot countdown. Reads like a live massage-intensity/PWM modulation value tied to the running motor, not a "time remaining" field — exact meaning still open, needs more isolated testing.
- **Memory Red recalls a saved head/foot position.** Bytes #2/#3/#5 never showed a distinct trigger bit for it (likely too brief to catch at our ~0.06s sampling, or it's in a byte we haven't checked), but the *result* is unambiguous and highly reproducible: two separate presses both drove the bed to the exact same targets — head froze at `0x0720` both times, foot climbed toward `0x0DAD` both times (froze there fully on the first attempt) — the same drift-then-freeze signature used to identify the position bytes in the first place, just now triggered autonomously by a memory recall instead of a held directional button.

## CRC / Packet Validation (confirmed 2026-07-19)
The community write-up's checksum claim — "an inverted 8-bit sum (1's complement); summing all bytes including the CRC always equals `0xFF`" — checks out exactly against our own captures, and let us pin down the exact length formula too: **`total_packet_length = length_field + 3`** (their own worked example: length field `0x18`=24, total 27 bytes, 24+3=27 ✓; our captures: length field `0x2C`=44, total 47 bytes, 44+3=47 ✓ — their write-up's literal description of the length field was a little imprecise, but this formula held perfectly on every complete capture we had).

Every capture with the full 47 bytes passed with `sum(all bytes) mod 256 == 0xFF`, no exceptions. Captures with only 45-46 bytes failed — but that's not a protocol mystery, it's just an earlier truncated capture (a frame or two clipped at the edge of the acquisition window before some capture-tooling fixes later in the session). That turns the CRC check into a free, automatic way to tell a truncated capture from a real one going forward.

[`tools/scope_capture.py`](tools/scope_capture.py) now has this built in:
- `validate_packet(frames)` — checks a decoded capture against the length+CRC rules, returns `(is_valid, reason)`. Wired into the CLI output automatically (`# 47 frames decoded, 0 bad stop bits, packet VALID`).
- `build_command_packet(payload_after_source, source=0x01)` — builds a full length+source+payload+CRC packet ready to transmit, given just the payload bytes.
- `KNOWN_COMMANDS` — the community write-up's Full Stop / Head Up / Head Down / Foot Up / Foot Down / Zero Gravity / Flat payloads, ready to feed into `build_command_packet()`.

## Transmitting (untested — theory only, from the community write-up)
We have not attempted to transmit anything yet — everything so far has been passive listening. Per the community write-up:
- Command packets use source address `0x01` (vs. `0x07` for the bed unit). The full built packets (length + source + payload + CRC, via `build_command_packet()`) are: `05 01 00 00 00 00 00 F9` = Full Stop, `05 01 01 00 00 00 00 F8` = Head Up, `05 01 02 00 00 00 00 F7` = Head Down, `05 01 04 00 00 00 00 F5` = Foot Up, `05 01 08 00 00 00 00 F1` = Foot Down, `05 01 00 10 00 00 00 E9` = Zero Gravity, `05 01 00 00 00 08 00 F1` = Flat.
- A motor keeps running only as long as its command byte is **repeatedly sent**; it stops on an explicit Full Stop or a short guard timeout if transmission just stops.
- **Bus arbitration**: any transmitter must wait for at least a 5 ms silent window on the bus before sending — this is the piece that was missing from our earlier theorizing about whether we could safely inject our own frames without colliding with the bed's own ~139ms broadcast. It suggests this is designed as a genuine shared/multi-drop bus (both the bed and a commander can talk), not a single fixed always-driving master — though we still don't know the electrical drive type (open-drain vs. push-pull), which matters for how safe a mistimed collision actually is. Worth confirming before ever driving the line.
- The multi-base sync/master-slave question from earlier tonight is *not* addressed by this write-up either — still open.

## Next Steps
1. Decode Memory Amber and Memory Green (single tap only — same recall behavior expected as Memory Red, just different saved positions). Preset 1/2/3 also still untested.
2. Catch the Flat momentary flag (byte #5 = `0x08`) live — never actually observed yet, only documented from the community write-up.
3. Catch Memory Red's actual trigger bit/byte, if it has one distinct from the position-recall movement itself (tried at ~0.06s sampling and missed it both times — may need faster sampling or a different byte entirely).
4. Figure out what byte #14 (and correlated #15/#22/#24/#26/#30/#46) actually represents during active massage — the sawtooth pattern suggests live intensity/PWM modulation, not confirmed.
5. Map the raw position values to actual physical angle if possible, keeping in mind they're virtual/estimated, not a real sensor reading.
6. Identify the remaining unaccounted-for bytes — rule out padding vs. something real.
7. Confirm the byte #2 directional bitmask combines correctly (e.g. Head Up + Foot Up → `0x05`), and check whether byte #3's special-function bitmask does too.
8. Determine the sync line's electrical drive type (open-drain vs. push-pull) before ever attempting to transmit.
9. Interface with Home Assistant: build a way to both listen to and *transmit* this protocol from an ESP module (8E1 framing is standard UART, so this is more tractable than we first thought when we assumed 9 raw data bits).
10. Control Bed: use the confirmed directional bitmask, position telemetry, and the community write-up's command payloads to drive real motor commands via Home Assistant.

## Tooling Notes
- [`tools/scope_capture.py`](tools/scope_capture.py) talks to the Siglent scope over SCPI (port 5025) and auto-saves every raw waveform it fetches into `captures/raw/` with a timestamped filename.
- The scope's built-in trigger is a **Serial** pattern trigger (`TRSE? → SERIAL`) tuned to lock onto this bus — it's fragile. Changing memory depth (`MSIZ`) can knock it out of lock (leaves it stuck in `Ready`, never firing); if that happens, front-panel re-selecting the Serial decode/trigger is more reliable than trying to fix it blind over SCPI.
- A Saleae Logic analyzer (`fx2lafw` via `sigrok-cli`) was also tried for continuous multi-button capture. Signal integrity was poor over bare single-wire probes (real EMI pickup from the motor drivers, confirmed by seeing sub-microsecond chatter appear only once sampling past 1MHz) — a twisted signal+ground pair was suggested as the fix but not yet retested. The scope's shielded probe doesn't have this problem.
- The bus is **not continuously active** — real packets ("bursts" of ~46-47 frames) are separated by long silent gaps of roughly 120-150ms. Any decoder working from a free-running/untriggered capture needs to segment on those idle gaps first before decoding, rather than assuming byte-grid alignment from sample 0.
- **Reduced memory depth (`MSIZ 140K` instead of the default `14M`) works fine and is much faster, but the Serial trigger needs a few seconds to re-lock after the change** — don't panic and switch to `AUTO`/free-running if `SAST?` still says `Ready` right after changing depth; waiting ~5-10s let it recover to `Trig'd` on its own without any front-panel intervention.
- `fetch_waveform()` originally waited for a socket **timeout** to detect end-of-transfer, which padded every capture by several seconds regardless of actual transfer size. Fixed to read exactly the byte count the scope declares in its own `#9<9-digit-length>` response header instead. Combined with reduced memory depth and a persistent connection ([`tools/scope_sweep.py`](tools/scope_sweep.py)), per-capture time went from ~7.25s down to ~0.06s.


## Conclusion
This project is still a work in progress. If anyone has experience with similar integrations or insights into working with UART signals, your help would be greatly appreciated.

## Contribution
Feel free to open issues or submit pull requests if you have suggestions or improvements.



