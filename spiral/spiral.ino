// spiral.ino: Etchatron backlash test. An Archimedean spiral out from the
// centre, for photographing.
//
// Why a spiral: every turn reverses each axis twice. X reverses at the left
// and right extremes and Y at the top and bottom. Any slop in the belt, the
// over-knob or the EaS's own string drive shows up as a flat spot just
// after each reversal, where the motor turns but the stylus doesn't move yet:
//   X slop -> short VERTICAL flats at the far left and far right of each turn
//   Y slop -> short HORIZONTAL flats at the very top and bottom
// Flat length in knob degrees = backlash. The rings are exactly PITCH_DEG
// apart, so the photo carries its own scale: flat length / ring spacing *
// PITCH_DEG. It also shows whether the slop is the same on every turn, and
// whether it is a fixed amount (backlash) or grows with radius (slipping).
//
// BACKLASH_X/Y_DEG add extra uncounted steps whenever that axis reverses.
// The first photo (21 Oct, at 0) fitted X 25 / Y 15: spiral_fit_2026-10-21.png.
// Second photo, compensated at 25/15, fitted X 23.1 / Y 16.7 (4.9 px error). Same pins and drive as
// lorenz.ino (CNC Shield V3, 20T -> 60T, 1/16).
// Third photo at 23/17: round, but small notches stay at N/S/E/W, and the
// photo fit can no longer tell 20/15 from 30/21. So v0.3.0 is a LADDER:
// each ring uses a different backlash, LADDER_DEG apart, centred on ring 4:
//   ring 1..7 = base -9, -6, -3, 0, +3, +6, +9   (X 14..32, Y 8..26)
// Read the ring whose top/bottom notch (Y) and left notch (X) vanish. The
// right-hand reversal is where a ring starts, so it uses the next ring's
// value; read left, not right. Serial prints each ring's values.
// Ladder result: under = rounded flat, over = sharp step. Changeover at
// X ring 2-3 (17-20) and Y ring 2-3 (11-14): X 18, Y 12. The photo fits
// (23/17) read high because they could not tell a flat from a step.
//
// Start: wipe the screen, centre the stylus, press reset. Serial 115200: any
// byte pauses / resumes.

#define VERSION "0.4.0"

// ---- tune these -----------------------------------------------------------
#define TURNS         8
#define PITCH_DEG     50.0    // knob degrees between rings: radius 400 at 8 turns
#define CHORD_DEG     4.0     // segment length along the curve
#define MAX_DEG_S     60.0    // same as lorenz.ino
#define BACKLASH_X_DEG 23.0   // extra knob degrees on every X reversal
#define BACKLASH_Y_DEG 17.0   // extra knob degrees on every Y reversal
#define BLEND         1       // extra slack steps per drawn step after a reversal.
                              // 0 = all at once (v0.3 and earlier, notches);
                              // 1 = that knob runs double speed until taken up
#define INVERT_X      0
#define INVERT_Y      0
#define START_DELAY_S 3
#define LADDER_DEG    0.0     // backlash change per ring, 0 = plain spiral (3 for the ladder)
#define LADDER_MID    4       // ring that uses exactly BACKLASH_X/Y_DEG
// ---------------------------------------------------------------------------

const float STEPS_PER_DEG = 200.0 * 16 * 60 / 20 / 360.0;   // 26.667
const unsigned long STEP_US = (unsigned long)(1e6 / (MAX_DEG_S * STEPS_PER_DEG));
long BL_X = 0, BL_Y = 0;     // set per ring by setRing()

void setRing(int ring) {
  float bx = BACKLASH_X_DEG + (ring - LADDER_MID) * LADDER_DEG;
  float by = BACKLASH_Y_DEG + (ring - LADDER_MID) * LADDER_DEG;
  BL_X = lround(max(bx, 0.0f) * STEPS_PER_DEG);
  BL_Y = lround(max(by, 0.0f) * STEPS_PER_DEG);
  Serial.print("ring "); Serial.print(ring);
  Serial.print("  backlash deg X "); Serial.print(max(bx, 0.0f), 1);
  Serial.print(" Y "); Serial.println(max(by, 0.0f), 1);
}

const int X_STEP = 2, Y_STEP = 3, X_DIR = 5, Y_DIR = 6, EN = 8;

long posX = 0, posY = 0;     // commanded position in steps, backlash steps excluded
int lastDirX = 0, lastDirY = 0;   // +1 / -1, 0 = not moved yet
long pendX = 0, pendY = 0;   // slack steps still owed since the last reversal

void setDir(int pin, bool positive, bool invert) {
  digitalWrite(pin, (positive != invert) ? LOW : HIGH);   // LOW = positive, as GRBL
}

void pulse(int pin) {
  digitalWrite(pin, HIGH);
  delayMicroseconds(4);
  digitalWrite(pin, LOW);
}

bool gotPress() {
  if (!Serial.available()) return false;
  delay(20);
  while (Serial.available()) Serial.read();
  return true;
}

void checkSerial() {
  if (!gotPress()) return;
  Serial.println("paused");
  while (!gotPress()) {}
  Serial.println("running");
}

// Take up slack on a reversal: extra steps that move the motor but are not
// counted, because the stylus shouldn't move during them. The first move is
// not compensated: nobody knows which side of the slack it was left on.
//
// v0.4: BLENDED take-up. The ladder (v0.3.0) showed the EaS slack is part
// dead gap, part springy string: a burst big enough to keep circles round
// (~23/17) overshoots the springy part and leaves a sharp step, and one
// small enough to leave no step (~18/12) leaves a flat. So instead of a
// burst, the slack is owed (pendX/pendY) and paid off BLEND extra steps per
// drawn step on that axis. An axis is barely moving at its reversal, so the
// take-up spreads over the start of the curve instead of happening on the
// spot. If the axis reverses again before it is paid off, only what was
// actually taken up has to be crossed back: pend = BL - pend.
void takeUp(int stepPin, long n) {
  for (long i = 0; i < n; i++) {
    unsigned long t0 = micros();
    pulse(stepPin);
    while (micros() - t0 < STEP_US) {}
  }
}

void reversal(int stepPin, long bl, long &pend) {
  if (BLEND == 0) { takeUp(stepPin, bl); pend = 0; }
  else pend = bl - pend;
}

void payOff(int stepPin, long &pend) {
  for (int k = 0; k < BLEND && pend > 0; k++) {
    delayMicroseconds(150);
    pulse(stepPin);
    pend--;
  }
}

void moveTo(long tx, long ty) {
  long dx = tx - posX, dy = ty - posY;
  if (dx == 0 && dy == 0) return;
  bool px = dx >= 0, py = dy >= 0;
  setDir(X_DIR, px, INVERT_X);
  setDir(Y_DIR, py, INVERT_Y);
  delayMicroseconds(5);
  int sx = px ? 1 : -1, sy = py ? 1 : -1;
  if (dx != 0 && sx != lastDirX) { if (lastDirX != 0) reversal(X_STEP, BL_X, pendX); lastDirX = sx; }
  if (dy != 0 && sy != lastDirY) { if (lastDirY != 0) reversal(Y_STEP, BL_Y, pendY); lastDirY = sy; }
  dx = labs(dx); dy = labs(dy);
  long n = max(dx, dy), ex = 0, ey = 0;
  for (long i = 0; i < n; i++) {
    unsigned long t0 = micros();
    ex += dx; ey += dy;
    if (ex >= n) { ex -= n; pulse(X_STEP); posX += sx; payOff(X_STEP, pendX); }
    if (ey >= n) { ey -= n; pulse(Y_STEP); posY += sy; payOff(Y_STEP, pendY); }
    while (micros() - t0 < STEP_US) {}
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("=== Etchatron spiral v" VERSION " ===");
  Serial.println("Backlash test: Archimedean spiral from the centre, CNC Shield V3 step/dir");
  Serial.println("https://github.com/sui001/etchatron/tree/master/spiral");

  pinMode(X_STEP, OUTPUT); pinMode(Y_STEP, OUTPUT);
  pinMode(X_DIR, OUTPUT);  pinMode(Y_DIR, OUTPUT);
  pinMode(EN, OUTPUT);
  digitalWrite(EN, LOW);

  Serial.print("turns "); Serial.print(TURNS);
  Serial.print("  pitch deg "); Serial.print(PITCH_DEG, 1);
  Serial.print("  backlash deg X "); Serial.print(BACKLASH_X_DEG, 1);
  Serial.print(" Y "); Serial.print(BACKLASH_Y_DEG, 1);
  Serial.print("  blend "); Serial.println(BLEND);
  for (int s = START_DELAY_S; s > 0; s--) {
    Serial.print("start in "); Serial.println(s);
    delay(1000);
  }
  Serial.println("running (any byte pauses)");

  // r = PITCH * theta / 2pi. Step theta so each segment is ~CHORD_DEG long;
  // near the centre the arc is short, so floor r to keep the step finite.
  float thetaEnd = TURNS * TWO_PI;
  float theta = 0;
  int ring = 0;
  setRing(0);
  while (theta < thetaEnd) {
    float r = PITCH_DEG * theta / TWO_PI;
    theta += CHORD_DEG / max(r, PITCH_DEG / 4);
    if (theta > thetaEnd) theta = thetaEnd;
    r = PITCH_DEG * theta / TWO_PI;
    moveTo(lround(r * cos(theta) * STEPS_PER_DEG), lround(r * sin(theta) * STEPS_PER_DEG));
    if ((int)(theta / TWO_PI) != ring && theta < thetaEnd) {
      ring = theta / TWO_PI;
      setRing(ring);
    }
    checkSerial();
  }
  digitalWrite(EN, HIGH);    // let go: knob friction holds the stylus
  Serial.println("done");
}

void loop() {}
