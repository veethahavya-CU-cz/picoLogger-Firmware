## picoLogger Firmware

This repository contains the MicroPython firmware for the picoLogger, the data acquisition and logging system at the heart of the picoSMS (pico Soil Moisture Station). The picoLogger is a low-cost, open-source, and robust datalogger designed for long-term, off-grid measurement of soil moisture and temperature; however, other sensors can be integrated as needed over the free I2C/SPI buses or via the three free ADC and the 10 free GPIO pins. Additionally, multiplexers can be used to further expand the number of sensors connected.

This work is part of a scientific publication and is designed to be reproducible. For a comprehensive overview of the hardware, software, and experimental validation, please refer to the associated manuscript.

### Features

- **Low-Cost & Open-Source:** Built with affordable, off-the-shelf components and open-source software.
- **Advanced Power Management:** Intelligent MOSFET-based power switching system for ultra-low power consumption during deep-sleep cycles, extending battery life significantly.
- **Solar Charging System:** Integrated solar panel charging with overvoltage protection (zener clamp), reverse voltage protection (schottky diodes), and real-time battery voltage monitoring.
- **Raspberry Pi Pico:** Utilises the powerful and flexible RP2040 microcontroller with extensive GPIO capabilities.
- **MicroPython:** Programmed in MicroPython for ease of development, maintenance, and rapid prototyping.
- **Multi-Sensor Support:** Supports up to 3x soil moisture sensors and 3x temperature sensors simultaneously with expandable I2C/SPI buses for additional sensors.
- **Precision Data Acquisition:** 16-bit ADS1115 ADC for high-resolution sensor readings and battery monitoring with configurable sampling rates.
- **Real-Time Data Logging:** Accurate timestamping with DS3231 RTC module and reliable CSV data storage on microSD cards.
- **User Interface:** RGB status LED for system status indication and toggle switches for power control and function selection.
- **Modular & Configurable:** Centralized configuration system allowing easy customization of pins, sensors, measurement intervals, and power management settings.
- **Remote Management:** Comprehensive helper scripts for firmware deployment, data retrieval, and system maintenance.

### Hardware Overview

The picoLogger integrates several key components in a sophisticated, power-optimized design:

- **Compute Module:** Raspberry Pi Pico (RP2040 dual-core ARM Cortex-M0+ microcontroller)
- **High-Resolution ADC:** ADS1115 16-bit ADC with programmable gain amplifier (for precise soil moisture readings and battery voltage monitoring)
- **Precision Timekeeping:** DS3231 RTC Module with temperature-compensated crystal oscillator (±2ppm accuracy)
- **Reliable Storage:** MicroSD Card Module with SPI interface for robust data logging
- **Advanced Power Management System:**
    - 3000mAh LiPo Battery with integrated protection circuit
    - 1W Solar Panel with intelligent charging capabilities
    - Zener clamp overvoltage protection (5.6V/1.3W Zener + 6.8Ω current limiting resistor)
    - DFRobot DFR0264 Solar Charging Module with MPPT-like functionality
    - Precision voltage divider (R1=2.2kΩ, R2=22kΩ) for real-time battery monitoring
    - Schottky diode array for reverse voltage and backflow protection
    - MOSFET IRFZ44N low-side switching for intelligent peripheral power control
- **User Interface & Status:**
    - RGB Status LED (Red, Green, Blue) for comprehensive system status indication
    - Dual toggle switches (Main power ON/OFF, Function mode selection)
- **Multi-Sensor Array:**
    - 3x Capacitive Low-Cost Soil Moisture Sensors (LCSMS) with individual ADC channels
    - 3x DS18B20 Digital Temperature Sensors on shared One-Wire bus with parasite power capability

### Software Architecture

The firmware is organized into a modular structure for clarity and ease of modification.

- **`main.py`:** The main entry point and control script. It initializes the hardware, manages the measurement-sleep cycle, and handles data logging.
- **`src/config.py`:** A centralized configuration file for all user-definable parameters, such as pin assignments, I2C/SPI bus settings, and data acquisition intervals.
- **`src/picologger.py`:** Contains the core `picoLogger` class, encapsulating the main operational logic.
- **`lib/`:** A directory containing the necessary driver modules for the peripheral components (ADS1115, DS3231, SD card, etc.).

### Hardware Wiring

The following table details the default wiring connections between the Raspberry Pi Pico and the peripheral modules. These connections are defined in `src/config.py` and can be modified to suit different hardware configurations.

#### Raspberry Pi Pico Pin Connections

| RPi Pico Pin | Module              | Pin/Function        | Notes                                    |
| ------------- | ------------------- | ------------------- | ---------------------------------------- |
| GP0 (I2C0 SDA) | DS3231 RTC Module   | SDA                 | I2C Bus 0 for Real-Time Clock            |
| GP1 (I2C0 SCL) | DS3231 RTC Module   | SCL                 | I2C Bus 0 for Real-Time Clock            |
| GP2 (SPI0 SCK) | MicroSD Card Module | SCK                 | SPI Bus 0 for SD Card                    |
| GP3 (SPI0 MOSI)| MicroSD Card Module | MOSI                | SPI Bus 0 for SD Card                    |
| GP4 (SPI0 MISO)| MicroSD Card Module | MISO                | SPI Bus 0 for SD Card                    |
| GP5            | MicroSD Card Module | CS (Chip Select)    |                                          |
| GP6 (I2C1 SDA) | ADS1115 ADC Module  | SDA                 | I2C Bus 1 for Analog-to-Digital Converter|
| GP7 (I2C1 SCL) | ADS1115 ADC Module  | SCL                 | I2C Bus 1 for Analog-to-Digital Converter|
| GP12 (UART0 TX)| Debugging           | TX                  | UART for debugging output                |
| GP13 (UART0 RX)| Debugging           | RX                  | UART for debugging output                |
| GP14          | 3x DS18B20 STS      | Data (S)            | One-Wire interface for temperature sensors|
| GP15          | Toggle Switch #2    | Function Toggle     | Toggles data recording ON/OFF (to 3V3_OUT or GND)|
| GP18          | Status LED          | Blue Cathode        |                                          |
| GP19          | Status LED          | Green Cathode       |                                          |
| GP20          | Status LED          | Red Cathode         |                                          |
| GP21          | MOSFET IRFZ44N      | Gate                | Switches power to sensors and modules    |
| 3V3_EN        | Toggle Switch #1    | Power Control       | ON/OFF switch (floating or GND)         |
| 3V3_OUT       | Status LED + ADS1115 + DS3231 + SD Card + 3x LCSMS + 3x DS18B20| (+) Power | 3.3V power supply to all modules |
| GND           | Multiple            | Ground              | Common ground connection                 |
| VSYS          | Voltage Divider     | Through Schottky    | Battery power input via voltage protection|

#### Power Distribution

| Power Rail           | Connected Modules                      | Control Method                           |
| -------------------- | -------------------------------------- | ---------------------------------------- |
| Pico 3V3_OUT        | Status LED, ADS1115, DS3231, SD Card, 3x LCSMS, 3x DS18B20 | Always on (when Pico is powered) |
| MOSFET Switched GND | ADS1115, DS3231, SD Card, 3x LCSMS, 3x DS18B20 | Controlled by Pico GP21 |
| Pico GND           | Status LED, MOSFET Source              | Permanent ground reference               |

**Note:** The MOSFET (IRFZ44N) acts as a low-side switch, controlling the ground path for all peripheral modules. When GP21 is HIGH, the MOSFET conducts, connecting peripheral grounds to system ground, powering the modules. When GP21 is LOW, the MOSFET is off, cutting power to all peripherals for power saving.

#### ADS1115 ADC Module Connections

| ADS1115 Pin  | Connected To         | Notes                                    |
| ------------ | -------------------- | ---------------------------------------- |
| VDD          | Pico 3V3_OUT        | Power supply                             |
| GND          | MOSFET Switched Rail | Ground via power switching              |
| SCL          | Pico GP7 (I2C1 SCL) | I2C clock line                          |
| SDA          | Pico GP6 (I2C1 SDA) | I2C data line                           |
| A0 (CH0)     | Voltage Divider     | Battery voltage monitoring               |
| A1 (CH1)     | LCSMS #1            | Soil moisture sensor #1                  |
| A2 (CH2)     | LCSMS #2            | Soil moisture sensor #2                  |
| A3 (CH3)     | LCSMS #3            | Soil moisture sensor #3                  |

#### Power System Connections

| Component               | Connection From      | Connection To        | Notes                                    |
| ----------------------- | -------------------- | -------------------- | ---------------------------------------- |
| Solar Panel (+)         | Solar Panel         | 6.8Ω Resistor       | Through current limiting resistor        |
| 6.8Ω Resistor           | Solar Panel (+)     | Zener Anode         | Current limiting for zener protection    |
| Zener Diode (5.6V/1.3W) | Anode (Resistor)   | Cathode (VIN+)      | Voltage clamp protection circuit         |
| Solar Panel (-)         | Solar Panel         | Solar Charger VIN(-) | Direct ground connection                 |
| Solar Charger VIN(+)    | Zener Cathode      | Charging Circuit     | Protected solar input                    |
| Solar Charger VIN(-)    | Solar Panel (-)     | Charging Circuit     | Solar input ground                       |
| Solar Charger BAT(+)    | 3000mAh LiPo (+)    | Battery Charging     | Direct battery connection                |
| Solar Charger BAT(-)    | 3000mAh LiPo (-)    | Battery Charging     | Direct battery connection                |
| Solar Charger VOUT(+)   | Voltage Divider + Schottky | System Power    | Feeds both voltage monitoring and Pico   |
| Solar Charger VOUT(-)   | Pico GND           | System Ground        | Direct connection                        |
| Voltage Divider (Input) | Solar Charger VOUT(+) | R1 (2.2kΩ)       | Battery voltage sensing input            |
| Voltage Divider (Output)| Between R1 & R2    | ADS1115 CH0         | Scaled voltage (≈0.91× input voltage to clip the max BAT voltage of 4.2V to 3.8V)   |
| Voltage Divider (R2)    | Between R1 & R2    | GND (22kΩ)          | Completes voltage divider to ground      |
| Schottky Diodes         | Solar Charger VOUT(+) | Pico VSYS        | Reverse voltage protection for Pico      |
| MOSFET IRFZ44N (Gate)   | Pico GP21          | Power Switching      | Controls sensor power                    |
| MOSFET IRFZ44N (Source) | Pico GND           | Ground Reference     | MOSFET ground connection                 |
| MOSFET IRFZ44N (Drain)  | Peripheral GNDs    | Switched Ground      | Controls ground to all peripherals       |

#### Sensor Connections

| Sensor Type    | Quantity | (+) Power     | (-) Ground           | Signal/Data          |
| -------------- | -------- | ------------- | -------------------- | -------------------- |
| LCSMS          | 3x       | Pico 3V3_OUT  | MOSFET Switched Rail | ADS1115 CH1,CH2,CH3  |
| DS18B20 (STS)  | 3x       | Pico 3V3_OUT  | MOSFET Switched Rail | Pico GP14 (One-Wire) |

#### System Schematic

```
                    SOLAR PANEL
                    [+]     [-]
                     |       |
                     |       |
                 6.8Ω|       |
                 ────|       |
                     |       |
                 ┌───▼───┐   |
                 │ 5.6V  │   |
                 │ Zener │   |
                 │   │   │   |
                 └───┼───┘   |
                     |       |
                     |       |
               SOLAR CHARGER MODULE (DFRobot DFR0264)
               VIN[+]  VIN[-]  BAT[+]  BAT[-]  VOUT[+]  VOUT[-]
                 |       |       |       |       |        |
                 |       |    3000mAh    |       |        |
                 |       |    LiPo       |       |        |
                 |       |    [+] [-]    |       |        |
                 |       |      |  |     |       |        |
                 |       |      |  |     |       |        |
                 |       +------+  +-----+       |        |
                 |                               |        |
                 |                         VOUT(+)──┬─────┼─── To Schottky Diodes
                 |          Voltage Divider     │   |     |
                 |          R1=2.2kΩ            │   |     |
                 |             │                │   |     |
                 |             ├── ADS1115 CH0  │   |     |
                 |             │                │   |     |
                 |          R2=22kΩ             │   |     |
                 |             │                │   |     |
                 +──────────GND───────────VOUT(-)───┘   __|
                                               |       |
                                    Schottky   |       |
                                    Diodes ----|       |
                                               |       |
                    RASPBERRY PI PICO          |       |
                    ┌─────────────────────────┐|       |
         SW1 ──────►│3V3_EN            VSYS  ├┘        |
                    │                        │         |
                    │3V3_OUT──┬──────────────┼─────────┼─── (+) Power Rail
                    │         │              │         │    (Status LED, ADS1115,
                    │         │              │         │     DS3231, SD Card, 
                    │         │              │         │     LCSMS×3, DS18B20×3)
                    │GP0──────┼──────────────┼── DS3231 SDA
                    │GP1──────┼──────────────┼── DS3231 SCL  
                    │GP2──────┼──────────────┼── SD Card SCK
                    │GP3──────┼──────────────┼── SD Card MOSI
                    │GP4──────┼──────────────┼── SD Card MISO
                    │GP5──────┼──────────────┼── SD Card CS
                    │GP6──────┼──────────────┼── ADS1115 SDA
                    │GP7──────┼──────────────┼── ADS1115 SCL
                    │GP12─────┼──────────────┼── UART TX (Debug)
                    │GP13─────┼──────────────┼── UART RX (Debug)
                    │GP14─────┼──────────────┼── DS18B20×3 (One-Wire)
         SW2 ──────►│GP15     │              │
                    │GP18─────┼──────────────┼── Status LED (Blue)
                    │GP19─────┼──────────────┼── Status LED (Green)
                    │GP20─────┼──────────────┼── Status LED (Red)
                    │GP21─────┼──────────────┼── MOSFET Gate
                    │         │              │
                    │GND──────┼──────────────┼───┬───────────────── GND
                    └─────────────────────────┘  │               │
                                                 │         MOSFET IRFZ44N
                                                 │         ┌─────┐ │
                                                 │    Gate │  │  │ │
                                                 │    ◄────┤  │  │ │
                                                 │         │  │  │ │
                                    System GND ──┴── Source│  │  │Drain ── Switched GND Rail
                                                           └─────┘     (ADS1115, DS3231,
                                                                       SD Card, LCSMS×3,
                                                                       DS18B20×3)

    ADS1115 CONNECTIONS:           SENSORS:
    CH0 ← Voltage Divider         LCSMS #1 ← ADS1115 CH1
    CH1 ← LCSMS #1                LCSMS #2 ← ADS1115 CH2  
    CH2 ← LCSMS #2                LCSMS #3 ← ADS1115 CH3
    CH3 ← LCSMS #3                DS18B20×3 ← GP14 (One-Wire Bus)

    SWITCHES:
    SW1: Power ON/OFF (3V3_EN ↔ Floating/GND)
    SW2: Function Toggle (GP15 ↔ 3V3_OUT/GND)
```

### Usage

#### Prerequisites

To deploy the firmware to a picoLogger device, you will need a computer with Python and the following tools installed:

- **`mpremote`:** A tool to remotely control a MicroPython device. Install it via pip:
  ```bash
  pip install mpremote
  ```
- **`mpy-cross`:** A tool to compile Python scripts into more efficient `.mpy` bytecode. It should be compiled from the MicroPython repository, matching the version on your device.

#### Deployment

The `flash.py` script automates the process of compiling and transferring the firmware to the picoLogger.

1.  Connect the picoLogger to your computer via USB.
2.  Run the script:
    ```bash
    python flash.py
    ```

The script will:
1.  Compile the Python files in `src/` and `lib/` into `.mpy` bytecode.
2.  Transfer the compiled library files to the `/lib` directory on the device.
3.  Copy `main.py` to the root directory of the device.

The device will then be ready to operate autonomously.

#### Data Cleanup

The `cleanup.py` script provides a safe way to delete data and log files from the device's internal flash and the SD card. This is useful when preparing the device for a new deployment.

1.  Connect the picoLogger to your computer.
2.  Run the script:
    ```bash
    python cleanup.py
    ```
This will remove all `.csv` and `.log` files, resetting the storage without affecting the core application files.
