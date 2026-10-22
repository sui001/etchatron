// controller.ino: Etchatron move controller for control/index.html.
//
// The page does the thinking (attractors, sound, scale, limits); this does
// the moving. It takes absolute moves in STEPS over serial, queues them,
// runs them with the blended slack take-up worked out on spiral/, and
// reports where the stylus is so the page's sound and trail can follow it.
//
// Uno + Protoneer CNC Shield V3 + BTT TMC2209 at 1/16:
//   X  STEP D2  DIR D5   horizontal knob (left)
//   Y  STEP D3  DIR D6   vertical knob (right)
//   EN D8, active LOW. Motors boot OFF, so the knobs turn by hand for
//   centring the stylus; the page turns them on.
//   UART: both drivers on one PDN_UART bus. A0 = RX (straight to the bus),
//   A1 = TX (through 1k to the bus). Addresses come from the MS jumpers:
//   X has M0 + M1 = address 3, Y has M0 only = address 1. M2 off on both,
//   since the M2 slot is PDN_UART and a jumper there ties it to 5 V.
//   Current stays on the Vref pots (I_scale_analog left at 1).
// 20T motor pulley -> 60T push-over knob = 3:1, 26.667 steps per knob degree.
//
// Protocol, 115200, one command per line, every line answered "ok" or "err":
//   M x y        queue a move to absolute (x, y) steps
//   J dx dy      queue a move relative to the last queued target
//   Z            call the current position (0, 0); only when idle
//   E 0|1        motors off / on
//   B bx by n    slack X, Y in steps, blend n (0 = take up all at once)
//   F sps        dominant-axis speed, steps per second
//   N 0..4       noise, only when idle:
//                  0 quiet  StealthChop, 1/16 smoothed to 1/256 (the old sound)
//                  1 hiss   SpreadCycle, 1/16 smoothed
//                  2 grit   SpreadCycle, true 1/16, no smoothing
//                  3 sing   SpreadCycle, half step
//                  4 full   SpreadCycle, full step
//                Answers "noise n X ok|- Y ok|-" then ok/err. Moves stay in
//                1/16 steps whatever the level, so the page never knows; at
//                half and full step the stylus lands on the nearest real
//                step. Drivers need motor power to answer, so E 1 resends it.
// Realtime, no newline needed, work mid-move:
//   !            stop: drop the queue and the current move -> "aborted <n>"
//   ?            status -> "S x y queued done motors bx by blend sps noise"
// Reports:
//   D n          n moves finished in total
//   P n pm x y   moving: move n, pm per mille done, stylus at (x, y) steps
//
// Flow control: the queue holds QN moves. The host keeps (moves sent -
// moves done) at or below QN - 2, using the D reports.

#define VERSION "0.2.0"
#define NOISE_BOOT 3          // level set at boot and on every E 1

#include <SoftwareSerial.h>

const int X_STEP = 2, Y_STEP = 3, X_DIR = 5, Y_DIR = 6, EN = 8;
const int TMC_RX = A0, TMC_TX = A1;
const uint8_t X_ADDR = 3, Y_ADDR = 1;
const float STEPS_PER_DEG = 200.0 * 16 * 60 / 20 / 360.0;   // 26.667

#define QN 16
struct Move { long x, y; };
Move q[QN];
uint8_t qHead = 0, qCount = 0;

long posX = 0, posY = 0;     // stylus position in steps, slack excluded
long tgtX = 0, tgtY = 0;     // last queued target, for J
int lastDirX = 0, lastDirY = 0;
long pendX = 0, pendY = 0;   // slack steps still owed since the last reversal

// Defaults = what spiral/ and lorenz/ settled on (21 Oct). The page sends its own.
long blX = lround(23.0 * STEPS_PER_DEG), blY = lround(17.0 * STEPS_PER_DEG);
int blend = 3;
long sps = lround(60.0 * STEPS_PER_DEG);
unsigned long stepUs = 1000000UL / sps;

unsigned long accepted = 0, done = 0;
bool motors = false;
bool abortReq = false;
unsigned long lastReport = 0;

// Noise. div = 1/16 steps per real driver step; only applied to an axis
// whose driver confirmed the change, so a missing wire means the old
// standalone behaviour, not a machine moving at 1/16 the distance.
struct Level { bool spread, intpol; uint8_t mres, div; };
const Level LEVELS[5] = {
  { false, true,  4, 1 },   // quiet
  { true,  true,  4, 1 },   // hiss
  { true,  false, 4, 1 },   // grit
  { true,  false, 7, 8 },   // sing, half step
  { true,  false, 8, 16 },  // full step
};
int noise = -1;               // -1 = never confirmed
uint8_t divX = 1, divY = 1, subX = 0, subY = 0;
bool fwdX = true, fwdY = true;
bool moving = false;
SoftwareSerial tmc(TMC_RX, TMC_TX);

char line[48];
uint8_t len = 0;

void setMotors(bool on) {
  motors = on;
  digitalWrite(EN, on ? LOW : HIGH);
}

void setDir(int pin, bool positive) {
  digitalWrite(pin, positive ? LOW : HIGH);   // LOW = clockwise = positive, as GRBL $3=0
  if (pin == X_DIR) fwdX = positive; else fwdY = positive;
}

void pulse(int pin) {
  digitalWrite(pin, HIGH);
  delayMicroseconds(4);
  digitalWrite(pin, LOW);
}

// One 1/16 step. At a coarser driver step this only pulses when the 1/16
// count crosses a real step, rounding down both ways, so it adds no slack.
void step(int pin) {
  bool isX = pin == X_STEP;
  uint8_t d = isX ? divX : divY;
  if (d == 1) { pulse(pin); return; }
  uint8_t &sub = isX ? subX : subY;
  if (isX ? fwdX : fwdY) { if (++sub >= d) { sub = 0; pulse(pin); } }
  else if (sub == 0) { sub = d - 1; pulse(pin); }
  else sub--;
}

// ---- TMC2209 single-wire UART (datasheet section 4)
uint8_t crc8(const uint8_t *b, uint8_t n) {
  uint8_t crc = 0;
  for (uint8_t i = 0; i < n; i++) {
    uint8_t c = b[i];
    for (uint8_t j = 0; j < 8; j++) {
      crc = ((crc >> 7) ^ (c & 1)) ? (crc << 1) ^ 0x07 : crc << 1;
      c >>= 1;
    }
  }
  return crc;
}

void tmcWrite(uint8_t addr, uint8_t reg, uint32_t v) {
  uint8_t b[8] = { 0x05, addr, (uint8_t)(reg | 0x80),
                   (uint8_t)(v >> 24), (uint8_t)(v >> 16), (uint8_t)(v >> 8), (uint8_t)v, 0 };
  b[7] = crc8(b, 7);
  tmc.write(b, 8);
  delay(2);
}

// Our own bytes echo back on the shared wire, so look for the reply's
// 05 FF reg header rather than trusting byte positions.
bool tmcRead(uint8_t addr, uint8_t reg, uint32_t &v) {
  uint8_t req[4] = { 0x05, addr, reg, 0 };
  req[3] = crc8(req, 3);
  while (tmc.available()) tmc.read();
  tmc.write(req, 4);
  uint8_t b[16]; uint8_t n = 0;
  unsigned long t0 = millis();
  while (millis() - t0 < 30 && n < sizeof(b)) if (tmc.available()) b[n++] = tmc.read();
  for (uint8_t i = 0; i + 8 <= n; i++) {
    if (b[i] == 0x05 && b[i + 1] == 0xFF && b[i + 2] == reg && crc8(b + i, 7) == b[i + 7]) {
      v = ((uint32_t)b[i + 3] << 24) | ((uint32_t)b[i + 4] << 16) | ((uint32_t)b[i + 5] << 8) | b[i + 6];
      return true;
    }
  }
  return false;
}

// GCONF: I_scale_analog (pot keeps the current), pdn_disable (UART owns
// the PDN pin), mstep_reg_select (MRES not the jumpers), multistep_filt.
// CHOPCONF: TOFF 4, HSTRT 1, HEND 2, TBL 2 (Marlin's 24 V chopper) + MRES, intpol.
bool tmcLevel(uint8_t addr, const Level &L) {
  uint32_t gconf = 0x1C1UL | (L.spread ? 0x04UL : 0);
  uint32_t chop = 0x04UL | (5UL << 7) | (2UL << 15) | ((uint32_t)L.mres << 24) | (L.intpol ? (1UL << 28) : 0);
  tmcWrite(addr, 0x00, gconf);
  tmcWrite(addr, 0x6C, chop);
  uint32_t g, c;
  return tmcRead(addr, 0x00, g) && tmcRead(addr, 0x6C, c) && (g & 0x1FF) == gconf && c == chop;
}

bool setNoise(int n) {
  const Level &L = LEVELS[n];
  tmc.listen();
  bool okX = tmcLevel(X_ADDR, L), okY = tmcLevel(Y_ADDR, L);
  if (okX) { divX = L.div; subX = 0; }
  if (okY) { divY = L.div; subY = 0; }
  if (okX && okY) noise = n;
  Serial.print("noise "); Serial.print(n);
  Serial.print(okX ? " X ok" : " X -"); Serial.println(okY ? " Y ok" : " Y -");
  return okX && okY;
}

void status() {
  Serial.print("S "); Serial.print(posX); Serial.print(' '); Serial.print(posY);
  Serial.print(' '); Serial.print(qCount); Serial.print(' '); Serial.print(done);
  Serial.print(' '); Serial.print(motors ? 1 : 0);
  Serial.print(' '); Serial.print(blX); Serial.print(' '); Serial.print(blY);
  Serial.print(' '); Serial.print(blend); Serial.print(' '); Serial.print(sps);
  Serial.print(' '); Serial.println(noise);
}

// Pull a number off the line; false if there isn't one.
bool num(char *&p, long &out) {
  while (*p == ' ') p++;
  char *end;
  out = strtol(p, &end, 10);
  if (end == p) return false;
  p = end;
  return true;
}

bool queueMove(long x, long y) {
  if (qCount >= QN) { Serial.println("err full"); return false; }
  q[(qHead + qCount) % QN] = { x, y };
  qCount++;
  accepted++;
  tgtX = x; tgtY = y;
  Serial.println("ok");
  return true;
}

void handleLine(char *s) {
  char c = s[0];
  char *p = s + 1;
  long a, b, n;
  switch (c) {
    case 'M':
      if (num(p, a) && num(p, b)) queueMove(a, b); else Serial.println("err M x y");
      break;
    case 'J':
      if (num(p, a) && num(p, b)) queueMove(tgtX + a, tgtY + b); else Serial.println("err J dx dy");
      break;
    case 'Z':
      if (qCount) { Serial.println("err busy"); break; }
      posX = posY = tgtX = tgtY = 0;
      Serial.println("ok");
      break;
    case 'E':
      if (num(p, a)) {
        setMotors(a != 0);
        if (a && !moving && !qCount) setNoise(noise >= 0 ? noise : NOISE_BOOT);
        Serial.println("ok");
      } else Serial.println("err E 0|1");
      break;
    case 'B':
      if (num(p, a) && num(p, b) && num(p, n) && a >= 0 && b >= 0 && n >= 0) {
        blX = a; blY = b; blend = n; Serial.println("ok");
      } else Serial.println("err B bx by blend");
      break;
    case 'F':
      if (num(p, a) && a >= 100 && a <= 8000) { sps = a; stepUs = 1000000UL / sps; Serial.println("ok"); }
      else Serial.println("err F 100..8000");
      break;
    case 'N':
      if (!num(p, a) || a < 0 || a > 4) { Serial.println("err N 0..4"); break; }
      if (moving || qCount) { Serial.println("err busy"); break; }
      Serial.println(setNoise(a) ? "ok" : "err noise: a driver did not answer, check the UART wire and motor power");
      break;
    default:
      Serial.println("err ?");
  }
}

void serviceSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '!') { abortReq = true; continue; }
    if (c == '?') { status(); continue; }
    if (c == '\r') continue;
    if (c == '\n') {
      line[len] = 0;
      if (len) handleLine(line);
      len = 0;
    } else if (len < sizeof(line) - 1) {
      line[len++] = c;
    }
  }
}

void takeUp(int stepPin, long n) {
  for (long i = 0; i < n && !abortReq; i++) {
    unsigned long t0 = micros();
    step(stepPin);
    serviceSerial();
    while (micros() - t0 < stepUs) {}
  }
}

// Same rule as lorenz/ and spiral/: on a reversal the slack is owed and
// paid off `blend` extra steps per drawn step; reversing again before it
// is paid only has to cross back what was taken up.
void reversal(int stepPin, long bl, long &pend) {
  if (blend == 0) { takeUp(stepPin, bl); pend = 0; }
  else pend = bl - pend;
}

void payOff(int stepPin, long &pend) {
  for (int k = 0; k < blend && pend > 0; k++) {
    delayMicroseconds(150);
    step(stepPin);
    pend--;
  }
}

void report(unsigned long n, long pm) {
  Serial.print("P "); Serial.print(n); Serial.print(' '); Serial.print(pm);
  Serial.print(' '); Serial.print(posX); Serial.print(' '); Serial.println(posY);
}

void runMove(long tx, long ty) {
  long dx = tx - posX, dy = ty - posY;
  if (dx == 0 && dy == 0) return;
  bool px = dx >= 0, py = dy >= 0;
  setDir(X_DIR, px);
  setDir(Y_DIR, py);
  delayMicroseconds(5);
  int sx = px ? 1 : -1, sy = py ? 1 : -1;
  if (dx != 0 && sx != lastDirX) { if (lastDirX != 0) reversal(X_STEP, blX, pendX); lastDirX = sx; }
  if (dy != 0 && sy != lastDirY) { if (lastDirY != 0) reversal(Y_STEP, blY, pendY); lastDirY = sy; }
  dx = labs(dx); dy = labs(dy);
  long n = max(dx, dy), ex = 0, ey = 0;
  unsigned long id = done + 1;
  for (long i = 0; i < n; i++) {
    unsigned long t0 = micros();
    ex += dx; ey += dy;
    if (ex >= n) { ex -= n; step(X_STEP); posX += sx; payOff(X_STEP, pendX); }
    if (ey >= n) { ey -= n; step(Y_STEP); posY += sy; payOff(Y_STEP, pendY); }
    serviceSerial();
    if (abortReq) return;
    if (millis() - lastReport >= 50) {
      lastReport = millis();
      report(id, (i + 1) * 1000L / n);
    }
    while (micros() - t0 < stepUs) {}
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("=== Etchatron controller v" VERSION " ===");
  Serial.println("Queued step/dir moves for the control page, CNC Shield V3, blended slack take-up");
  Serial.println("https://github.com/sui001/etchatron/tree/master/controller");

  pinMode(X_STEP, OUTPUT); pinMode(Y_STEP, OUTPUT);
  pinMode(X_DIR, OUTPUT);  pinMode(Y_DIR, OUTPUT);
  pinMode(EN, OUTPUT);
  setMotors(false);
  tmc.begin(19200);
  setNoise(NOISE_BOOT);   // only answers if motor power is already on
  Serial.println("ready");
}

void loop() {
  serviceSerial();
  if (abortReq) {
    abortReq = false;
    qCount = 0;
    done = accepted;
    tgtX = posX; tgtY = posY;
    Serial.print("aborted "); Serial.println(done);
    return;
  }
  if (qCount) {
    Move m = q[qHead];
    qHead = (qHead + 1) % QN;
    qCount--;
    moving = true;
    runMove(m.x, m.y);
    moving = false;
    if (abortReq) return;          // loop() reports it
    done++;
    report(done, 1000);
    Serial.print("D "); Serial.println(done);
  }
}
