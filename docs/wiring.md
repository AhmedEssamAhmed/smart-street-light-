# Wiring Guide — Adaptive Street Light (Arduino Uno)

## System Overview

```
┌──────────────────────────────────────────────────┐
│  ESP32-CAM                                        │
│  (Motion detection via camera)                    │
│                                                   │
│  TX (GPIO1) ──────────────→ Pin 11 (Arduino RX)  │
│  RX (GPIO3) ←────────────── (not connected)      │
│  GND        ──────────────→ GND                   │
│  5V         → external 5V supply (separate)      │
└──────────────────────────────────────────────────┘
                         │
                         │ UART (115200 baud)
                         │ "CAR" / "CLEAR"
                         ▼
┌──────────────────────────────────────────────────┐
│  Arduino Uno                                      │
│                                                   │
│  A0  ← LDR voltage divider (10kΩ + LDR)          │
│  D2..D10 → 9 LEDs (each via 220Ω → GND)          │
│  D11 ← ESP32 TX (GPIO1) via SoftwareSerial       │
│                                                    │
│  Powered via USB from laptop                      │
└──────────────────────────────────────────────────┘
```

---

## 1. LDR Circuit (Voltage Divider)

The LDR + 10kΩ resistor form a voltage divider to measure ambient light:

```
         5V  (Arduino 5V pin)
           │
          ┌┴┐
          │ │  LDR (light-dependent resistor)
          │ │
          └┬┘
           │
           ├──── A0 (analog input)
           │
          ┌┴┐
          │ │  10kΩ resistor
          │ │
          └┬┘
           │
          GND
```

### How it works:
- **Bright light** → LDR resistance low (~1kΩ) → voltage at A0 **high** (~4.5V)
- **Dark** → LDR resistance high (~1MΩ) → voltage at A0 **low** (~0.05V)

### Troubleshooting:

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Reads 1023 always | No current path to GND | Add 10kΩ resistor to GND |
| Reads 0 always | No connection to 5V or LDR upside down | Check wiring & LDR orientation |
| ADC flips opposite | LDR and resistor swapped | Swap LDR and 10kΩ positions |

### Calibration:
1. Upload code to Arduino Uno
2. Open Serial Monitor (9600 baud)
3. Cover the LDR with your hand → note the value (e.g., `500`)
4. Shine a flashlight on the LDR → note the value (e.g., `900`)
5. Set `DAY_THRESHOLD` in code to a value between them (e.g., `700`)

**Default threshold:** `2000`

> **Note:** Arduino Uno ADC is 10-bit (0–1023), while STM32 is 12-bit (0–4095).
> If you see values 0–1023, they are correct. Adjust thresholds accordingly
> (e.g., `DAY_THRESHOLD = 700` instead of 2000). The defaults in the code
> are set for the old STM32 — calibrate and update as needed.

---

## 2. ESP32-CAM → Arduino Uno (UART)

```
ESP32-CAM           Arduino Uno
─────────           ───────────
GPIO1 (TX)  ─────→  Pin 11  (SoftwareSerial RX)
GND         ─────→  GND
5V           → external 5V supply (NOT from Arduino!)
```

**Important:**
- ESP32-CAM draws ~300 mA with camera active. **Do NOT power it from the Arduino's 5V pin** (the Uno's regulator can overheat). Use a separate 5V supply or an FTDI programmer.
- Connect GNDs together (Arduino GND ↔ ESP32-CAM GND).
- The communication is **one-way** (ESP32 → Arduino). The ESP32-CAM sends `"CAR\n"` and `"CLEAR\n"` at 115200 baud.
- 3.3V from ESP32 is safe for Arduino's 5V logic input (HIGH threshold is ~2.5V).

---

## 3. LEDs (9 Channels — Software PWM)

All 9 LEDs are controlled via software PWM in the code (no hardware PWM needed).

| LED # | Arduino Pin | Resistor |
|-------|-------------|----------|
| 1     | D2          | 220Ω → GND |
| 2     | D3          | 220Ω → GND |
| 3     | D4          | 220Ω → GND |
| 4     | D5          | 220Ω → GND |
| 5     | D6          | 220Ω → GND |
| 6     | D7          | 220Ω → GND |
| 7     | D8          | 220Ω → GND |
| 8     | D9          | 220Ω → GND |
| 9     | D10         | 220Ω → GND |

Each LED: **Anode → Arduino pin**, **Cathode → 220Ω resistor → GND**.

> All 9 LEDs are dimmable (software PWM at 200 Hz). During standby they glow at
> 30% brightness; during the wave they reach 100%.

---

## 4. Power Supply

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│  Laptop USB  │──────→│  Arduino Uno │       │  ESP32-CAM   │
│  (5V)        │       │  (VIN / USB) │       │              │
│              │       │              │       │  5V pin ←─── │
└──────────────┘       └──────────────┘       │  from FTDI   │
                                               │  or ext 5V   │
                          GND ───────────────→│  GND          │
                                               └──────────────┘
```

- **Arduino Uno**: Powered via USB from laptop (provides 5V on VIN/VCC).
- **ESP32-CAM**: Powered separately via FTDI programmer or external 5V supply.
- **Common GND**: Connect Arduino GND and ESP32-CAM GND together.

---

## 5. Pin Table (Arduino Uno)

| Pin  | Connected to        | Direction |
|------|---------------------|-----------|
| A0   | LDR voltage divider | Input     |
| D2   | LED 1               | Output    |
| D3   | LED 2               | Output    |
| D4   | LED 3               | Output    |
| D5   | LED 4               | Output    |
| D6   | LED 5               | Output    |
| D7   | LED 6               | Output    |
| D8   | LED 7               | Output    |
| D9   | LED 8               | Output    |
| D10  | LED 9               | Output    |
| D11  | ESP32-CAM TX (GPIO1) | Input    |

---

## 6. Breadboard Layout (Simple Reference)

```
                     Arduino Uno
              ┌─────────────────────────┐
              │                         │
              │  USB ←── laptop power   │
              │                         │
              │  A0 ←── LDR divider     │
              │                         │
              │  D2 ──┐                 │
              │  D3 ──┤                 │
              │  D4 ──┤                 │
              │  D5 ──┤  9 LEDs via     │
              │  D6 ──┤  220Ω each      │
              │  D7 ──┤  to GND         │
              │  D8 ──┤                 │
              │  D9 ──┤                 │
              │  D10 ─┘                 │
              │                         │
              │  D11 ←── ESP32 TX       │
              │  GND ←── ESP32 GND      │
              └─────────────────────────┘
```

---

## 7. LDR Threshold Notes (Uno vs STM32)

The previous version used an STM32 with a **12-bit ADC** (0–4095). The Arduino Uno has a **10-bit ADC** (0–1023). All threshold values in the code must be scaled:

| Parameter    | STM32 (old) | Arduino Uno |
|-------------|------------|-------------|
| ADC range   | 0–4095     | 0–1023      |
| Bright (day)| ~3000–4000 | ~750–1023   |
| Dark (night)| ~500–1000  | ~125–250    |

**Update the thresholds in** `adaptive_street_light.ino` **after calibration.**
