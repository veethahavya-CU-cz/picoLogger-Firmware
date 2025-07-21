from micropython import const
from machine import Pin, ADC, PWM
from machine import SPI, I2C
from machine import UART
from machine import RTC as iRTC
from machine import reset, reset_cause
from machine import lightsleep, deepsleep
from machine import unique_id
from uos import mount, umount, mkdir
from uos import VfsFat
from utime import localtime, ticks_ms, ticks_diff
from utime import sleep_ms as pause_ms

from os import path, remove
from datetime import datetime, timedelta

from ujson import load as load_json, dump as dump_json

from sdcard import SDCard
from ds3231 import DS3231
from ads1115 import ADS1115
from onewire import OneWire
from ds18x20 import DS18X20


# --- Constants ---
DEEPSLEEP_RESET = const(3)  # Value of `machine.reset_cause()` for wake from `machine.deepsleep()`
HARD_RESET = const(1) # Value of `machine.reset_cause()` for wake from `machine.reset()` or HW-RST or via Power Interrupt

# --- Core Classes: IO ---

class _Logger_:
    STATUS, MSG = None, None
    levels = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3, 'CRITICAL': 4}
    default_log_path = '/stray.log'

    def __init__(self, path, level, uart_cnf=None, rewrite=False, **kwargs):
        """
        Initialize the logger

        Args:
            path (str): 
                The path to the log file.
            level (Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']): 
                The logging level to use. Defaults to 'INFO'.
            uart_cnf (dict, optional):
                A dict containing UART configuration; keys: [ID, BAUDRATE, TX, RX]. Defaults to None.
            rewrite (bool, optional):
                Whether to rewrite the log file if it exists. Defaults to False.
        """

        self.path = path
        self.level = level
        if rewrite and self.path != self.default_log_path:
            open(path, 'w').close()
        if uart_cnf:
            self.uart_obj = UART(uart_cnf['id'],
                                 tx=Pin(uart_cnf.get('tx', 0)),
                                 rx=Pin(uart_cnf.get('rx', 1)),
                                 baudrate=uart_cnf.get('baudrate', 9600))
        else:
            self.uart_obj = None
    
    def __get_str_time(self):
        t = localtime()
        return "{:04d}-{:02d}-{:02d} {:02d}:{:02d}:{:02d}".format(t[0], t[1], t[2], t[3], t[4], t[5])

    def __copy_logfile(self, src, dst, rm_src=False):
        try:
            with open(src, 'r') as f_src, open(dst, 'a') as f_dst:
                while True:
                    chunk = f_src.read(256)
                    if not chunk:
                        break
                    f_dst.write(chunk)
            if rm_src:
                remove(src)
            self.debug("Log file content moved from {} to {}".format(src, dst))
            return True, "Log file copied from {} to {}".format(src, dst)
        except Exception as e:
            self.error("Failed to copy log file: {}".format(str(e)))
            return False, "Failed to copy log file: {}".format(str(e))
        
    def __write_msg(self, slevel, msg):
        if self.levels[self.level] <= self.levels[slevel]:
            formatted_msg = "[{}] {} :: {}\n".format(slevel, self.__get_str_time(), msg)
            try:
                with open(self.path, 'a') as f:
                    f.write(formatted_msg)
            except Exception as e:
                # If logging to the primary path fails, write to the default path
                formatted_msg_err = "[ERROR] {} :: FAILED TO WRITE TO {}: {}. Original message: {}\n".format(
                    self.__get_str_time(), self.path, str(e), msg)
                with open(self.default_log_path, 'a') as f:
                    f.write(formatted_msg_err)
            
            if self.uart_obj:
                self.uart_obj.write(formatted_msg)


    def debug(self, msg): self.__write_msg('DEBUG', msg)
    def info(self, msg): self.__write_msg('INFO', msg)
    def warning(self, msg): self.__write_msg('WARNING', msg)
    def error(self, msg): self.__write_msg('ERROR', msg)
    def critical(self, msg): self.__write_msg('CRITICAL', msg)

    def update_config(self, path=None, level=None, uart_cnf=None, rewrite=False, **kwargs):
        """
        Update the logger configuration.

        Args:
            path (str, optional):
                The new path to the log file. Defaults to None.
            level (Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], optional):
                The new logging level. Defaults to None.
            uart_cnf (dict, optional):
                A dict containing UART configuration with keys: ['id', 'baudrate', 'tx', 'rx']. Defaults to None.
        """
        if path:
            STATUS, MSG = self.__copy_logfile(self.path, path, rm_src=True)
            if not STATUS:
                self.error(MSG)
                self.warning("Failed to copy log file, all future logs will be written to '{}' without copying old records.".format(path))
            self.path = path
        if level:
            self.level = level
        if rewrite:
            open(self.path, 'w').close()
        if uart_cnf:
            self.uart_obj = UART(uart_cnf['id'],
                                 tx=Pin(uart_cnf.get('tx', 0)),
                                 rx=Pin(uart_cnf.get('rx', 1)),
                                 baudrate=uart_cnf.get('baudrate', 9600))

class _sLED_:
    STATUS, MSG = None, None

    COLORS = {
        'red':     (1.00, 0.00, 0.00),
        'green':   (0.00, 1.00, 0.00),
        'blue':    (0.00, 0.00, 1.00),
        'white':   (1.00, 0.80, 0.75),
        'yellow':  (1.00, 0.33, 0.00),
        'cyan':    (0.00, 0.90, 0.75),
        'magenta': (1.00, 0.00, 1.00),
        'dim-red': (0.20, 0.00, 0.00),
        'orange':  (1.00, 0.12, 0.00),
        'off':     (0.00, 0.00, 0.00),
    }

    def __init__(self, R=20, G=19, B=18):
        self.R = PWM(Pin(R))
        self.G = PWM(Pin(G))
        self.B = PWM(Pin(B))
        for ch in (self.R, self.G, self.B):
            ch.freq(1000)
        self.off()
        self.STATUS, self.MSG = True, "Status LED initialized successfully."

    def _set_pwm(self, r, g, b):
        self.R.duty_u16(int(65535 * r))
        self.G.duty_u16(int(65535 * g))
        self.B.duty_u16(int(65535 * b))

    def _set_color(self, color):
        vals = self.COLORS.get(color.lower(), (0.0, 0.0, 0.0))
        self._set_pwm(*vals)

    def on(self, color):
        self._set_color(color)

    def off(self):
        self._set_pwm(0.0, 0.0, 0.0)

    def flash(self, color, n=3, on_ms=200, off_ms=100):
        for _ in range(n):
            self.on(color)
            pause_ms(on_ms)
            self.off()
            pause_ms(off_ms)
        self.off()
    
    def dual_flash(self, color1, color2, n=3, c1_ms=200, c2_ms=200):
        for _ in range(n):
            self.on(color1)
            pause_ms(c1_ms)
            self.on(color2)
            pause_ms(c2_ms)
        self.off()


# --- Core Classes: Modules ---

class _SDC_:
    STATUS, MSG = None, None

    def __init__(self, ID=0, CS=5, MOSI=3, MISO=4, SCK=2, **kwargs):
        """
        Initialize the SD Card.

        Args:
            ID (int):
                The ID of the SPI bus. Defaults to 0.
            CS (int):
                The chip select pin for the SD card. Defaults to 5.
            MOSI (int):
                The MOSI pin for the SD card. Defaults to 3.
            MISO (int):
                The MISO pin for the SD card. Defaults to 4.
            SCK (int):
                The clock pin for the SD card. Defaults to 2.
        """
        self.SPI_ID = ID
        self.CS = CS
        self.MOSI = MOSI
        self.MISO = MISO
        self.SCK = SCK
        self.STATUS, self.MSG = self.activate()

    def activate(self):
        """
        Mount the SD card.
        """
        if not path.exists('/sd'):
            try:
                # Ensure pins are properly configured for SPI
                sck_pin = Pin(self.SCK)
                mosi_pin = Pin(self.MOSI) 
                miso_pin = Pin(self.MISO)
                cs_pin = Pin(self.CS, Pin.OUT)
                
                sdc_spi = SPI(self.SPI_ID, sck=sck_pin, mosi=mosi_pin, miso=miso_pin)
                # Add a small delay to allow SPI to stabilize
                pause_ms(100)
                self.obj = SDCard(sdc_spi, cs_pin)

                vfs = VfsFat(self.obj)
                mount(vfs, '/sd')
            except Exception as e:
                self.STATUS, self.MSG = False, "Failed to mount SD card: {}".format(str(e))
                return self.STATUS, self.MSG
        else:
            self.STATUS, self.MSG = True, "SD card already mounted."
            return self.STATUS, self.MSG
        
        self.STATUS, self.MSG = True, "SD card mounted successfully."
        return self.STATUS, self.MSG

    def deactivate(self):
        """
        Unmount the SD card and deactivate the SPI pins.
        """
        try:
            umount('/sd')
            Pin(self.CS, Pin.IN, pull=None)
            Pin(self.MOSI, Pin.IN, pull=None)
            Pin(self.MISO, Pin.IN, pull=None)
            Pin(self.SCK, Pin.IN, pull=None)
        except Exception as e:
            self.STATUS, self.MSG = False, "Failed to unmount SD card: {}".format(str(e))
            return self.STATUS, self.MSG

        self.STATUS, self.MSG = True, "SD card unmounted successfully."
        return self.STATUS, self.MSG

class _RTC_:
#TODO: Add support for DS1307
    STATUS, MSG = None, None

    def __init__(self, ID=0, SDA=0, SCL=1, setup=False, **kwargs):
        """
        Initialize the RTCs: External and Internal.

        Args:
            ID (int):
                The ID of the I2C bus. Defaults to 0.
            SDA (int):
                The SDA pin for the RTC. Defaults to 0.
            SCL (int):
                The SCL pin for the RTC. Defaults to 1.
        """
        self.I2C_ID = ID
        self.SDA = SDA
        self.SCL = SCL
        if setup:
            self.STATUS, self.MSG = self.setup()
        else:
            self.STATUS, self.MSG = self.activate()
    
    def setup(self):
        """
        Set up the External RTC
        """
        self.STATUS, self.MSG = self.activate()
        if not self.STATUS:
            self.log.error("Failed to activate RTC: {}".format(self.MSG))
            return self.STATUS, self.MSG
        # Check if the RTC's OSF (Oscillator Stop Flag) is set, and reset it if necessary
        if self.eClock.OSF():
            self.eClock._OSF_reset()
        # Set the RTC time to the current machine time
        self.STATUS, self.MSG = self.set_from_machine()
        return self.STATUS, self.MSG

    def activate(self):
        """
        Activate the RTCs: External and Internal.
        """
        try:
            # Ensure pins are properly configured for I2C
            sda_pin = Pin(self.SDA)
            scl_pin = Pin(self.SCL)
            rtc_i2c = I2C(self.I2C_ID, sda=sda_pin, scl=scl_pin, freq=100000)
            # Add a small delay to allow I2C to stabilize
            pause_ms(50)
            self.eClock = DS3231(rtc_i2c)
            self.iClock = iRTC()
        except Exception as e:
            self.STATUS, self.MSG = False, "Failed to activate RTC: {}".format(str(e))
            return self.STATUS, self.MSG
        
        self.STATUS, self.MSG = True, "RTC activated successfully."
        return self.STATUS, self.MSG
    
    def deactivate(self):
        """
        Deactivate the access to external RTC.
        """
        try:
            Pin(self.SDA, Pin.IN, pull=None)
            Pin(self.SCL, Pin.IN, pull=None)
        except Exception as e:
            self.STATUS, self.MSG = False, "Failed to deactivate RTC: {}".format(str(e))
            return self.STATUS, self.MSG
        
        self.STATUS, self.MSG = True, "RTC deactivated successfully."
        return self.STATUS, self.MSG
    
    def set_from_machine(self):
        """
        Set the external RTC's time from the Machine's time.
        """
        try:
            self.eClock.datetime(localtime()[:6])
            self.STATUS, self.MSG = True, "RTC time set from machine successfully."
        except Exception as e:
            self.STATUS, self.MSG = False, "Failed to set RTC time from machine: {}".format(str(e))
        return self.STATUS, self.MSG

    def set_to_machine(self):
        """
        Set the Machine's time from the external RTC's time.
        """
        try:
            self.iClock.datetime(self.eClock.datetime())
            self.STATUS, self.MSG = True, "Machine time set from RTC successfully."
        except Exception as e:
            self.STATUS, self.MSG = False, "Failed to set machine time from RTC: {}".format(str(e))
        return self.STATUS, self.MSG

class _eADC_:
    STATUS, MSG = None, None

    def __init__(self, ID=1, SDA=6, SCL=7, **kwargs):
        """
        Initialize the external ADC.

        Args:
            ID (int):
                The ID of the I2C bus. Defaults to 1.
            SDA (int):
                The SDA pin for the external ADC. Defaults to 6.
            SCL (int):
                The SCL pin for the external ADC. Defaults to 7.
        """
        self.I2C_ID = ID
        self.SDA = SDA
        self.SCL = SCL
        self.STATUS, self.MSG = self.activate()

    def activate(self):
        """
        Activate the external ADC.
        """
        try:
            # Ensure pins are properly configured for I2C
            sda_pin = Pin(self.SDA)
            scl_pin = Pin(self.SCL)
            adc_i2c = I2C(self.I2C_ID, sda=sda_pin, scl=scl_pin, freq=100000)
            # Add a small delay to allow I2C to stabilize
            pause_ms(50)
            self.obj = ADS1115(adc_i2c)
            self.obj.set_gain(ADS1115.GAIN_4_096V)
        except Exception as e:
            self.STATUS, self.MSG = False, "Failed to activate external ADC: {}".format(str(e))
            return self.STATUS, self.MSG
        
        self.STATUS, self.MSG = True, "External ADC activated successfully."
        return self.STATUS, self.MSG
    
    def deactivate(self):
        """
        Deactivate the external ADC.
        """
        try:
            Pin(self.SDA, Pin.IN, pull=None)
            Pin(self.SCL, Pin.IN, pull=None)
        except Exception as e:
            self.STATUS, self.MSG = False, "Failed to deactivate external ADC: {}".format(str(e))
            return self.STATUS, self.MSG
        
        self.STATUS, self.MSG = True, "External ADC deactivated successfully."
        return self.STATUS, self.MSG


# --- Core Classes: Sensors and System ---

class _SMS_:
    STATUS, MSG = None, None

    def __init__(self, loc='ADS1115', SMS1_CH=1, SMS2_CH=2, SMS3_CH=3, eADC=None, **kwargs):
        """
        Initialize the SMS class.
        
        Args:
            loc (Literal['INT', 'ADS1115']): 
                The ADC location (Internal/ADS1115). Defaults to 'INT'.
            SMS1_CH (int): 
                The channel for the first SMS module. Defaults to 1.
            SMS2_CH (int): 
                The channel for the second SMS module. Defaults to 2.
            SMS3_CH (int): 
                The channel for the third SMS module. Defaults to 3.
        """
        self.loc = loc
        self.SMS1_CH = SMS1_CH
        self.SMS2_CH = SMS2_CH
        self.SMS3_CH = SMS3_CH
        self.eADC = eADC.obj if eADC is not None else None

        if self.loc not in ['INT', 'ADS1115']:
            self.STATUS, self.MSG = False, "Invalid location for SMS module. Use 'INT' or 'ADS1115'."
            return
        if self.loc == 'ADS1115' and self.eADC is None:
            self.STATUS, self.MSG = False, "eADC object must be provided for 'ADS1115' location."
            return
            
        if self.loc == 'INT':
            try:
                self.SMS1 = ADC(self.SMS1_CH) if SMS1_CH is not None else None
                self.SMS2 = ADC(self.SMS2_CH) if SMS2_CH is not None else None
                self.SMS3 = ADC(self.SMS3_CH) if SMS3_CH is not None else None
                self.STATUS, self.MSG = True, "Internal SMS initialized successfully."
            except Exception as e:
                self.STATUS, self.MSG = False, "Failed to initialize internal SMS: {}".format(str(e))
                return
        
        self.SM1, self.SM2, self.SM3 = None, None, None
        self.STATUS, self.MSG = True, "SMS initialized successfully."
    
    def read(self):
        """
        Read the values from the SMS modules.
        """
        try:
            if self.loc == 'INT':
                self.SM1 = self.SMS1.read_u16() if self.SMS1 is not None else None
                self.SM2 = self.SMS2.read_u16() if self.SMS2 is not None else None
                self.SM3 = self.SMS3.read_u16() if self.SMS3 is not None else None
            else:
                self.SM1 = self.eADC.read_raw(self.SMS1_CH) if self.SMS1_CH is not None else None
                self.SM2 = self.eADC.read_raw(self.SMS2_CH) if self.SMS2_CH is not None else None
                self.SM3 = self.eADC.read_raw(self.SMS3_CH) if self.SMS3_CH is not None else None
            self.STATUS, self.MSG = True, "SMS values read successfully."
        except Exception as e:
            self.STATUS, self.MSG = False, "Failed to read SMS values: {}".format(str(e))
            self.SM1, self.SM2, self.SM3 = None, None, None
            return

class _OW_:
    STATUS, MSG = None, None

    def __init__(self, PIN=14, **kwargs):
        """
        Initialize the One-Wire sensor.
        Args:
            pin (int): The GPIO pin number for the One-Wire sensor. Defaults to 14.
        """
        try:
            self.obj = DS18X20(OneWire(Pin(PIN)))
            self.roms = self.obj.scan()
            if not self.roms:
                self.STATUS, self.MSG = False, "No DS18X20 devices found"
                return
            self.VAL = None
        except Exception as e:
            self.STATUS, self.MSG = False, "Failed to initialize One-Wire sensor: {}".format(str(e))
            self.VAL = None
        self.STATUS, self.MSG = True, "One-Wire sensor initialized successfully."

    def read(self):
        """
        Read temperature from the One-Wire sensor and store in self.temp.
        """
        try:
            self.obj.convert_temp()
            pause_ms(750)
            self.VAL = self.obj.read_temp(self.roms[0])
            self.STATUS, self.MSG = True, "Temperature read successfully."
        except Exception as e:
            self.STATUS, self.MSG = False, "Read error: {}".format(e)
            self.VAL = None
        return self.STATUS, self.MSG

class _iTEMP_:
    STATUS, MSG = None, None
    VAL = None

    def __init__(self):
        """
        Initialize the internal temperature sensor.
        """
        try:
            self.adc = ADC(4)  # Internal temperature sensor on ADC4
            self.STATUS, self.MSG = True, "Internal temperature sensor initialized successfully."
        except Exception as e:
            self.STATUS, self.MSG = False, "Failed to initialize internal temperature sensor: {}".format(str(e))
            self.TEMP = None

    def read(self):
        """
        Read the temperature from the internal ADC.
        """
        try:
            t = self.adc.read_u16() * 3.3 / 65535
            self.VAL = 27 - (t - 0.706) / 0.001721  # Convert voltage to temperature in Celsius
            self.STATUS, self.MSG = True, "Internal temperature read successfully."
        except Exception as e:
            self.STATUS, self.MSG = False, "Failed to read internal temperature: {}".format(str(e))
            self.VAL = None
        return self.STATUS, self.MSG

class _BAT_:
    STATUS, MSG = None, None
    voltage, percent = None, None
    is_eADC = False
    is_INT = False

    def __init__(self, loc='eADC', CH=0, eADC=None, R1=220_000, R2=22_000):
        """
        Initialize the battery class.
        
        Args:
            loc (Literal['INT', 'EXT']): 
                Location of the battery voltage measurement. Defaults to 'EXT'.
            channel (int): Channel on external ADC (0-3).
            eadc (object): eADC wrapper object with 'obj.read_voltage(channel)'.
            R1 (float): Upper resistor in voltage divider (ohms).
            R2 (float): Lower resistor in voltage divider (ohms).
        """
        if loc not in ['INT', 'iADC', 'eADC']:
            self.STATUS, self.MSG = False, "Invalid location for battery voltage measurement. Use 'INT' or 'EXT'."
            return
        if not R1 and not R2:
            R1, R2 = 1, 1  # Default to 1 ohm for R1 and R2 if R1 and R2 are not defined
        elif not R1 or not R2 or R1 <= 0 or R2 <= 0:
            self.STATUS, self.MSG = False, "Invalid values for R1 or R2. They must be positive numbers."
            return

        if loc == 'eADC':
            if CH is None or eADC is None:
                self.STATUS, self.MSG = False, "Missing 'channel', 'eADC', 'R1', or 'R2' for external ADC."
                return
            self.is_eADC = True
            self.channel = CH
            self.adc = eADC.obj
            self.R1 = R1
            self.R2 = R2
        elif loc == 'iADC':
            if CH is None:
                self.STATUS, self.MSG = False, "Missing 'channel', 'R1', or 'R2' for internal ADC."
                return
            self.channel = CH
            self.adc = ADC(CH)
        elif loc == 'INT':
            self.adc = ADC(3)  # VSYS on ADC3
            self.is_INT = True
        else:
            self.STATUS, self.MSG = False, "Invalid location for battery voltage measurement. Use 'INT', 'iADC', or 'eADC'."
            return

        self.STATUS, self.MSG = True, "Battery initialized successfully."

    def _read_voltage(self):
        v = (
            self.adc.read_voltage(self.channel)
            if self.is_eADC
            else self.adc.read_u16() * 3.3 / 65535
        )
        if self.is_INT:
            self.voltage = v * 3 # Internal ADC has a voltage divider ratio of 3:1
        else:
            self.voltage = v * ((self.R1 + self.R2) / self.R2)

    def read(self, vmin=3.0, vmax=4.2):
        try:
            self._read_voltage()
            p = (self.voltage - vmin) / (vmax - vmin) * 100
            self.percent = max(0, min(100, round(p)))
            self.STATUS, self.MSG = True, "Battery voltage and percentage read successfully."
        except Exception as e:
            self.STATUS, self.MSG = False, "Failed to read battery voltage: {}".format(str(e))
            self.voltage, self.percent = None, None
        return self.STATUS, self.MSG


# --- Abstraction Classes: Time Management ---

class _TIM_:
    NXT, CUR, PRV = None, None, None
    SLEEP_ms = None
    isLOGIC_RESET, isPWR_RESET, isABV_IVL_DLT = False, False, False

    def __init__(self, config, CACHE_DIR, setup=False):
        """
        Initialize the TIM class.
        This class provides methods to handle time intervals and calculate next record times.
        Args:
            config (dict): 
                A dictionary containing configuration parameters for time management.
            CACHE_DIR (str): 
                Directory for caching time data.
        """
        self.CACHE_DIR = CACHE_DIR
        self.fLOGIC_RESET = path.join(self.CACHE_DIR, 'LOGIC.RESET')
        self.fEXE_ms = path.join(self.CACHE_DIR, 'EXE.TIM')
        self.fCUR = path.join(self.CACHE_DIR, 'CUR.TIM')
        self.fPRV = path.join(self.CACHE_DIR, 'PRV.TIM')
        self.isLOGIC_RESET = self._check_logic_reset()

        self.IVL = timedelta(seconds=config.get('interval_s', 15*60))  # Default 15 minutes
        self.IVL_DLT = timedelta(seconds=config.get('delta_interval_s', 2*60))  # Default 2 minutes
        self.WAK_HST = timedelta(seconds=config.get('wake_haste_s', 3))  # Default 3 seconds
        self.__read_cached_exe_ms()
        if self.EXE_ms:
            self.WAK_HST = timedelta(milliseconds=self.EXE_ms*1.10)  # Add 10% to execution time to be safe

        self.read_delay_ms = {
            'SMS': config['SMS'].get('read_delay_ms', 25),      # Default 25 ms
            'OW': config['OW'].get('read_delay_ms', 750),       # Default 750 ms
            'BAT': config['BAT'].get('read_delay_ms', 25),     # Default 25 ms
            'iTEMP': config['iTEMP'].get('read_delay_ms', 25),  # Default 25 ms
        }
        self.n_reads = {
            'SMS': config['SMS'].get('n_reads', 25),    # Default 25 reads for SMS
            'OW': config['OW'].get('n_reads', 3),       # Default 3 reads for OW
            'BAT': config['BAT'].get('n_reads', 7),     # Default 7 reads for BAT
            'iTEMP': config['iTEMP'].get('n_reads', 7), # Default 7 reads for iTEMP
        }
        
        if reset_cause() not in [DEEPSLEEP_RESET, ] or self.isLOGIC_RESET:
            if reset_cause() == HARD_RESET:
                self.isPWR_RESET = True
            self.CUR = self.NOW
            self.__get_next_record_time()
            CUR = self.NXT - self.IVL
            if abs(self.NOW - CUR) > self.IVL_DLT:
                self.isABV_IVL_DLT = True
            self.__read_cached_times(cur=False)
        else:
            self.STATUS, self.MSG = self.__read_cached_times()
            if not self.STATUS:
                self.STATUS, self.MSG = self.__flag_logic_reset()
                if not self.STATUS:
                    self.MSG = "Failed to flag logic reset: {}".format(self.MSG)
                    return
                self.isLOGIC_RESET = True
                return
            NXT = self.CUR + self.IVL
            if not self.PRV == self.CUR - self.IVL:
                if (self.NOW + self.WAK_HST > NXT) or (self.NOW + self.WAK_HST*3 < self.CUR) or (self.NOW < self.PRV):
                    self.STATUS, self.MSG = self.__flag_logic_reset()
                    if not self.STATUS:
                        self.MSG = "Failed to flag logic reset: {}".format(self.MSG)
                        return
                    self.isLOGIC_RESET = True
                    self.MSG = "Logic reset flagged due to time inconsistency."
                    return
            if abs(self.NOW - self.CUR) > self.IVL_DLT:
                self.isABV_IVL_DLT = True

        self.STATUS, self.MSG = True, "Time management initialized successfully."
    
    @property
    def NOW(self):
        """
        Get the current time.
        Returns:
            datetime: The current time as a datetime object.
        """
        return datetime(*localtime()[:6])
    
    @property
    def NULL(self):
        """
        Get the null time (epoch).
        Returns:
            datetime: The null time as a datetime object.
        """
        return datetime(*localtime(0)[:6])

    def __flag_logic_reset(self):
        try:
            open(self.fLOGIC_RESET, 'w').close()
            self.STATUS, self.MSG = True, "Logic reset flagged successfully."
        except Exception as e:
            self.STATUS, self.MSG = False, "Failed to flag logic reset: {}".format(str(e))
        return self.STATUS, self.MSG
    
    def _check_logic_reset(self):
        if path.exists(self.fLOGIC_RESET):
            remove(self.fLOGIC_RESET)
            return True
        else:
            return False
    
    def __read_cached_exe_ms(self):
        try:
            with open(self.fEXE_ms, 'r') as f:
                self.EXE_ms = int(f.readline().strip())
            self.STATUS, self.MSG = True, "Cached execution time read successfully."
        except Exception as e:
            self.EXE_ms = None
            self.STATUS, self.MSG = False, "Failed to read cached execution time: {}".format(str(e))
    
    def __read_cached_times(self, cur=True, prv=True):
        try:
            if cur:
                with open(self.fCUR) as f:
                    self.CUR = datetime.fromisoformat(f.readline().strip())
            if prv:
                with open(self.fPRV) as f:
                    self.PRV = datetime.fromisoformat(f.readline().strip())
            self.STATUS, self.MSG = True, "Cached time data read successfully."
        except Exception as e:
            if cur:
                self.CUR = None
            if prv:
                self.PRV = None
            self.STATUS, self.MSG = False, "Failed to read cached time data: {}".format(str(e))
        return self.STATUS, self.MSG
        
    def __cache_times(self):
        try:
            with open(self.fCUR, 'w') as f:
                f.write(self.NXT.isoformat() + '\n')
            with open(self.fPRV, 'w') as f:
                f.write(self.CUR.isoformat() + '\n')
            self.STATUS, self.MSG = True, "Cached times updated successfully."
        except Exception as e:
            self.STATUS, self.MSG = False, "Failed to cache times: {}".format(str(e))
        return self.STATUS, self.MSG

    def __get_next_record_time(self):
        try:
            elapsed_seconds_since_null = int((self.NOW - self.NULL).total_seconds())
            interval_seconds = int(self.IVL.total_seconds())
            next_seconds_since_null = ((elapsed_seconds_since_null // interval_seconds) + 1) * interval_seconds
            self.NXT = self.NULL + timedelta(seconds=next_seconds_since_null)
            self.STATUS, self.MSG = True, "Next record time calculated successfully."
        except Exception as e:
            self.STATUS, self.MSG = False, "Failed to calculate next record time: {}".format(str(e))
        return self.STATUS, self.MSG
    
    def get_ms_until_next_rec(self):
        """ Calculate the milliseconds until the next record time."""
        try:
            if not self.NXT or self.NXT < self.NOW:
                self.__get_next_record_time()
            self.SLEEP_ms = max(int((self.NXT - self.NOW - self.WAK_HST).total_seconds() * 1000), 1)
        except Exception as e:
            self.STATUS, self.MSG = False, "Failed to calculate milliseconds until next record: {}".format(str(e))
            self.SLEEP_ms = None
            return self.STATUS, self.MSG
        self.STATUS, self.MSG = True, "Determined sleep period (in ms) successfully."
        return self.STATUS, self.MSG

    def update(self):
        """
        Update the next record time and cache the current and previous times.
        """
        self.__get_next_record_time()
        self.STATUS, self.MSG = self.__cache_times()
        return self.STATUS, self.MSG


# --- Abstraction Classes: Sensors ---

class SEN:
    STATUS, MSG = None, None

    def __init__(self, config, TIM, DATA_DIR, REC_DIR, eADC, fname_SMS='sm.csv', fname_OW='ow.csv', rewrite=False):
        """
        Initialize the sensor class.
        
        config (dict):
            A dictionary containing sensor configuration. If None, it will use default values.
        TIM (_TIM_):
            An instance of the _TIM_ class for time management.
        DATA_DIR (str):
            Directory for storing sensor data.
        REC_DIR (str):
            Directory for storing sensor records.
        eADC (_eADC_):
            An instance of the _eADC_ class for external ADC access.
        fname_SMS (str):
            Filename for SMS records. Defaults to 'sms.csv'.
        fname_OW (str):
            Filename for One-Wire records. Defaults to 'ow.csv'.
        rewrite (bool):
            If True, will rewrite the record files if they already exist. Defaults to False.
        """
        self.TIM = TIM
        self.DATA_DIR = DATA_DIR
        self.REC_DIR = REC_DIR
        self.fname_SMS = fname_SMS
        self.fname_OW = fname_OW

        self.SMS = _SMS_(**config.get('SMS', {}), eADC=eADC)
        if not self.SMS.STATUS:
            self.STATUS, self.MSG = self.SMS.STATUS, self.SMS.MSG
            return
        self.OW = _OW_(**config.get('OW', {}))
        if not self.OW.STATUS:
            self.STATUS, self.MSG = self.OW.STATUS, self.OW.MSG
            return

        self.DAT = {'SM1': None, 'SM2': None, 'SM3': None, 'OW': None}
        self.REC = {
            'SM1': [],
            'SM2': [],
            'SM3': [],
            'OW': []
        }

        if not path.exists(path.join(self.REC_DIR, self.fname_SMS)) or rewrite:
            with open(path.join(self.REC_DIR, self.fname_SMS), 'w') as f_sms:
                header = ','.join(['timestamp', 'SM1', 'SM2', 'SM3']) + '\n'
                f_sms.write(header)
            with open(path.join(self.REC_DIR, self.fname_OW), 'w') as f_ow:
                header = ','.join(['timestamp', 'OW']) + '\n'
                f_ow.write(header)
        if not path.exists(path.join(self.DATA_DIR, self.fname_SMS)) or rewrite:
            with open(path.join(self.DATA_DIR, self.fname_SMS), 'w') as f_sms:
                header = ','.join(['timestamp', 'SM1', 'SM2', 'SM3']) + '\n'
                f_sms.write(header)
            with open(path.join(self.DATA_DIR, self.fname_OW), 'w') as f_ow:
                header = ','.join(['timestamp', 'OW']) + '\n'
                f_ow.write(header)

        self.STATUS, self.MSG = True, "Sensors initialized successfully."

    def __read(self):
        try:
            self.REC['SM1'].clear()
            self.REC['SM2'].clear()
            self.REC['SM3'].clear()
            self.REC['OW'].clear()
            self.SMS.SM1, self.SMS.SM2, self.SMS.SM3 = None, None, None
            self.OW.VAL = None
            
            # Read SMS sensors with error handling
            sms_read_count = 0
            for i in range(self.TIM.n_reads['SMS']):
                try:
                    self.SMS.read()
                    if self.SMS.STATUS:
                        if self.SMS.SM1 is not None:
                            self.REC['SM1'].append(self.SMS.SM1)
                        if self.SMS.SM2 is not None:
                            self.REC['SM2'].append(self.SMS.SM2)
                        if self.SMS.SM3 is not None:
                            self.REC['SM3'].append(self.SMS.SM3)
                        sms_read_count += 1
                    pause_ms(self.TIM.read_delay_ms['SMS'])
                except Exception as e:
                    self.STATUS, self.MSG = False, "SMS read error on attempt {}: {}".format(i+1, str(e))
                    return self.STATUS, self.MSG
            
            # Calculate averages for SMS
            self.DAT['SM1'] = sum(self.REC['SM1']) / len(self.REC['SM1']) if self.REC['SM1'] else None
            self.DAT['SM2'] = sum(self.REC['SM2']) / len(self.REC['SM2']) if self.REC['SM2'] else None
            self.DAT['SM3'] = sum(self.REC['SM3']) / len(self.REC['SM3']) if self.REC['SM3'] else None
            
            # Read OW sensor with error handling
            ow_read_count = 0
            for i in range(self.TIM.n_reads['OW']):
                try:
                    ow_status, ow_msg = self.OW.read()
                    if ow_status and self.OW.VAL is not None:
                        self.REC['OW'].append(self.OW.VAL)
                        ow_read_count += 1
                    pause_ms(self.TIM.read_delay_ms['OW'])
                except Exception as e:
                    self.STATUS, self.MSG = False, "OW read error on attempt {}: {}".format(i+1, str(e))
                    return self.STATUS, self.MSG
                    
            self.DAT['OW'] = sum(self.REC['OW']) / len(self.REC['OW']) if self.REC['OW'] else None
            
            # Check if we got any valid readings
            if sms_read_count == 0 and ow_read_count == 0:
                self.STATUS, self.MSG = False, "No successful sensor readings obtained"
                return self.STATUS, self.MSG
                
        except Exception as e:
            self.STATUS, self.MSG = False, "Error reading sensors: {}".format(str(e))
            return self.STATUS, self.MSG
        self.STATUS, self.MSG = True, "Sensors read successfully."
        return self.STATUS, self.MSG
    
    def __write(self):
        try:
            with open(path.join(self.REC_DIR, self.fname_SMS), 'a') as f_sms:
                for idx in range(self.TIM.n_reads['SMS']):
                    sm1_val = self.REC['SM1'][idx] if idx < len(self.REC['SM1']) else None
                    sm2_val = self.REC['SM2'][idx] if idx < len(self.REC['SM2']) else None
                    sm3_val = self.REC['SM3'][idx] if idx < len(self.REC['SM3']) else None
                    f_sms.write("{}, {}, {}, {}\n".format(self.TIM.CUR, sm1_val, sm2_val, sm3_val))
            if self.REC['OW']:
                with open(path.join(self.REC_DIR, self.fname_OW), 'a') as f_ow:
                    for idx in range(self.TIM.n_reads['OW']):
                        ow_val = self.REC['OW'][idx] if idx < len(self.REC['OW']) else None
                        f_ow.write("{}, {}\n".format(self.TIM.CUR, ow_val))
            else:
                with open(path.join(self.REC_DIR, self.fname_OW), 'a') as f_ow:
                    f_ow.write("{}, {}\n".format(self.TIM.CUR, self.DAT['OW']))
            with open(path.join(self.DATA_DIR, self.fname_SMS), 'a') as f_sms:
                f_sms.write("{}, {}, {}, {}\n".format(self.TIM.CUR, self.DAT['SM1'], self.DAT['SM2'], self.DAT['SM3']))
            with open(path.join(self.DATA_DIR, self.fname_OW), 'a') as f_ow:
                f_ow.write("{}, {}\n".format(self.TIM.CUR, self.DAT['OW']))
        except Exception as e:
            self.STATUS, self.MSG = False, "Error writing sensor data: {}".format(str(e))
            return self.STATUS, self.MSG
        self.STATUS, self.MSG = True, "Sensor data written successfully."
        return self.STATUS, self.MSG

    def record(self):
        """Read and record the values from the sensors."""        
        self.STATUS, self.MSG = self.__read()
        if not self.STATUS:
           self.MSG = "Failed to read sensor data: {}".format(self.MSG)
           return self.STATUS, self.MSG
        self.STATUS, self.MSG = self.__write()
        if not self.STATUS:
            self.MSG = "Failed to write sensor data: {}".format(self.MSG)
            return self.STATUS, self.MSG
        self.STATUS, self.MSG = True, "Recorded data from SMS and OW sensors successfully."
        return self.STATUS, self.MSG


class SYS:
    STATUS, MSG = None, None

    def __init__(self, config, TIM, DATA_DIR, REC_DIR, eADC=None, fname_BAT='bat.csv', fname_iTEMP='itemp.csv', rewrite=False):
        """
        Initialize the system class.
        
        Args:
            config (dict):
                A dictionary containing system configuration. If None, it will use default values.
            TIM (_TIM_):
                An instance of the _TIM_ class for time management.
            DATA_DIR (str):
                Directory for storing system data.
            REC_DIR (str):
                Directory for storing system records.
            fname_BAT (str):
                Filename for battery records. Defaults to 'bat.csv'.
            fname_iTEMP (str):
                Filename for internal temperature records. Defaults to 'itemp.csv'.
            rewrite (bool):
                Whether to rewrite existing files. Defaults to False.
        """
        self.TIM = TIM
        self.DATA_DIR = DATA_DIR
        self.REC_DIR = REC_DIR
        self.fname_BAT = fname_BAT
        self.fname_iTEMP = fname_iTEMP

        self.BAT = _BAT_(**config.get('BAT', {}), eADC=eADC)
        self.iTEMP = _iTEMP_()

        self.DAT = {'BAT': None, 'iTEMP': None}
        self.REC = {
            'BAT': [],
            'iTEMP': []
        }

        if not path.exists(path.join(self.REC_DIR, self.fname_BAT)) or rewrite:
            with open(path.join(self.REC_DIR, self.fname_BAT), 'w') as f_bat:
                header = ','.join(['timestamp', 'voltage', 'percent']) + '\n'
                f_bat.write(header)
            with open(path.join(self.REC_DIR, self.fname_iTEMP), 'w') as f_itemp:
                header = ','.join(['timestamp', 'temperature']) + '\n'
                f_itemp.write(header)
        if not path.exists(path.join(self.DATA_DIR, self.fname_BAT)) or rewrite:
            with open(path.join(self.DATA_DIR, self.fname_BAT), 'w') as f_bat:
                header = ','.join(['timestamp', 'voltage', 'percent']) + '\n'
                f_bat.write(header)
            with open(path.join(self.DATA_DIR, self.fname_iTEMP), 'w') as f_itemp:
                header = ','.join(['timestamp', 'temperature']) + '\n'
                f_itemp.write(header)

        self.STATUS, self.MSG = True, "System initialized successfully."

    def __read(self):
        try:
            self.REC['BAT'].clear()
            self.REC['iTEMP'].clear()
            self.BAT.voltage, self.BAT.percent = None, None
            self.iTEMP.VAL = None
            for _ in range(self.TIM.n_reads['BAT']):
                self.BAT.read()
                if self.BAT.voltage and self.BAT.percent:
                    self.REC['BAT'].append((self.BAT.voltage, self.BAT.percent))
                else:
                    self.REC['BAT'].append((None, None))
                pause_ms(self.TIM.read_delay_ms['BAT'])
            _v = sum(voltage for voltage, _ in self.REC['BAT']) / len(self.REC['BAT']) if self.REC['BAT'] else None
            _p = sum(percent for _, percent in self.REC['BAT']) / len(self.REC['BAT']) if self.REC['BAT'] else None
            self.DAT['BAT'] = {
                'voltage': sum(voltage for voltage, _ in self.REC['BAT']) / len(self.REC['BAT']) if self.REC['BAT'] else None,
                'percent': sum(percent for _, percent in self.REC['BAT']) / len(self.REC['BAT']) if self.REC['BAT'] else None
            }
            for _ in range(self.TIM.n_reads['iTEMP']):
                self.iTEMP.read()
                if self.iTEMP.VAL:
                    self.REC['iTEMP'].append(self.iTEMP.VAL)
                pause_ms(self.TIM.read_delay_ms['iTEMP'])
            self.DAT['iTEMP'] = sum(self.REC['iTEMP']) / len(self.REC['iTEMP']) if self.REC['iTEMP'] else None
        except Exception as e:
            self.STATUS, self.MSG = False, "Error reading system sensors: {}".format(str(e))
            return self.STATUS, self.MSG
        self.STATUS, self.MSG = True, "System sensors read successfully."
        return self.STATUS, self.MSG
        
    def __write(self):
        try:
            with open(path.join(self.REC_DIR, self.fname_BAT), 'a') as f_bat:
                for voltage, percent in self.REC['BAT']:
                    f_bat.write("{}, {}, {}\n".format(self.TIM.CUR, voltage, percent))
            with open(path.join(self.REC_DIR, self.fname_iTEMP), 'a') as f_itemp:
                for temp in self.REC['iTEMP']:
                    f_itemp.write("{}, {}\n".format(self.TIM.CUR, temp))
            with open(path.join(self.DATA_DIR, self.fname_BAT), 'a') as f_bat:
                f_bat.write("{}, {}, {}\n".format(self.TIM.CUR, self.DAT['BAT']['voltage'], self.DAT['BAT']['percent']))
            with open(path.join(self.DATA_DIR, self.fname_iTEMP), 'a') as f_itemp:
                f_itemp.write("{}, {}\n".format(self.TIM.CUR, self.DAT['iTEMP']))
        except Exception as e:
            self.STATUS, self.MSG = False, "Error writing system data: {}".format(str(e))
            return self.STATUS, self.MSG
        self.STATUS, self.MSG = True, "System data written successfully."
        return self.STATUS, self.MSG
        
    def record(self):
        """ Read and record the values from the system sensors."""
        self.STATUS, self.MSG = self.__read()
        if not self.STATUS:
            return self.STATUS, self.MSG
        self.STATUS, self.MSG = self.__write()
        if not self.STATUS:
            return self.STATUS, self.MSG
        self.STATUS, self.MSG = True, "Recorded data from battery and internal temperature sensors successfully."
        return self.STATUS, self.MSG


class picoLogger:
    STATUS, MSG = None, None

    CONFIG_DIR = '/.config'
    CACHE_DIR = '/.cache'
    DAT_DIR = '/sd/data'
    REC_DIR = path.join(DAT_DIR, 'records')
    CONFIG_FILE = path.join(CONFIG_DIR, 'picoLogger.json')
    fname_SMS = 'sms.csv'
    fname_OW = 'ow.csv'
    fname_BAT = 'bat.csv'
    fname_iTEMP = 'itemp.csv'

    # Default logger configuration
    default_ini_config = {
        'log_path': '/stray.log',
        'log_level': 'DEBUG',
        'uart_cnf': {'id': 0, 'baud': 9600, 'tx': 16, 'rx': 17},
    }

    EXE_ms = 0
    
    def __init__(self, fCONFIG=None):
        """
        Initialize the picoLogger.

        Args:
            CONFIG (dict, optional):
                A dictionary containing configuration settings. If empty, it will attempt to load from the config file.
        """
        self.time_start = ticks_ms()

        # Set up a dummy logger to log initialisation messages
        self.log = _Logger_(path=self.default_ini_config['log_path'], 
                             level=self.default_ini_config['log_level'], 
                             uart_cnf=self.default_ini_config['uart_cnf'], 
                             rewrite=True)
        self.sLED = _sLED_()
        
        if not fCONFIG:
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    self.CONFIG = load_json(f)
                
                self.STATUS, self.MSG = self.activate()
                if not self.STATUS:
                    self.log.critical("Failed to activate picoLogger! Check the log file for more details.")
                    self.STATUS, self.MSG = False, "Failed to activate picoLogger! Check the log file for more details."
                    self.sLED.on('red')
            except Exception as e:
                self.log.critical("Failed to activate picoLogger. Error: {}".format(str(e)))
                self.STATUS, self.MSG = False, "Failed to activate picoLogger. Error: {}".format(str(e))
        else:
            self.STATUS, self.MSG = self.__setup(fCONFIG)
            if not self.STATUS:
                self.log.critical("Failed to set up picoLogger with provided configuration: {}".format(self.MSG))
                self.sLED.on('red')
                return

    def __setup(self, fCONFIG):
        self.MSG = "\n########################## picoLogger setup initiated #########################"
        self.log.info(self.MSG)
        print(self.MSG)

        # Load the configuration from the provided file
        self.log.debug("Loading configuration from file: {}".format(fCONFIG))
        with open(fCONFIG, 'r') as f:
            self.CONFIG = load_json(f)
        self.log.info("Configuration loaded successfully.")
        
        # Initialize the Status LED
        self.log.debug("Initializing Status LED")
        self.sLED = _sLED_(R=self.CONFIG['HW']['sLED']['R'],
                         G=self.CONFIG['HW']['sLED']['G'], 
                         B=self.CONFIG['HW']['sLED']['B'])
        self.sLED.on('yellow')
        self.log.info("Status LED initialized successfully.")

        # Power on peripheral devices
        self.log.debug("Powering on peripheral devices")
        self.PWR = Pin(self.CONFIG['HW']['SWITCH']['PWR'], Pin.OUT)
        if self.PWR.value() == 1:
            self.log.warning("Power was already on! Keeping it on.")
        else:
            self.PWR.value(1)
            self.log.debug("Powering on peripheral devices.")
        pause_ms(100)
        self.MSG = "Peripheral devices powered on successfully."
        self.log.info(self.MSG)
        print(self.MSG)

        self.log.debug("Setting up the Function Switch")
        self.FN = Pin(self.CONFIG['HW']['SWITCH']['FN'], Pin.IN)
        self.MSG = "Function Switch State: {}".format("LOGGING" if self.FN.value() else "IDLE")
        self.log.info(self.MSG)
        print(self.MSG)

        # Setting up SD Card
        self.log.debug("Setting up SD Card")
        self.SDC = _SDC_(**self.CONFIG['HW']['SDC'])
        if not self.SDC.STATUS:
            self.log.critical("Failed to initialise/mount SD Card")
            self.log.error(self.SDC.MSG)
            self.sLED.on('red')
            self.STATUS, self.MSG = False, "Failed to initialise/mount SD Card: {}".format(self.SDC.MSG)
            print(self.MSG)
            return self.STATUS, 
        self.MSG = "SD Card set-up and mounted successfully."
        self.log.info(self.MSG)
        print(self.MSG)
        
        # Update logger to actual config from dummy config
        update_log_args = self.CONFIG['LOG'].copy()
        update_log_args.update(self.CONFIG['HW']['UART'])
        self.log.update_config(**update_log_args)
        self.log.debug("Updated Logger configuration: {}".format(update_log_args))
        print("Logger configuration updated successfully.")

        # Setting up RTC
        self.log.debug("Setting up RTC")
        self.RTC = _RTC_(**self.CONFIG['HW']['RTC'], setup=True)
        if not self.RTC.STATUS:
            self.log.critical("Failed to set up RTC")
            self.log.error(self.RTC.MSG)
            self.sLED.on('red')
            self.STATUS, self.MSG = False,  "Failed to set up RTC: {}".format(self.RTC.MSG)
            print(self.MSG)
            return self.STATUS, self.MSG
        self.MSG = "RTC set-up successfully."
        self.log.info(self.MSG)
        print(self.MSG)

        # Setting up external ADC if configured
        if 'eADC' in self.CONFIG['HW'].keys():
            self.log.debug("Setting up external ADC")
            self.eADC = _eADC_(**self.CONFIG['HW']['eADC'])
            if not self.eADC.STATUS:
                self.log.critical("Failed to set up external ADC")
                self.log.error(self.eADC.MSG)
                self.sLED.on('red')
                self.STATUS, self.MSG = False,  "Failed to set up external ADC: {}".format(self.eADC.MSG)
                print(self.MSG)
                return self.STATUS, self.MSG
            else:
                self.MSG = "External ADC set-up successfully."
                self.log.info(self.MSG)
                print(self.MSG)
        else:
            self.eADC = None
            self.MSG = "No external ADC configured."
            self.log.info(self.MSG)
            print(self.MSG)
        
        # Create necessary directories if they do not exist
        self.log.debug("Creating necessary directories if they do not exist")
        if not path.exists(self.CONFIG_DIR):
            try:
                mkdir(self.CONFIG_DIR)
            except Exception as e:
                self.MSG = "Failed to create config directory: {}".format(str(e))
                self.log.error(self.MSG)
                print(self.MSG)
                self.sLED.on('red')
                return False, self.MSG
        if not path.exists(self.DAT_DIR):
            try:
                mkdir(self.DAT_DIR)
            except Exception as e:
                self.MSG = "Failed to create data directory: {}".format(str(e))
                self.log.error(self.MSG)
                print(self.MSG)
                self.sLED.on('red')
                return False, self.MSG
        if not path.exists(self.REC_DIR):
            try:
                mkdir(self.REC_DIR)
            except Exception as e:
                self.MSG = "Failed to create records directory: {}".format(str(e))
                self.log.error(self.MSG)
                print(self.MSG)
                self.sLED.on('red')
                return False, self.MSG
        if not path.exists(self.CACHE_DIR):
            try:
                mkdir(self.CACHE_DIR)
            except Exception as e:
                self.MSG = "Failed to create cache directory: {}".format(str(e))
                self.log.error(self.MSG)
                print(self.MSG)
                self.sLED.on('red')
                return False, self.MSG
        self.MSG = "Working Directories set up successfully."
        self.log.info(self.MSG)
        print(self.MSG)
        
        # Setting up Time Management
        self.log.debug("Setting up Time Management")
        self.TIM = _TIM_(config=self.CONFIG['TIM'], CACHE_DIR=self.CACHE_DIR)
        if not self.TIM.STATUS:
            if self.TIM.isLOGIC_RESET:
                self.log.critical("Device was possibly in depsleep mode before OR Deep Sleep detection logic is broken. Reset device and retry...")
                self.log.error(self.TIM.MSG)
            self.sLED.on('red')
            self.STATUS, self.MSG = False, "Failed to set up Time Management: {}".format(self.TIM.MSG)
            print(self.MSG)
            return self.STATUS, self.MSG
        if self.TIM.isPWR_RESET:
            self.log.info("Power Reset detected successfully.")
        if self.TIM.isABV_IVL_DLT:
            self.log.info("Difference between the recording time {} and target recording time: {} is above the desired amount: {}.".format(self.TIM.NOW, self.TIM.CUR, self.TIM.IVL_DLT))
        self.TIM.__get_next_record_time()
        self.log.debug("Next record time calculated: {}".format(self.TIM.NXT))
        self.MSG = "Time Management set-up successfully. Current time: {}; Next record time: {}".format(self.TIM.CUR, self.TIM.NXT)
        self.log.info(self.MSG)
        print(self.MSG)

        # Setting up Sensors
        self.log.debug("Setting up Sensors")
        self.SEN = SEN(config=self.CONFIG['SEN'],
                          TIM=self.TIM,
                          DATA_DIR=self.DAT_DIR,
                          REC_DIR=self.REC_DIR,
                          eADC=self.eADC,
                          fname_SMS=self.fname_SMS,
                          fname_OW=self.fname_OW,
                          rewrite=True)
        if not self.SEN.STATUS:
            self.log.critical("Failed to set up Sensors")
            self.log.error(self.SEN.MSG)
            self.sLED.on('red')
            self.STATUS, self.MSG = False, "Failed to set up Sensors: {}".format(self.SEN.MSG)
            print(self.MSG)
            return self.STATUS, self.MSG
        
        self.sLED.on('blue')
        self.STATUS, self.MSG = self.SEN.__read()  # Read initial sensor values
        self.sLED.on('yellow')
        if not self.STATUS:
            self.log.critical("Failed to read initial sensor values")
            self.log.error(self.SEN.MSG)
            self.sLED.on('red')
            self.STATUS, self.MSG = False, "Failed to read initial sensor values: {}".format(self.SEN.MSG)
            print(self.MSG)
            return self.STATUS, self.MSG
        self.MSG = "Sensors set-up successfully. Initial sensor values: {}".format(self.SEN.DAT)
        self.log.info(self.MSG)
        print(self.MSG)

        # Setting up System
        self.log.debug("Setting up System")
        self.SYS = SYS(config=self.CONFIG['SYS'],
                          TIM=self.TIM,
                          DATA_DIR=self.DAT_DIR,
                          REC_DIR=self.REC_DIR,
                          eADC=self.eADC,
                          fname_BAT=self.fname_BAT,
                          fname_iTEMP=self.fname_iTEMP,
                          rewrite=True)
        if not self.SYS.STATUS:
            self.log.critical("Failed to set up System")
            self.log.error(self.SYS.MSG)
            self.sLED.on('red')
            self.STATUS, self.MSG = False, "Failed to set up System: {}".format(self.SYS.MSG)
            print(self.MSG)
            return self.STATUS, self.MSG
        self.STATUS, self.MSG = self.SYS.__read()  # Read initial system values
        if not self.STATUS:
            self.log.critical("Failed to read initial system values")
            self.log.error(self.SYS.MSG)
            self.sLED.on('red')
            self.STATUS, self.MSG = False, "Failed to read initial system values: {}".format(self.SYS.MSG)
            print(self.MSG)
            return self.STATUS, self.MSG
        self.MSG = "System set-up successfully. Initial system values: {}".format(self.SYS.DAT)
        self.log.info(self.MSG)
        print(self.MSG)

        # Write initial execution time to cache
        self.log.debug("Writing initial execution time to cache")
        self.EXE_ms = ticks_diff(ticks_ms(), self.time_start)
        try:
            with open(self.TIM.fEXE_ms, 'w') as f:
                if int(self.TIM.WAK_HST.total_seconds()) != int(self.CONFIG['TIM']['wake_haste_s']):
                    f.write(str(max(self.EXE_ms, int(self.TIM.WAK_HST.total_seconds()*1000))) + '\n')
                else:
                    f.write(str(self.EXE_ms) + '\n')
            self.log.info("Initial execution time cached successfully: {} ms".format(self.EXE_ms))
        except Exception as e:
            self.log.error("Failed to write initial execution time to cache: {}".format(str(e)))
            self.STATUS, self.MSG = False, "Failed to write initial execution time to cache: {}".format(str(e))
            self.sLED.on('red')
            self.log.error(self.MSG)
            print(self.MSG)
            return self.STATUS, self.MSG

        # Deactivate picoLogger
        self.log.debug("Deactivating picoLogger")
        self.STATUS, self.MSG = self.deactivate()
        if not self.STATUS:
            self.sLED.on('red')
            self.MSG = "Failed to deactivate picoLogger: {}".format(self.MSG)
            self.log.error(self.MSG)
            print(self.MSG)
            return self.STATUS, self.MSG
        self.log.info("picoLogger deactivated successfully.")

        self.MSG = "########################## picoLogger setup completed #########################\n"
        self.log.info(self.MSG)
        print(self.MSG)
        self.sLED.flash('green')

        self.STATUS, self.MSG = True, "picoLogger setup completed successfully."
        return self.STATUS, self.MSG
    
    def activate(self):
        """
        Activate the picoLogger.

        This method powers on the peripherals and initialises the SD card, RTC, and the external-ADC (if configured).
        """
        # Initialize the Status LED
        self.log.debug("Initializing Status LED")
        self.sLED = _sLED_(R=self.CONFIG['HW']['sLED']['R'],
                         G=self.CONFIG['HW']['sLED']['G'], 
                         B=self.CONFIG['HW']['sLED']['B'])
        self.sLED.on('yellow')
        self.log.info("Status LED initialized successfully.")

        self.log.info("--------------------- Activating picoLogger ---------------------")

        # Power on peripheral devices
        self.PWR = Pin(self.CONFIG['HW']['SWITCH']['PWR'], Pin.OUT)
        if self.PWR.value() == 1:
            self.log.warning("Power was already on! Keeping it on.")
        else:
            self.PWR.value(1)
            self.log.debug("Peripheral devices powered on.")
        pause_ms(100)
        self.log.info("Peripheral devices powered on successfully.")

        self.log.debug("Initializing peripherals")
        self.FN = Pin(self.CONFIG['HW']['SWITCH']['FN'], Pin.IN)

        # Initialize SD Card
        self.log.debug("Initializing SD Card")
        self.SDC = _SDC_(**self.CONFIG['HW']['SDC'])
        if not self.SDC.STATUS:
            self.log.critical("Failed to initialise/mount SD Card")
            self.log.error(self.SDC.MSG)
            self.sLED.on('red')
            self.STATUS, self.MSG = False, "Failed to initialise/mount SD Card: {}".format(self.SDC.MSG)
            return self.STATUS, self.MSG
        self.log.info("SD Card initialised and mounted successfully.")
        
        # Update logger to actual config from dummy config
        update_log_args = self.CONFIG['LOG'].copy()
        update_log_args.update(self.CONFIG['HW']['UART'])
        self.log.update_config(**update_log_args)
        self.log.debug("Updated Logger configuration: {}".format(update_log_args))

        # Initialize RTC
        self.RTC = _RTC_(**self.CONFIG['HW']['RTC'])
        if not self.RTC.STATUS:
            self.log.critical("Failed to initialise RTC")
            self.log.error(self.RTC.MSG)
            self.sLED.on('red')
            self.STATUS, self.MSG = False, "Failed to initialise RTC: {}".format(self.RTC.MSG)
            return self.STATUS, self.MSG
        self.log.debug("RTC initialised successfully. Current machine: {}".format(localtime()))
        self.log.debug("Setting machine time from eRTC")
        self.STATUS, self.MSG = self.RTC.set_to_machine()
        if not self.STATUS:
            self.log.critical("Failed to set RTC from machine time")
            self.log.error(self.MSG)
            self.sLED.on('red')
            self.STATUS, self.MSG = False,  "Failed to set RTC from machine time: {}".format(self.MSG)
            return self.STATUS, self.MSG
        self.log.info("RTC initialised successfully.")
        
        # Initialize external ADC if configured
        if 'eADC' in self.CONFIG['HW'].keys():
            self.log.debug("Initializing external ADC")
            self.eADC = _eADC_(**self.CONFIG['HW']['eADC'])
            if not self.eADC.STATUS:
                self.log.critical("Failed to initialise external ADC")
                self.log.error(self.eADC.MSG)
                self.sLED.on('red')
                self.STATUS, self.MSG = False, "Failed to initialise external ADC: {}".format(self.eADC.MSG)
                return self.eADC.STATUS, self.eADC.MSG
            else:
                self.log.info("External ADC initialised successfully.")
        else:
            self.log.info("No external ADC configured.")

        # Initialize Time Management
        self.log.debug("Initializing Time Management")
        self.TIM = _TIM_(config=self.CONFIG['TIM'], CACHE_DIR=self.CACHE_DIR)
        if not self.TIM.STATUS:
            if self.TIM.isLOGIC_RESET:
                self.log.critical("Unable to read cached Times. TIM requested a logic reset! This is likely due to a change in the configuration or a power loss.")
                self.log.error(self.TIM.MSG)
                self.log.info("Resetting picoLogger...\n")
                self.sLED.blink('red')
                reset()
            self.STATUS, self.MSG = False, "Failed to initialise Time Management: {}".format(self.TIM.MSG)
            self.sLED.on('red')
            return self.STATUS, self.MSG
        if self.TIM.isPWR_RESET:
            self.log.critical("Power Loss/Manual Reset detected! Last record time was: {}".format(self.TIM.PRV))
        if self.TIM.isABV_IVL_DLT:
            self.log.warning("Difference between the recording time {} and target recording time: {} is above the desired amount: {}.".format(self.TIM.NOW, self.TIM.CUR, self.TIM.IVL_DLT))
        self.log.info("Time Management initialised successfully.")

        # Initialize Sensors
        self.log.debug("Initializing Sensors")
        self.SEN = SEN(config=self.CONFIG['SEN'],
                       TIM=self.TIM,
                       DATA_DIR=self.DAT_DIR,
                       REC_DIR=self.REC_DIR,
                       eADC=self.eADC,
                       fname_SMS=self.fname_SMS,
                       fname_OW=self.fname_OW)
        if not self.SEN.STATUS:
            self.log.critical("Failed to initialise Sensors")
            self.log.error(self.SEN.MSG)
            self.sLED.on('red')
            self.STATUS, self.MSG = False, "Failed to initialise Sensors: {}".format(self.SEN.MSG)
            return self.STATUS, self.MSG
        self.log.info("Sensors initialised successfully.")

        # Initialize System
        self.log.debug("Initializing System")
        self.SYS = SYS(config=self.CONFIG['SYS'],
                       TIM=self.TIM,
                       DATA_DIR=self.DAT_DIR,
                       REC_DIR=self.REC_DIR,
                       eADC=self.eADC,
                       fname_BAT=self.fname_BAT,
                       fname_iTEMP=self.fname_iTEMP)
        if not self.SYS.STATUS:
            self.log.critical("Failed to initialise System")
            self.log.error(self.SYS.MSG)
            self.sLED.on('red')
            self.STATUS, self.MSG = False, "Failed to initialise System: {}".format(self.SYS.MSG)
            return self.STATUS, self.MSG
        self.log.info("System initialised successfully.")

        self.sLED.flash('green')
        self.sLED.off()
        self.log.info("picoLogger activated successfully.")
        self.STATUS, self.MSG = True, "picoLogger activated successfully."
        return self.STATUS, self.MSG

    def record(self):
        """
        Record the current state of the picoLogger.

        This method reads the sensors and logs the data to the SD card.
        """
        self.log.info("Recording current state of picoLogger")

        # Record data from Sensors
        self.log.debug("Reading SMS sensors")
        self.sLED.on('blue')
        self.STATUS, self.MSG = self.SEN.record()
        if not self.STATUS:
            self.log.error("Failed to read/write sensors: {}".format(self.MSG))
            self.sLED.on('red')
            return self.STATUS, self.MSG
        self.log.info("Sensors read successfully.")
        self.log.debug("Sensors 'DAT': {}".format(self.SEN.DAT))
        self.sLED.dual_flash('green', 'blue', c1_ms=150, c2_ms=100)
        

        # Read data from System
        self.log.debug("Reading System sensors")
        self.sLED.on('magenta')
        self.STATUS, self.MSG = self.SYS.record()
        if not self.STATUS:
            self.log.error("Failed to read system sensors: {}".format(self.MSG))
            self.sLED.on('red')
            return self.STATUS, self.MSG
        self.log.info("System sensors read successfully.")
        self.log.debug("System 'DAT': {}".format(self.SYS.DAT))
        self.sLED.dual_flash('green', 'magenta', c1_ms=150, c2_ms=100)

        self.STATUS, self.MSG = True, "picoLogger recorded successfully."
        return self.STATUS, self.MSG
    
    def update(self):
        """
        Update the picoLogger's time management and next record time.
        
        This method updates the next record time and caches the current and previous times.
        """
        self.log.info("Updating picoLogger 'Times'")
        self.sLED.on('white')
        
        # Update time management
        self.TIM.update()
        if not self.TIM.STATUS:
            self.log.critical("Failed to update 'Times': {}".format(self.TIM.MSG))
            self.sLED.on('red')
            self.STATUS, self.MSG = False, "Failed to update 'Times': {}".format(self.TIM.MSG)
            return self.STATUS, self.MSG
        
        self.log.info("'Times' updated successfully.")
        self.log.debug("Current Time: {}".format(self.TIM.CUR))
        self.log.debug("Next Record Time: {}".format(self.TIM.NXT))

        self.time_end = ticks_ms()
        self.EXE_ms = ticks_diff(self.time_end, self.time_start)
        self.log.info("picoLogger updated successfully in {} ms.".format(self.EXE_ms))

        self.log.debug("Caching Execution Time")
        with open(self.TIM.fEXE_ms, 'w') as f:
            if int(self.TIM.WAK_HST.total_seconds()) != int(self.CONFIG['TIM']['wake_haste_s']):
                f.write(str(max(self.EXE_ms, int(self.TIM.WAK_HST.total_seconds()*1000))) + '\n')
            else:
                f.write(str(self.EXE_ms) + '\n')
        self.log.info("Execution Time cached successfully.")

        self.sLED.dual_flash('green', 'white', c1_ms=150, c2_ms=100)
        self.sLED.off()
        self.log.info("picoLogger updated successfully.")
        self.STATUS, self.MSG = True, "picoLogger updated successfully"
        return self.STATUS, self.MSG

    def deactivate(self):
        """
        Deactivate the picoLogger.

        This method powers off the peripherals and unmounts the SD card.
        """
        self.log.info("--------------------- Deactivating picoLogger ---------------------")
        
        # Deactivate RTC
        STATUS, MSG = self.RTC.deactivate()
        if STATUS:
            self.log.info("RTC deactivated successfully.")
        else:
            self.log.error("Failed to deactivate RTC: {}".format(MSG))
            self.sLED.on('red')
            self.STATUS, self.MSG = STATUS, MSG
            return self.STATUS, self.MSG
        
        # Deactivate external ADC (if configured)
        if hasattr(self, 'eADC') and self.eADC.STATUS:
            STATUS, MSG = self.eADC.deactivate()
            if STATUS:
                self.log.info("External ADC deactivated successfully.")
            else:
                self.log.error("Failed to deactivate external ADC: {}".format(MSG))
                self.sLED.on('red')
                self.STATUS, self.MSG = STATUS, MSG
                return self.STATUS, self.MSG
            
        self.log.update_config(**self.default_ini_config)  # Reset logger to default config

        # Deactivate SD Card
        STATUS, MSG = self.SDC.deactivate()
        if STATUS:
            self.log.info("SD Card deactivated successfully.")
        else:
            self.log.error("Failed to unmount SD Card: {}".format(MSG))
            self.sLED.on('red')
            self.STATUS, self.MSG = STATUS, MSG
            return self.STATUS, self.MSG
        
        # Power off peripheral devices
        self.sLED.flash('orange', on_ms=100, off_ms=50)
        self.log.debug("Powering off peripheral devices")
        if self.PWR.value() == 0:
            self.log.warning("Power was already off! Keeping it off.")
        else:
            self.PWR.value(0)
        pause_ms(100)
        self.log.info("picoLogger deactivated successfully.")

        self.STATUS, self.MSG = True, "picoLogger deactivated successfully."
        return self.STATUS, self.MSG
    
    def sleep(self, mode='deep'):
        """
        Put the picoLogger to sleep until the next record time.
        This method calculates the milliseconds until the next record time and puts the device to sleep.
        Args:
            mode Literal['light', 'deep']:
                The sleep mode to use. 'light' mode will use the standard sleep, while 'deep' mode will use deep sleep. Default is 'deep'.
        """
        self.log.info("Putting picoLogger to sleep until next record time")

        # Calculate milliseconds until next record time
        self.STATUS, self.MSG = self.TIM.get_ms_until_next_rec()
        if not self.STATUS:
            self.log.error("Failed to calculate milliseconds until next record: {}".format(self.MSG))
            return self.STATUS, self.MSG

        self.sLED.flash('dim-red', on_ms=100, off_ms=75)
        # Sleep until next record time
        if mode == 'deep':
            self.log.info("Putting picoLogger to deep sleep for {} ms.".format(self.TIM.SLEEP_ms))
            deepsleep(self.TIM.SLEEP_ms)
        elif mode == 'light':
            self.log.info("Putting picoLogger to light sleep for {} ms.".format(self.TIM.SLEEP_ms))
            lightsleep(self.TIM.SLEEP_ms)
        else:
            self.log.error("Invalid sleep mode: {}. Use 'light' or 'deep'.".format(mode))
            return False, "Invalid sleep mode: {}. Use 'light' or 'deep'.".format(mode)
