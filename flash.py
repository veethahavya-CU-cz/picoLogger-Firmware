"""
MicroPython Project Flash Script
================================
This script compiles Python files to bytecode and flashes them to a Raspberry Pi Pico.
It handles source compilation, library management, and device setup.
"""

import subprocess
import sys
import os
from datetime import datetime

# Configuration
LOGFILE = 'flash.log'
COMPILE_VERSION = '1.25'
COMPILE_ARCH = 'armv6m'
OPTIMIZATION_LEVEL = '3'

# Global list to collect warnings
warnings_found: list[str] = []

def print_banner(message, char='='):
    """Print a formatted banner message."""
    border = char * len(message)
    print(f"\n{border}")
    print(message)
    print(f"{border}")

def log_command(cmd):
    """Log command to file with timestamp."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(LOGFILE, 'a', encoding='utf-8') as log:
        log.write(f"\n[{timestamp}] >>> {cmd}\n")

def run(cmd, show_output=False):
    """
    Execute a shell command with proper logging and error handling.
    
    Args:
        cmd (str): Command to execute
        show_output (bool): Whether to show output in console
    """
    print(f"🔄 Running: {cmd}")
    log_command(cmd)
    
    if show_output:
        # Capture output and display it while also logging it
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        # Write output to log file
        with open(LOGFILE, 'a', encoding='utf-8') as log:
            if proc.stdout:
                log.write(proc.stdout)
            if proc.stderr:
                log.write(proc.stderr)
        
        # Display output to console and collect warnings
        if proc.stdout:
            output_lines = proc.stdout.rstrip().split('\n')
            for line in output_lines:
                if line.strip().startswith('WARNING:'):
                    warnings_found.append(line.strip())
                print(line)
        if proc.stderr:
            stderr_lines = proc.stderr.rstrip().split('\n')
            for line in stderr_lines:
                if line.strip().startswith('WARNING:'):
                    warnings_found.append(line.strip())
                print(line)
    else:
        # Standard logging without console output
        with open(LOGFILE, 'a', encoding='utf-8') as log:
            proc = subprocess.run(cmd, shell=True, stdout=log, stderr=log)
    
    if proc.returncode != 0:
        print(f"❌ Command failed: {cmd}")
        print(f"📋 Check {LOGFILE} for details")
        sys.exit(proc.returncode)
    else:
        print(f"✅ Command completed successfully")

def initialize_log():
    """Initialize the log file with header information."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    header = f"""
PicoSMS Flash Script Log
========================
Started: {timestamp}
Working Directory: {os.getcwd()}
Platform: {sys.platform}

"""
    with open(LOGFILE, 'w', encoding='utf-8') as log:
        log.write(header)

# Initialize logging
initialize_log()
print_banner("PicoSMS Flash Script")

# Install required packages
print_banner("Installing Required Packages", "-")
run("mpremote mip install os-path datetime")

# Define source files for compilation
src_files = [os.path.join('src', 'picologger.py'), os.path.join('src', 'config.py')]
lib_files = [os.path.join('lib', 'sled.py'), os.path.join('lib', 'logging.py'), os.path.join('lib', 'sdcard.py'), os.path.join('lib', 'ds3231.py'), os.path.join('lib', 'ads1115.py')]

print_banner("Compiling Source Files", "-")
print(f"📁 Compiling {len(src_files)} source files...")
for i, f in enumerate(src_files, 1):
    out = f.replace('src' + os.sep, 'bin' + os.sep).replace('.py', '.mpy')
    print(f"  [{i}/{len(src_files)}] {os.path.basename(f)} → {os.path.basename(out)}")
    run(f"mpy-cross -v -c {COMPILE_VERSION} -march={COMPILE_ARCH} -O{OPTIMIZATION_LEVEL} {f} -o {out}")

print_banner("Compiling Library Files", "-")
print(f"📚 Compiling {len(lib_files)} library files...")
for i, f in enumerate(lib_files, 1):
    out = f.replace('lib' + os.sep, 'bin' + os.sep).replace('.py', '.mpy')
    print(f"  [{i}/{len(lib_files)}] {os.path.basename(f)} → {os.path.basename(out)}")
    run(f"mpy-cross -v -c {COMPILE_VERSION} -march={COMPILE_ARCH} -O{OPTIMIZATION_LEVEL} {f} -o {out}")

# Copy compiled files to device
print_banner("Transferring Files to Device", "-")
bin_files = [f.replace('lib' + os.sep, 'bin' + os.sep).replace('src' + os.sep, 'bin' + os.sep).replace('.py', '.mpy') for f in lib_files + src_files]
bin_list = ' '.join(bin_files)
print(f"📤 Copying {len(bin_files)} compiled files to device lib directory...")
run(f"mpremote cp {bin_list} :lib/")

# Device setup
print_banner("Device Setup", "-")
print("🕐 Setting real-time clock...")
run("mpremote rtc --set")

print("📋 Copying main.py to device...")
run(f"mpremote cp {os.path.join('src', 'main.py')} :main.py")

# Initialize and test the logger
print_banner("Testing Logger Setup", "-")
print("🧪 Initializing and testing picoLogger...")
run('mpremote exec "from picologger import picoLogger; datalogger = picoLogger(); datalogger.setup()"', show_output=True)

print_banner("Flash Process Complete! 🎉")

# Display any warnings found during the process
if warnings_found:
    print()
    for warning in warnings_found:
        print(f"⚠️  {warning}")
    print()

print(f"📄 Full log available in: {LOGFILE}")
print("✅ picoLogger is configured and ready to use!")
