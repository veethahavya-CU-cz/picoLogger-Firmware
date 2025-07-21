# PicoAL.py
from os import path, makedirs
from dataclasses import dataclass, field, asdict
from typing import Literal, Tuple
from json import dump as dump_json


@dataclass
class LOG:
    path: str = '/sd/picoLogger.log'
    level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'DEBUG'

@dataclass
class UART:
    id: int = 0
    baudrate: int = 9600
    tx: int = 16
    rx: int = 17


@dataclass
class SDC:
    ID: int = 0
    CS: int = 5
    MOSI: int = 3
    MISO: int = 4
    SCK: int = 2

@dataclass
class RTC:
    ID: int = 0
    SDA: int = 0
    SCL: int = 1

@dataclass
class eADC:
    ID: int = 1
    SDA: int = 6
    SCL: int = 7

@dataclass
class SWITCH:
    PWR: int = 21  # Pin to power peripherals
    FN: int = 15   # Function button pin

@dataclass
class sLED:
    R: int = 20
    G: int = 19
    B: int = 18

@dataclass
class HW:
    VERSION: Literal['1.0'] = '1.0'
    SDC: 'SDC' = field(default_factory=SDC)
    RTC: 'RTC' = field(default_factory=RTC)
    eADC: 'eADC' = field(default_factory=eADC)
    UART: 'UART' = field(default_factory=UART)
    SWITCH: 'SWITCH' = field(default_factory=SWITCH)
    sLED: 'sLED' = field(default_factory=sLED)


@dataclass
class SMS:
    loc: Literal['ADS1115', 'INT'] = 'ADS1115'
    SMS1_CH: int = 1
    SMS2_CH: int = 2
    SMS3_CH: int = 3

@dataclass
class OW:
    PIN: int = 14

@dataclass
class SEN:
    OW: 'OW' = field(default_factory=OW)
    SMS: 'SMS' = field(default_factory=SMS)


@dataclass
class BAT:
    loc: Literal['INT', 'iADC', 'eADC'] = 'eADC'
    CH: int = 0
    R1: float = 22_000
    R2: float = 220_000

@dataclass
class SYS:
    BAT: 'BAT' = field(default_factory=BAT)


@dataclass
class tREC:
    read_delay: Tuple[int, Literal['H', 'M', 's', 'ms']] = (25, 'ms')
    n_read: int = 5

    read_delay_ms: int = field(init=False)
    
    @staticmethod
    def __convert_to_ms(interval: Tuple[int, str]) -> int:
        val, unit = interval
        if unit.lower() == 'ms':
            return val
        elif unit.lower() == 's':
            return val * 1000
        elif unit.lower() == 'm':
            return val * 60 * 1000
        elif unit.lower() == 'h':
            return val * 60 * 60 * 1000
        raise ValueError("Invalid time unit. Use 'H', 'M', 's', or 'ms'.")

    def __post_init__(self):
        self.read_delay_ms = tREC.__convert_to_ms(self.read_delay)
    def update(self):
        self.read_delay_ms = tREC.__convert_to_ms(self.read_delay)

@dataclass
class TIM:
    interval: Tuple[int, Literal['H', 'M', 's', 'ms']] = (15, 'M')
    delta_interval: Tuple[int, Literal['H', 'M', 's', 'ms']] = (2, 'M')
    wake_haste = (3, 's')
    SMS: 'tREC' = field(default_factory=lambda: tREC(n_read=25))
    OW: 'tREC' = field(default_factory=lambda: tREC(read_delay=(750, 'ms'), n_read=3))
    BAT: 'tREC' = field(default_factory=lambda: tREC(n_read=7))
    iTEMP: 'tREC' = field(default_factory=lambda: tREC(n_read=7))

    interval_s: int = field(init=False)
    delta_interval_s: int = field(init=False)
    wake_haste_s: int = field(init=False)

    @staticmethod
    def __convert_to_s(interval: Tuple[int, str]) -> int:
        val, unit = interval
        if unit.lower() == 'ms':
            return val / 1000
        elif unit.lower() == 's':
            return val
        elif unit.lower() == 'm':
            return val * 60
        elif unit.lower() == 'h':
            return val * 60 * 60
        raise ValueError("Invalid time unit. Use 'H', 'M', 's', or 'ms'.")

    def __post_init__(self):
        self.interval_s = TIM.__convert_to_s(self.interval)
        self.delta_interval_s = TIM.__convert_to_s(self.delta_interval)
        self.wake_haste_s = TIM.__convert_to_s(self.wake_haste)
    
    def update(self):
        self.SMS.update()
        self.OW.update()
        self.BAT.update()
        self.iTEMP.update()
        self.interval_s = TIM.__convert_to_s(self.interval)
        self.delta_interval_s = TIM.__convert_to_s(self.delta_interval)
        self.wake_haste_s = TIM.__convert_to_s(self.wake_haste)


@dataclass
class picoConfig:
    VERSION: Literal['1.0'] = '1.0'

    ID: int = 0
    NAME: str = ''
    LOCATION: str = ''
    DESCRIPTION: str = ''

    LOG: 'LOG' = field(default_factory=LOG)
    HW: 'HW' = field(default_factory=HW)
    SYS: 'SYS' = field(default_factory=SYS)
    SEN: 'SEN' = field(default_factory=SEN)
    TIM: 'TIM' = field(default_factory=TIM)

    def to_json(self, fpath: str):
        """Saves the configuration dataclass to a JSON file."""
        self.TIM.update()
        dirpath = path.dirname(fpath)
        if dirpath:
            makedirs(dirpath, exist_ok=True)
        with open(fpath, 'w') as f:
            dump_json(asdict(self), f, indent=4)

if __name__ == '__main__':
    config = picoConfig()
    config.to_json('picoLogger.json')
    print("Generated 'picoLogger.json' with default settings.")