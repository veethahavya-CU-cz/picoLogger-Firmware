## picoLogger Firmware

This repository contains the MicroPython firmware for the picoLogger, the data acquisition and logging system at the heart of the picoSMS (pico Soil Moisture Sensor). The picoLogger is a low-cost, open-source, and robust monitoring station designed for long-term, off-grid measurement of soil moisture and temperature.

This work is part of a scientific publication and is designed to be highly reproducible. For a comprehensive overview of the hardware, software, and experimental validation, please refer to the associated manuscript.

### Features

- **Low-Cost & Open-Source:** Built with affordable, off-the-shelf components and open-source software.
- **Power Efficient:** Designed for long-term, autonomous operation with a deep-sleep cycle, powered by a LiPo battery and a solar panel.
- **Raspberry Pi Pico:** Utilises the powerful and flexible RP2040 microcontroller.
- **MicroPython:** Programmed in MicroPython for ease of development and maintenance.
- **Modular & Configurable:** The software is structured to allow easy configuration of pins, sensors, and measurement intervals.
- **Data Logging:** Stores timestamped data in CSV format on a microSD card for easy retrieval and analysis.
- **Remote Management:** Includes helper scripts to simplify flashing the firmware and cleaning up data logs.

### Hardware Overview

The picoLogger integrates several key components to achieve its functionality:

- **Compute Module:** Raspberry Pi Pico
- **Analog-to-Digital Converter:** ADS1115 (for soil moisture sensor readings)
- **Real-Time Clock:** DS3231 (for accurate timestamping)
- **Storage:** MicroSD Card Module
- **Power:** 3000mAh LiPo Battery, 1W Solar Panel, and a DFRobot DFR0264 charging module.
- **Sensors:**
    - Low-Cost Soil Moisture Sensor (LCSMS)
    - DS18B20 Temperature Sensor (STS)

For a detailed bill of materials, assembly instructions, and schematics, please see Appendix A of the manuscript.

### Software Architecture

The firmware is organized into a modular structure for clarity and ease of modification.

- **`main.py`:** The main entry point and control script. It initializes the hardware, manages the measurement-sleep cycle, and handles data logging.
- **`src/config.py`:** A centralized configuration file for all user-definable parameters, such as pin assignments, I2C/SPI bus settings, and data acquisition intervals.
- **`src/picologger.py`:** Contains the core `picoLogger` class, encapsulating the main operational logic.
- **`lib/`:** A directory containing the necessary driver modules for the peripheral components (ADS1115, DS3231, SD card, etc.).

### Hardware Wiring

The following table details the default wiring connections between the Raspberry Pi Pico and the peripheral modules. These connections are defined in `src/config.py` and can be modified to suit different hardware configurations.

| Raspberry Pi Pico Pin | Module              | Pin/Function        | Notes                                    |
| --------------------- | ------------------- | ------------------- | ---------------------------------------- |
| GP0 (I2C0 SDA)        | DS3231 RTC Module   | SDA                 | I2C Bus 0 for Real-Time Clock            |
| GP1 (I2C0 SCL)        | DS3231 RTC Module   | SCL                 | I2C Bus 0 for Real-Time Clock            |
| GP2 (SPI0 SCK)        | MicroSD Card Module | SCK                 | SPI Bus 0 for SD Card                    |
| GP3 (SPI0 MOSI)       | MicroSD Card Module | MOSI                | SPI Bus 0 for SD Card                    |
| GP4 (SPI0 MISO)       | MicroSD Card Module | MISO                | SPI Bus 0 for SD Card                    |
| GP5                   | MicroSD Card Module | CS (Chip Select)    |                                          |
| GP6 (I2C1 SDA)        | ADS1115 ADC Module  | SDA                 | I2C Bus 1 for Analog-to-Digital Converter|
| GP7 (I2C1 SCL)        | ADS1115 ADC Module  | SCL                 | I2C Bus 1 for Analog-to-Digital Converter|
| GP14                  | DS18B20 STS         | Data                | One-Wire interface for temperature sensors|
| GP15                  | Function Toggle     | Switch Pin          | Toggles data recording ON/OFF            |
| GP18                  | Status LED          | Blue Cathode        |                                          |
| GP19                  | Status LED          | Green Cathode       |                                          |
| GP20                  | Status LED          | Red Cathode         |                                          |
| GP21                  | Power Control       | MOSFET Gate         | Switches power to sensors and modules    |

**Note on UART:** The default configuration also specifies `UART0` on `GP0` (TX) and `GP1` (RX) for debugging purposes. This shares pins with the `DS3231 RTC` on `I2C0`. While both can be defined, they cannot be used simultaneously in this configuration. The primary function is the RTC, while the UART is for debugging and can be re-assigned in `src/config.py` if needed.

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
