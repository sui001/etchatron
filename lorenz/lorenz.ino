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
// The stylus start position is the Lorenz origin (x=0, z=0), and the figure
// grows UP from there: roughly x +-20 and z 0..50 in Lorenz units. So start
// the stylus bottom-centre. Size is DEG_PER_UNIT (knob degrees per Lorenz
// unit), a guess until stylus travel per knob turn is measured.
//
// Serial 115200: any byte pauses / resumes.

#define VERSION "0.1.0"

// ---- tune these -----------------------------------------------------------
#define DEG_PER_UNIT  10.0    // knob degrees per Lorenz unit: x +-200, z 0..500 deg
#define MAX_DEG_S     60.0    // dominant axis knob speed, same as GRBL $110 (3600/min)
#define SWAP_AXES     0       // 1 = z horizontal, x vertical (the original layout)
#define INVERT_X      0       // 1 flips X. Positive = clockwise = stylus right
#define INVERT_Y      0       // 1 flips Y. Positive = clockwise = stylus up
#define START_DELAY_S 3       // countdown before the first move
// ---------------------------------------------------------------------------

// 1/16 microstep (all three jumpers), 40T motor -> 60T over-knob = 1.5:1.
// Same number as $100/$101 in grbl_setup.py.
const float STEPS_PER_DEG  = 200.0 * 16 * 60 / 40 / 360.0;   // 13.333
const float STEPS_PER_UNIT = STEPS_PER_DEG * DEG_PER_UNIT;
const unsigned long STEP_US = (unsigned long)(1e6 / (MAX_DEG_S * STEPS_PER_DEG));

const int X_STEP = 2, Y_STEP = 3, X_DIR = 5, Y_DIR = 6, EN = 8;

float x = 0.01, y = 0, z = 0;
const float a = 10.0, b = 28.0, c = 2.66, dt = 0.01;

long posX = 0, posY = 0;     // where the steppers are, in steps

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
// rate on the longer axis. No acceleration: at 800 steps/s a NEMA17 starts
// and stops dead without missing.
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
  x += (a * (y - x)) * dt;
  y += (x * (b - z) - y) * dt;
  z += ((x * y) - (c * z)) * dt;

  // Absolute targets, so rounding never accumulates the way the original's
  // int() deltas did.
  float h = SWAP_AXES ? z : x;
  float v = SWAP_AXES ? x : z;
  moveTo(lround(h * STEPS_PER_UNIT), lround(v * STEPS_PER_UNIT));

  checkSerial();
}
