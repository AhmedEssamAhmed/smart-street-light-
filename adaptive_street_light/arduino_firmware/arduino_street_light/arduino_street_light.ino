// ============================================================
//  Smart Adaptive Street Light — FreeRTOS (ESP32)
//  9 LEDs + LDR + concurrent wave animations
//
//  Each "WAVE" on Serial spawns an independent animation that
//  marches across the LEDs.  Multiple waves overlap correctly
//  via brightness compositing (max over all waves + ambient).
// ============================================================

#include <Arduino.h>

// ── Pin configuration (tweak for your ESP32 board) ───────────
#define LDR_PIN         34          // ADC1 channel (GPIO 34)
#define NUM_LEDS        9
int ledPins[NUM_LEDS] = { 2, 4, 5, 12, 13, 14, 15, 16, 17 };

// ── Brightness & timing ──────────────────────────────────────
#define DIM_PERCENT     30          // night standby glow
#define PWM_FREQ        20000       // 20 kHz LEDC
#define PWM_RES         8           // 0–255

#define DAY_THRESHOLD   700
#define NIGHT_THRESHOLD 500
#define WAVE_DELAY_MS   150
#define HOLD_MS         3000
#define MAX_WAVES       10

// ── Wave state ───────────────────────────────────────────────
//  litUntil  = highest LED index currently lit by this wave
//              (-1 = none, 0..NUM_LEDS-1 = advancing, then retreating)
//  holding   = pause after reaching the far end
//  holdUntil = absolute ms when hold ends
struct Wave {
  bool active;
  int8_t litUntil;
  unsigned long lastStep;
  bool holding;
  unsigned long holdUntil;
};

static Wave waves[MAX_WAVES];
static bool isNight = false;

// ── FreeRTOS ─────────────────────────────────────────────────
static QueueHandle_t cmdQueue;
enum Cmd : uint8_t { CMD_NONE, CMD_WAVE, CMD_NIGHT, CMD_DAY };

// ============================================================
//  Compositing – each LED gets MAX(ambient, ANY wave covering it)
// ============================================================
static void recomputeLEDs() {
  int full = (1 << PWM_RES) - 1;        // 255
  int ambient = isNight ? (DIM_PERCENT * full / 100) : 0;

  for (int i = 0; i < NUM_LEDS; i++) {
    int val = ambient;
    for (int w = 0; w < MAX_WAVES; w++) {
      if (waves[w].active && waves[w].litUntil >= i) {
        val = full;
        break;
      }
    }
    ledcWrite(i, val);
  }
}

// ============================================================
//  Spawn a wave (find free slot, or drop oldest if full)
// ============================================================
static void spawnWave() {
  for (int i = 0; i < MAX_WAVES; i++) {
    if (!waves[i].active) {
      waves[i].active   = true;
      waves[i].litUntil = -1;
      waves[i].lastStep = 0;
      waves[i].holding  = false;
      waves[i].holdUntil = 0;
      Serial.printf("Wave #%d spawned\n", i);
      return;
    }
  }
  Serial.println("Wave pool full");
}

// ============================================================
//  FreeRTOS task: wave manager (core 1)
// ============================================================
static void waveTask(void *pv) {
  Cmd cmd;

  for (;;) {
    // ── Consume commands ──────────────────────────────────
    while (xQueueReceive(cmdQueue, &cmd, 0) == pdTRUE) {
      switch (cmd) {
        case CMD_WAVE:  spawnWave(); break;
        case CMD_NIGHT: isNight = true;  break;
        case CMD_DAY:   isNight = false; break;
        default: break;
      }
    }

    // ── Advance every active wave ─────────────────────────
    unsigned long now = millis();
    for (int i = 0; i < MAX_WAVES; i++) {
      if (!waves[i].active) continue;
      if (now - waves[i].lastStep < WAVE_DELAY_MS) continue;
      waves[i].lastStep = now;

      if (waves[i].holding) {
        if (now >= waves[i].holdUntil) {
          waves[i].holding  = false;
          waves[i].litUntil--;
          if (waves[i].litUntil < 0) {
            waves[i].active = false;
          }
        }
      } else if (waves[i].litUntil < NUM_LEDS - 1) {
        waves[i].litUntil++;
      } else {
        waves[i].holding  = true;
        waves[i].holdUntil = now + HOLD_MS;
      }
    }

    // ── Write LEDs ────────────────────────────────────────
    recomputeLEDs();

    vTaskDelay(pdMS_TO_TICKS(20));   // ~50 Hz
  }
}

// ============================================================
//  FreeRTOS task: serial reader (core 1)
// ============================================================
static void serialTask(void *pv) {
  String buf;

  for (;;) {
    while (Serial.available()) {
      char c = Serial.read();
      if (c == '\n') {
        buf.trim();
        if (buf == "WAVE") {
          Cmd c2 = CMD_WAVE;
          xQueueSend(cmdQueue, &c2, 0);
        } else if (buf == "NIGHT") {
          Cmd c2 = CMD_NIGHT;
          xQueueSend(cmdQueue, &c2, 0);
        } else if (buf == "DAY") {
          Cmd c2 = CMD_DAY;
          xQueueSend(cmdQueue, &c2, 0);
        }
        buf = "";
      } else if (c != '\r') {
        buf += c;
      }
    }
    vTaskDelay(pdMS_TO_TICKS(10));
  }
}

// ============================================================
//  FreeRTOS task: ambient light monitor (core 1)
// ============================================================
static void ambientTask(void *pv) {
  for (;;) {
    int ldr = analogRead(LDR_PIN);
    if (ldr > DAY_THRESHOLD)      isNight = false;
    else if (ldr < NIGHT_THRESHOLD) isNight = true;

    Serial.printf("LDR:%d %s\n", ldr, isNight ? "NIGHT" : "DAY");
    vTaskDelay(pdMS_TO_TICKS(1000));
  }
}

// ============================================================
void setup() {
  Serial.begin(9600);
  delay(500);
  Serial.println("\n=== Smart Adaptive Street Light (FreeRTOS) ===");

  // ── LEDC PWM: one channel per LED ──────────────────────
  for (int i = 0; i < NUM_LEDS; i++) {
    ledcSetup(i, PWM_FREQ, PWM_RES);
    ledcAttachPin(ledPins[i], i);
  }

  pinMode(LDR_PIN, INPUT);
  analogReadResolution(10);       // match Uno's 10-bit ADC (0-1023)

  // ── Command queue ──────────────────────────────────────
  cmdQueue = xQueueCreate(10, sizeof(Cmd));

  // ── Spawn tasks ────────────────────────────────────────
  // PWM is handled by LEDC hardware — no soft-PWM task needed.
  xTaskCreatePinnedToCore(waveTask,   "Wave",   4096, NULL, 2, NULL, 1);
  xTaskCreatePinnedToCore(serialTask, "Serial", 2048, NULL, 1, NULL, 1);
  xTaskCreatePinnedToCore(ambientTask,"Ambient",2048, NULL, 1, NULL, 1);

  Serial.println("Ready — send WAVE / NIGHT / DAY on Serial");
}

void loop() {
  vTaskDelete(NULL);
}
