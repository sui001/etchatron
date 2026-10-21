#!/usr/bin/env python3
"""
lorenz_av.py — real-time audiovisual Lorenz attractor.

Extends lorenz_sonification.py: a Doppler-shifted harmonic tone with
distance-driven gain, duplex (level + interaural-time) panning, a
geometry-locked floor reflection (Lloyd's mirror: height as interference),
and elevation-driven spectral brightness, playing live while a portrait,
all-black window shows the moving point trailing an afterglow trace.

Dependencies:   pip install numpy pygame sounddevice
Run:            python3 lorenz_av.py
Quit:           Esc / Q / close window

If sounddevice (PortAudio) is unavailable, the app still runs silently,
with the animation driven by the wall clock instead of the audio clock.
"""

# Thomas Fischer's script, as sent to Sui on 21 Oct 2026 ("Re: attractors
# script"). Kept verbatim as the reference for the port in ../index.html.

import math
import random
import sys
import time
from collections import deque

import numpy as np
import pygame

try:
    import sounddevice as sd
    HAVE_AUDIO = True
except Exception:
    HAVE_AUDIO = False

# --------------------------------------------------------------- model / audio

SRATE = 44100
BLOCK = int(0.010 * SRATE)          # 10 ms: one Lorenz step per audio block
STEPS = 45000                       # ~450 s, as in the offline script

# observer location:
ox = 1.177
oy = 24.787
oz = 27.280


def distfromobs(tx, ty, tz):
    return math.sqrt((ox - tx) ** 2 + (oy - ty) ** 2 + (oz - tz) ** 2)


START_JITTER = 0.05  # each run begins from a slightly different point; the
                     # attractor's sensitivity to initial conditions turns
                     # two tiny random offsets into a wholly different
                     # trajectory within seconds

# ------------------------------------------------------------- attractors


def d_lorenz(x, y, z):
    return 10.0 * (y - x), 28.0 * x - x * z - y, x * y - (8.0 / 3.0) * z


def d_rossler(x, y, z):
    return -y - z, x + 0.2 * y, 0.2 + z * (x - 5.7)


def d_thomas(x, y, z):
    bt = 0.208186
    return (math.sin(y) - bt * x,
            math.sin(z) - bt * y,
            math.sin(x) - bt * z)


def d_aizawa(x, y, z):
    a, ab, c, d, e, f = 0.95, 0.7, 0.6, 3.5, 0.25, 0.1
    return ((z - ab) * x - d * y,
            d * x + (z - ab) * y,
            c + a * z - z ** 3 / 3 - (x * x + y * y) * (1 + e * z)
            + f * z * x ** 3)


def d_halvorsen(x, y, z):
    a = 1.89
    return (-a * x - 4 * y - 4 * z - y * y,
            -a * y - 4 * z - 4 * x - z * z,
            -a * z - 4 * x - 4 * y - x * x)


# The sonification (observer, gain law, projection) was tuned in Lorenz
# coordinates, so that box is the common "sonification space": each
# attractor is affine-mapped from its measured raw ranges into TARGET.
# dt values are calibrated so all five move through that space at the
# same average speed; one block = one step, taken as `sub` Euler substeps
# where a single step of that size would be unstable (Aizawa).
TARGET = ((-19.0, 21.0), (-24.0, 25.0), (1.0, 54.0))

#   name         derivative   dt       sub  start (on attractor)   raw ranges
ATTRACTORS = [
    ("Lorenz",    d_lorenz,    0.01000, 1, (0.0, 1.0, 1.05),
     TARGET),                            # identity map: the original piece
    ("Rössler",   d_rossler,   0.04208, 1, (1.1125, -6.1135, 0.0360),
     ((-9.62, 12.79), (-11.81, 8.03), (0.01, 38.81))),
    ("Thomas",    d_thomas,    0.11213, 1, (3.2616, 2.3306, 1.9864),
     ((-1.07, 3.78), (-1.07, 3.78), (-1.07, 3.78))),
    ("Aizawa",    d_aizawa,    0.02680, 4, (0.0624, 0.0830, -0.2338),
     ((-1.55, 1.54), (-1.50, 1.59), (-0.60, 1.93))),
    ("Halvorsen", d_halvorsen, 0.00878, 1, (-5.5514, -2.2521, 0.7790),
     ((-12.58, 6.51), (-13.32, 6.42), (-12.95, 6.26))),
]

freq = 440.0        # base frequency

REFL_MIX = 0.4      # level of the floor-reflection path (0 disables)
REFL_TAU = 0.008    # s per scaled unit of path difference: turns the
                    # direct/reflected path gap into a real delay, locking
                    # the interference pattern (Lloyd's mirror) to height

PARTIAL_RATIOS = np.array([0.5, 1.0, 2.0, 3.0, 4.0])
PARTIAL_BASE = np.array([0.45, 1.0, 0.50, 0.22, 0.12])
PARTIAL_TILT_EXP = np.array([0.0, 0.0, 1.0, 2.0, 3.0])
                    # the instrument's voice: a soft sub-octave (ratio 0.5)
                    # under the fundamental warms the bare sine, and a
                    # gently decaying harmonic bed rounds it out.  The
                    # elevation tilt acts only on partials with a nonzero
                    # TILT_EXP, so the core tone is height-independent.
BRIGHT_LO = 0.15    # tilt at the bottom of the attractor
BRIGHT_HI = 0.20    # tilt at the top (subtle shimmer)
EZ_LO, EZ_HI = 1.0, 54.0            # z range mapped onto brightness

ITD_MAX = 0.0006    # s: interaural time difference at full pan (0 disables).
                    # At 440 Hz interaural phase, not level, is the dominant
                    # left-right cue; this delays the far ear by up to 0.6 ms

#GAIN_LO, GAIN_HI = 0.03, 0.64       # observed gain range for this metric
GAIN_LO, GAIN_HI = 0.17, 0.60

class AttractorVoice:
    """One attractor step -> one 10 ms stereo block."""

    def __init__(self, index=0):
        self.phase = 0.0
        self.prev = None                    # ramp targets from last block
        self.step = 0
        self.gen = 0                        # bumps on every attractor switch
        self.history = deque()              # (x, y, z, gain, gen)
        self.pending = None
        self._load(index)

    def set_attractor(self, index):
        if index != self.index:
            self.pending = index            # applied at the next audio block

    def _load(self, index):
        name, deriv, adt, sub, start, ranges = ATTRACTORS[index]
        self.index, self.deriv, self.adt, self.sub = index, deriv, adt, sub
        self.scale, self.offset = [], []
        for (lo, hi), (tlo, thi) in zip(ranges, TARGET):
            k = (thi - tlo) / (hi - lo)
            self.scale.append(k)
            self.offset.append(tlo - lo * k)
        # jitter two coordinates (scaled to the attractor's own size)
        jy = (ranges[1][1] - ranges[1][0]) / 50.0
        jz = (ranges[2][1] - ranges[2][0]) / 53.0
        self.rx = start[0]
        self.ry = start[1] + random.uniform(-START_JITTER, START_JITTER) * jy
        self.rz = start[2] + random.uniform(-START_JITTER, START_JITTER) * jz
        self._to_canonical()
        # distance memory starts from the actual geometry (no startup blip)
        self.olddistance = distfromobs(self.xs, self.ys, self.zs) / 92
        self.gen += 1
        print(f"{name}: start y = {self.ry:.9f}, z = {self.rz:.9f}",
              file=sys.stderr)   # log it: this is the run's whole identity

    def _to_canonical(self):
        self.xs = self.rx * self.scale[0] + self.offset[0]
        self.ys = self.ry * self.scale[1] + self.offset[1]
        self.zs = self.rz * self.scale[2] + self.offset[2]

    def next_block(self):
        if self.step >= STEPS:
            return None
        if self.pending is not None:
            self._load(self.pending)
            self.pending = None

        h = self.adt / self.sub
        for _ in range(self.sub):
            dxdt, dydt, dzdt = self.deriv(self.rx, self.ry, self.rz)
            self.rx += dxdt * h
            self.ry += dydt * h
            self.rz += dzdt * h
        self._to_canonical()

        currdistance = distfromobs(self.xs, self.ys, self.zs) / 92
        gain = 0.03 + currdistance
        speed = self.olddistance - currdistance
        self.olddistance = currdistance

        # floor reflection as a geometry-locked delayed copy (Lloyd's
        # mirror): the extra path length becomes a real delay, so the phase
        # relationship between direct and reflected sound is a function of
        # position -- dominated by height -- while its rate of change is
        # still heard as beating on fast vertical/depth motion.
        refldistance = distfromobs(self.xs, self.ys, -self.zs) / 92
        gain_r = (0.03 + refldistance) * REFL_MIX
        tau = (refldistance - currdistance) * REFL_TAU

        pan = self.xs / 21
        so_freq = freq - speed * 300

        p = max(-1.0, min(1.0, pan))
        theta = (p + 1.0) * math.pi / 4.0
        cl, cr = math.cos(theta), math.sin(theta)

        # interaural time difference as a phase offset at the fundamental;
        # multiplying inside k*(ph +/- d) scales it per harmonic, which is
        # exactly a time delay.  p > 0 (right): right ear leads, left lags.
        itd = math.pi * freq * ITD_MAX * p

        # elevation -> spectral tilt on the upper partials, applied over
        # the instrument's base spectrum; amplitude-normalized so
        # brightness doesn't change the level
        e = max(0.0, min(1.0, (self.zs - EZ_LO) / (EZ_HI - EZ_LO)))
        tilt = BRIGHT_LO + (BRIGHT_HI - BRIGHT_LO) * e
        w = PARTIAL_BASE * tilt ** PARTIAL_TILT_EXP
        w /= w.sum()

        if self.prev is None:               # first block: nothing to ramp from
            self.prev = (so_freq, gain, gain_r, cl, cr, w, itd, tau)
        pf, pg, pgr, pcl, pcr, pw, pitd, ptau = self.prev

        # per-path gain ramps; pan is ramped separately so both paths share
        # one constant-power pan (they arrive from the same lateral
        # direction, only the elevation of the bounce differs)
        f_d = np.linspace(pf, so_freq, BLOCK, endpoint=False)
        g_d = np.linspace(pg, gain, BLOCK, endpoint=False)
        g_r = np.linspace(pgr, gain_r, BLOCK, endpoint=False)
        c_l = np.linspace(pcl, cl, BLOCK, endpoint=False)
        c_r = np.linspace(pcr, cr, BLOCK, endpoint=False)
        d_i = np.linspace(pitd, itd, BLOCK, endpoint=False)
        d_t = np.linspace(ptau, tau, BLOCK, endpoint=False)
        ramp = np.arange(BLOCK)[:, None] / BLOCK
        W = pw[None, :] + (w - pw)[None, :] * ramp      # per-partial ramps

        ph_d = self.phase + np.cumsum(2.0 * math.pi * f_d / SRATE)
        # wrap modulo 4 pi, not 2 pi: the sub-octave partial (ratio 0.5)
        # has a 4 pi period in the fundamental's phase, and a 2 pi wrap
        # would flip its sign at every block boundary
        self.phase = ph_d[-1] % (4.0 * math.pi)
        # first-order delayed copy: s(t - tau) ~ sin(ph(t) - 2 pi f(t) tau(t))
        off = 2.0 * math.pi * f_d * d_t

        # partials k*ph stay phase-locked to the Doppler-modulated carrier;
        # offsets applied inside k*(...) scale per partial, i.e. they are
        # true time shifts.  Each ear renders both paths with its own ITD.
        k = PARTIAL_RATIOS[None, :]
        mixL = ((np.sin((ph_d - d_i)[:, None] * k) * W).sum(axis=1) * g_d
                + (np.sin((ph_d - off - d_i)[:, None] * k) * W).sum(axis=1) * g_r)
        mixR = ((np.sin((ph_d + d_i)[:, None] * k) * W).sum(axis=1) * g_d
                + (np.sin((ph_d - off + d_i)[:, None] * k) * W).sum(axis=1) * g_r)

        self.prev = (so_freq, gain, gain_r, cl, cr, w, itd, tau)
        self.step += 1
        self.history.append((self.xs, self.ys, self.zs, gain, self.gen))

        return np.column_stack((mixL * c_l, mixR * c_r))


voice = AttractorVoice()


def audio_callback(outdata, frames, time_info, status):
    block = voice.next_block()
    if block is None:
        outdata.fill(0.0)
        raise sd.CallbackStop()
    outdata[:] = np.clip(block, -1.0, 1.0).astype(np.float32)


# -------------------------------------------------------------------- visuals

W, H = 450, 800                     # portrait, phone-like
BAR_H = 48                          # attractor selector strip at the bottom
SS = 3                              # supersampling: trail is drawn at SS x
                                    # resolution and smoothly downscaled each
                                    # frame, which anti-aliases everything
BLOOM = 0.35                        # 0..1: adds a softly blurred copy of the
                                    # trail on top (0 disables the pass)
MARGIN = 24

XSPAN = 23.0                        # attractor x roughly in [-19, 21]
ZLO, ZHI = -1.0, 55.0               # attractor z roughly in [1, 54]

FADE = (7, 2, 9)                    # per-frame subtraction: red and blue die
                                    # fast, so the trail settles from warm
                                    # yellow through firefly green as it fades
TRAIL_DIM = (80, 150, 40)
TRAIL_HOT = (225, 255, 110)


def to_screen(x, z):
    sx = W / 2 + (x / XSPAN) * (W / 2 - MARGIN)
    sy = ((H - BAR_H - MARGIN)
          - ((z - ZLO) / (ZHI - ZLO)) * (H - BAR_H - 2 * MARGIN))
    return sx, sy


def loudness(gain):
    return max(0.0, min(1.0, (gain - GAIN_LO) / (GAIN_HI - GAIN_LO)))


def trail_color(gain):
    t = loudness(gain)
    return tuple(int(a + (b - a) * t) for a, b in zip(TRAIL_DIM, TRAIL_HOT))


def draw_head(surf, pos, gain):
    t = loudness(gain)
    size = 64
    hi = pygame.Surface((size * SS, size * SS), pygame.SRCALPHA)
    c = size * SS // 2
    for r, a in ((26, 16), (16, 40), (9, 105)):
        pygame.draw.circle(hi, (185, 255, 90, int(a * (0.35 + 0.65 * t))),
                           (c, c), r * SS)
    pygame.draw.circle(hi, (255, 250, 205), (c, c),
                       round((2 + 2 * t) * SS))
    surf.blit(pygame.transform.smoothscale(hi, (size, size)),
              (pos[0] - size // 2, pos[1] - size // 2))


def draw_bar(surf, font, selected):
    y0 = H - BAR_H
    pygame.draw.line(surf, (35, 55, 20), (0, y0), (W, y0))
    cell = W / len(ATTRACTORS)
    for i, att in enumerate(ATTRACTORS):
        cx = int(cell * i + cell / 2)
        cy = y0 + 15
        col = (200, 255, 120) if i == selected else (95, 115, 70)
        pygame.draw.circle(surf, col, (cx, cy), 6, 1)
        if i == selected:
            pygame.draw.circle(surf, col, (cx, cy), 3)
        lab = font.render(att[0], True, col)
        surf.blit(lab, lab.get_rect(center=(cx, cy + 17)))


def main():
    smoke = "--smoke" in sys.argv   # headless self-test: run 150 frames, exit

    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Attractor sonification")
    font = pygame.font.SysFont(None, 16)

    trail = pygame.Surface((W * SS, H * SS))
    trail.fill((0, 0, 0))
    fade = pygame.Surface((W * SS, H * SS))
    fade.fill(FADE)

    clock = pygame.time.Clock()

    stream = None
    if HAVE_AUDIO and not smoke:
        try:
            stream = sd.OutputStream(samplerate=SRATE, blocksize=BLOCK,
                                     channels=2, dtype="float32",
                                     callback=audio_callback)
            stream.start()
        except Exception as e:
            print(f"audio unavailable ({e}); running silent", file=sys.stderr)
    if stream is None and not HAVE_AUDIO:
        print("sounddevice not installed; running silent", file=sys.stderr)

    silent = stream is None
    t0 = time.monotonic()
    stepped = 0                     # steps taken in silent mode
    read = 0                        # history read cursor
    prev_pt = None
    prev_gen = None
    head = None
    frames = 0
    running = True

    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (
                    ev.type == pygame.KEYDOWN
                    and ev.key in (pygame.K_ESCAPE, pygame.K_q)):
                running = False
            elif (ev.type == pygame.MOUSEBUTTONDOWN
                    and ev.pos[1] >= H - BAR_H):
                idx = min(len(ATTRACTORS) - 1,
                          int(ev.pos[0] * len(ATTRACTORS) // W))
                voice.set_attractor(idx)
            elif (ev.type == pygame.KEYDOWN
                    and pygame.K_1 <= ev.key <= pygame.K_5):
                voice.set_attractor(ev.key - pygame.K_1)

        if silent:                  # clock-driven fallback (or --smoke test)
            due = min(int((time.monotonic() - t0) / 0.010), STEPS)
            while stepped < due and voice.next_block() is not None:
                stepped += 1

        # afterglow: subtractive fade of everything drawn so far
        trail.blit(fade, (0, 0), special_flags=pygame.BLEND_RGB_SUB)

        # draw the path segments produced since the last frame
        hist = voice.history
        n = len(hist)
        while read < n:
            x, y, z, gain, gen = hist[read]
            pt = to_screen(x, z)
            if prev_pt is not None and gen == prev_gen:
                pygame.draw.line(trail, trail_color(gain),
                                 (prev_pt[0] * SS, prev_pt[1] * SS),
                                 (pt[0] * SS, pt[1] * SS), 2 * SS)
            prev_pt, prev_gen = pt, gen
            head = (pt, gain)
            read += 1

        screen.blit(pygame.transform.smoothscale(trail, (W, H)), (0, 0))
        if BLOOM > 0:
            # cheap blur: shrink far down, dim, and scale back up additively
            small = pygame.transform.smoothscale(trail, (W // 4, H // 4))
            small.fill((int(255 * BLOOM),) * 3,
                       special_flags=pygame.BLEND_RGB_MULT)
            screen.blit(pygame.transform.smoothscale(small, (W, H)), (0, 0),
                        special_flags=pygame.BLEND_RGB_ADD)
        if head is not None:
            draw_head(screen, *head)
        draw_bar(screen, font, voice.index)
        pygame.display.flip()
        clock.tick(60)

        frames += 1
        if smoke and frames >= 150:
            running = False

    if stream is not None:
        stream.stop()
        stream.close()
    pygame.quit()
    if smoke:
        print(f"smoke test ok: {frames} frames, {voice.step} steps, "
              f"read {read} history points")


if __name__ == "__main__":
    main()
