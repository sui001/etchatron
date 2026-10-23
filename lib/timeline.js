// Attractor timeline: the entries, their generator and their calibration.
// One copy, loaded by timeline/index.html and control/index.html (served
// from the repo root, so both reach it as ../lib/timeline.js). On plotterpi
// the deploy script inlines it into etchatron.html, since piplot serves
// pages, not loose scripts.
//
// Everything is under TIMELINE, so the control page's own Gen and TARGET
// do not collide with these.
'use strict';
const TIMELINE = (() => {
// ------------------------------------------------------------------- eras
const ERAS = {
  ancient:   { name: 'Ancient',            ink: [184, 0, 31] },
  clockwork: { name: 'Clockwork',          ink: [196, 85, 0] },
  machines:  { name: 'Machines and radio', ink: [0, 71, 194] },
  cyber:     { name: 'Cybernetics',        ink: [138, 0, 194] },
  chaos:     { name: 'Chaos',              ink: [0, 122, 61] },
};
const BEHAVES = {
  chaotic: 'chaotic: never repeats, and nearby starts part',
  quasi:   'never quite repeats, but not chaotic',
  settles: 'settles, is disturbed, rewires itself',
};

// Forced oscillators carry the push's phase as time goes around a ring:
// the ring is the rhythm, the oscillator moves across it.
const ring = (R, a, b, phase) => [(R + a) * Math.cos(phase), (R + a) * Math.sin(phase), b];

// Seeded random numbers, so a calibration run is the same every time. The
// state is kept on the function (.st) so a generator can be cloned mid-run.
function rng(seed) {
  const st = { a: seed >>> 0 };
  const f = () => { st.a = (st.a + 0x6D2B79F5) >>> 0; let t = st.a;
    t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  f.st = st;
  return f;
}

// ---------------------------------------------------------------- entries
// d(t, s, g): derivative of state s at time t. view(s, t, g): the 3D point
// drawn. warm / T: time units of silent run before and during calibration,
// at fine step h. hmax: largest RK4 substep the system tolerates.
// plot: the two axes a flat machine (Etch A Sketch, plotter) draws, if not
// the front view [x, z]. The forced oscillators and Ptolemy are flat bands
// from the front, since their depth is only the oscillator's swing, so they
// draw from the top, where the ring of the push's rhythm shows.
const ENTRIES = [
  { id: 'ptolemy', plot: [0, 1], year: 150, era: 'ancient', behaves: 'quasi', name: 'Epicycles (Mars)',
    who: 'Ptolemy, Almagest, about 150 CE',
    note: 'Mars rides a small circle (the epicycle) whose centre rides a big one (the deferent). The two periods do not divide evenly, so the retrograde loops never land in the same place twice. No chaos: it is clockwork that never quite repeats. Equant left out, and the epicycle\'s tilt exaggerated so the 3D views have depth.',
    s0: [0], d: () => [1],
    view: (s) => { const t = s[0], wd = 2 * Math.PI / 1.8809, ws = 2 * Math.PI;
      return [60 * Math.cos(wd * t) + 39.5 * Math.cos(ws * t), 60 * Math.sin(wd * t) + 39.5 * Math.sin(ws * t),
        12 * Math.sin((ws - wd) * t)]; },
    warm: 0, T: 120, h: 0.002, hmax: 0.01 },

  { id: 'pendulum', plot: [0, 1], year: 1673, era: 'clockwork', behaves: 'chaotic', name: 'Pendulum, pushed in rhythm',
    who: 'Galileo (about 1602) and Huygens, Horologium Oscillatorium (1673)',
    note: 'The pendulum that made clocks keep time. Give it friction and a rhythmic push and it goes chaotic, sometimes swinging, sometimes whirling right over the top. The settings are Baker and Gollub\'s (1990). Drawn on a ring for the push\'s rhythm, with the swing wrapping a tube whose thickness is the speed.',
    p: { q: 2, g: 1.5, w: 2 / 3 },
    s0: [0.2, 0], jit: [0.05, 0.05],
    d: (t, [th, om], gn) => { const p = gn.e.p; return [om, -om / p.q - Math.sin(th) + p.g * Math.cos(p.w * t)]; },
    view: ([th, om], t, gn) => { const r = 1 + 0.2 * om, R = 3, ph = gn.e.p.w * t;
      return ring(R, r * Math.cos(th), r * Math.sin(th), ph); },
    warm: 200, T: 3000, h: 0.01, hmax: 0.05 },

  { id: 'governor', plot: [0, 1], year: 1788, yearText: '1788 / 1868', era: 'cyber', behaves: 'chaotic', name: 'Watt governor',
    who: 'James Watt (1788); James Clerk Maxwell, "On Governors" (1868)',
    note: 'The flyball governor holds a steam engine\'s speed: faster, the balls fly out and close the steam. Maxwell\'s paper on it began control theory, and Wiener named cybernetics after the governor. Equations as Pontryagin gives them (arm angle, arm speed, engine speed); the rhythmic load and its chaotic settings are ours, found by search.',
    p: { eps: 0.4, alpha: 1.2, beta: 0.5, b1: 0.3, w: 0.9 },
    s0: [0.8, 0, 1.4], jit: [0.01, 0.01, 0.01],
    d: (t, [x, y, z], gn) => { const p = gn.e.p, beta = p.beta + p.b1 * Math.sin(p.w * t);
      return [y, z * z * Math.sin(x) * Math.cos(x) - Math.sin(x) - p.eps * y, p.alpha * (Math.cos(x) - beta)]; },
    view: ([x, y, z]) => [Math.sin(x) * z, Math.cos(x) * z, y],
    warm: 300, T: 3000, h: 0.01, hmax: 0.05 },

  { id: 'duffing', plot: [0, 1], year: 1918, era: 'machines', behaves: 'chaotic', name: 'Duffing oscillator',
    who: 'Georg Duffing, on forced vibration in machines (1918)',
    note: 'A spring that stiffens as it stretches, with two resting places. Pushed in rhythm it hops between them unpredictably. The chaos was found later; these settings are the classic ones (Holmes, 1979).',
    p: { delta: 0.3, gamma: 0.5, w: 1.2 },
    s0: [1, 0], jit: [0.05, 0.05],
    d: (t, [x, v], gn) => { const p = gn.e.p; return [v, -p.delta * v + x - x * x * x + p.gamma * Math.cos(p.w * t)]; },
    view: ([x, v], t, gn) => ring(3, x, v, gn.e.p.w * t),
    warm: 200, T: 3000, h: 0.01, hmax: 0.05 },

  { id: 'vanderpol', plot: [0, 1], year: 1927, era: 'machines', behaves: 'chaotic', name: 'Van der Pol oscillator',
    who: 'Balthasar van der Pol and Jan van der Mark, valve radio circuits (1927)',
    note: 'A valve circuit that keeps itself oscillating. Driven by a second rhythm, van der Pol and van der Mark heard an "irregular noise" they put down to the apparatus; it is now read as an early sighting of chaos. Cartwright and Littlewood proved the strange behaviour in 1945. Settings after Parlitz and Lauterborn (1987).',
    p: { mu: 8.53, A: 1.2, w: 2 * Math.PI / 10 },
    s0: [1, 0], jit: [0.05, 0.05],
    d: (t, [x, v], gn) => { const p = gn.e.p; return [v, p.mu * (1 - x * x) * v - x + p.A * Math.sin(p.w * t)]; },
    view: ([x, v], t, gn) => ring(4, x, v / 6, gn.e.p.w * t),
    warm: 300, T: 4000, h: 0.002, hmax: 0.004 },

  { id: 'homeostat', year: 1948, era: 'cyber', behaves: 'settles', name: 'Homeostat',
    who: 'W. Ross Ashby, Design for a Brain (1952; built 1948)',
    note: 'Four units, each a needle driven by the other three. When a needle passes its limit, that unit\'s uniselector steps and rewires its inputs at random, until the four find a way to settle. Then the experimenter disturbs it again. Not chaos: adaptation. Drawn from the first three needles. Our model, after Ashby\'s equations.',
    p: { limit: 1, kick: 12, amp: 1, stepGap: 0.5, self: -1, w: 0.8 },
    s0: [0.3, -0.2, 0.1, 0, 0, 0, 0, 0], seeded: true,
    init: (g) => {
      g.x.table = [0, 1, 2, 3].map(() => Array.from({ length: 25 }, () => [0, 1, 2, 3].map(() => (g.rand() * 2 - 1) * g.e.p.w)));
      g.x.pos = [0, 0, 0, 0]; g.x.lastStep = [-9, -9, -9, -9]; g.x.nextKick = g.e.p.kick;
      g.x.a = [0, 1, 2, 3].map((i) => g.x.table[i][0].map((v, j) => (i === j ? g.e.p.self : v)));
    },
    d: (t, s, g) => { const a = g.x.a, out = new Array(8);
      for (let i = 0; i < 4; i++) {
        let f = 0; for (let j = 0; j < 4; j++) f += a[i][j] * s[j];
        out[i] = s[4 + i]; out[4 + i] = f - s[4 + i];          // x'' = sum(a x) - x'
      }
      return out; },
    event: (g) => { const s = g.s, p = g.e.p, x = g.x;
      for (let i = 0; i < 4; i++) {
        if (Math.abs(s[i]) > 1.5) { s[i] = Math.sign(s[i]) * 1.5; s[4 + i] = 0; }   // end of the trough
        if (Math.abs(s[i]) > p.limit && g.t - x.lastStep[i] > p.stepGap) {          // uniselector steps
          x.pos[i] = (x.pos[i] + 1) % 25; x.lastStep[i] = g.t;
          x.a[i] = x.table[i][x.pos[i]].map((v, j) => (i === j ? p.self : v));
          g.rewires = (g.rewires || 0) + 1;
        }
      }
      if (g.t >= x.nextKick) { s[4 + Math.floor(g.rand() * 4)] += (g.rand() < 0.5 ? -1 : 1) * p.amp; x.nextKick += p.kick; }
    },
    view: (s) => [s[0], s[1], s[2]],
    dtFixed: 0.04, warm: 0, T: 2000, h: 0.01, hmax: 0.02 },

  { id: 'ueda', plot: [0, 1], year: 1961, era: 'machines', behaves: 'chaotic', name: 'Ueda attractor',
    who: 'Yoshisuke Ueda, on an analogue computer (November 1961)',
    note: 'A forced circuit studied on an analogue computer at Kyoto. Ueda saw chaos on its screen two years before Lorenz, but it was dismissed as error and not published for years. Sometimes called the Japanese attractor.',
    p: { k: 0.05, B: 7.5 },
    s0: [2.5, 0], jit: [0.05, 0.05],
    d: (t, [x, v], gn) => { const p = gn.e.p; return [v, -p.k * v - x * x * x + p.B * Math.cos(t)]; },
    view: ([x, v], t) => ring(6, x, v / 2, t),
    warm: 200, T: 3000, h: 0.005, hmax: 0.02 },

  { id: 'lorenz', year: 1963, era: 'chaos', behaves: 'chaotic', name: 'Lorenz',
    who: 'Edward Lorenz, "Deterministic Nonperiodic Flow" (1963)',
    note: 'A cut-down model of convection, run on a Royal McBee LGP-30 at MIT. Restarting a run from rounded numbers gave a different forecast: the start of chaos as a science. The first strange attractor, though the name came in 1971.',
    s0: [0, 1, 1.05], jit: [0, 0.02, 0.02],
    d: (t, [x, y, z]) => [10 * (y - x), 28 * x - x * z - y, x * y - (8 / 3) * z],
    view: (s) => s, warm: 0, T: 4000, h: 0.002, hmax: 0.01 },

  { id: 'moore', year: 1966, era: 'chaos', behaves: 'chaotic', name: 'Moore and Spiegel',
    who: 'Derek Moore and Edward Spiegel, a model of stellar convection (1966)',
    note: 'A parcel of gas bobbing in a star, heated and cooled as it rises and falls. One of the earliest chaotic systems after Lorenz, found independently. Its three variables are position, speed and acceleration, so speed is drawn at 1/2.5 and acceleration at 1/20 to keep the figure readable.',
    p: { T: 6, R: 20 },
    s0: [0.1, 0, 0], jit: [0.02, 0.02, 0.02],
    d: (t, [x, y, z], gn) => { const p = gn.e.p; return [y, z, -z - (p.T - p.R + p.R * x * x) * y - p.T * x]; },
    view: ([x, y, z]) => [x, y / 2.5, z / 20], warm: 200, T: 3000, h: 0.002, hmax: 0.01 },

  { id: 'rossler', year: 1976, era: 'chaos', behaves: 'chaotic', name: 'Rössler',
    who: 'Otto Rössler, after a chemical reaction (1976)',
    note: 'Designed to be the simplest possible chaos: a spiral that every so often flicks up and folds back in, like a strip of pastry.',
    s0: [7.72, -8.53, 0.15], jit: [0, 0.1, 0.01],
    d: (t, [x, y, z]) => [-y - z, x + 0.2 * y, 0.2 + z * (x - 5.7)],
    view: (s) => s, warm: 200, T: 4000, h: 0.005, hmax: 0.02 },

  { id: 'rabinovich', plot: [1, 2], year: 1979, era: 'chaos', behaves: 'chaotic', name: 'Rabinovich and Fabrikant',
    who: 'Mikhail Rabinovich and Anatoly Fabrikant, waves in a nonequilibrium medium (1979)',
    note: 'From the physics of waves in plasma. Its shapes change sharply with its two settings; these are the ones usually drawn.',
    p: { g: 0.87, a: 1.1 },
    s0: [-1, 0, 0.5], jit: [0.01, 0.01, 0.01],
    d: (t, [x, y, z], gn) => { const p = gn.e.p;
      return [y * (z - 1 + x * x) + p.g * x, x * (3 * z + 1 - x * x) + p.g * y, -2 * z * (p.a + x * y)]; },
    view: (s) => s, warm: 200, T: 3000, h: 0.002, hmax: 0.005 },

  { id: 'aizawa', year: 1982, era: 'chaos', behaves: 'chaotic', name: 'Aizawa',
    who: 'Yoji Aizawa (1982), as given in later collections',
    note: 'A ball with a tube through its axis: the path winds round the sphere and every so often shoots up the middle.',
    s0: [-1.086, -0.398, 1.386], jit: [0, 0.01, 0.01],
    d: (t, [x, y, z]) => { const a = 0.95, ab = 0.7, c = 0.6, d = 3.5, e = 0.25, f = 0.1;
      return [(z - ab) * x - d * y, d * x + (z - ab) * y,
        c + a * z - z ** 3 / 3 - (x * x + y * y) * (1 + e * z) + f * z * x ** 3]; },
    view: (s) => s, warm: 200, T: 4000, h: 0.002, hmax: 0.01 },

  { id: 'chua', year: 1983, era: 'chaos', behaves: 'chaotic', name: 'Chua\'s circuit',
    who: 'Leon Chua, a circuit built to be chaotic (1983)',
    note: 'Two capacitors, an inductor and one piecewise-linear resistor: the first electronic circuit designed to be chaotic, and proved so. The double scroll.',
    p: { al: 15.6, be: 28, m0: -1.143, m1: -0.714 },
    s0: [0.7, 0, 0], jit: [0.01, 0.01, 0.01],
    d: (t, [x, y, z], gn) => { const p = gn.e.p, f = p.m1 * x + 0.5 * (p.m0 - p.m1) * (Math.abs(x + 1) - Math.abs(x - 1));
      return [p.al * (y - x - f), x - y + z, -p.be * y]; },
    view: (s) => s, warm: 200, T: 3000, h: 0.002, hmax: 0.01 },

  { id: 'thomas', year: 1999, era: 'chaos', behaves: 'chaotic', name: 'Thomas',
    who: 'René Thomas, cyclically symmetric (1999)',
    note: 'Each variable is driven by the sine of the next, with friction b. A labyrinth that looks the same from all three axes. b = 0.185: the commonly quoted 0.208186 is a repeating loop.',
    p: { b: 0.185 },
    s0: [0.197, -0.823, 0.473], jit: [0, 0.02, 0.02],
    d: (t, [x, y, z], gn) => { const b = gn.e.p.b; return [Math.sin(y) - b * x, Math.sin(z) - b * y, Math.sin(x) - b * z]; },
    view: (s) => s, warm: 200, T: 4000, h: 0.01, hmax: 0.05 },

  { id: 'chen', year: 1999, era: 'chaos', behaves: 'chaotic', name: 'Chen',
    who: 'Guanrong Chen and Tetsushi Ueta (1999)',
    note: 'Found while trying to control chaos: Lorenz\'s near relation, with a different twist between the wings.',
    s0: [-10, 0, 37], jit: [0, 0.1, 0.1],
    d: (t, [x, y, z]) => { const a = 35, b = 3, c = 28; return [a * (y - x), (c - a) * x - x * z + c * y, x * y - b * z]; },
    view: (s) => s, warm: 200, T: 3000, h: 0.001, hmax: 0.004 },

  { id: 'halvorsen', year: 2010, era: 'chaos', behaves: 'chaotic', name: 'Halvorsen',
    who: 'Arne Dehli Halvorsen, collected in Sprott\'s Elegant Chaos (2010)',
    note: 'Three-fold symmetric, like Thomas: three lobes chasing each other. a = 1.4: the 1.89 often quoted repeats.',
    p: { a: 1.4 },
    s0: [1.447, -6.437, -4.455], jit: [0, 0.05, 0.05],
    d: (t, [x, y, z], gn) => { const a = gn.e.p.a;
      return [-a * x - 4 * y - 4 * z - y * y, -a * y - 4 * z - 4 * x - z * z, -a * z - 4 * x - 4 * y - x * x]; },
    view: (s) => s, warm: 200, T: 4000, h: 0.002, hmax: 0.01 },
];

// ------------------------------------------------------------- generator
const TARGET = [[-19, 21], [-24, 25], [1, 54]];         // the control page's box
const TC = TARGET.map(([lo, hi]) => (lo + hi) / 2);
const MAX_DRAWN = 8;                                    // points drawn per 10 ms step, at most

class Gen {
  constructor(e, { jitter = true, seed = 1 } = {}) {
    this.e = e; this.t = 0; this.steps = 0; this.x = {};
    this.rand = rng(e.seeded && jitter ? Math.floor(Math.random() * 2 ** 31) : seed);
    const r = () => Math.random() * 2 - 1;
    this.s = e.s0.map((v, i) => v + (jitter && e.jit ? e.jit[i] * r() : 0));
    if (e.init) e.init(this);
  }
  advance(h) {
    const d = this.e.d, s = this.s, t = this.t;
    const k1 = d(t, s, this);
    const k2 = d(t + h / 2, s.map((v, i) => v + k1[i] * h / 2), this);
    const k3 = d(t + h / 2, s.map((v, i) => v + k2[i] * h / 2), this);
    const k4 = d(t + h, s.map((v, i) => v + k3[i] * h), this);
    this.s = s.map((v, i) => v + (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]) * h / 6);
    this.t += h;
    if (this.e.event) this.e.event(this);
  }
  // an independent copy that carries on exactly as this one would: the
  // control page pre-runs a copy to size the sheet, and keeps the best
  // starting point it passes
  clone() {
    const g = Object.create(Gen.prototype);
    Object.assign(g, this, { s: [...this.s], x: structuredClone(this.x), rand: rng(0) });
    g.rand.st.a = this.rand.st.a;
    return g;
  }
  raw() { return this.e.view(this.s, this.t, this); }
  canon() { const c = this.e.cal, r = this.raw(); return r.map((v, i) => TC[i] + (v - c.mid[i]) * c.k); }
  // one step = 10 ms; returns the canonical points to draw for it
  step() {
    const c = this.e.cal, out = [], every = Math.ceil(c.n / MAX_DRAWN);
    for (let i = 1; i <= c.n; i++) {
      this.advance(c.dt / c.n);
      if (i % every === 0 || i === c.n) out.push(this.canon());
    }
    this.steps++;
    return out;
  }
}

// Calibration, once per entry: a silent run from the entry's own start (no
// jitter, fixed seed) measures the figure's box (0.5 to 99.5 percentile, so a
// rare excursion does not shrink the whole figure) and its average speed. One
// scale for all three axes, so shapes are not stretched; dt so it moves at
// Lorenz's average speed per step at dt 0.01.
let VREF = null;
function calibrate(e) {
  if (e.cal) return e.cal;
  const g = new Gen(e, { jitter: false }), h = e.h;
  for (let t = 0; t < e.warm; t += h) g.advance(h);
  const seen = [[], [], []];
  let prev = g.raw(), path = 0, n = 0;
  for (let t = 0; t < e.T; t += h) {
    g.advance(h);
    const r = g.raw();
    if (n % 4 === 0) for (let i = 0; i < 3; i++) seen[i].push(r[i]);
    path += Math.hypot(r[0] - prev[0], r[1] - prev[1], r[2] - prev[2]); prev = r; n++;
  }
  const pick = (a, q) => a[Math.min(a.length - 1, Math.floor(q * a.length))];
  seen.forEach((a) => a.sort((u, v) => u - v));
  const lo = seen.map((a) => pick(a, 0.005)), hi = seen.map((a) => pick(a, 0.995));
  const k = Math.min(...[0, 1, 2].map((i) => (TARGET[i][1] - TARGET[i][0]) / Math.max(1e-9, hi[i] - lo[i])));
  const speed = k * path / (n * h);                     // canonical units per time unit
  if (e.id === 'lorenz') VREF = 0.01 * speed;
  else if (VREF === null) calibrate(ENTRIES.find((q) => q.id === 'lorenz'));
  const dt = e.dtFixed || VREF / speed;
  e.cal = { k, mid: lo.map((v, i) => (v + hi[i]) / 2), dt, n: Math.max(1, Math.ceil(dt / e.hmax)), lo, hi };
  return e.cal;
}

return { ERAS, BEHAVES, ENTRIES, TARGET, TC, MAX_DRAWN, Gen, calibrate };
})();
