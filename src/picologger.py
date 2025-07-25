from machine import Pin, ADC, SPI, I2C, RTC
from machine import unique_id
from machine import deepsleep
from gc import collect as collect_garbage
from uos import mount, umount, VfsFat
from utime import localtime, ticks_ms, ticks_diff
from utime import time as epoch_time, sleep_ms as pause_ms
from datetime import datetime

from logging import Logger
from sled import sLED
from sdcard import SDCard
from onewire import OneWire
from ds18x20 import DS18X20
from ds3231 import DS3231
from ads1115 import ADS1115

from config import *

class picoLogger():
    STATUS, MSG = None, None

    def __init__(self):
        """Initializes a picoLogger instance"""
        self.start_tick = ticks_ms()
        self.log = Logger(path=Logger.default_logfile, level='DEBUG', uart_id=UART_ID, uart_baud=UART_BAUD, uart_tx=UART_TX, uart_rx=UART_RX)
        self.led = sLED(R=SLED_R, G=SLED_G, B=SLED_B)
        if SLED_n_flash is not None:
            self.led.update(n_flash=SLED_n_flash)
        if SLED_on_ms is not None:
            self.led.update(on_ms=SLED_on_ms)
        if SLED_off_ms is not None:
            self.led.update(off_ms=SLED_off_ms)
        self.log.br(n=3)
        self.log.debug("Initialising PicoLogger")
        self.log.debug("Setting paths")
        mID = unique_id().hex()
        ROOT_PATH = '/sd/'
        self.fDATA = ROOT_PATH + 'data-{}.csv'.format(mID)
        self.fLOG = ROOT_PATH + 'picoLogger-{}.log'.format(mID)
        self.log.debug("Initialising Function Toggle")
        self.FN = Pin(FN_PIN, Pin.IN)
        self.log.debug("Listening to Function Toggle on Pin {}".format(FN_PIN))
        self.log.debug("Paths set. Writing data to {} and log to {}".format(self.fDATA, self.fLOG))

    def _init_PWR(self, turn_on=True):
        self.log.debug("Initialising Power Switch")
        self.PWR = Pin(PWR_PIN, Pin.OUT)
        self.log.debug("Power Switch initialised on Pin {}".format(PWR_PIN))
        if self.PWR.value():
            self.log.warning("Power Rail was already ON")
        if turn_on:
            self.PWR.on()
        # Wait for power rail to stabilise
        pause_ms(50)
        self.log.info("Powered Rail turned ON")

    def _init_SD(self):
        self.log.debug("Initialising SD card")
        try:
            self.log.debug("Initialising SD Card on SPI ID {} with SCK={}, MOSI={}, MISO={}, CS={}".format(SDC_SPI_ID, SDC_SPI_SCK, SDC_SPI_MOSI, SDC_SPI_MISO, SDC_SPI_CS))
            spi = SPI(SDC_SPI_ID, sck=Pin(SDC_SPI_SCK), mosi=Pin(SDC_SPI_MOSI), miso=Pin(SDC_SPI_MISO))
            cs = Pin(SDC_SPI_CS, Pin.OUT)
            sd = SDCard(spi, cs)
            vfs = VfsFat(sd)
            mount(vfs, '/sd')
        except Exception as e:
            self.log.error("Failed to mount SD card: {}".format(str(e)))
            self.STATUS, self.MSG = False, "ERROR: SD card mount failed! Error: {}".format(str(e))
            return
        self.log.info("SD card mounted successfully")
        return True, ""
    
    def _init_RTC(self, set_to_machine=False, set_from_machine=False):
        self.log.debug("Initialising RTC")
        self.iRTC = RTC()
        self.log.debug("Initialising RTC on I2C ID {} with SDA={}, SCL={}, FREQ={}".format(RTC_I2C_ID, RTC_I2C_SDA, RTC_I2C_SCL, RTC_I2C_FREQ))
        try:
            i2c = I2C(RTC_I2C_ID, sda=Pin(RTC_I2C_SDA), scl=Pin(RTC_I2C_SCL), freq=RTC_I2C_FREQ)
            self.log.debug("I2C devices found: {}".format(i2c.scan()))
            self.eRTC = DS3231(i2c)
            if self.eRTC.OSF():
                self.eRTC._OSF_reset()
                self.log.critical("RTC Oscillator was stopped! Re-enabling it. Time is most probably off! Please check the RTC battery.")
        except Exception as e:
            self.log.error("Failed to initialise RTC: {}".format(str(e)))
            return False, "ERROR: RTC initialisation failed! Error: {}".format(str(e))
        self.log.info("RTC initialised successfully")
        if set_to_machine:
            self.log.debug("Updating Machine time from RTC")
            self.iRTC.datetime(self.eRTC.datetime())
            self.log.info("Machine time updated from RTC")
        if set_from_machine:
            self.log.debug("Setting RTC time to Machine time")
            self.eRTC.datetime(localtime()[:6])
            self.log.info("RTC time set to Machine time")
        return True, ""
    
    def _init_eADC(self):
        self.log.debug("Initialising ADC: ADS1115")
        try:
            i2c = I2C(EADC_I2C_ID, sda=Pin(EADC_I2C_SDA), scl=Pin(EADC_I2C_SCL), freq=EADC_I2C_FREQ)
            self.log.debug("I2C devices found: {}".format(i2c.scan()))
            self.eADC = ADS1115(i2c=i2c)
            self.eADC.set_gain(ADS1115.GAIN_4_096V)
            self.ADC_CH0_VD_R1 = EADC_CH0_VD_R1
            self.ADC_CH0_VD_R2 = EADC_CH0_VD_R2
        except Exception as e:
            self.log.error("Failed to initialise ADC: {}".format(str(e)))
            return False, "ERROR: ADC initialisation failed! Error: {}".format(str(e))
        self.log.info("ADC: ADS1115 initialised successfully")
        return True, ""
        
    def setup(self):
        """Sets up the picoLogger and prepares it for deployment"""
        self.log.debug("Setting up and Testing PicoLogger")
        self.led.on('yellow')
        print("Setting up picoLogger...")
        # Power Switch
        self._init_PWR(turn_on=True)
        print("Power Rail turned ON")
        # SD Card
        self.STATUS, self.MSG = self._init_SD()
        if not self.STATUS:
            print(f"ERROR: Unable to initialise SD Card {self.MSG}")
            self.led.on('red')
            return
        print("SD Card mounted successfully")
        # Update logfile path
        self.log.debug("Updating logfile path")
        self.STATUS, self.MSG = self.log.update(path=self.fLOG)
        if not self.STATUS:
            print(f"ERROR: Unable to update log file path {self.MSG}")
            self.led.on('red')
            return
        self.log.debug("Log file path updated to {}".format(self.fLOG))
        print("Log file path updated to {}".format(self.fLOG))
        # RTC
        self.STATUS, self.MSG = self._init_RTC(set_from_machine=True)
        if not self.STATUS:
            print(f"ERROR: Unable to initialise RTC {self.MSG}")
            self.led.on('red')
            return
        print("RTC initialised successfully")
        # ADC: ADS1115
        self.STATUS, self.MSG = self._init_eADC()
        if not self.STATUS:
            print(f"ERROR: Unable to initialise ADC {self.MSG}")
            self.led.on('red')
            return
        print("ADC: ADS1115 initialised successfully")
        # Read Sensors
        self.log.debug("Reading Sensors")
        self.STATUS, self.MSG = self._read()
        if not self.STATUS:
            print(f"ERROR: Unable to read sensors {self.MSG}")
            self.led.on('red')
            return
        self.log.debug("Sensors read successfully")
        print("Sensors read successfully. Data: {}".format(self.DATA))
        # Write Data header
        self.log.debug("Writing Data header to file: {}".format(self.fDATA))
        try:
            with open(self.fDATA, 'w') as f:
                f.write('timestamp,key,value\n')
        except Exception as e:
            self.log.error("Failed to write header to data file: {}".format(str(e)))
            print(f"ERROR: Unable to write header to data file {str(e)}")
            self.led.on('red')
            return
        self.log.info("PicoLogger set-up successfully")
        self.led.off()
        self.log.debug("Deactivating picoLogger")
        self.log.info("PicoLogger is ready for deployment!")
        self.deactivate()
        print("PicoLogger is ready for deployment")
        if not self.FN.value():
            print("WARNING: Function Toggle is OFF. To record data, please toggle the Function button ON.")
        return True, ""
          
    def activate(self):
        """Activates the picoLogger and prepares it for data recording"""
        self.log.debug("Activating PicoLogger")
        self.led.on('yellow')
        # Power Switch
        self._init_PWR(turn_on=True)
        # SD Card
        self.STATUS, self.MSG = self._init_SD()
        if not self.STATUS:
            self.led.on('red')
            return False, self.MSG
        # Update logfile path
        self.log.debug("Updating logfile path")
        self.STATUS, self.MSG = self.log.update(path=self.fLOG)
        if not self.STATUS:
            self.led.on('red')
            return False, self.MSG
        self.log.debug("Log file path updated to {}".format(self.fLOG))
        # RTC
        self.STATUS, self.MSG = self._init_RTC(set_to_machine=True)
        if not self.STATUS:
            self.led.on('red')
            return False, self.MSG
        # ADC: ADS1115
        self.STATUS, self.MSG = self._init_eADC()
        if not self.STATUS:
            self.led.on('red')
            return False, self.MSG
        self.log.info("PicoLogger activated successfully")
        self.led.off()
        return True, ""
    
    def _read(self):
        self.DATA = {'SM1': [], 'SM2': [], 'SM3': [], 'OW': [], 'BAT': [], 'iTEMP': []}
        # Soil Moisture
        self.log.debug("Acquiring Data: SMS")
        self.led.on('blue')
        if SMS1_CH is not None:
            for _ in range(SMS_COUNT):
                self.DATA['SM1'].append(self.eADC.read_raw(SMS1_CH))
                pause_ms(SMS_IVL)
        if SMS2_CH is not None:
            for _ in range(SMS_COUNT):
                self.DATA['SM2'].append(self.eADC.read_raw(SMS2_CH))
                pause_ms(SMS_IVL)
        if SMS3_CH is not None:
            for _ in range(SMS_COUNT):
                self.DATA['SM3'].append(self.eADC.read_raw(SMS3_CH))
                pause_ms(SMS_IVL)
        self.log.debug("SMS data acquisition completed")
        # Soil Temperature
        self.log.debug("Acquiring Data: OneWire")
        self.led.on('magenta')
        try:
            ow = OneWire(Pin(OW_PIN))
            TS = DS18X20(ow)
            roms = TS.scan()
            if roms:
                for _ in range(OW_COUNT):
                    TS.convert_temp()
                    pause_ms(750)
                    self.DATA['OW'].append(TS.read_temp(roms[0]))
                self.log.debug("OneWire data acquisition completed")
            else:
                self.log.critical("No OneWire devices found")
        except Exception as e:
            self.log.error("OneWire data acquisition failed: {}".format(str(e)))
            self.DATA['OW'] = [None] * OW_COUNT
        # Battery
        self.log.debug("Acquiring Data: Battery")
        self.led.on('cyan')
        for _ in range(BAT_COUNT):
            self.DATA['BAT'].append(self.eADC.read_raw(BAT_CH))
            pause_ms(BAT_IVL)
        # Internal Temperature
        self.log.debug("Acquiring Data: Internal Temperature")
        iTEMP_ADC = ADC(4)
        for _ in range(ITEMP_COUNT):
            self.DATA['iTEMP'].append(iTEMP_ADC.read_u16())
            pause_ms(ITEMP_IVL)
        self.led.off()
        return True, ""
    
    def _write(self):
        self.led.on('white')
        timestamp = str(datetime(*localtime()[:6]))
        self.log.debug("Writing Data to file: {}".format(self.fDATA))
        try:
            with open(self.fDATA, 'a') as f:
                data = self.DATA
                write = f.write
                for key in data:
                    vals = data[key]
                    for val in vals:
                        write(timestamp + ',' + key + ',' + str(val) + '\n')
        except Exception as e:
            self.log.error("Failed to write data to file: {}".format(str(e)))
            return False, "ERROR: Data write failed! Error: {}".format(str(e))
        self.log.debug("Data written to file {} successfully".format(self.fDATA))
        self.led.off()
        return True, ""

    def record(self):
        """Records data from sensors and writes it to a file"""
        self.led.on('yellow')
        # Read
        self.log.info("Starting Data Acquisition")
        self.STATUS, self.MSG = self._read()
        if not self.STATUS:
            return False, self.MSG
        self.log.info("Data Aquired successfully")
        # Write
        self.log.debug("Writing Data to file")
        self.STATUS, self.MSG = self._write()
        if not self.STATUS:
            return False, self.MSG
        self.log.info("Data written successfully")
        self.led.flash('green')
        return True, ""
    
    def _get_next_record_time(self):  
        now = epoch_time()
        self.next_record_time_epoch = ((now // REC_IVL) + 1) * REC_IVL
        self.next_record_time_dt = datetime(*localtime(self.next_record_time_epoch)[:6])
    
    def _ms_to_next_record(self):
        now = epoch_time()
        return int((self.next_record_time_epoch - now) * 1000)

    def update(self):
        self.led.on('yellow')
        """Updates the picoLogger state and prepares for the next recording"""
        self.log.debug("Updating PicoLogger state")
        self._get_next_record_time()
        self.log.info("Next record time is at {}".format(str(self.next_record_time_dt)))
        sleep_time = self._ms_to_next_record()
        self.log.debug("Sleeping for {} ms until next record".format(sleep_time))
        self.led.off()
        return True, ""

    def deactivate(self):
        """Deactivates the picoLogger and cleans up resources"""
        self.log.debug("Calculating execution time")
        execution_time = ticks_diff(ticks_ms(), self.start_tick)
        self.log.debug("Execution time: {} ms".format(execution_time))
        self.log.debug("Deactivating PicoLogger")
        self.log.debug("Unmounting SD card")
        try:
            umount('/sd')
        except Exception as e:
            self.log.error("Failed to unmount SD card: {}".format(str(e)))
        Pin(SDC_SPI_CS, Pin.IN, pull=None)
        Pin(SDC_SPI_SCK, Pin.IN, pull=None)
        Pin(SDC_SPI_MOSI, Pin.IN, pull=None)
        Pin(SDC_SPI_MISO, Pin.IN, pull=None)
        Pin(RTC_I2C_SDA, Pin.IN, pull=None)
        Pin(RTC_I2C_SCL, Pin.IN, pull=None)
        Pin(EADC_I2C_SDA, Pin.IN, pull=None)
        Pin(EADC_I2C_SCL, Pin.IN, pull=None)
        Pin(OW_PIN, Pin.IN, pull=None)
        pause_ms(50)  # Wait for power rail to stabilise
        self.PWR.off()
        pause_ms(50)  # Wait for power rail to turn off
        return True, ""
    
    def sleep(self):
        sleep_time = self._ms_to_next_record()
        collect_garbage()
        pause_ms(250) # Wait for any pending operations to complete
        deepsleep(sleep_time)