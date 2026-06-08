"""
GUI simulation — Adaptive Street Light
9 LEDs that light up in real-time. Exactly matches firmware logic.

Run:  python3 led_sim_gui.py
"""

import tkinter as tk
import time

WAVE_DELAY = 0.3
MIN_BRIGHTNESS = 20
MAX_BRIGHTNESS = 255


class Light:
    """Matches firmware vTaskWave logic exactly"""
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

    def step(self, car_now):
        self.t += WAVE_DELAY
        self.car = car_now

        if self.day:
            self.leds = [0] * 9
            self.active = False
            self.pos = 0
            return

        if not self.car and not self.active:
            self.leds = [MIN_BRIGHTNESS] * 9
            return

        if not self.active:
            self.active = True
            self.pos = 0
            self.new_car = False
        elif self.new_car:
            if self.pos > 0:
                self.leds[self.pos - 1] = MIN_BRIGHTNESS
            self.pos = 0
            self.new_car = False

        if self.pos > 0:
            self.leds[self.pos - 1] = MIN_BRIGHTNESS
        self.leds[self.pos] = MAX_BRIGHTNESS
        self.pos += 1

        if self.pos >= 9:
            self.leds = [MAX_BRIGHTNESS] * 9
            self.holding = True
            self.hold_t = self.t + 0.8

    def hold_tick(self):
        if not self.holding:
            return False
        if self.new_car:
            self.holding = False
            self.pos = 0
            self.new_car = False
            return True
        self.t += 0.05
        if self.t >= self.hold_t:
            self.leds = [MIN_BRIGHTNESS] * 9
            self.active = False
            self.pos = 0
            self.holding = False
        return False


class LEDSimGUI:
    BG = '#1a1a2e'
    LED_ON = '#ffd700'
    LED_DIM = '#443300'
    LED_OFF = '#222222'
    GLOW_ON = '#ffaa00'
    GLOW_DIM = '#1a0f00'
    WHITE = '#ffffff'
    GRAY = '#aaaaaa'
    DGRAY = '#555555'
    GREEN = '#00cc66'

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Adaptive Street Light - Simulation")
        self.root.configure(bg=self.BG)
        self.root.resizable(False, False)

        self.light = Light()
        self.step_n = 0
        self.running = True
        self.paused = False
        self.speed = 1.0

        # Scenario: (steps, car, label, newcar)
        self.scenario = [
            (5,  False, "",                          False),
            (1,  True,  ">>> CAR 1 ENTERS <<<",     False),
            (5,  True,  "",                          False),
            (1,  True,  ">>> CAR 2 mid-wave! RESTART! <<<", True),
            (5,  True,  "",                          False),
            (1,  False, ">>> Road clear <<<",        False),
            (9,  False, "",                          False),
            (1,  False, ">>> DAYTIME <<<",           False),
            (4,  False, "",                          False),
            (1,  False, ">>> NIGHT <<<",             False),
            (3,  False, "",                          False),
        ]
        self.scene_i = 0
        self.scene_n = 0

        self._build_ui()
        self.root.after(100, self.tick)
        self.root.mainloop()

    def _build_ui(self):
        # Title
        tk.Label(self.root, text="Adaptive Street Light",
                 font=('Arial', 18, 'bold'), fg=self.WHITE, bg=self.BG
                 ).pack(pady=(20, 5))

        # Status
        self.status_var = tk.StringVar(value="NIGHT  |  ---  |  IDLE")
        tk.Label(self.root, textvariable=self.status_var,
                 font=('Arial', 14), fg=self.WHITE, bg=self.BG
                 ).pack(pady=(0, 10))

        # LED frame
        led_frame = tk.Frame(self.root, bg=self.BG)
        led_frame.pack(pady=10)

        self.led_canvases = []
        self.led_circles = []
        r = 28
        for i in range(9):
            c = tk.Canvas(led_frame, width=70, height=80,
                          bg=self.BG, highlightthickness=0)
            c.pack(side=tk.LEFT, padx=5)

            # Outer glow
            glow = c.create_oval(70//2-r-12, 80//2-r-12,
                                 70//2+r+12, 80//2+r+12,
                                 fill=self.BG, outline='')
            # LED body
            led = c.create_oval(70//2-r, 80//2-r,
                                70//2+r, 80//2+r,
                                fill=self.LED_OFF, outline=self.DGRAY, width=2)
            # Number
            c.create_text(70//2, 75, text=str(i+1),
                          fill=self.GRAY, font=('Arial', 9))

            self.led_canvases.append(c)
            self.led_circles.append((glow, led))

        # Label
        self.label_var = tk.StringVar()
        lbl = tk.Label(self.root, textvariable=self.label_var,
                       font=('Arial', 13, 'bold'), fg=self.GREEN,
                       bg=self.BG)
        lbl.pack(pady=(5, 15))

        # Info
        self.info_var = tk.StringVar(value="Step: 0")
        tk.Label(self.root, textvariable=self.info_var,
                 font=('Arial', 10), fg=self.GRAY, bg=self.BG
                 ).pack()

        # Controls
        ctrl = tk.Frame(self.root, bg=self.BG)
        ctrl.pack(pady=(15, 5))

        self.pause_btn = tk.Button(ctrl, text="Pause", command=self.toggle_pause,
                                   bg='#0f3460', fg='#fff', font=('Arial', 10),
                                   padx=12, relief=tk.FLAT, cursor='hand2')
        self.pause_btn.pack(side=tk.LEFT, padx=4)

        tk.Button(ctrl, text="Reset", command=self.reset,
                  bg='#555', fg='#fff', font=('Arial', 10),
                  padx=10, relief=tk.FLAT, cursor='hand2'
                  ).pack(side=tk.LEFT, padx=4)

        tk.Label(ctrl, text="Speed:", fg=self.GRAY, bg=self.BG,
                 font=('Arial', 10)).pack(side=tk.LEFT, padx=(15, 2))
        self.speed_var = tk.DoubleVar(value=1.0)
        tk.Scale(ctrl, from_=0.25, to=3.0, resolution=0.25,
                 orient=tk.HORIZONTAL, variable=self.speed_var,
                 bg=self.BG, fg=self.WHITE, troughcolor='#333',
                 highlightbackground=self.BG, length=80,
                 font=('Arial', 8)).pack(side=tk.LEFT)

        # Hint
        tk.Label(self.root, text="[Pause]  [Reset]  [Speed slider]",
                 font=('Arial', 9), fg=self.DGRAY, bg=self.BG
                 ).pack(pady=(5, 15))

    def _update_leds(self):
        for i, (glow, led) in enumerate(self.led_circles):
            v = self.light.leds[i]
            if v >= 200:
                fill = self.LED_ON
                glow_c = self.GLOW_ON
            elif v >= 15:
                fill = self.LED_DIM
                glow_c = self.GLOW_DIM
            else:
                fill = self.LED_OFF
                glow_c = self.BG
            self.led_canvases[i].itemconfig(led, fill=fill)
            self.led_canvases[i].itemconfig(glow, fill=glow_c)

    def _update_text(self, label):
        st = "DAY" if self.light.day else "NIGHT"
        ca = "CAR" if self.light.car else "---"
        wa = "WAVE" if self.light.active else "IDLE"
        ho = " HOLD" if self.light.holding else ""
        self.status_var.set(f"{st}  |  {ca}  |  {wa}{ho}")
        self.info_var.set(f"Step: {self.step_n}")
        is_event = ">>>" in label
        self.label_var.set(label)
        fg = self.GREEN if is_event else self.GRAY
        self.root.children['!label'].configure(fg=fg)

    def toggle_pause(self):
        self.paused = not self.paused
        self.pause_btn.config(text="Run" if self.paused else "Pause")

    def reset(self):
        self.light = Light()
        self.step_n = 0
        self.scene_i = 0
        self.scene_n = 0
        self._update_leds()
        self.status_var.set("NIGHT  |  ---  |  IDLE")
        self.label_var.set("")
        self.info_var.set("Step: 0")

    def tick(self):
        if self.paused:
            self.root.after(50, self.tick)
            return

        if self.scene_i < len(self.scenario):
            n, car, lbl, newcar = self.scenario[self.scene_i]

            if newcar and self.scene_n == 0:
                self.light.new_car = True
            if "DAYTIME" in lbl:
                self.light.day = True
                self.light.car = False
            elif "NIGHT" in lbl:
                self.light.day = False

            if self.light.holding:
                for _ in range(20):
                    self.light.hold_tick()

            self.light.step(car)
            self._update_leds()
            self._update_text(lbl if self.scene_n == 0 else "")
            self.step_n += 1

            self.scene_n += 1
            if self.scene_n >= n:
                self.scene_i += 1
                self.scene_n = 0
        else:
            self.label_var.set("Simulation complete - press Reset")
            self.root.after(500, self.tick)
            return

        delay = int(WAVE_DELAY * 1000 / self.speed_var.get())
        self.root.after(delay, self.tick)


if __name__ == "__main__":
    LEDSimGUI()
