# Captures

Raw and decoded data pulled from the Siglent SDS1202X-E over SCPI on 2026-07-18. See the "Protocol Findings" section of the top-level [README](../README.md) for what these show.

- `idle_c1_wf.bin` — raw channel 1 waveform, no button pressed, recaptured after tightening the scope's vertical scale (500 mV/div, -1.75V offset) to use ~69% of the 8-bit ADC range instead of the original ~35%. Signed 8-bit samples (DAT2 format) at 1 GSa/s, 14,000,000 points = 14 ms. Decode with `tools/scope_capture.py`'s `decode_9bit_uart()`, or:
  ```python
  import numpy as np
  samples = np.fromfile("idle_c1_wf.bin", dtype=np.int8).astype(np.int32)
  ```
- `idle.txt` — decoded frame table for the same idle capture above.
- `flatten.txt`, `headup.txt`, `headdown.txt`, `footup.txt`, `footdown.txt`, `zerog.txt` — decoded frame tables (`tools/scope_capture.py` stdout) captured while each button was held.
- `released.txt` — decoded frames captured immediately after releasing Head Up, to confirm byte #3 reverts to idle.
- `headup_series.txt`, `footup_series.txt` — 4 successive captures taken during a single continuous button hold (~1.2s apart), used to find the head/foot position bytes (#18–19 and #20–21) by watching which bytes drift then freeze when the motor hits its travel limit.
- `flatten_series.txt` — 8 successive captures (~1s apart) taken during a single momentary Flatten press. Confirms #18–19 and #20–21 as head/foot position: both drift while the base is still moving, then land on exactly `00 00` simultaneously and hold there once the base finishes flattening (`0` = flat/home reference for both axes).
- `light.txt`, `light2.txt`, `light_r1_held.txt`...`light_r6_released.txt` — 6 alternating held/released round-trip captures for the Light button, confirming byte #4 as its momentary-press status (`0x02` held, `0x00` released, 6/6 clean).
- `light_rapid.txt` — one capture taken during rapid on/off toggling (inconclusive by itself — capture cadence is too slow relative to the toggling to correlate a single snapshot).
- `light_physically_off.txt`, `light_physically_on.txt`, `light_state_r1_on.txt`...`light_state_r6_off.txt` — 4 "light on" + 4 "light off" captures (button released, bulb state only) used to find byte #11 as the actual persistent light-state bit: exactly `0x21` every time it's on, exactly `0x20` (header bit set) every time it's off, across all 8 samples.
- `raw/` — raw waveform `.bin` files auto-saved by `tools/scope_capture.py` on every run (added once the script started doing this automatically partway through the session — earlier captures above predate it and only have decoded text).
- `full_sweep_2.txt` — 750 samples over 75s (`tools/scope_sweep.py`) taken while going through the full button list in order. Used to reconfirm the directional bitmask, Light, and find Zero G's byte #3 = `0x10` live for the first time; also surfaced (but didn't confirm) candidate values for the massage/timer/memory buttons, which were then verified individually below.
- `massage_left2.txt`, `center_timer.txt`, `massage_right.txt` — fast bursts (~50 samples over 4s, `tools/scope_sweep.py`) confirming byte #3's special-function bitmask: `0x08` = Massage-left, `0x02` = Timer (the clock icon, cycles 10/20/30 min with repeated taps), `0x04` = Massage-right.
- `timer10_v3.txt`, `timer20.txt` — fast bursts while triggering the Timer/massage function, showing byte #14 (and correlated bytes) ramping in a repeating sawtooth once the massage motor is running — live intensity/PWM modulation, not a simple flag. Meaning not fully confirmed.
- `memory_red2.txt`, `memory_red3.txt` — two separate Memory Red presses, each showing the bed autonomously drive to the same target position (head froze at `0x0720`, foot climbed toward `0x0DAD` both times) — reproducible confirmation that Memory Red recalls a saved position, even though the discrete trigger byte for the button press itself was never caught.
- `memory_amber_yellow.txt`, `memory_green.txt` — 15s padded captures (`tools/scope_sweep.py`) around firing the Amber and Green memory presets, used to nail down byte #11 bit 2 as a "traveling to a preset" flag: set for the whole travel, clears the instant the base stops. Cross-checked live against `headup_series.txt`/`footup_series.txt` (a directly-held directional button, not a preset) to confirm the bit stays clear there even with the motor clearly running — it's specifically preset-travel, not general motor activity.

Only the idle capture and everything under `raw/` have the raw waveform saved; the other listed files only have decoded byte/timing output.
