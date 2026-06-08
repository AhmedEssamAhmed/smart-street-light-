// ============================================================
//  Smart Adaptive Street Light — Arduino Uno
//  9 LEDs (software PWM) + LDR (day/night) + ESP32-CAM (UART)
//
//  No FreeRTOS — single loop with non-blocking millis() timing
//  Software PWM on all 9 pins for smooth 30% dimming
// ============================================================

#include <SoftwareSerial.h>

// ── Pin definitions ─────────────────────────────────────────
#define LDR_PIN       A0
#define ESP_RX_PIN    11          // SoftwareSerial RX (from ESP32 TX)
#define NUM_LEDS      9
int ledPins[NUM_LEDS] = {2, 3, 4, 5, 6, 7, 8, 9, 10};

// ── Software PWM constants ──────────────────────────────────
#define PWM_STEPS     100         // 0–100 brightness resolution
#define PWM_INTERVAL  50          // microseconds per step → 200 Hz
static unsigned long lastPwmUs = 0;
static byte pwmPhase = 0;
static byte ledBrightness[NUM_LEDS] = {0};

// ── Thresholds & Timing ─────────────────────────────────────
// NOTE: Arduino Uno uses 10-bit ADC (0–1023).
// Calibrate these values — see docs/wiring.md §7.
#define DAY_THRESHOLD   700       // LDR > this = day
#define NIGHT_THRESHOLD 500       // LDR < this = night (hysteresis)
#define DIM_PERCENT     30        // 30% standby glow
#define FULL_BRIGHT     100       // 100% = PWM_STEPS
#define WAVE_DELAY_MS   150       // ms between each LED step
#define HOLD_MS         3000      // ms without car before returning to dim

// ── State machine ───────────────────────────────────────────
enum State { DAY, NIGHT_IDLE, WAVE_ON, ALL_ON, WAVE_OFF };
State state = DAY;
bool carPresent = false;

int wavePos = 0;                  // which LED we're animating
unsigned long lastWaveMs = 0;
unsigned long lastCarMs = 0;

// ── UART buffer ─────────────────────────────────────────────
SoftwareSerial espSerial(ESP_RX_PIN, 12);   // RX=D11, TX=D12 (unused)
String uartBuf = "";

// ============================================================
void setBrightness(byte value) {
  for (int i = 0; i < NUM_LEDS; i++) {
    ledBrightness[i] = value;
  }
}

void setOneBrightness(int idx, byte value) {
  if (idx >= 0 && idx < NUM_LEDS) ledBrightness[idx] = value;
}

// ============================================================
// Fast software PWM — call on EVERY loop iteration
// ============================================================
void updatePWM() {
  unsigned long now = micros();
  if (now - lastPwmUs >= PWM_INTERVAL) {
    lastPwmUs = now;
    pwmPhase = (pwmPhase + 1) % PWM_STEPS;
    for (int i = 0; i < NUM_LEDS; i++) {
      digitalWrite(ledPins[i], ledBrightness[i] > pwmPhase ? HIGH : LOW);
    }
  }
}

// ============================================================
// Parse a complete line from ESP32
// ============================================================
void parseLine(const String &line) {
  if (line == "CAR") {
    carPresent = true;
    lastCarMs = millis();
    if (state == NIGHT_IDLE) {
      state = WAVE_ON;
      wavePos = 0;
      lastWaveMs = millis();
    } else if (state == WAVE_ON || state == ALL_ON || state == WAVE_OFF) {
      // New car arriving mid-wave — restart
      state = WAVE_ON;
      wavePos = 0;
      lastWaveMs = millis();
    }
  } else if (line == "CLEAR") {
    carPresent = false;
    if (state == ALL_ON) {
      state = WAVE_OFF;
      wavePos = NUM_LEDS - 1;
      lastWaveMs = millis();
    }
  }
}

// ============================================================
// Non-blocking UART reader
// ============================================================
void readUART() {
  while (espSerial.available()) {
    char c = espSerial.read();
    if (c == '\n') {
      uartBuf.trim();
      if (uartBuf.length() > 0) parseLine(uartBuf);
      uartBuf = "";
    } else {
      uartBuf += c;
    }
  }

  // Safety timeout — if no CAR refresh or CLEAR for HOLD_MS
  if (carPresent && (millis() - lastCarMs > HOLD_MS)) {
    carPresent = false;
    if (state == ALL_ON) {
      state = WAVE_OFF;
      wavePos = NUM_LEDS - 1;
      lastWaveMs = millis();
    }
  }
}

// ============================================================
// Debug output over USB serial (for calibration)
// ============================================================
void debugPrint(int ldr) {
  static unsigned long lastDbg = 0;
  if (millis() - lastDbg > 2000) {
    Serial.print("LDR:"); Serial.print(ldr);
    Serial.print("  State:");
    switch (state) {
      case DAY:        Serial.print("DAY"); break;
      case NIGHT_IDLE: Serial.print("NIGHT_IDLE"); break;
      case WAVE_ON:    Serial.print("WAVE_ON"); break;
      case ALL_ON:     Serial.print("ALL_ON"); break;
      case WAVE_OFF:   Serial.print("WAVE_OFF"); break;
    }
    Serial.print("  Car:"); Serial.println(carPresent);
    lastDbg = millis();
  }
}

// ============================================================
void setup() {
  Serial.begin(9600);           // USB debug
  espSerial.begin(115200);      // ESP32-CAM

  for (int i = 0; i < NUM_LEDS; i++) {
    pinMode(ledPins[i], OUTPUT);
    digitalWrite(ledPins[i], LOW);
  }
  pinMode(LDR_PIN, INPUT);

  Serial.println("=== Adaptive Street Light (Arduino Uno) ===");
  Serial.println("Waiting for ESP32-CAM...");
}

// ============================================================
void loop() {
  // 1) Fast PWM update — runs every ~50 µs
  updatePWM();

  // 2) Main logic at ~50 Hz
  static unsigned long lastTick = 0;
  unsigned long now = millis();
  if (now - lastTick < 20) return;   // ~50 Hz
  lastTick = now;

  // ── Read LDR & UART ─────────────────────────────────────
  int ldr = analogRead(LDR_PIN);
  readUART();

  bool isDay = (ldr > DAY_THRESHOLD);
  bool isNight = (ldr < NIGHT_THRESHOLD);

  debugPrint(ldr);

  // ── State transitions ───────────────────────────────────
  switch (state) {

    // ────── DAY ───────────────────────────────────────────
    case DAY:
      setBrightness(0);
      if (isNight) {
        state = NIGHT_IDLE;
        setBrightness(map(DIM_PERCENT, 0, 100, 0, PWM_STEPS));
      }
      break;

    // ────── NIGHT_IDLE: dim glow, waiting for car ─────────
    case NIGHT_IDLE:
      if (isDay) {
        state = DAY;
        break;
      }
      setBrightness(map(DIM_PERCENT, 0, 100, 0, PWM_STEPS));
      break;

    // ────── WAVE_ON: LEDs turn on one by one ──────────────
    case WAVE_ON:
      if (now - lastWaveMs >= WAVE_DELAY_MS) {
        lastWaveMs = now;
        setOneBrightness(wavePos, FULL_BRIGHT);
        wavePos++;
        if (wavePos >= NUM_LEDS) {
          state = ALL_ON;
          lastCarMs = now;
        }
      }
      break;

    // ────── ALL_ON: full brightness while car passes ──────
    case ALL_ON:
      setBrightness(FULL_BRIGHT);
      break;

    // ────── WAVE_OFF: LEDs return to dim one by one ───────
    case WAVE_OFF:
      if (now - lastWaveMs >= WAVE_DELAY_MS) {
        lastWaveMs = now;
        setOneBrightness(wavePos, map(DIM_PERCENT, 0, 100, 0, PWM_STEPS));
        wavePos--;
        if (wavePos < 0) {
          state = NIGHT_IDLE;
        }
      }
      break;
  }
}
