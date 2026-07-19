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

Only the idle capture has the raw waveform saved; the rest only have the decoded byte/timing output (the raw samples for those runs weren't written to disk).
