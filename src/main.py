from machine import Pin
from picologger import picoLogger


datalogger = picoLogger()
if datalogger.FN.value():
    # Datalogger Mode
    # Activate
    STATUS, MSG = datalogger.activate()
    if not STATUS:
        print(f"ERROR: {MSG}")
    # Record
    STATUS, MSG = datalogger.record()
    if not STATUS:
        print(f"ERROR: {MSG}")
    # Update
    STATUS, MSG = datalogger.update()
    if not STATUS:
        print(f"ERROR: {MSG}")
    # Deactivate
    STATUS, MSG = datalogger.deactivate()
    if not STATUS:
        print(f"ERROR: {MSG}")
    # Sleep
    datalogger.sleep()
else:
    # UART Terminal Mode
    try:
        datalogger._init_PWR(turn_on=True)
        datalogger.led.on('white')
        print("NotImplemented: UART terminal mode")
    except KeyboardInterrupt:
        print("Exiting...")
        datalogger.led.off()
    except Exception as e:
        datalogger.led.on('red')
