from machine import Pin
from picologger import picoLogger, FN_PIN, _sLED_

def main():
    """Main execution function - optimized for compatibility"""
    # Function switch check
    fn_pin = Pin(FN_PIN, Pin.IN)
    
    if fn_pin.value():
        # Logging mode - normal operation
        try:
            logger = picoLogger()
            
            # Record data
            success, msg = logger.record()
            if not success:
                return False, f"Record failed: {msg}"
            
            # Update timing
            success, msg = logger.update()
            if not success:
                return False, f"Update failed: {msg}"
            
            # Deactivate and sleep
            success, msg = logger.deactivate()
            if not success:
                return False, f"Deactivate failed: {msg}"
            
            # Sleep until next recording
            logger.sleep()
            return True, "Normal operation completed"
            
        except Exception as e:
            return False, f"Logger error: {str(e)}"
    else:
        # UART terminal mode (placeholder)
        try:
            sled = _sLED_()
            sled.flash('white', n=5)
            return True, "UART mode - not implemented"
        except:
            return True, "UART mode - LED failed"

if __name__ == "__main__":
    success, message = main()
    if not success:
        print(f"ERROR: {message}")
        # Flash red LED to indicate error
        try:
            sled = _sLED_()
            sled.flash('red', n=10)
        except:
            pass