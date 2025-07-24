"""
# Logger class for logging messages to a file and optionally to UART.
# Supports different logging levels and can be configured to rewrite logs.
Author: veethahavya_cu-cz
"""

from machine import Pin, UART
from micropython import const
from time import localtime
from datetime import datetime
from os import remove

class Logger:
    STATUS, MSG = None, None
    levels = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3, 'CRITICAL': 4}
    DEBUG = const(0)
    INFO = const(1)
    WARNING = const(2)
    ERROR = const(3)
    CRITICAL = const(4)
    default_logfile = '/stray.log'

    def __init__(self, path, level, uart_id, uart_baud, uart_tx, uart_rx, rewrite=False):
        """
        Initialize the logger

        Args:
            path (str): 
                The path to the log file.
            level (Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']): 
                The logging level to use. Defaults to 'INFO'. Defaults to LOG_LEVEL.
            uart_id (int):
                The UART ID to use for logging. Defaults to UART_ID.
            uart_baud (int):
                The baud rate for the UART connection. Defaults to UART_BAUD.
            uart_tx (int):
                The GPIO pin number for UART TX. Defaults to UART_TX.
            uart_rx (int):
                The GPIO pin number for UART RX. Defaults to UART_RX.
            rewrite (bool, optional):
                Whether to rewrite the log file if it exists. Defaults to False.
        """
        self.level = self.levels[level]
        self.path = path
        if uart_id is not None:
            try:
                self.uart_obj = UART(uart_id, tx=Pin(uart_tx), rx=Pin(uart_rx), baudrate=uart_baud)
            except Exception as e:
                self.uart_obj = None
                self.error("Failed to initialize UART: {}".format(str(e)))
        if rewrite:
            open(path, 'w').close()
    
    def __get_str_time(self):
        return str(datetime(*localtime()[:6]))

    def __copy_logfile(self, src, dst, rm_src=False):
        try:
            with open(src, 'r') as f_src, open(dst, 'a') as f_dst:
                while True:
                    chunk = f_src.read(512)
                    if not chunk:
                        break
                    f_dst.write(chunk)
            if rm_src:
                remove(src)
            self.debug("Log file content moved from {} to {}".format(src, dst))
            return True, "Log file copied from {} to {}".format(src, dst)
        except Exception as e:
            self.error("Failed to copy log file: {}".format(str(e)))
            return False, "Failed to copy log file: {}".format(str(e))
        
    def __write_msg(self, ilevel, slevel, msg):
        if self.level <= ilevel:
            formatted_msg = "[{}] {} :: {}\n".format(slevel, self.__get_str_time(), msg)
            try:
                with open(self.path, 'a') as f:
                    f.write(formatted_msg)
            except Exception as e:
                # If logging to the primary path fails, write to the default path
                formatted_msg_err = "[ERROR] {} :: FAILED TO WRITE TO {}: {}. Original message: {}\n".format(
                    self.__get_str_time(), self.path, str(e), msg)
                with open(self.default_logfile, 'a') as f:
                    f.write(formatted_msg_err)
            
            if self.uart_obj:
                self.uart_obj.write(formatted_msg)

    def debug(self, msg): self.__write_msg(self.DEBUG, 'DEBUG', msg)
    def info(self, msg): self.__write_msg(self.INFO, 'INFO', msg)
    def warning(self, msg): self.__write_msg(self.WARNING, 'WARNING', msg)
    def error(self, msg): self.__write_msg(self.ERROR, 'ERROR', msg)
    def critical(self, msg): self.__write_msg(self.CRITICAL, 'CRITICAL', msg)

    def br(self, n=1):
        with open(self.path, 'a') as f:
            f.write('\n' * n)

    def update(self, path=None, level=None, uart_id=None, uart_baud=None, uart_tx=None, uart_rx=None, rewrite=False):
        """
        Update the logger configuration.

        Args:
            path (str, optional):
                The new path to the log file. Defaults to None.
            level (Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], optional):
                The new logging level. Defaults to None.
            uart_id (int, optional):
                The new UART ID for logging. Defaults to None.
            uart_baud (int, optional):
                The new baud rate for the UART connection. Defaults to None.
            uart_tx (int, optional):
                The new GPIO pin number for UART TX. Defaults to None.
            uart_rx (int, optional):
                The new GPIO pin number for UART RX. Defaults to None.
        """
        if rewrite:
            open(self.path, 'w').close()
        if path:
            self.STATUS, self.MSG = self.__copy_logfile(self.path, path, rm_src=True)
            if not self.STATUS:
                self.MSG = "Failed to copy log file! Error: {}".format(self.MSG)
                self.error(self.MSG)
                return False, self.MSG
            self.path = path
        if level:
            self.level = level if isinstance(level, str) else self.levels.get(level, self.INFO)
        if uart_id is not None or uart_baud is not None or uart_tx is not None or uart_rx is not None:
            self.uart_obj = UART(uart_id, tx=Pin(uart_tx), rx=Pin(uart_rx), baudrate=uart_baud)
        return True, ""
