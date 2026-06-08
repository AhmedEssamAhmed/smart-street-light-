const int LED_PINS[] = { PB0, PB1, PB3, PB4, PB5, PB6, PB7, PB8, PB9 };
const int NUM_LEDS = 9;
const int LDR_PIN = PA0;
const int LDR_NIGHT_THRESHOLD = 40;
const int WAVE_DELAY_MS = 350;
const int LED_PEAK_MS = 80;
const int LED_TAIL_MS = 160;
const int SW_PWM_PERIOD = 10;
const int SW_PWM_ON_TIME = 4;
#define MAX_WAVES 10
struct Wave {
  bool active;
  int currentLED;
  unsigned long lastStepTime;
};
struct PulseLED {
  bool active;
  unsigned long offTime;
};
Wave waves[MAX_WAVES];
PulseLED pulses[NUM_LEDS];
bool isNight = false;
unsigned long lastLDRPrint = 0;
void setup() {
  Serial1.begin(9600);
  for (int i = 0; i < NUM_LEDS; i++) {
    pinMode(LED_PINS[i], OUTPUT);
    pulses[i].active = false;
  }
  for (int i = 0; i < MAX_WAVES; i++) {
    waves[i].active = false;
  }
  setAllOff();
  Serial1.println("System ready");
}
void loop() {
  readLDR();
  printLDRStatus();
  if (!isNight) {
    setAllOff();
    clearWaves();
    clearPulses();
    checkSerial();
    delay(100);
    return;
  }
  checkSerial();
  updateWaves();
  updatePulses();
  render();
}
void readLDR() {
  isNight = (analogRead(LDR_PIN) < LDR_NIGHT_THRESHOLD);
}
void printLDRStatus() {
  unsigned long now = millis();
  if (now - lastLDRPrint >= 1000) {
    lastLDRPrint = now;
    int v = analogRead(LDR_PIN);
    Serial1.print("LDR=");
    Serial1.print(v);
    Serial1.print(" Mode=");
    Serial1.println(isNight ? "NIGHT" : "DAY");
  }
}
void checkSerial() {
  if (!Serial1.available()) return;
  String msg = Serial1.readStringUntil('\n');
  msg.trim();
  if (msg == "WAVE" || msg == "CAR") {
    Serial1.println("car");
    if (isNight) {
      createWave();
    }
  }
}
void createWave() {
  for (int i = 0; i < MAX_WAVES; i++) {
    if (!waves[i].active) {
      waves[i].active = true;
      waves[i].currentLED = -1;
      waves[i].lastStepTime = millis() - WAVE_DELAY_MS;
      return;
    }
  }
}
void updateWaves() {
  unsigned long now = millis();
  for (int i = 0; i < MAX_WAVES; i++) {
    if (!waves[i].active) continue;
    if (now - waves[i].lastStepTime >= WAVE_DELAY_MS) {
      waves[i].lastStepTime = now;
      waves[i].currentLED++;
      if (waves[i].currentLED < NUM_LEDS) {
        triggerPulse(waves[i].currentLED);
      } else {
        waves[i].active = false;
      }
    }
  }
}
void triggerPulse(int led) {
  pulses[led].active = true;
  pulses[led].offTime = millis() + LED_PEAK_MS + LED_TAIL_MS;
}
void updatePulses() {
  unsigned long now = millis();
  for (int i = 0; i < NUM_LEDS; i++) {
    if (pulses[i].active && now >= pulses[i].offTime) {
      pulses[i].active = false;
    }
  }
}
void render() {
  bool anyPulse = false;
  for (int i = 0; i < NUM_LEDS; i++) {
    if (pulses[i].active) {
      digitalWrite(LED_PINS[i], HIGH);
      anyPulse = true;
    } else {
      digitalWrite(LED_PINS[i], LOW);
    }
  }
  if (!anyPulse) {
    nightDim();
  } else {
    mixedRender();
  }
}
void mixedRender() {
  for (int i = 0; i < NUM_LEDS; i++) {
    if (!pulses[i].active) {
      digitalWrite(LED_PINS[i], HIGH);
    }
  }
  delay(SW_PWM_ON_TIME);
  for (int i = 0; i < NUM_LEDS; i++) {
    if (!pulses[i].active) {
      digitalWrite(LED_PINS[i], LOW);
    }
  }
  delay(SW_PWM_PERIOD - SW_PWM_ON_TIME);
}
void nightDim() {
  for (int i = 0; i < NUM_LEDS; i++) {
    digitalWrite(LED_PINS[i], HIGH);
  }
  delay(SW_PWM_ON_TIME);
  for (int i = 0; i < NUM_LEDS; i++) {
    digitalWrite(LED_PINS[i], LOW);
  }
  delay(SW_PWM_PERIOD - SW_PWM_ON_TIME);
}
void clearWaves() {
  for (int i = 0; i < MAX_WAVES; i++) {
    waves[i].active = false;
  }
}
void clearPulses() {
  for (int i = 0; i < NUM_LEDS; i++) {
    pulses[i].active = false;
  }
}
void setAllOff() {
  for (int i = 0; i < NUM_LEDS; i++) {
    digitalWrite(LED_PINS[i], LOW);
  }
}
