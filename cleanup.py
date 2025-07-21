from subprocess import run
from os import remove, makedirs

result = run(['mpremote', '--version'], capture_output=True, text=True)
if result.returncode != 0:
    print("mpremote is not installed or not found in PATH.")
    exit(1)

result = run(['mpremote', 'ls'], capture_output=True, text=True)
if result.returncode != 0:
    print(f"Error communicating with the device!\nAvailable devices:\n{run(['mpremote', 'devs'], capture_output=True, text=True).stdout.strip()}")
    exit(1)

def ls(path=':'):
    result = run(['mpremote', 'resume', 'ls', path], capture_output=True, text=True)
    entries = result.stdout.strip().splitlines()
    entries = [entry.strip().split()[1] for entry in entries if entry.strip()][1:]
    # Remove duplicates while preserving order
    entries = list(dict.fromkeys(entries))
    return entries

def list_all_entries(path=':'):
    files = []
    dirs = []
    seen_paths = set()  # Track what we've already processed
    
    for entry in ls(path):
        full_path = f"{path}{entry}"
        
        # Skip if we've already seen this path
        if full_path in seen_paths:
            continue
        seen_paths.add(full_path)
        
        if entry.endswith('/'):
            if 'os' in entry:
                continue
            # Recurse first
            sub_files, sub_dirs = list_all_entries(full_path)
            files.extend(sub_files)
            dirs.extend(sub_dirs)
            dirs.append(full_path)
        else:
            files.append(full_path)
    
    # Remove duplicates while preserving order
    files = list(dict.fromkeys(files))
    dirs = list(dict.fromkeys(dirs))
    
    return files, dirs

def mount_sd():
    result = run(['mpremote', 'resume', 'exec', 'from machine import Pin, SPI; from os import VfsFat, mount; from sdcard import SDCard; from utime import sleep_ms'], capture_output=True, text=True)
    if result.returncode != 0:
        return False, f"Error importing SD Card Library: {result.stderr.strip()}"
    result = run(['mpremote', 'resume', 'exec', 'pwr = Pin(21, Pin.OUT); pwr.value(1); sleep_ms(100); spi = SPI(0, sck=Pin(2), mosi=Pin(3), miso=Pin(4)); cs = Pin(5, Pin.OUT); sd = SDCard(spi, cs)'], capture_output=True, text=True)
    if result.returncode != 0:
        return False, f"Error initializing SD Card: {result.stderr.strip()}"
    result = run(['mpremote', 'resume', 'exec', 'vfs = VfsFat(sd); mount(vfs, "/sd")'], capture_output=True, text=True)
    if result.returncode != 0:
        return False, f"Error mounting SD Card: {result.stderr.strip()}"
    return True, ""

def unmount_sd():
    # Try to unmount - if it fails, it might already be unmounted
    result = run(['mpremote', 'resume', 'exec', 'from os import umount; umount("/sd")'], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Warning: Could not unmount SD card (might already be unmounted): {result.stderr.strip()}")
        # Continue with power off even if unmount fails
    
    # Power off peripherals with extended delays and debugging
    commands = [
        'from machine import Pin',
        'from utime import sleep_ms', 
        'pwr = Pin(21, Pin.OUT)',
        'Pin(2, Pin.IN, pull=None)',
        'Pin(3, Pin.IN, pull=None)', 
        'Pin(4, Pin.IN, pull=None)',
        'Pin(5, Pin.IN, pull=None)',
        'sleep_ms(50)',
        'pwr.value(0)',
        'sleep_ms(100)'
    ]
    command_string = '; '.join(commands)
    result = run(['mpremote', 'resume', 'exec', command_string], capture_output=True, text=True)
    if result.returncode != 0:
        return False, f"Error powering off peripherals: {result.stderr.strip()}"
    return True, ""

SD_CARD = True
if SD_CARD:
    res = mount_sd()
    if not res[0]:
        run(['mpremote', 'resume', 'cp', './lib/sdcard.py', ':'], capture_output=True, text=True)
        res = mount_sd()
        if not res[0]:
            print(f"Failed to mount SD card.\n{res[1]}")
            exit(1)

CACHE = False
if CACHE:
    print("Caching the files before deletion.")
    makedirs('.cleanup_cache', exist_ok=True)

files, dirs = list_all_entries(':')
print(f"Files: {files}")
print(f"Directories: {dirs}")

for file in reversed(files):
    if not file in [':sd/System']:
        print(f"Removing file: {file}")
        if CACHE:
            result = run(['mpremote', 'resume', 'cp', file, '.cleanup_cache/'], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Error copying file {file} to cache: {result.stderr.strip()}")
                continue
        result = run(['mpremote', 'resume', 'rm', file], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error removing file {file}: {result.stderr.strip()}")
for dir in reversed(dirs):
    if 'lib' in dir or 'os' in dir or dir == ':sd/':
        print(f"Skipping directory: {dir}")
        continue
    print(f"Removing directory: {dir}")
    result = run(['mpremote', 'resume', 'rmdir', dir], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error removing directory {dir}: {result.stderr.strip()}")

for file in ['flash_cmds.log', 'flash.log', 'flash.err', 'picoLogger.log']:
    try:
        remove(file)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"Error removing file {file}: {e}")

if SD_CARD:
    print("Unmounting SD card and powering off peripherals...")
    result = unmount_sd()
    if result[0]:
        print("SD card unmounted and peripherals powered off successfully.")
    else:
        print(f"Error during SD card unmounting: {result[1]}")
        
print("Cleanup completed successfully.")