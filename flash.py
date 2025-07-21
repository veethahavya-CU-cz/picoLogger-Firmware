from subprocess import run
from os import path, remove
from picoconfig import picoConfig

# --- Config ---
mpy_ver = '1.25'
DEBUG = True

CONFIG = picoConfig()
CONFIG.ID = 1
CONFIG.TIM.interval = (15, 'M')
CONFIG.HW.sLED.R, CONFIG.HW.sLED.G, CONFIG.HW.sLED.B = 18, 19, 20
CONFIG.to_json('picoLogger.json')

# --- Initialization ---
open('flash_cmds.log', 'w').close()  # Clear previous log
open('flash.log', 'w').close()       # Clear previous log
open('flash.err', 'w').close()       # Clear previous error log

# --- Paths ---
dI = {
    'src': path.join('.', 'src'),
    'lib': path.join('.', 'lib'),
    'pL_': path.join('.', 'src', 'picologger.py'),
    'pL': path.join('.', 'src', 'picologger.mpy'),
    'pC': path.join('.', 'picoLogger.json'),
    'main': path.join('.', 'src', 'main.py')
}
dO = {
    'root': ':',
    'lib': ':lib',
    'config': ':.config',
    'pL': ':lib/picologger.mpy',
    'pC': ':.config/picoLogger.json'
}
libs = ['ads1115.py', 'ds3231.py', 'sdcard.py']

# --- Utility Functions ---
def log_cmd(cmd):
    if DEBUG:
        with open('flash_cmds.log', 'a') as f:
            f.write(' '.join(cmd) + '\n')

def run_cmd(cmd, **kwargs):
    log_cmd(cmd)
    run(cmd, **kwargs)

def compile_and_copy(src, dest, log_out, log_err):
    compiled = src.replace('.py', '.mpy')
    run_cmd(['mpy-cross', '-v', '-c', mpy_ver, '-march=armv6m', '-O3', src, '-o', compiled], check=True, stdout=log_out, stderr=log_err)
    run_cmd(['mpremote', 'rm', dest], stdout=log_out, stderr=log_err)
    run_cmd(['mpremote', 'cp', compiled, dest], check=True, stdout=log_out, stderr=log_err)
    remove(compiled)

def create_and_copy_config(src, dest, log_out, log_err):
    run_cmd(['mpremote', 'mkdir', dO['config']], stdout=log_out, stderr=log_err)
    run_cmd(['mpremote', 'rm', dest], stdout=log_out, stderr=log_err)
    run_cmd(['mpremote', 'cp', src, dest], check=True, stdout=log_out, stderr=log_err)
    remove(src)

def set_rtc():
    try:
        run_cmd(['mpremote', 'rtc', '--set'], check=True)
    except:
        raise RuntimeError("Failed to connect to device!")

# --- Main ---
if __name__ == "__main__":
    with open('flash.log', 'w') as log_out, open('flash.err', 'w') as log_err:
        print("Setting Machine RTC")
        set_rtc()

        print("Installing micropython libraries")
        run_cmd(['mpremote', 'mkdir', dO['lib']], stdout=log_out, stderr=log_err)

        for lib in libs:
            src = path.join(dI['lib'], lib)
            dest = dO['lib'] + '/' + lib.replace('.py', '.mpy')
            compile_and_copy(src, dest, log_out, log_err)
        
        run_cmd(['mpremote', 'mip', 'install', 'os-path'], stdout=log_out, stderr=log_err, check=True)
        run_cmd(['mpremote', 'mip', 'install', 'datetime'], stdout=log_out, stderr=log_err, check=True)

        print("Compiling and copying over picoLogger")
        compile_and_copy(dI['pL_'], dO['pL'], log_out, log_err)
        create_and_copy_config(dI['pC'], dO['pC'], log_out, log_err)
        
        print("Setting up picoLogger on the device")
        cmd = 'mpremote exec "from picologger import picoLogger; picoLogger(\\"/.config/picoLogger.json\\")"'
        log_cmd(cmd.strip())
        run(cmd, shell=True, check=True)

        run_cmd(['mpremote', 'cp', dI['main'], ':main.py'], check=True, stdout=log_out, stderr=log_err)
        print("Flash completed successfully!\nDisconnect the device and reset it to run the new firmware.")