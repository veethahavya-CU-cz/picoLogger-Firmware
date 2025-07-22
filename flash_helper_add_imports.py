# TODO: Integrate this script into the flashing process
import re

def append_imports(file_path, new_imports):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    last_import_idx = 0
    import_pattern = re.compile(r'^\s*(import|from)\s+')

    for i, line in enumerate(lines):
        if import_pattern.match(line):
            last_import_idx = i

    for new_import in new_imports:
        lines.insert(last_import_idx + 1, new_import + '\n')
        last_import_idx += 1

    with open(file_path, 'w') as f:
        f.writelines(lines)

# Example usage:
append_imports('./src/picologger.py', ['from config import *'])
ADC = 'ADS1115' # Literal['INTERNAL', 'ADS1115']
RTC = 'DS3231' # Literal['DS1307', 'DS3231']
