from subprocess import run
from os import remove, makedirs
import re
import time

def safe_run(cmd, fatal=True):
    result = run(cmd, capture_output=True, text=True)
    if result.returncode != 0 and fatal:
        print(f"❌ {' '.join(cmd)}\n{result.stderr.strip()}")
        exit(1)
    return result

def list_entries(base=':'):
    result = safe_run(['mpremote', 'resume', 'ls', base])
    lines = result.stdout.strip().splitlines()
    files, dirs = [], []
    for line in lines[1:]:  # Skip device header
        match = re.match(r'^\s*(\d+|<DIR>)\s+(.+)$', line.strip())
        if not match:
            continue
        entry = match.group(2)
        full_path = base + entry if base.endswith('/') else base + '/' + entry
        if entry.endswith('/'):
            dirs.append(full_path)
        else:
            files.append(full_path)
    return files, dirs

def list_all(path=':'):
    all_files, all_dirs = [], []
    files, dirs = list_entries(path)
    all_files.extend(files)
    for d in dirs:
        sub_files, sub_dirs = list_all(d)
        all_files.extend(sub_files)
        all_dirs.extend(sub_dirs)
        all_dirs.append(d)
    return all_files, all_dirs

def mount_sd():
    cmds = [
        'from machine import Pin, SPI',
        'from os import VfsFat, mount',
        'from sdcard import SDCard',
        'from utime import sleep_ms',
        'pwr = Pin(21, Pin.OUT); pwr.value(1); sleep_ms(100)',
        'spi = SPI(0, sck=Pin(2), mosi=Pin(3), miso=Pin(4))',
        'cs = Pin(5, Pin.OUT)',
        'sd = SDCard(spi, cs)',
        'vfs = VfsFat(sd); mount(vfs, "/sd")'
    ]
    result = run(['mpremote', 'resume', 'exec', '; '.join(cmds)], capture_output=True, text=True)
    return result.returncode == 0

def unmount_sd():
    run(['mpremote', 'resume', 'exec', 'from os import umount; umount("/sd")'], capture_output=True)
    poweroff = '; '.join([
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
    ])
    run(['mpremote', 'resume', 'exec', poweroff], capture_output=True)

# --- Main ---
safe_run(['mpremote', '--version'])
safe_run(['mpremote', 'ls'])

SD_CARD = True
if SD_CARD:
    if not mount_sd():
        print("⛔ Could not mount SD. Trying to upload sdcard driver...")
        safe_run(['mpremote', 'resume', 'cp', './lib/sdcard.py', ':'])
        if not mount_sd():
            print("❌ Failed to mount SD card after copying driver.")
            exit(1)

files, dirs = list_all(':')
if SD_CARD:
    sd_files, sd_dirs = list_all(':/sd')
    files += sd_files
    dirs += sd_dirs
BACKUP = False
BACKUP_DIR = '.backup_before_cleanup'

if BACKUP:
    makedirs(BACKUP_DIR, exist_ok=True)

# Delete files
for f in files:
    if f.startswith(':sd/System') or f == ':main.py' or f.startswith(':lib/') or f.startswith(':os'):
        continue
    if BACKUP:
        safe_run(['mpremote', 'resume', 'cp', f, BACKUP_DIR + '/'], fatal=False)
    print(f"Deleting file: {f}")
    safe_run(['mpremote', 'resume', 'rm', f], fatal=False)

# Delete directories
for d in sorted(set(dirs), reverse=True):
    if d in (':sd/', ':lib/', ':os/') or d.startswith(':sd/System') or d.startswith(':lib/') or d.startswith(':os/'):
        continue
    print(f"Deleting dir: {d}")
    safe_run(['mpremote', 'resume', 'rmdir', d], fatal=False)

# Local cleanup
for f in ['flash.log', 'flash.err', 'picoLogger.log']:
    try:
        remove(f)
    except FileNotFoundError:
        pass

if SD_CARD:
    print("Unmounting SD...")
    unmount_sd()

print("✅ Cleanup complete.")
