# CLAUDE_INSTALL.md: setting up the Etchatron on this computer

For Claude Code (or another coding agent). The person you are helping has the
Etchatron hardware: a motorised Etch A Sketch driven by an Arduino Uno with a
Protoneer CNC Shield V3 and two TMC2209 drivers. Your job is to get the
control page running on their computer and talking to the Uno. Human-readable
version: [INSTALL.md](INSTALL.md). Upstream: https://github.com/sui001/etchatron

Read INSTALL.md first; it has the hardware facts and the page's controls.
This file adds what an agent needs.

## Ground rules

- **Never move the motors without the person's go-ahead.** Moves draw on the
  screen. Before any move (`M`, `J`, or a Draw from the page) ask them to
  confirm the stylus is centred and the screen is clear.
- Switching motors on (`E 1`) only makes them hold; that is safe to do to test
  power, but say so first and switch them off again (`E 0`) after.
- Stay inside ±550 knob degrees of the zero point (±14667 steps). The screen
  edge is about ±830 horizontally and ±585 vertically; past it the knob turns
  but the stylus doesn't and positions are lost.
- Don't push to the GitHub repo or change the firmware unless asked.
- Only one program can hold the serial port. Close your own connection before
  the person clicks **Connect Uno** in the browser.

## Steps

1. **Check the folder.** You should be in the folder holding this file, with
   `control/`, `lib/`, `controller/` beside it. Read `VERSION` (in the USB
   package; in a git clone use `git log -1 --format="%h %ad"`) and tell the
   person which version this is.
2. **Python 3.** `python --version` (Windows) or `python3 --version` (macOS/Linux).
   If missing, ask before installing (python.org installer, `winget install Python.Python.3.12`,
   or `brew install python`).
3. **Browser.** Chrome or Edge must be installed (Web Serial). Safari and
   Firefox won't work.
4. **Find the Uno.** With USB plugged in:
   - Windows (PowerShell): `Get-CimInstance Win32_PnPEntity | ? Name -match '\(COM\d+\)' | % Name`
     and look for "Arduino Uno (COMn)".
   - macOS: `ls /dev/cu.usbmodem*`. Linux: `ls /dev/ttyACM*` (the user may need
     to be in the `dialout` group).
5. **Check the firmware.** Open the port at 115200 baud, wait ~2.5 s (opening
   resets the Uno), read the banner, then send `?`:
   ```
   === Etchatron controller v0.2.0 ===
   ...
   noise 3 X - Y -
   ready
   S 0 0 0 0 0 613 453 3 1600 -1
   ```
   `noise 3 X - Y -` is **expected**: all three microstep jumpers are fitted on
   both drivers, which ties the TMC2209 UART pin high, so the noise-level
   feature is off and both axes run at 1/16. Don't try to "fix" it.
   Current is on each driver's Vref pot, set to 0.8 V (INSTALL.md, "Motor
   current"); if motors run hot or a driver was replaced, ask the person to
   check it with a multimeter.
   Send a lone newline before your first command: leftover boot bytes can make
   the first line answer `err ?`.
   With pyserial: `python -m pip install pyserial`, then a few lines of Python;
   on Windows, `System.IO.Ports.SerialPort` in PowerShell works with nothing installed.
6. **If there's no banner** (other firmware, or blank board): flash
   `controller/controller.ino`. With arduino-cli:
   ```
   arduino-cli core install arduino:avr
   arduino-cli compile --fqbn arduino:avr:uno controller
   arduino-cli upload  --fqbn arduino:avr:uno -p <PORT> controller
   ```
   No extra libraries (SoftwareSerial is built in). Or ask the person to use
   Arduino IDE 2 (INSTALL.md, "Reflashing").
   If the board has GRBL and they want it back later: `python grbl_setup.py --port <PORT>`.
7. **Power check (optional, with permission).** Send `E 1`, ask whether both
   knobs now feel locked, then `E 0`. Free knobs = no 12 V on the shield: most
   often the barrel plug has come out.
8. **Serve the page from this folder (the root, not `control/`):**
   ```
   python -m http.server 8000
   ```
   Run it in the background. The page loads `../lib/timeline.js`, so serving
   `control/` alone breaks it (404 on `/lib/timeline.js`).
9. **Open http://localhost:8000/control/** in Chrome or Edge. The header shows
   the page version (0.10.1 or later). Then walk the person through INSTALL.md
   "Running it" from step 4: Connect Uno, Output = "Etch A Sketch, Uno on this
   computer", centre by hand with motors off, **Zero here**, clear the screen, Draw.

## Serial protocol (controller v0.2.0, 115200, one command per line)

Full description in the header of `controller/controller.ino`. In short, units
are 1/16 steps, **26.667 steps per knob degree** (200 x 16 x 3 / 360):

| Command | Meaning |
|---|---|
| `M x y` | queue a move to absolute (x, y) |
| `J dx dy` | queue a move relative to the last target |
| `Z` | current position becomes (0, 0), idle only |
| `E 0` / `E 1` | motors off / on |
| `B bx by n` | slack take-up in steps, blend n (page default: 613 453 3) |
| `F sps` | speed, steps per second (100-8000) |
| `!` | stop now, no newline needed |
| `?` | status: `S x y queued done motors bx by blend sps noise` |

Positive X = right, positive Y = up (DIR LOW = clockwise = positive).

## Where things are

| Path | What |
|---|---|
| `control/index.html` | the control page (attractors, sound, drawing) |
| `lib/timeline.js` | 16 timeline attractors, shared with `timeline/` |
| `views/`, `timeline/` | screen-only pages, same server |
| `controller/controller.ino` | Uno firmware for the page |
| `lorenz/lorenz.ino` | stand-alone Lorenz sketch, no computer needed |
| `spiral/` | backlash test that set slack X 23° / Y 17°, blend 3 |
| `knob/`, `tools/etchatron_knob.py` | printable pulleys and their generator |
| `control/fischer/lorenz_av.py` | Prof. Fischer's original script (Python, pygame, sounddevice); the page is a port of it |

## When reporting back

Tell the person the package version (`VERSION`), the page version (header),
and the firmware version (banner), so all three can be traced if something
needs fixing.
