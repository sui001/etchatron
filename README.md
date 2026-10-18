# Etchatron

A motorised Etch A Sketch, made for Thomas Fischer (SUSTech). Two steppers
turn the knobs through GT2 belts. Moved out of gen3d on 19 Oct 2026 with its
history.

| Path | What it is |
|---|---|
| `lorenz/` | Standalone Lorenz attractor sketch for an Uno + Protoneer CNC Shield V3 + TMC2209s (step/dir, replaces GRBL) |
| `grbl_setup.py` | Apply and read back the GRBL settings, for when the Uno runs GRBL 1.1h instead |
| `tools/etchatron_knob.py` | Knob and pulley generator: replacement knob, motor twin, and the over-knob 60T pulley that slots over the original knob. Writes to `knob/` |
| `tools/claims.py` | Geometry assertions the knob build has to pass (a copy of gen3d's) |
| `knob/` | Generated STLs, renders and `claims_*.json` |

Current drive: the over-knob 60T pulley on each original knob, driven by 20T
motor pulleys (3:1).

```bash
python tools/etchatron_knob.py --over-knob
python grbl_setup.py --port COM60 --show
```
