import subprocess
import sys

logfile = 'flash.log'

def run(cmd, show_output=False):
    print(f"Running: {cmd}")
    with open(logfile, 'a') as log:
        log.write(f"\n>>> {cmd}\n")
        if show_output:
            proc = subprocess.run(cmd, shell=True)
        else:
            proc = subprocess.run(cmd, shell=True, stdout=log, stderr=log)
        if proc.returncode != 0:
            print(f"❌ Command failed: {cmd}. Check {logfile}")
            sys.exit(proc.returncode)

# Clear log at start
with open(logfile, 'w') as log:
    log.write("Flash log\n==========\n")

# Commands
run("mpremote mip install os-path datetime")

src_files = ['src\\picologger.py', 'src\\config.py']
lib_files = ['lib\\sled.py', 'lib\\logging.py', 'lib\\sdcard.py', 'lib\\ds3231.py', 'lib\\ads1115.py']

for f in src_files:
    out = f.replace('src\\', 'bin\\').replace('.py', '.mpy')
    run(f"mpy-cross -v -c 1.25 -march=armv6m -O3 {f} -o {out}")

for f in lib_files:
    out = f.replace('lib\\', 'bin\\').replace('.py', '.mpy')
    run(f"mpy-cross -v -c 1.25 -march=armv6m -O3 {f} -o {out}")

bin_files = [f.replace('lib\\', 'bin\\').replace('src\\', 'bin\\').replace('.py', '.mpy') for f in lib_files + src_files]
bin_list = ' '.join(bin_files)
run(f"mpremote cp {bin_list} :lib/")

run("mpremote rtc --set")
run("mpremote cp src\\main.py :main.py")

# Show output for final command
run('mpremote exec "from picologger import picoLogger; datalogger = picoLogger(); datalogger.setup()"', show_output=True)
