// lorenz.ino: Etchatron standalone Lorenz attractor, no GRBL.
//
// Port of sketch_may26a.ino (Stepper.h, 2-pin phase mode on pins 9/3/10/11)
// to the Protoneer CNC Shield V3 + BTT TMC2209s, which want step/dir:
//   X  STEP D2  DIR D5   horizontal knob (left)
//   Y  STEP D3  DIR D6   vertical knob (right)
//   EN D8, active LOW, shared by all drivers
//
// Flashing this replaces GRBL. To go back: reflash grbl_v1.1h, then
// python etchatron/grbl_setup.py --port COM60
//
// The maths is unchanged (a=10, b=28, c=2.66, dt=0.01). Lorenz x goes to the
// X knob and z to the Y knob, so the butterfly stands upright. The original
// had them the other way round (z horizontal); set SWAP_AXES 1 for that.
//
// START THE STYLUS IN THE CENTRE OF THE SCREEN. On boot the attractor is run
// silently until it crosses the middle of the figure (x~0, z~Z_CENTRE, which
// it does at iteration ~1610 from the original start), and drawing begins
// there. So there is no lead-in line, and the figure (x -19..19, z 3..47
// Lorenz units) sits centred on the screen, give or take a few degrees.
// Size is DEG_PER_UNIT (knob degrees per Lorenz unit), a guess until stylus
// travel per knob turn is measured. At 10: about +-190 deg wide, +-220 tall.
//
// Serial 115200: any byte pauses / resumes.

#define VERSION "0.2.0"

// ---- tune these -----------------------------------------------------------
#define DEG_PER_UNIT  10.0    // knob degrees per Lorenz unit: about +-190 x +-220 deg
#define MAX_DEG_S     60.0    // dominant axis knob speed, same as GRBL $110 (3600/min)
#define SWAP_AXES     0       // 1 = z horizontal, x vertical (the original layout)
#define INVERT_X      0       // 1 flips X. Positive = clockwise = stylus right
#define INVERT_Y      0       // 1 flips Y. Positive = clockwise = stylus up
#define START_DELAY_S 3       // countdown before the first move
#define Z_CENTRE      25.25   // middle of the figure's z range (3.5..47)
// ---------------------------------------------------------------------------

// 1/16 microstep (all three jumpers), 20T motor pulley -> 60T push-over
// knob = 3:1. Same number as $100/$101 in grbl_setup.py.
const float STEPS_PER_DEG  = 200.0 * 16 * 60 / 20 / 360.0;   // 26.667
const float STEPS_PER_UNIT = STEPS_PER_DEG * DEG_PER_UNIT;
const unsigned long STEP_US = (unsigned long)(1e6 / (MAX_DEG_S * STEPS_PER_DEG));

const int X_STEP = 2, Y_STEP = 3, X_DIR = 5, Y_DIR = 6, EN = 8;

float x = 0.01, y = 0, z = 0;
const float a = 10.0, b = 28.0, c = 2.66, dt = 0.01;

long posX = 0, posY = 0;     // where the steppers are, in steps

void step() {
  x += (a * (y - x)) * dt;
  y += (x * (b - z) - y) * dt;
  z += ((x * y) - (c * z)) * dt;
}

// Absolute targets in steps, relative to the figure's centre, so rounding
// never accumulates the way the original's int() deltas did.
long targetX() { return lround((SWAP_AXES ? z - Z_CENTRE : x) * STEPS_PER_UNIT); }
long targetY() { return lround((SWAP_AXES ? x : z - Z_CENTRE) * STEPS_PER_UNIT); }

void setDir(int pin, bool positive, bool invert) {
  // GRBL convention, already checked on this rig with $3=0: DIR LOW = positive.
  digitalWrite(pin, (positive != invert) ? LOW : HIGH);
}

void pulse(int pin) {
  digitalWrite(pin, HIGH);
  delayMicroseconds(4);      // 2209 wants >100 ns, this is plenty
  digitalWrite(pin, LOW);
}

// One burst of bytes (a line plus its \r\n) counts as one press.
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

// Bresenham line from where we are to (tx, ty) in steps, at a fixed step
// rate on the longer axis. No acceleration: at 60 deg/s of knob the motor
// is doing half a turn a second, which a NEMA17 starts and stops dead.
void moveTo(long tx, long ty) {
  long dx = tx - posX, dy = ty - posY;
  bool px = dx >= 0, py = dy >= 0;
  setDir(X_DIR, px, INVERT_X);
  setDir(Y_DIR, py, INVERT_Y);
  delayMicroseconds(5);      // DIR setup time before the first step
  dx = labs(dx); dy = labs(dy);
  long n = max(dx, dy), ex = 0, ey = 0;
  for (long i = 0; i < n; i++) {
    unsigned long t0 = micros();
    ex += dx; ey += dy;
    if (ex >= n) { ex -= n; pulse(X_STEP); posX += px ? 1 : -1; }
    if (ey >= n) { ey -= n; pulse(Y_STEP); posY += py ? 1 : -1; }
    while (micros() - t0 < STEP_US) {}
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("=== gen3d Etchatron Lorenz v" VERSION " ===");
  Serial.println("Standalone Lorenz attractor on an Etch A Sketch, CNC Shield V3 step/dir, no GRBL");
  Serial.println("https://github.com/sui001/gen3d/tree/master/etchatron/lorenz");

  pinMode(X_STEP, OUTPUT); pinMode(Y_STEP, OUTPUT);
  pinMode(X_DIR, OUTPUT);  pinMode(Y_DIR, OUTPUT);
  pinMode(EN, OUTPUT);
  digitalWrite(EN, LOW);     // drivers on

  // Run the attractor without drawing until it passes the figure's centre,
  // then call that point "here". Deterministic, so it lands on the same
  // point every boot.
  for (long i = 0; ; i++) {
    step();
    if (i > 500 && fabs(x) < 0.3 && fabs(z - Z_CENTRE) < 1.0) {
      Serial.print("start at iteration "); Serial.print(i);
      Serial.print("  x "); Serial.print(x, 2); Serial.print("  z "); Serial.println(z, 2);
      break;
    }
  }
  posX = targetX(); posY = targetY();

  Serial.print("steps/deg "); Serial.print(STEPS_PER_DEG, 3);
  Serial.print("  deg/unit "); Serial.print(DEG_PER_UNIT, 1);
  Serial.print("  step us "); Serial.println(STEP_US);
  for (int s = START_DELAY_S; s > 0; s--) {
    Serial.print("start in "); Serial.println(s);
    delay(1000);
  }
  Serial.println("running (any byte pauses)");
}

void loop() {
  step();
  moveTo(targetX(), targetY());

  checkSerial();
}
