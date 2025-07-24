"""
# sLED.py - A simple class to control a status LED using PWM.
# Author: veethahavya_cu-cz
"""
from machine import Pin, PWM
from time import sleep_ms as pause_ms

class sLED:
    STATUS, MSG = None, None

    RED = (1.00, 0.00, 0.00)
    GREEN = (0.00, 1.00, 0.00)
    BLUE = (0.00, 0.00, 1.00)
    WHITE = (1.00, 0.80, 0.75)
    YELLOW = (1.00, 0.33, 0.00)
    CYAN = (0.00, 0.90, 0.75)
    MAGENTA = (1.00, 0.00, 1.00)

    def __init__(self, R, G, B, n_flash=3, on_ms=125, off_ms=75):
        self.R = PWM(Pin(R))
        self.G = PWM(Pin(G))
        self.B = PWM(Pin(B))
        self.n_flash = n_flash
        self.on_ms = on_ms
        self.off_ms = off_ms
        for ch in (self.R, self.G, self.B):
            ch.freq(1000)
        self.off()
        self.STATUS, self.MSG = True, "Status LED initialized successfully."

    def _set_pwm(self, r, g, b):
        self.R.duty_u16(int(65535 * r))
        self.G.duty_u16(int(65535 * g))
        self.B.duty_u16(int(65535 * b))

    def _set_color(self, color):
        color = color.lower()
        if color == 'red':
            vals = self.RED
        elif color == 'green':
            vals = self.GREEN
        elif color == 'blue':
            vals = self.BLUE
        elif color == 'white':
            vals = self.WHITE
        elif color == 'yellow':
            vals = self.YELLOW
        elif color == 'cyan':
            vals = self.CYAN
        elif color == 'magenta':
            vals = self.MAGENTA
        else:
            raise ValueError("Unknown color: {}".format(color))
        self._set_pwm(*vals)

    def on(self, color):
        self._set_color(color)

    def off(self):
        self._set_pwm(0.0, 0.0, 0.0)

    def flash(self, color):
        for _ in range(self.n_flash):
            self.on(color)
            pause_ms(self.on_ms)
            self.off()
            pause_ms(self.off_ms)
        self.off()
    
    def dual_flash(self, color1, color2):
        for _ in range(self.n_flash):
            self.on(color1)
            pause_ms(self.on_ms)
            self.on(color2)
            pause_ms(self.on_ms)
        self.off()

    def update(self, n_flash=None, on_ms=None, off_ms=None):
        if n_flash is not None:
            self.n_flash = n_flash
        if on_ms is not None:
            self.on_ms = on_ms
        if off_ms is not None:
            self.off_ms = off_ms