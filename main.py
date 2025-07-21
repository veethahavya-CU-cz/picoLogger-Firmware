from machine import Pin
from picologger import picoLogger, FN_PIN, _sLED_

FN = Pin(FN_PIN, Pin.IN)

def loop():
    if FN.value():
        system = picoLogger()
        STATUS, MSG = system.record()
        if not STATUS:
            return False, f"Error Recording: {MSG}"
        STATUS, MSG = system.update()
        if not STATUS:
            return False, f"Error Updating: {MSG}"
        STATUS, MSG = system.deactivate()
        if not STATUS:
            return False, f"Error Deactivating: {MSG}"
        system.sleep()
        return True, "Normal Operation"
    else:
        sLED = _sLED_()
        sLED.blink('white')
        return True, "NotImplemented Error: UART Command Terminal not implemented yet"
    
if __name__ == "__main__":
    STATUS, MSG = loop()
    if not STATUS:
        print(MSG)