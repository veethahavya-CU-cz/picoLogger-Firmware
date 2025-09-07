from micropython import const

REC_IVL = const(900)

LOG_LEVEL = 'DEBUG'
UART_ID = const(0)
UART_BAUD = const(9600)
UART_TX = const(12)
UART_RX = const(13)

SLED_R = const(20)
SLED_G = const(19)
SLED_B = const(18)
SLED_n_flash = const(3)
SLED_on_ms = const(125)
SLED_off_ms = const(75)

PWR_PIN = const(21)
FN_PIN = const(15)

SDC_SPI_ID = const(0)
SDC_SPI_SCK = const(2)
SDC_SPI_MOSI = const(3)
SDC_SPI_MISO = const(4)
SDC_SPI_CS = const(5)

RTC_I2C_ID = const(0)
RTC_I2C_SDA = const(0)
RTC_I2C_SCL = const(1)
RTC_I2C_FREQ = const(100000)

EADC_I2C_ID = const(1)
EADC_I2C_SDA = const(6)
EADC_I2C_SCL = const(7)
EADC_I2C_FREQ = const(400000)
EADC_CH0_VD_R1 = const(2200)
EADC_CH0_VD_R2 = const(22000)

OW_PIN = const(14)

BAT_CH = const(0)
SMS1_CH = const(1)
SMS2_CH = const(2)
SMS3_CH = const(3)

SMS_COUNT = const(7)
SMS_IVL = const(25)
OW_COUNT = const(1)
OW_IVL = const(750)
BAT_COUNT = const(3)
BAT_IVL = const(25)
ITEMP_COUNT = const(5)
ITEMP_IVL = const(25)