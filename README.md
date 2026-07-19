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

## Protocol Findings (2026-07-18)
The oscilloscope used above (a Siglent SDS1202X-E) exposes a SCPI socket on the network, so instead of reading screenshots by eye, the raw waveform samples were pulled directly and decoded in software. See [`tools/scope_capture.py`](tools/scope_capture.py) — point it at the scope's IP and it fetches and decodes channel 1.

- **Bit timing:** 26,000 ns per bit (~38,461 baud — close to, but not exactly, the standard 38400 baud rate).
- **Framing:** 1 start bit + **9 data bits** + 1 stop bit (11 unit intervals total) — not plain 8-bit UART. Switching the decoder from 8 to 9 data bits dropped stop-bit framing errors from ~50% to 0%, which is strong confirmation this is the real frame size.
- **Cadence:** frames run back-to-back with zero idle gap, at a rock-steady 286.00 µs/frame (~3,496 frames/sec) — confirmed with zero jitter across every capture taken.
- **9th bit as a header marker:** the extra data bit behaves like the classic 9-bit multiprocessor-UART scheme, where frames with bit 9 set act as packet headers and the following bit-9-clear bytes are payload.
- **Fixed framing bytes:** every packet opens with `2C 07` and closes with `08(hdr) FF FF A4(hdr) 00 01(hdr) 01(hdr) 00 00`, identical in every capture regardless of button state.
- **Byte #3 is a directional-button bitmask**, confirmed by holding each button individually and watching the byte change live, then revert to `0x00` on release:

  | Bit | Value | Button |
  |---|---|---|
  | 0 | `0x01` | Head Up |
  | 1 | `0x02` | Head Down |
  | 2 | `0x04` | Foot Up |
  | 3 | `0x08` | Foot Down |

  Because it's a real bitmask (not a sequential code), it should support simultaneous combinations, e.g. Head Up + Foot Up held together should read `0x05`.
- **Momentary/preset buttons behave differently:** Zero G and Flatten did *not* set byte #3 while held. Likely explanation: they trigger a one-shot canned motion on the base itself, unlike the directional buttons, which probably need a continuous "held" signal from the remote to keep driving a motor.
- **Bytes #18–19 and #20–21 look like live head/foot position telemetry.** Taking several captures in a row *during a single continuous button hold* (rather than one snapshot per button) showed:
  - While holding Head Up, bytes #18–19 changed capture-to-capture, then froze the instant the motor hit its mechanical travel limit (confirmed against real-time "it stopped" feedback while still holding the button).
  - While holding Foot Up, bytes #18–19 stayed **exactly** at the value they'd frozen at during the Head Up test (carried over correctly since the head wasn't touched), while bytes #20–21 did the same drift-then-freeze dance instead.
  - This cross-check (moving one axis leaves the other axis's field untouched, and values persist across separate test runs) is good evidence these are real 2-byte position registers: **#18–19 = head position, #20–21 = foot position.**
  - Confirmed further with a momentary Flatten press, sampled 8 times over the run: both #18–19 and #20–21 were still drifting in the first two samples, then **landed on exactly `0x0000` simultaneously** and held there once the base finished flattening — `0` is the flat/home reference for both axes. Bytes #9 and #11 also flip state at the same instant, looking like a separate "system moving / idle" status flag independent of the per-button bitmask (which stays `0x00` throughout since Flatten is momentary, not held).
- **Byte #27 looks like a motor current/voltage-sense reading**, not position: it sits in a narrow band (`0x46`–`0x4D`) and steps by a small fixed amount exactly when a motor transitions from actively driving to stalled/idle — consistent with supply-rail sag under motor load rather than a per-axis encoder value (Head Up and Foot Up read identically, which a true per-axis position value shouldn't).
- **Other bytes in the middle block** (roughly #22–26, #30) still vary between captures with no obvious pattern tied to button state or position — likely a rolling counter, timestamp, or checksum. Not yet understood.

## Next Steps
1. Decode the remaining buttons: massage functions, light, and presets 1/2/3.
2. Map the raw values of bytes #18–19 / #20–21 to actual physical angle (e.g. capture at both extreme travel limits and at several points in between) to get real min/max/scale.
3. Identify the remaining unexplained bytes (#22–26, #30) — rule out rolling counter vs. checksum vs. something else.
4. Confirm the button bitmask combines correctly (e.g. Head Up + Foot Up → `0x05`).
5. Interface with Home Assistant: build a way to both listen to and *transmit* this 9-bit protocol from an ESP module (most UART peripherals only support 8 data bits, so this will need extra care).
6. Control Bed: use the confirmed directional bitmask and position telemetry to drive real motor commands via Home Assistant with position feedback.


## Conclusion
This project is still a work in progress. If anyone has experience with similar integrations or insights into working with UART signals, your help would be greatly appreciated.

## Contribution
Feel free to open issues or submit pull requests if you have suggestions or improvements.



