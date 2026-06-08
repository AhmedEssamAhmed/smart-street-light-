# Smart Adaptive Street Lighting System

## Project Structure

```
adaptive_street_light/
├── README.md
├── arduino_firmware/
│   └── adaptive_street_light/
│       └── adaptive_street_light.ino   # Arduino Uno (main controller)
├── esp32_cam_firmware/
│   └── esp32_cam_motion/
│       └── esp32_cam_motion.ino        # ESP32-CAM car detector
├── stm32_firmware/                     # (previous version — archived)
│   └── adaptive_street_light/
│       └── adaptive_street_light.ino
├── docs/
│   └── wiring.md                       # Full wiring diagrams & LDR fix
├── animate_leds.py
├── led_sim_gui.py
└── test_simulation.py
```

## How It Works

```
         ┌──────────────┐     "CAR\n" / "CLEAR\n"    ┌──────────────┐
         │  ESP32-CAM   │ ──────────────────────────→ │  Arduino Uno │
         │  (camera +    │    UART @ 115200 baud       │  (main μC)   │
         │   motion      │                             │              │
         │   detection)  │                             │  A0 ← LDR   │
         └──────────────┘                             │  D2-D10 → 9 LEDs │
                                                      └──────────────┘
```

1. **LDR** detects day/night (LEDs off during day, dim 30% glow at night)
2. **ESP32-CAM** captures frames at ~12 FPS, detects motion using block-based differencing
3. When motion is detected, ESP32-CAM sends `"CAR\n"` via UART to Arduino
4. **Arduino Uno** starts the wave animation (LEDs turn on one by one, 150 ms apart)
5. All 9 LEDs stay at 100% while the car passes
6. When no motion for 3 seconds (or `"CLEAR\n"` received), LEDs return to 30% dim
7. If a second car arrives mid-wave → the wave restarts immediately

**Note:** All 9 LEDs are dimmable via **software PWM** (200 Hz). No hardware PWM pins needed.

## Flashing Instructions

### Arduino Uno
- Open `arduino_firmware/adaptive_street_light/adaptive_street_light.ino` in Arduino IDE
- Board: `Arduino Uno`
- Port: Select the correct COM port
- Click Upload

### ESP32-CAM
- Open `esp32_cam_firmware/esp32_cam_motion/esp32_cam_motion.ino` in Arduino IDE
- Board: `AI Thinker ESP32-CAM`
- Partition Scheme: `Huge APP (3MB No OTA)` or `Minimal SPIFFS`
- **Important:** Connect GPIO0 to GND during upload, remove after upload
- Click Upload

## LDR Calibration

Open Serial Monitor at **9600 baud** after uploading Arduino code. You'll see:

```
LDR: 512  State:NIGHT_IDLE  Car:0
LDR: 890  State:DAY  Car:0
```

- **Dark** (cover LDR): ~100–300 (10-bit ADC)
- **Bright** (flashlight): ~750–1023
- Set `DAY_THRESHOLD` in the Arduino code to a value between them

**Important:** Arduino Uno has a 10-bit ADC (0–1023), unlike the previous STM32's 12-bit ADC (0–4095). Adjust all thresholds accordingly.

See `docs/wiring.md` for the LDR voltage divider circuit.

## Team

- Ahmed Essam (221004518)
- Mohammed Moatasem (221006382)
- Ahmed Khaled (221005429)

Supervised by Dr. Amr Fahmy — AAST, Computer Engineering
