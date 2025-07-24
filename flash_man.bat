mpremote mip install os-path datetime
mpy-cross -v -c 1.25 -march=armv6m -O3 src\picologger.py -o bin\picologger.mpy
mpy-cross -v -c 1.25 -march=armv6m -O3 src\config.py -o bin\config.mpy

mpy-cross -v -c 1.25 -march=armv6m -O3 lib\sled.py -o bin\sled.mpy
mpy-cross -v -c 1.25 -march=armv6m -O3 lib\logging.py -o bin\logging.mpy
mpy-cross -v -c 1.25 -march=armv6m -O3 lib\sdcard.py -o bin\sdcard.mpy
mpy-cross -v -c 1.25 -march=armv6m -O3 lib\ds3231.py -o bin\ds3231.mpy
mpy-cross -v -c 1.25 -march=armv6m -O3 lib\ads1115.py -o bin\ads1115.mpy


mpremote cp bin\sled.mpy bin\logging.mpy bin\sdcard.mpy bin\ds3231.mpy bin\ads1115.mpy bin\picologger.mpy bin\config.mpy :lib/

mpremote rtc --set
mpremote cp src\main.py :main.py

mpremote exec "from picologger import picoLogger; datalogger = picoLogger(); datalogger.setup()"