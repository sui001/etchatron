# Etchatron

A motorised Etch A Sketch, made for Thomas Fischer (SUSTech). Two steppers
turn the knobs through GT2 belts. Moved out of gen3d on 19 Oct 2026 with its
history.

![Etchatron drawing the Lorenz attractor, 25 Nov 2026](photos/etchatron_lorenz_2026-11-25.jpg)

*The Lorenz attractor at scale 20, drawn from the control page (25 Nov 2026). The crosshair is the jog test that measured the screen's travel.*

Setting it up on a new computer: [INSTALL.md](INSTALL.md) (people) and [CLAUDE_INSTALL.md](CLAUDE_INSTALL.md) (for Claude Code).

| Path | What it is |
|---|---|
| `control/index.html` | Control page: Thomas's five attractors with sound and afterglow (port of `control/thomas/lorenz_av.py`). Outputs: any piplot machine, including this Etch A Sketch when its Uno is on plotterpi (piplot 0.12.0 `etchatron` driver), or the Uno on this laptop over Web Serial. Served by piplot at http://100.68.139.69:8080/etchatron.html; `control/deploy_to_plotterpi.sh` puts it there |
| `views/index.html` | Views page: one of the same five attractors as four live screens, looking down x, y and z plus an orthogonal 3D view you drag to turn. Screens only, no sound or machine output. `python -m http.server 8000 --directory views` |
| `timeline/index.html` | Attractor timeline: 16 entries from Ptolemy's epicycles (about 150 CE) through the pendulum, Watt's governor, van der Pol, Ashby's homeostat and Ueda to Lorenz and after, each live on the same four screens, in ink on paper. Every entry is tested for chaos and calibrated to Lorenz's speed. Screens only for now. Serve the repo root and open `/timeline/` |
| `controller/` | Uno firmware the control page talks to: queued absolute moves, blended slack take-up, position reports. Protocol in the file header |
| `spiral/` | Slack (backlash) test spiral with ring ladders for amount and blend speed; where X 23 / Y 17, blend 3 came from |
| `lorenz/` | Standalone Lorenz attractor sketch for an Uno + Protoneer CNC Shield V3 + TMC2209s (step/dir, replaces GRBL) |
| `grbl_setup.py` | Apply and read back the GRBL settings, for when the Uno runs GRBL 1.1h instead |
| `tools/etchatron_knob.py` | Knob and pulley generator: replacement knob, motor twin, and the over-knob 60T pulley that slots over the original knob. Writes to `knob/` |
| `tools/claims.py` | Geometry assertions the knob build has to pass (a copy of gen3d's) |
| `knob/` | Generated STLs, renders and `claims_*.json` |

Current drive: the over-knob 60T pulley on each original knob, driven by 20T
motor pulleys (3:1), 26.667 steps per knob degree. Measured screen travel (25 Nov 2026): about 1660 knob degrees wide by 1170 tall, so ±830 and ±585 from the centre; the page's Limit defaults to ±550.

Control page: flash `controller/`, then serve the repo root (Web Serial wants localhost, and the page loads `lib/timeline.js`):

```bash
python -m http.server 8000
```

then open http://localhost:8000/control/ in Chrome or Edge. Simulate machine runs it with nothing plugged in.

```bash
python tools/etchatron_knob.py --over-knob
python grbl_setup.py --port COM60 --show
```
