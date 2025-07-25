"""
MicroPython Device Cleanup Script
=================================
This script safely removes user files from a Raspberry Pi Pico while preserving
system files, libraries, and optionally backing up important data.
"""

from subprocess import run
from os import remove, makedirs
import re
import time
from datetime import datetime

# Configuration
SD_CARD = True
BACKUP = False
BACKUP_DIR = '.backup_before_cleanup'

def print_banner(message, char='='):
    """Print a formatted banner message."""
    border = char * len(message)
    print(f"\n{border}")
    print(message)
    print(f"{border}")

def print_step(message):
    """Print a step message with emoji."""
    print(f"🔄 {message}")

def print_success(message):
    """Print a success message with emoji."""
    print(f"✅ {message}")

def print_warning(message):
    """Print a warning message with emoji."""
    print(f"⚠️  {message}")

def print_error(message):
    """Print an error message with emoji."""
    print(f"❌ {message}")

def safe_run(cmd, fatal=True):
    """
    Execute a command safely with error handling.
    
    Args:
        cmd (list): Command and arguments to execute
        fatal (bool): Whether to exit on failure
        
    Returns:
        subprocess.CompletedProcess: Result of the command
    """
    result = run(cmd, capture_output=True, text=True)
    if result.returncode != 0 and fatal:
        print_error(f"{' '.join(cmd)}")
        if result.stderr.strip():
            print(f"   Error details: {result.stderr.strip()}")
        exit(1)
    return result

def list_entries(base=':'):
    """
    List files and directories at a specific path on the device.
    
    Args:
        base (str): Base path to list entries from
        
    Returns:
        tuple: (files, directories) lists
    """
    # Skip trying to list certain problematic directories
    skip_paths = [':sd/System Volume Information', ':sd/$RECYCLE.BIN']
    if base in skip_paths or any(base.startswith(path) for path in skip_paths):
        return [], []
    
    result = safe_run(['mpremote', 'resume', 'ls', base], fatal=False)
    if result.returncode != 0:
        # If listing fails, return empty lists and continue
        return [], []
        
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
    """
    Recursively list all files and directories from a path.
    
    Args:
        path (str): Starting path for recursive listing
        
    Returns:
        tuple: (all_files, all_directories) lists
    """
    # Define directories to skip during scanning
    skip_prefixes = [':sd/System Volume Information', ':sd/$RECYCLE.BIN', ':sd/System']
    
    all_files, all_dirs = [], []
    files, dirs = list_entries(path)
    all_files.extend(files)
    
    for d in dirs:
        # Skip scanning Windows system directories and other protected dirs
        if any(d.startswith(prefix) for prefix in skip_prefixes):
            all_dirs.append(d)  # Still add to list but don't scan contents
            continue
            
        sub_files, sub_dirs = list_all(d)
        all_files.extend(sub_files)
        all_dirs.extend(sub_dirs)
        all_dirs.append(d)
        
    return all_files, all_dirs

def mount_sd():
    """
    Attempt to mount the SD card on the device.
    
    Returns:
        bool: True if mount successful, False otherwise
    """
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
    """Safely unmount the SD card and power down SD hardware."""
    print_step("Unmounting SD card...")
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
    print_success("SD card unmounted and powered down")

# Initialize cleanup process
print_banner("PicoSMS Device Cleanup Script")
timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
print(f"🕐 Started at: {timestamp}")

# Verify mpremote connection and version
print_banner("Verifying Device Connection", "-")
print_step("Checking mpremote version...")
safe_run(['mpremote', '--version'])
print_success("mpremote is available")

print_step("Testing device connection...")
safe_run(['mpremote', 'ls'])
print_success("Device connection established")

# Handle SD card mounting if enabled
if SD_CARD:
    print_banner("SD Card Management", "-")
    print_step("Attempting to mount SD card...")
    if not mount_sd():
        print_warning("Could not mount SD card - trying to upload driver...")
        safe_run(['mpremote', 'resume', 'cp', './lib/sdcard.py', ':'])
        if not mount_sd():
            print_error("Failed to mount SD card after copying driver")
            exit(1)
    print_success("SD card mounted successfully")

# Discover all files and directories
print_banner("Scanning Device Files", "-")
print_step("Scanning device filesystem...")
files, dirs = list_all(':')
print(f"📁 Found {len(dirs)} directories")
print(f"📄 Found {len(files)} files")

if SD_CARD:
    print_step("Scanning SD card filesystem...")
    sd_files, sd_dirs = list_all(':/sd')
    files += sd_files
    dirs += sd_dirs
    print(f"📁 SD card directories: {len(sd_dirs)}")
    print(f"📄 SD card files: {len(sd_files)}")

# Setup backup if enabled
if BACKUP:
    print_banner("Backup Setup", "-")
    print_step(f"Creating backup directory: {BACKUP_DIR}")
    makedirs(BACKUP_DIR, exist_ok=True)
    print_success("Backup directory ready")

# File cleanup process
print_banner("File Cleanup", "-")
protected_files = [':main.py']
protected_prefixes = [':sd/System Volume Information', ':sd/$RECYCLE.BIN', ':sd/System', ':lib/', ':os']
files_to_delete = []
files_protected = []

for f in files:
    if f in protected_files or any(f.startswith(prefix) for prefix in protected_prefixes):
        files_protected.append(f)
    else:
        files_to_delete.append(f)

print(f"🛡️  Protected files: {len(files_protected)}")
print(f"🗑️  Files to delete: {len(files_to_delete)}")

if files_to_delete:
    print_step("Deleting user files...")
    for i, f in enumerate(files_to_delete, 1):
        if BACKUP:
            print(f"  [{i}/{len(files_to_delete)}] Backing up: {f}")
            safe_run(['mpremote', 'resume', 'cp', f, BACKUP_DIR + '/'], fatal=False)
        
        print(f"  [{i}/{len(files_to_delete)}] Deleting: {f}")
        safe_run(['mpremote', 'resume', 'rm', f], fatal=False)
    print_success(f"Deleted {len(files_to_delete)} files")
else:
    print_success("No user files found to delete")

# Directory cleanup process
print_banner("Directory Cleanup", "-")
protected_dirs = [':sd/', ':lib/', ':os/']
protected_dir_prefixes = [':sd/System Volume Information', ':sd/$RECYCLE.BIN', ':sd/System', ':lib/', ':os/']
dirs_to_delete = []
dirs_protected = []

for d in sorted(set(dirs), reverse=True):
    if d in protected_dirs or any(d.startswith(prefix) for prefix in protected_dir_prefixes):
        dirs_protected.append(d)
    else:
        dirs_to_delete.append(d)

print(f"🛡️  Protected directories: {len(dirs_protected)}")
print(f"🗑️  Directories to delete: {len(dirs_to_delete)}")

if dirs_to_delete:
    print_step("Removing empty directories...")
    for i, d in enumerate(dirs_to_delete, 1):
        print(f"  [{i}/{len(dirs_to_delete)}] Removing: {d}")
        safe_run(['mpremote', 'resume', 'rmdir', d], fatal=False)
    print_success(f"Removed {len(dirs_to_delete)} directories")
else:
    print_success("No user directories found to delete")

# Local file cleanup
print_banner("Local Cleanup", "-")
local_files = ['flash.log']
removed_count = 0

print_step("Cleaning up local log files...")
for f in local_files:
    try:
        remove(f)
        print(f"  ✅ Removed: {f}")
        removed_count += 1
    except FileNotFoundError:
        print(f"  ℹ️  Not found: {f}")

if removed_count > 0:
    print_success(f"Removed {removed_count} local files")
else:
    print_success("No local files to remove")

# Final cleanup
if SD_CARD:
    unmount_sd()

print_banner("Cleanup Complete! 🎉")
end_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
print(f"🕐 Completed at: {end_timestamp}")
print("✅ picoLogger has been cleaned up successfully!")
if BACKUP:
    print(f"📦 Backup files saved in: {BACKUP_DIR}")
