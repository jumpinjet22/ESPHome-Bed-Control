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

Only the idle capture and everything under `raw/` have the raw waveform saved; the other listed files only have decoded byte/timing output.
