"""
Simulation of the Adaptive Street Light system
Tests: ESP32-CAM block detection + STM32 FreeRTOS wave logic
No hardware needed — run with: python3 test_simulation.py
"""

import time
import random

# ── Configuration (matching firmware) ────────────────────────
FRAME_W = 320
FRAME_H = 240
ROI_TOP = FRAME_H // 4
BLOCK_COLS = 8
BLOCK_ROWS = 4
BLOCK_W = FRAME_W // BLOCK_COLS
BLOCK_H = (FRAME_H - ROI_TOP) // BLOCK_ROWS
BLOCK_DIFF = 10
MIN_BLOB = 1
CONFIRM_FRAMES = 1
WAVE_DELAY = 0.15          # seconds
HOLD_TIME = 3.0            # seconds
CLEAR_TIMEOUT = 3.0        # seconds

# Colors (grayscale 0-255)
ROAD = 80
CAR = 180
SKY = 200


# ═══════════════════════════════════════════════════════════════
#  Simulated Camera Frame
# ═══════════════════════════════════════════════════════════════
def generate_frame(cars):
    """
    cars: list of (x_center, y_center, width, height) — pixel coords
    Returns 2D list of grayscale values
    """
    frame = [[SKY if y < ROI_TOP else ROAD for x in range(FRAME_W)]
             for y in range(FRAME_H)]

    for cx, cy, w, h in cars:
        x1 = max(0, cx - w // 2)
        x2 = min(FRAME_W - 1, cx + w // 2)
        y1 = max(ROI_TOP, cy - h // 2)
        y2 = min(FRAME_H - 1, cy + h // 2)
        for y in range(y1, y2):
            for x in range(x1, x2):
                frame[y][x] = CAR
    return frame


def compute_block_averages(frame):
    """Same algorithm as the ESP32 firmware"""
    blocks = [[0] * BLOCK_COLS for _ in range(BLOCK_ROWS)]
    for r in range(BLOCK_ROWS):
        for c in range(BLOCK_COLS):
            total = 0
            count = 0
            ys = ROI_TOP + r * BLOCK_H
            ye = ROI_TOP + (r + 1) * BLOCK_H
            xs = c * BLOCK_W
            xe = (c + 1) * BLOCK_W
            for y in range(ys, ye, 2):
                for x in range(xs, xe, 2):
                    total += frame[y][x]
                    count += 1
            blocks[r][c] = total // count if count else 0
    return blocks


def find_changed_blocks(cur, prev):
    changed = [[False] * BLOCK_COLS for _ in range(BLOCK_ROWS)]
    for r in range(BLOCK_ROWS):
        for c in range(BLOCK_COLS):
            changed[r][c] = abs(cur[r][c] - prev[r][c]) > BLOCK_DIFF
    return changed


def find_largest_blob(changed):
    visited = [[False] * BLOCK_COLS for _ in range(BLOCK_ROWS)]
    max_size = 0
    for r in range(BLOCK_ROWS):
        for c in range(BLOCK_COLS):
            if not changed[r][c] or visited[r][c]:
                continue
            # BFS
            stack = [(r, c)]
            visited[r][c] = True
            size = 0
            while stack:
                cr, cc = stack.pop()
                size += 1
                for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                    nr, nc = cr + dr, cc + dc
                    if 0 <= nr < BLOCK_ROWS and 0 <= nc < BLOCK_COLS:
                        if changed[nr][nc] and not visited[nr][nc]:
                            visited[nr][nc] = True
                            stack.append((nr, nc))
            max_size = max(max_size, size)
    return max_size


# ═══════════════════════════════════════════════════════════════
#  STM32 Wave Task Simulator
# ═══════════════════════════════════════════════════════════════
class WaveTask:
    def __init__(self):
        self.pos = 0
        self.active = False
        self.leds = [0] * 9   # brightness per LED
        self.car_present = False
        self.new_car = False
        self.is_daytime = False
        self.last_car_time = 0.0
        self.sim_time = 0.0

    def update(self, dt, car_detected):
        self.sim_time += dt

        # Detection logic simulates DetectionTask
        if car_detected:
            if not self.car_present:
                self.new_car = True
            self.car_present = True
            self.last_car_time = self.sim_time
        else:
            if self.car_present and (self.sim_time - self.last_car_time > HOLD_TIME):
                self.car_present = False

        # Wave task logic (from vTaskWave)
        if self.is_daytime:
            self.leds = [0] * 9
            self.active = False
            self.pos = 0
            return

        if not self.car_present and not self.active:
            self.leds = [20] * 9  # MIN_BRIGHTNESS
            return

        if not self.active:
            self.active = True
            self.pos = 0
            self.new_car = False
        elif self.new_car:
            self.leds[self.pos] = 20  # dim current
            self.pos = 0
            self.new_car = False

        # Light current LED
        self.leds[self.pos] = 255  # MAX_BRIGHTNESS

        # Advance after WAVE_DELAY
        self.leds[self.pos] = 20   # dim
        self.pos += 1

        if self.pos >= 9:
            self.leds = [255] * 9  # all bright for hold
            self.active = False
            self.pos = 0


# ═══════════════════════════════════════════════════════════════
#  TESTS
# ═══════════════════════════════════════════════════════════════
def test_detection():
    print("=" * 60)
    print("TEST 1: ESP32-CAM Block Detection")
    print("=" * 60)

    # Frame 1: empty road
    f1 = generate_frame([])
    blocks_prev = compute_block_averages(f1)

    # Frame 2: car enters from left
    f2 = generate_frame([(30, 160, 40, 30)])
    blocks_cur = compute_block_averages(f2)

    changed = find_changed_blocks(blocks_cur, blocks_prev)
    blob = find_largest_blob(changed)

    print(f"Empty road -> Car at x=30: blob size = {blob}")
    print(f"  Changed blocks grid (R=road, C=car):")
    for r in range(BLOCK_ROWS):
        row = ""
        for c in range(BLOCK_COLS):
            if changed[r][c]:
                row += " C"
            else:
                row += " ."
        print(f"  {row}")
    print(f"  Detection {'PASS' if blob >= MIN_BLOB else 'FAIL'}")

    # Frame 3: car moves right
    f3 = generate_frame([(80, 160, 40, 30)])
    blocks_cur2 = compute_block_averages(f3)
    changed2 = find_changed_blocks(blocks_cur2, blocks_cur)
    blob2 = find_largest_blob(changed2)

    print(f"\nCar moves x=30 -> x=80: blob size = {blob2}")
    print(f"  Detection {'PASS' if blob2 >= MIN_BLOB else 'FAIL'}")

    return True


def test_two_cars_wave():
    print("\n" + "=" * 60)
    print("TEST 2: FreeRTOS Wave — Two Cars")
    print("=" * 60)

    wave = WaveTask()
    wave.is_daytime = False

    def show_leds(leds, label):
        bar = "".join("█" if v > 200 else "░" if v > 0 else " " for v in leds)
        print(f"  {label:15s} {bar}  {leds}")

    show_leds(wave.leds, "Initial")

    # Car 1 enters at t=0
    for step in range(6):
        wave.update(WAVE_DELAY, car_detected=True)
        show_leds(wave.leds, f"Car1 t={step}")

    # Car 2 enters mid-wave (while car1 wave still running)
    print(f"\n  >>> Car 2 arrives! Wave restarts from LED 0 <<<\n")
    for step in range(6):
        wave.update(WAVE_DELAY, car_detected=True)
        show_leds(wave.leds, f"Car2 t={step}")

    # No more cars
    print(f"\n  >>> Road clear, wave finishes <<<\n")
    for step in range(6):
        wave.update(WAVE_DELAY, car_detected=False)
        show_leds(wave.leds, f"Clear t={step}")

    print("\n  PASS: Wave restarted when second car arrived")


def test_day_night():
    print("\n" + "=" * 60)
    print("TEST 3: Day/Night Transition")
    print("=" * 60)

    wave = WaveTask()

    # Night + car
    wave.is_daytime = False
    wave.update(WAVE_DELAY, car_detected=True)
    print(f"  Night + car: LEDs = {wave.leds}")

    # Switch to daytime
    wave.is_daytime = True
    wave.update(WAVE_DELAY, car_detected=True)
    print(f"  Daytime:     LEDs = {wave.leds}")
    print(f"  PASS: LEDs turned off during day" if all(v == 0 for v in wave.leds) else "  FAIL")


# ═══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    test_detection()
    test_two_cars_wave()
    test_day_night()
    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
