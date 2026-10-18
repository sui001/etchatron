"""Etchatron knob: a replacement Etch A Sketch knob with a GT2 pulley under it.

The original knob prises off its stem. This goes on in its place: the top
half keeps the look of the original (white, fluted, rounded top edge) so it
still turns by hand and still reads as an Etch A Sketch, and the bottom half,
nearest the frame, is a GT2 tooth band between two flanges. The knob head is
the outer flange. Belt runs 1:1 to a stepper wearing the --motor twin of
this knob (Sui, 12 Oct: direct drive is proven on NEMA 17s, and 3200 steps
a turn is far finer than the line an EaS draws).

DIMENSIONS ARE GUESSES until the EaS arrives. The only number anyone has
published is the stem, 3/16" (4.76 mm), from two independent builds. Knob
OD, flute count and stem length are best estimates and every one is a flag:
measure with calipers, pass the real numbers, rebuild.

Stem grip is three crush ribs in a round bore (forgiving of a stem we have
not seen), plus an optional M3 grub tapped straight into the plastic.

Printed frame-side flange down on the bed, no supports. The only overhang is
the knob head's underside ledge over the tooth tips (about 1.5 mm).

--motor builds the twin that goes on the stepper. Drive is 1:1, so the motor
wears the same knob it turns: same head, same tooth band, and only the bore
differs. 5 mm D-bore with the flat facing an M3 grub tapped into the head
between two flutes; no nut trap, because its slot would have to open through
the top face and break the twin. The flat carries the torque, the grub only
stops it walking. The bore is blind and the knob pushes on until it bottoms
on the shaft tip, so where it sits is set by the shaft length, not by eye.

    python tools/etchatron_knob.py [--teeth 40] [--head-od 28] [--stem 4.76] ...
    python tools/etchatron_knob.py --motor [--shaft-len 24] ...
    python tools/etchatron_knob.py --over-knob [--knob-od 28 --knob-h 11] ...

--over-knob (15 Oct) leaves the original EaS knob on and slots over it
instead. Same form, enlarged: a 30 mm cavity (2 mm over the 28 mm knob)
with six crush ribs that grip the knob, and the M3 grub tightens on it.
A 28 mm knob inside means the tooth band has to grow to 60T to keep a wall
under the grooves, so the motor (still the 40T twin) drives it 1.5:1, not
1:1. Print it head down: the open cavity faces up and needs no bridge.

Writes etchatron/knob/knob[_motor]_gt2_<N>t.stl, claims and a render.
Exits 1 if any claim fails.
"""

import argparse
import math
import os
import sys

import numpy as np
import trimesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import claims as hc  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "etchatron", "knob")

# GT2: 2 mm pitch, pitch line 0.254 mm outside the tooth tips
PITCH, PLD = 2.0, 0.254
GROOVE_DEPTH, GROOVE_R = 0.75, 0.6     # belt tooth is 0.75 high, 0.555 radius
BELT_T = 1.38                          # GT2 overall thickness


def build(a):
    pd = a.teeth * PITCH / math.pi
    r_tip = pd / 2 - PLD
    R = a.head_od / 2
    Rf = a.flange_od / 2

    z_teeth0 = a.flange_t
    z_teeth1 = z_teeth0 + a.tooth_width
    z_head0 = z_teeth1
    z_top = z_head0 + a.head_h
    e = a.edge_r

    # revolve profile: frame flange, tooth band, head with a rounded top edge
    arc = [(R - e + e * math.cos(t), z_top - e + e * math.sin(t))
           for t in np.linspace(0, math.pi / 2, 12)]
    prof = ([(0, 0), (Rf, 0), (Rf, z_teeth0), (r_tip, z_teeth0), (r_tip, z_head0),
             (R, z_head0)] + arc + [(0, z_top)])
    body = trimesh.creation.revolve(np.array(prof), sections=a.facets)

    cuts = []
    # belt grooves, only in the tooth band
    rc = r_tip - GROOVE_DEPTH + GROOVE_R
    for i in range(a.teeth):
        th = 2 * math.pi * i / a.teeth
        c = trimesh.creation.cylinder(radius=GROOVE_R, height=a.tooth_width, sections=32)
        c.apply_translation([rc * math.cos(th), rc * math.sin(th),
                             (z_teeth0 + z_teeth1) / 2])
        cuts.append(c)

    # flutes round the head, stopping short of the rounded edge like the original
    fz0, fz1 = z_head0 + a.flute_skip, z_top - e + 0.4   # run out into the round
    rf = R + a.flute_r - a.flute_depth
    for i in range(a.flutes):
        th = 2 * math.pi * (i + 0.5) / a.flutes
        c = trimesh.creation.cylinder(radius=a.flute_r, height=fz1 - fz0, sections=24)
        c.apply_translation([rf * math.cos(th), rf * math.sin(th), (fz0 + fz1) / 2])
        cuts.append(c)

    # blind bore from the frame side; on the motor knob a D, flat facing +x
    bore = trimesh.creation.cylinder(radius=a.bore / 2, height=a.bore_depth + 1, sections=64)
    bore.apply_translation([0, 0, (a.bore_depth - 1) / 2])
    if a.motor:
        keep = trimesh.creation.box(extents=[a.bore, a.bore * 2, a.bore_depth + 4])
        keep.apply_translation([a.flat_at - a.bore / 2, 0, a.bore_depth / 2])
        bore = trimesh.boolean.intersection([bore, keep], engine="manifold")
    cuts.append(bore)

    # optional M3 grub, radial along +x, tapped into the plastic, in the head
    zg = None
    if a.grub > 0:
        zg = z_head0 + a.grub_up
        g = trimesh.creation.cylinder(radius=a.grub / 2, height=R + 1, sections=32)
        g.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2, [0, 1, 0]))
        g.apply_translation([(R + 1) / 2, 0, zg])
        cuts.append(g)

    part = trimesh.boolean.difference([body] + cuts, engine="manifold")
    dims = dict(pd=pd, r_tip=r_tip, rc=rc, z_teeth0=z_teeth0, z_teeth1=z_teeth1,
                z_head0=z_head0, z_top=z_top, zg=zg, rf=rf)
    if a.motor:
        return part, dims

    # crush ribs added back into the bore, clear of the grub
    ribs = []
    rib_w = a.bore / 2 - a.rib_id / 2
    for i in range(a.ribs):
        th = 2 * math.pi * (i + 0.5) / a.ribs     # half a pitch off +x, clear of the grub
        b = trimesh.creation.box(extents=[rib_w + 0.4, a.rib_t, a.bore_depth + 0.4])
        rmid = a.rib_id / 2 + (rib_w + 0.4) / 2
        b.apply_translation([rmid, 0, (a.bore_depth + 0.4) / 2])   # into the ceiling, not flush
        b.apply_transform(trimesh.transformations.rotation_matrix(th, [0, 0, 1]))
        ribs.append(b)
    # lead-in: ribs start a little above the bed so the stem finds the bore
    lead = trimesh.creation.cylinder(radius=a.bore / 2 + 0.6, height=2 * a.rib_lead, sections=64)
    rib = trimesh.boolean.difference([trimesh.boolean.union(ribs, engine="manifold"), lead],
                                     engine="manifold")
    part = trimesh.boolean.union([part, rib], engine="manifold")
    return part, dims


def parser():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--teeth", type=int, default=40,
                   help="40T: pitch dia 25.5, close to the knob; same on both ends, 1:1")
    p.add_argument("--head-od", type=float, default=28.0, help="GUESS, measure the original")
    p.add_argument("--head-h", type=float, default=11.0, help="GUESS, original knob height")
    p.add_argument("--edge-r", type=float, default=2.0, help="rounded top edge")
    p.add_argument("--flutes", type=int, default=24, help="GUESS, count the original")
    p.add_argument("--flute-r", type=float, default=1.3)
    p.add_argument("--flute-depth", type=float, default=0.8)
    p.add_argument("--flute-skip", type=float, default=1.0,
                   help="plain band at the bottom of the head before the flutes start")
    p.add_argument("--flange-od", type=float, default=30.0,
                   help="frame-side flange; hidden against the frame so it can outgrow the head")
    p.add_argument("--flange-t", type=float, default=1.4)
    p.add_argument("--tooth-width", type=float, default=7.0, help="6 mm belt + clearance")
    p.add_argument("--stem", type=float, default=4.76,
                   help="3/16\", the one published number; measure it")
    p.add_argument("--bore", type=float, default=5.3, help="round bore the ribs sit in")
    p.add_argument("--rib-id", type=float, default=4.55,
                   help="circle the rib tips touch; printed ribs come up a bit fat")
    p.add_argument("--rib-t", type=float, default=0.8)
    p.add_argument("--ribs", type=int, default=3, help="crush ribs round the bore")
    p.add_argument("--rib-lead", type=float, default=1.0, help="rib-free lead-in at the mouth")
    p.add_argument("--bore-depth", type=float, default=12.0, help="GUESS, stem length")
    p.add_argument("--grub", type=float, default=2.6,
                   help="M3 tapping hole; 0 for no grub")
    p.add_argument("--grub-up", type=float, default=1.5, help="grub height above head base")
    p.add_argument("--motor", action="store_true",
                   help="the stepper twin: D-bore, no ribs; changes the bore defaults")
    p.add_argument("--over-knob", action="store_true",
                   help="slot over the original knob instead of replacing it; changes defaults")
    p.add_argument("--knob-od", type=float, default=28.0, help="original knob, measured 15 Oct")
    p.add_argument("--knob-h", type=float, default=11.0, help="original knob, measured 15 Oct")
    p.add_argument("--flat-at", type=float, default=2.05, help="D flat, mm from the axis")
    p.add_argument("--shaft-len", type=float, default=24.0,
                   help="shaft length out from the motor face; measured X 15, Y 24 (12 Oct)")
    p.add_argument("--boss-h", type=float, default=2.0, help="NEMA 17 front boss height")
    p.add_argument("--facets", type=int, default=180)
    # thresholds
    p.add_argument("--min-flange-over-belt", type=float, default=0.8,
                   help="flange must stand this far beyond the belt's back")
    p.add_argument("--min-grip", type=float, default=0.1,
                   help="rib interference on the stem, diameter")
    p.add_argument("--min-wall", type=float, default=1.5, help="plastic over the bore end")
    p.add_argument("--min-boss-gap", type=float, default=0.8,
                   help="frame flange must clear the motor boss by this much")
    return p


MOTOR_BORE = 5.25
MOTOR_SEAT_GAP = 3.0        # knob flange off the motor face: boss 2 + clearance
MOTOR_MAX_DEPTH = 16.0      # leaves 3.4 mm of top over the shaft tip


def parse(argv=None):
    """Motor mode derives bore depth and grub height from --shaft-len, so the
    one number measured on each motor is the only one passed. The two 42-40s
    here differ (X 15 mm, Y 24 mm, 12 Oct), so one motor knob does not fit both.
    A flag given explicitly always wins."""
    argv = sys.argv[1:] if argv is None else argv
    a = parser().parse_args(argv)
    given = {x.split("=")[0] for x in argv}
    if a.over_knob:
        # cavity 2 mm over the knob, ribs 0.4 into it; 60T keeps ~3 mm under the grooves
        for k, v in (("teeth", 60), ("head_od", 42.0), ("flange_od", 42.0),
                     ("stem", a.knob_od), ("bore", a.knob_od + 2.0),
                     ("rib_id", a.knob_od - 0.4), ("ribs", 6),
                     ("bore_depth", a.knob_h + 0.5)):
            if "--" + k.replace("_", "-") not in given:
                setattr(a, k, v)
    if a.motor:
        if "--bore" not in given:
            a.bore = MOTOR_BORE
        if "--bore-depth" not in given:
            a.bore_depth = min(MOTOR_MAX_DEPTH, a.shaft_len - MOTOR_SEAT_GAP)
        if "--grub-up" not in given:
            # as high as it can go and still land on shaft with 0.8 to spare
            z_head0 = a.flange_t + a.tooth_width
            a.grub_up = min(4.0, a.bore_depth - a.grub / 2 - 0.8 - z_head0)
    return a


def main():
    a = parse()
    part, d = build(a)
    kind = "motor knob" if a.motor else "knob"
    C = hc.Claims("etchatron %s, GT2 %dT, head %.0f mm, %d flutes"
                  % (kind, a.teeth, a.head_od, a.flutes))

    hc.closed_volume(C, part, "knob")
    hc.single_body(C, part, "knob", floor=50.0)
    hc.survives_the_file(C, part, "knob")

    C.require("belt fits between the flanges", a.tooth_width >= 6.5,
              "%.1f mm for a 6 mm belt" % a.tooth_width)
    belt_back = d["pd"] / 2 - PLD + (BELT_T - GROOVE_DEPTH)
    # the belt sees the plain band under the flutes, full OD, unless there is none
    r_head = a.head_od / 2 if a.flute_skip >= 0.6 else a.head_od / 2 - a.flute_depth
    for name, r in (("frame flange", a.flange_od / 2), ("knob head", r_head)):
        C.require("%s stands beyond the belt back" % name,
                  r - belt_back >= a.min_flange_over_belt,
                  "%.2f mm past the belt back (floor %.2f)" % (r - belt_back, a.min_flange_over_belt))

    # measure off the mesh, not the parameters
    v = part.vertices
    rad = np.linalg.norm(v[:, :2], axis=1)
    head = v[:, 2] > d["z_head0"] + 0.01
    C.require("head OD measured on the mesh", abs(2 * rad[head].max() - a.head_od) < 0.05,
              "%.2f mm (frame flange %.2f)" % (2 * rad[head].max(), 2 * rad[~head].max()))
    z_mid = (d["z_teeth0"] + d["z_teeth1"]) / 2
    ring = np.array([[d["r_tip"] - 0.2, 0, z_mid]])
    rot = [trimesh.transformations.rotation_matrix(2 * math.pi * k / (4 * a.teeth), [0, 0, 1])
           for k in range(4 * a.teeth)]
    pts = np.vstack([trimesh.transform_points(ring, M) for M in rot])
    solid = part.contains(pts)
    edges = int(np.sum(solid & ~np.roll(solid, -1)))
    C.require("tooth count measured on the mesh", edges == a.teeth,
              "%d grooves found round the band, %d asked" % (edges, a.teeth))

    if a.motor:
        # the flat measured on the mesh: solid just past it at +x, open elsewhere
        zc = a.bore_depth / 2
        pr = part.contains(np.array([[a.flat_at + 0.15, 0, zc], [-(a.bore / 2 - 0.15), 0, zc],
                                     [0, a.bore / 2 - 0.15, zc]]))
        C.require("D flat on the mesh, facing the grub", pr[0] and not pr[1] and not pr[2],
                  "flat %.2f from axis, round side open to %.2f" % (a.flat_at, a.bore / 2))
        gap = a.shaft_len - a.bore_depth
        C.require("knob clears the motor boss", gap >= a.boss_h + a.min_boss_gap - 1e-9,
                  "bottoms on the shaft %.1f off the motor face, boss %.1f, shaft %.1f"
                  % (gap, a.boss_h, a.shaft_len))
        C.note("belt line", "belt centre %.1f mm off the motor face; the EaS knob belt "
               "centre must match, set by the motor mount"
               % (gap + d["z_teeth0"] + a.tooth_width / 2))
    else:
        grip = a.stem - a.rib_id
        C.require("ribs grip the stem", grip >= a.min_grip,
                  "%.2f mm interference on a %.2f stem" % (grip, a.stem))
        C.require("bore clears the stem between ribs", a.bore > a.stem + 0.3,
                  "%.2f bore, %.2f stem" % (a.bore, a.stem))
    root_wall = d["r_tip"] - GROOVE_DEPTH - a.bore / 2
    C.require("wall under the belt grooves", root_wall >= a.min_wall,
              "%.2f mm from groove root to bore (floor %.2f)" % (root_wall, a.min_wall))
    probe = np.array([[0, 0, a.bore_depth - 0.5], [0, 0, a.bore_depth + a.min_wall - 0.05]])
    inside = part.contains(probe)
    C.require("bore is open to its depth, closed above", (not inside[0]) and inside[1],
              "%.1f deep, %.1f mm over it" % (a.bore_depth, d["z_top"] - a.bore_depth))
    if d["zg"] is not None:
        C.require("grub lands in the bore", d["zg"] < a.bore_depth - a.grub / 2,
                  "grub at z %.1f, bore to %.1f" % (d["zg"], a.bore_depth))
        C.require("grub sits between flutes or in the plain band",
                  d["zg"] - a.grub / 2 >= d["z_head0"], "z %.1f" % d["zg"])

    if a.over_knob:
        C.note("fit", "slots over the original knob: %.0f mm cavity on a %.0f mm knob, "
               "%d ribs at %.1f, top bottoms on the knob and the rim sits %.1f below its base"
               % (a.bore, a.knob_od, a.ribs, a.rib_id, a.bore_depth - a.knob_h))
        C.note("print", "head down, no supports; frame flange overhangs the tooth tips",
               overhang_mm=round(a.flange_od / 2 - d["r_tip"], 2), height_mm=round(d["z_top"], 2))
        C.note("drive", "pitch dia %.2f mm, %dT; off the 40T motor twin that is %.2f:1, "
               "so GRBL steps/deg becomes %.3f" % (d["pd"], a.teeth, a.teeth / 40,
                                                   3200 * a.teeth / 40 / 360))
    else:
        C.note("guesses", "head OD, head height, flute count and stem length are not measured yet")
        C.note("print", "frame flange down, no supports; head underside overhangs the tips",
               overhang_mm=round(a.head_od / 2 - d["r_tip"], 2), height_mm=round(d["z_top"], 2))
        C.note("drive", "pitch dia %.2f mm, %.1f mm of belt per turn; 1:1, knob and motor twins"
               % (d["pd"], a.teeth * PITCH))

    os.makedirs(OUT, exist_ok=True)
    stem = ("knob_motor_gt2_%dt_shaft%g" % (a.teeth, a.shaft_len) if a.motor
            else "knob_over_gt2_%dt" % a.teeth if a.over_knob
            else "knob_gt2_%dt" % a.teeth)
    stl = os.path.join(OUT, stem + ".stl")
    part.export(stl)
    render(part, d, a, os.path.join(OUT, stem + ".png"))
    print("  wrote %s" % stl)
    return 0 if C.report(os.path.join(OUT, "claims_%s.json" % stem)) else 1


def _shade(ax, mesh, colour, light=(0.4, -0.6, 0.7)):
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    L = np.array(light) / np.linalg.norm(light)
    s = 0.3 + 0.7 * np.clip(mesh.face_normals @ L, 0, 1)
    ax.add_collection3d(Poly3DCollection(mesh.vertices[mesh.faces],
                                         facecolors=np.outer(s, colour), edgecolor="none"))


def render(part, d, a, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(16, 6), facecolor="white")
    lim = a.head_od / 2 + 1
    zc = d["z_top"] / 2

    ax = fig.add_subplot(1, 3, 1, projection="3d")
    _shade(ax, part, np.array([0.95, 0.95, 0.92]))
    ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim); ax.set_zlim(zc - lim, zc + lim)
    ax.view_init(22, -60); ax.set_axis_off()
    ax.set_title("as fitted: head out, belt band toward the frame", color="black")

    ax = fig.add_subplot(1, 3, 2)
    z_mid = (d["z_teeth0"] + d["z_teeth1"]) / 2
    plan = part.section(plane_origin=[0, 0, z_mid], plane_normal=[0, 0, 1])
    for e in plan.discrete:
        ax.fill(e[:, 0], e[:, 1], color="#1f77ff", alpha=0.35)
        ax.plot(e[:, 0], e[:, 1], color="#0040c0", lw=1.0)
    t = np.linspace(0, 2 * np.pi, 200)
    shaft_d = 5.0 if a.motor else a.stem
    ax.plot(shaft_d / 2 * np.cos(t), shaft_d / 2 * np.sin(t), color="#e00000", lw=1.2, ls="--")
    ax.plot(a.head_od / 2 * np.cos(t), a.head_od / 2 * np.sin(t), color="black", lw=0.8, ls=":")
    ax.set_aspect("equal"); ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
    ax.set_title("plan through the belt band: %d teeth, %s" % (
        a.teeth, "5 mm D-bore, flat to the grub" if a.motor
        else "%d ribs on the %.0f mm knob" % (a.ribs, a.stem) if a.over_knob
        else "3 crush ribs on the stem"),
        color="black")
    ax.tick_params(colors="black")

    ax2 = fig.add_subplot(1, 3, 3)
    sec = part.section(plane_origin=[0, 0, 0], plane_normal=[0, 1, 0])
    for e in sec.discrete:
        ax2.fill(e[:, 0], e[:, 2], color="#1f77ff", alpha=0.35)
        ax2.plot(e[:, 0], e[:, 2], color="#0040c0", lw=1.2)
    for sx in (-1, 1):
        x0, x1 = sorted((sx * (d["r_tip"] - GROOVE_DEPTH), sx * (a.head_od / 2 + 1)))
        ax2.fill_between([x0, x1], d["z_teeth0"], d["z_teeth1"], color="#ffb000", alpha=0.35)
    ax2.text(d["r_tip"] + 0.5, d["z_teeth1"] + 0.6, "6 mm belt", color="black", fontsize=10)
    ax2.plot([-shaft_d / 2, -shaft_d / 2, shaft_d / 2, shaft_d / 2],
             [-3, a.bore_depth, a.bore_depth, -3], color="#e00000", lw=1.5, ls="--")
    ax2.text(shaft_d / 2 + 0.5, -2, "motor shaft 5" if a.motor
             else "EaS knob %.0f" % a.stem if a.over_knob else "stem %.2f" % a.stem,
             color="#e00000", fontsize=10)
    ax2.axhline(0, color="black", lw=2)
    ax2.text(-lim, -0.8, "motor side" if a.motor else "frame side", color="black",
             fontsize=10, va="top")
    ax2.set_aspect("equal")
    ax2.set_title("section, OD %.0f, %.1f tall" % (a.head_od, d["z_top"]), color="black")
    ax2.set_xlabel("mm", color="black"); ax2.tick_params(colors="black")
    fig.tight_layout()
    fig.savefig(path, dpi=120)


if __name__ == "__main__":
    sys.exit(main())
