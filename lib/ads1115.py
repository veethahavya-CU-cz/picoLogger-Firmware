from machine import I2C
import time

class ADS1115:
    """
    MicroPython ADS1115 driver class.

    Supports:
    - 4 single-ended inputs (CH0–CH3)
    - Programmable gain amplifier (±6.144V to ±0.256V)
    - Sample rates from 8 SPS to 860 SPS
    - Single-shot or continuous mode
    - Raw ADC and voltage readings
    """

    # --- Registers ---
    REG_CONVERT = 0x00     # Conversion register (read ADC result)
    REG_CONFIG = 0x01      # Configuration register

    # --- Input Multiplexers (single-ended) ---
    CH0 = 0x4000  # AIN0
    CH1 = 0x5000  # AIN1
    CH2 = 0x6000  # AIN2
    CH3 = 0x7000  # AIN3
    CHANNELS = [CH0, CH1, CH2, CH3]

    # --- Gains: (value, voltage_range)
    GAIN_6_144V = (0x0000, 6.144)  # ±6.144 V
    GAIN_4_096V = (0x0200, 4.096)  # ±4.096 V
    GAIN_2_048V = (0x0400, 2.048)  # ±2.048 V (default)
    GAIN_1_024V = (0x0600, 1.024)  # ±1.024 V
    GAIN_0_512V = (0x0800, 0.512)  # ±0.512 V
    GAIN_0_256V = (0x0A00, 0.256)  # ±0.256 V

    # --- Data Rates (samples per second) ---
    DR_8SPS   = 0x0000
    DR_16SPS  = 0x0020
    DR_32SPS  = 0x0040
    DR_64SPS  = 0x0060
    DR_128SPS = 0x0080  # Default
    DR_250SPS = 0x00A0
    DR_475SPS = 0x00C0
    DR_860SPS = 0x00E0

    # --- Conversion modes ---
    MODE_CONTINUOUS = 0x0000
    MODE_SINGLESHOT = 0x0100  # Default

    def __init__(self, i2c: I2C, addr=0x48):
        """
        Initialize ADS1115 object.

        :param i2c: I2C instance
        :param addr: I2C address of the ADS1115 (default 0x48)
        """
        self.i2c = i2c
        self.addr = addr
        self.set_gain(self.GAIN_2_048V)
        self.set_mode(self.MODE_SINGLESHOT)
        self.set_datarate(self.DR_128SPS)

    def set_gain(self, gain_tuple):
        """
        Set gain and voltage reference.

        :param gain_tuple: One of the GAIN_* constants
        """
        self.gain, self.vref = gain_tuple

    def set_mode(self, mode):
        """
        Set ADC operating mode.

        :param mode: MODE_CONTINUOUS or MODE_SINGLESHOT
        """
        self.mode = mode

    def set_datarate(self, dr):
        """
        Set ADC sample rate.

        :param dr: One of the DR_* constants
        """
        self.datarate = dr

    def _write_config(self, chan):
        """
        Build and write config register to start ADC conversion.
        """
        config = 0x8000  # OS=1: start single conversion
        config |= chan | self.gain | self.mode | self.datarate | 0x0003  # disable comparator
        self.i2c.writeto_mem(self.addr, self.REG_CONFIG, config.to_bytes(2, 'big'))

    def _wait_conversion(self):
        """
        Wait for conversion to complete (only for single-shot mode).
        """
        while True:
            conf = int.from_bytes(self.i2c.readfrom_mem(self.addr, self.REG_CONFIG, 2), 'big')
            if conf & 0x8000:
                break
            time.sleep_ms(1)

    def _read_raw(self):
        """
        Read 16-bit signed ADC result.
        """
        data = self.i2c.readfrom_mem(self.addr, self.REG_CONVERT, 2)
        val = int.from_bytes(data, 'big')
        return val - 0x10000 if val > 0x7FFF else val

    def read_raw(self, channel=0):
        """
        Read raw ADC value from a specified channel.

        :param channel: 0–3 for AIN0–AIN3
        :return: 16-bit signed integer
        """
        self._write_config(self.CHANNELS[channel])
        if self.mode == self.MODE_SINGLESHOT:
            self._wait_conversion()
        return self._read_raw()

    def read_voltage(self, channel=0):
        """
        Read voltage from specified channel.

        :param channel: 0–3 for AIN0–AIN3
        :return: Voltage in float
        """
        raw = self.read_raw(channel)
        return round(raw * self.vref / 32768, 4)

    def read_all(self):
        """
        Read voltages from all 4 channels (CH0–CH3).

        :return: List of 4 voltages in volts
        """
        return [self.read_voltage(i) for i in range(4)]
