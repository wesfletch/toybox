#!/usr/bin/env python3

import logging
import sys

from typing import Dict

# LOG_LEVELS: Dict[str, int] = {
#     "DEBUG":logging.DEBUG,
#     "INFO":logging.INFO,
#     "WARN":logging.WARNING,
#     "ERR":logging.ERROR,
#     "FATAL":logging.CRITICAL
# }

class ColorFormatter(logging.Formatter):

    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    GREEN = "\x1b[32;20m"
    YELLOW = "\x1b[33;20m"
    GREY = "\x1b[38;20m"
    RESET = "\x1b[0m"

    FMT = '[%(asctime)s.%(msecs)03d][%(name)s][%(levelname)s]: %(message)s'
    DATE_FMT = '%H:%M:%S'

    FORMATS: dict[int,str] = {
        logging.DEBUG: GREY + FMT + RESET,
        logging.INFO: GREEN + FMT + RESET,
        logging.WARNING: YELLOW + FMT + RESET,
        logging.ERROR: RED + FMT + RESET,
        logging.CRITICAL: BOLD_RED + FMT + RESET
    }

    def format(self, record: logging.LogRecord) -> str:
        fmt: str = ColorFormatter.FORMATS.get(record.levelno)
        formatter = logging.Formatter(fmt=fmt, datefmt=ColorFormatter.DATE_FMT)
        return formatter.format(record)


# Rather than sub-classing logging.Logger like I should...
class TbxLogger():

    LOG_LEVELS: Dict[str, int] = {
        "DEBUG":    logging.DEBUG,
        "INFO":     logging.INFO,
        "WARN":     logging.WARNING,
        "ERR":      logging.ERROR,
        "FATAL":    logging.CRITICAL
    }

    def __init__(self, name: str = "tbx") -> None:

        self.logger: logging.Logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        ch: logging.StreamHandler = logging.StreamHandler(stream=sys.stdout)
        ch.setLevel(logging.DEBUG)
        ch_fmt: ColorFormatter = ColorFormatter()
        ch.setFormatter(ch_fmt)

        self.logger.addHandler(ch)

    def LOG(
        self,
        log_level: str,
        message: str
    ) -> None:
    
        if log_level not in self.LOG_LEVELS.keys():
            raise KeyError(f"Un-supported log level <{log_level}> provided. Supported levels are {self.LOG_LEVELS.keys()}")

        self.logger.log(self.LOG_LEVELS[log_level], message)

    def set_log_level(
        self,
        log_level: str,
    ) -> None:
        
        if log_level not in self.LOG_LEVELS.keys():
            raise KeyError(f"Un-supported log level <{log_level}> provided. Supported levels are {self.LOG_LEVELS.keys()}")

        self.logger.setLevel(self.LOG_LEVELS[log_level])


###############################################################3
# START: Global logger (LOG)

logger: TbxLogger = TbxLogger()
logger.set_log_level("INFO")

def LOG(
    log_level: str,
    message: str
) -> None:
    """
    Log `message` with level `log_level`

    Args:
        log_level (str): DEBUG|INFO|WARN|ERR|FATAL
        message (str): message to be logged

    Raises:
        Exception: Invalid log level provided.
    """
    logger.LOG(log_level, message)

def set_log_level(
    log_level: str
) -> None:
    """
    Set the global log level, i.e., the one used by the global LOG function above.
    """
    logger.set_log_level(log_level)

# END: Global logger (LOG)
############################################################