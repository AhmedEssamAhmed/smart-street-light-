"""
Firmware-accurate animated simulation.
LED[pos]=MAX, then after 150ms LED[pos]=MIN, pos++.
Result: ONE bright LED moves across at any moment.

Run:  python3 animate_leds.py
"""

import time
import sys

W = 0.3
MIN = 20
MAX = 255


class Light:
    def __init__(self):
        self.leds = [20] * 9
        self.pos = 0
        self.active = False
        self.car = False
        self.new_car = False
        self.holding = False
        self.hold_t = 0.0
        self.t = 0.0
        self.day = False

    def show(self):
        bar = "".join(chr(9608) if v >= 200 else chr(9617) if v >= 15 else ' ' for v in self.leds)
        st = "DAY" if self.day else "NIGHT"
        ca = "CAR" if self.car else "---"
        wa = f"W:{self.pos}" if self.active else "IDLE"
        h = " HOLD" if self.holding else ""
        return f"[{bar}] {st} {ca} {wa}{h}"

    def step(self, car_now):
        """Each call = one complete wave iteration (light + delay + dim + advance)"""
        self.t += W
        self.car = car_now

        if self.day:
            self.leds = [0] * 9
            self.active = False
            self.pos = 0
            return

        if not self.car and not self.active:
            self.leds = [MIN] * 9
            return

        # Start or restart
        if not self.active:
            self.active = True
            self.pos = 0
            self.new_car = False
        elif self.new_car:
            if self.pos > 0:
                self.leds[self.pos - 1] = MIN  # dim the one that was lit
            self.pos = 0
            self.new_car = False

        # Light current — this stays bright for the render
        if self.pos > 0:
            self.leds[self.pos - 1] = MIN  # dim the one lit last iteration
        self.leds[self.pos] = MAX
        self.pos += 1

        if self.pos >= 9:
            self.leds = [MAX] * 9
            self.holding = True
            self.hold_t = self.t + 0.8

    def hold_tick(self):
        """Simulates one vTaskDelay(50) tick inside the hold loop"""
        if not self.holding:
            return False
        if self.new_car:
            self.holding = False
            self.pos = 0
            self.new_car = False
            return True
        self.t += 0.05
        if self.t >= self.hold_t:
            self.leds = [MIN] * 9
            self.active = False
            self.pos = 0
            self.holding = False
        return False


# ── Scenario ────────────────────────────────────────────────
# Each: (steps, car, label, trigger_newcar)
scenario = []
# Phase 1: dim glow
scenario += [(5, False, "", False)]
# Phase 2: car 1 enters
scenario += [(1, True, ">>> CAR 1 enters <<<", False)]
scenario += [(5, True, "", False)]          # wave at LED 4 (mid-way)
# Phase 3: car 2 arrives mid-wave!
scenario += [(1, True, ">>> CAR 2 mid-wave! Wave restarts! <<<", True)]
scenario += [(5, True, "", False)]          # wave restarts, runs to LED 4
# Phase 4: cars gone
scenario += [(1, False, ">>> Road clear <<<", False)]
scenario += [(9, False, "", False)]         # wave finishes, then dim glow
# Phase 5: daytime
scenario += [(1, False, ">>> DAYTIME <<<", False)]
scenario += [(5, False, "", False)]
# Phase 6: night again
scenario += [(1, False, ">>> NIGHT <<<", False)]
scenario += [(3, False, "", False)]


light = Light()
sno = 0

print()
print("  ADAPTIVE STREET LIGHT — Firmware-Accurate")
print("  " + chr(9608) * 50)
print("  " + chr(9608) + "=full  " + chr(9617) + "=dim  (space)=off")
print()

try:
    for n, car, label, trigger_nc in scenario:
        for i in range(n):
            if trigger_nc and i == 0:
                light.new_car = True

            if "DAYTIME" in label:
                light.day = True
            elif "NIGHT" in label:
                light.day = False

            if light.holding:
                for _ in range(20):
                    light.hold_tick()

            light.step(car)

            lbl = label if i == 0 else ""
            sys.stdout.write("\033[2K\033[1G")
            sys.stdout.write(f"  {sno:3d}  {light.show()}  {lbl}")
            sys.stdout.flush()

            sno += 1
            time.sleep(W * 0.7)

except KeyboardInterrupt:
    pass

print()
print("  Done.")
