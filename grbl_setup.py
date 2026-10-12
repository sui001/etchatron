"""grbl_setup.py: push Etchatron's settings into a freshly flashed GRBL, and read them back.

    python etchatron/grbl_setup.py --port COM60            apply, then verify
    python etchatron/grbl_setup.py --port COM60 --show     read what is there, change nothing

Same pattern as genarm/host/grbl_setup.py. GRBL's $$ settings live in the
Uno's EEPROM and survive a power cycle but not a reflash, and they are the
sort of thing that gets typed into a terminal once and lost. This is the record.

Board: Uno + Protoneer CNC Shield V3, BTT TMC2209s standalone, Creality 42-40s.
Firmware: gnea/grbl 1.1h (grbl_v1.1h.20190825.hex), flashed 2026-10-12.
Supply: 12 V with the current limit at 2 A or more. On a limited bench supply
the second axis starves and sits there with a faint drag, which looks exactly
like a dead driver (2026-10-12, cost a driver swap to find).

X = horizontal knob (left), Y = vertical knob (right). Drive is 1:1, the
motor wears a twin of the knob, so a motor turn is a knob turn.

UNITS ARE KNOB DEGREES for now, not mm. Stylus travel per knob turn is
unknown until the Etch A Sketch arrives; when it is measured, $100/$101
become steps per mm of stylus and nothing else here needs to change.
"""

import argparse
import time

try:
    import serial
except ImportError:
    raise SystemExit("pyserial missing:  pip install pyserial")

# All three jumpers under each driver: on a BTT TMC2209 the shield's M0/M1
# land on MS1/MS2, both high = 1/16 (interpolated to 256 by the chip). The
# third lands on PDN_UART; high there turns OFF standstill current reduction,
# so idle motors sit at full current. $1=25 below lets them go limp instead.
MICROSTEP = 16
STEPS_PER_DEG = 200 * MICROSTEP / 360.0      # 8.889, 1:1 belt

# (setting, value, why). steps/unit before rates, so a rate is never briefly
# interpreted against the wrong scale.
SETTINGS = [
    ("$100", "%.3f" % STEPS_PER_DEG, "X knob steps/deg  1/16, 1:1 belt"),
    ("$101", "%.3f" % STEPS_PER_DEG, "Y knob steps/deg  1/16, 1:1 belt"),

    ("$110", "3600",   "X max deg/min = 10 knob turns/min, conservative to start"),
    ("$111", "3600",   "Y max deg/min"),

    ("$120", "720",    "X accel deg/s^2"),
    ("$121", "720",    "Y accel deg/s^2"),

    # DIR INVERT MASK, bit 0 = X, bit 1 = Y. + should move the stylus right
    # (X) and up (Y); on an EaS both of those are the knob turning CLOCKWISE.
    # A belt keeps the sense, so motor clockwise = knob clockwise, PROVIDED
    # the motor shaft faces out of the board like the knob (the 1:1 twin
    # layout). Mount a motor shaft-backwards and its bit flips.
    #
    # Both checked 2026-10-12: +360 turned each one clockwise seen from the
    # shaft end. Correct as they are.
    ("$3",   "0",      "dir invert: none, both checked clockwise-positive"),
    ("$4",   "0",      "step enable invert: shield enable is active low already"),

    ("$20",  "0",      "soft limits off, they need homing and there are no endstops"),
    ("$21",  "0",      "hard limits off, nothing on the limit pins"),
    ("$22",  "0",      "homing off, same reason"),

    # A plotter, not an arm: nothing falls when the motors let go, and the
    # knob friction holds the stylus. Default 25 ms is kind to the motors,
    # which matters more here because PDN high means no standstill reduction.
    ("$1",   "25",     "de-energise 25 ms after a move, knob friction holds"),

    # WPos, not MPos: genarm learned that G92 does not move MPos, so anything
    # checking position against MPos ignores a declared zero.
    ("$10",  "0",      "report WPos so G92 zeroing shows up"),
    ("$13",  "0",      "report in mm, i.e. degrees, not inches"),
]


class Grbl:
    def __init__(self, port):
        self.ser = serial.Serial(port, 115200, timeout=0.5)
        time.sleep(2.0)
        self.ser.reset_input_buffer()
        self.ser.write(b"\r\n")
        time.sleep(0.5)
        self.ser.reset_input_buffer()

    def send(self, line, wait=6.0):
        self.ser.write((line + "\n").encode())
        t0 = time.monotonic()
        out = []
        while time.monotonic() - t0 < wait:
            raw = self.ser.readline().decode(errors="replace").strip()
            if not raw:
                continue
            if raw == "ok":
                return out
            if raw.startswith("error:") or raw.startswith("ALARM"):
                raise RuntimeError("%s  (sent %s)" % (raw, line))
            out.append(raw)
        raise TimeoutError("no ok for %r" % line)

    def close(self):
        self.ser.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", required=True)
    ap.add_argument("--show", action="store_true", help="read only, change nothing")
    args = ap.parse_args()

    g = Grbl(args.port)
    try:
        if not args.show:
            for key, val, why in SETTINGS:
                g.send("%s=%s" % (key, val))
                print("  %-6s %-9s %s" % (key + "=", val, why))
            print()

        # read back and CHECK, rather than trusting that the writes landed
        have = {}
        for line in g.send("$$", wait=8.0):
            if line.startswith("$") and "=" in line:
                k, v = line.split("=", 1)
                have[k.strip()] = v.split(" ")[0].strip()

        bad = []
        for key, val, why in SETTINGS:
            got = have.get(key)
            if got is None:
                bad.append("%s missing from $$" % key)
            elif abs(float(got) - float(val)) > 1e-3:
                bad.append("%s is %s, expected %s" % (key, got, val))
        print("read back %d settings" % len(have))
        if bad:
            print("MISMATCH:")
            for b in bad:
                print("  " + b)
            raise SystemExit(1)
        print("all %d of ours verified against the board" % len(SETTINGS))
    finally:
        g.close()


if __name__ == "__main__":
    main()
