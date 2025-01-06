#!/usr/bin/env python3

import logging
import sys

from typing import Dict

logger: logging.Logger = logging.getLogger("tbx")
logger.setLevel(logging.INFO)

ch: logging.StreamHandler = logging.StreamHandler(stream=sys.stdout)
ch.setLevel(logging.DEBUG)
ch_fmt: logging.Formatter = logging.Formatter(fmt='[%(asctime)s.%(msecs)03d][%(name)s][%(levelname)s]: %(message)s',
                                              datefmt='%H:%M:%S')
ch.setFormatter(ch_fmt)

logger.addHandler(ch)

log_levels: Dict[str, int] = {
    "DEBUG":logging.DEBUG,
    "INFO":logging.INFO,
    "WARN":logging.WARNING,
    "ERR":logging.ERROR,
    "FATAL":logging.CRITICAL
}

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
    if log_level not in log_levels.keys():
        raise Exception(f"Invalid log level <{log_level}>")

    logger.log(log_levels[log_level], message)

def set_log_level(
    log_level: str
) -> None:
    """
    Set the global log level, i.e., the one used by the global LOG function above.
    """
    if log_level not in log_levels.keys():
        raise Exception(f"Invalid log level <{log_level}>")
    logger.setLevel(log_levels[log_level])

# Rather than sub-classing logging.Logger like I should...
class TbxLogger():

    log_levels: Dict[str, int] = {
        "DEBUG":    logging.DEBUG,
        "INFO":     logging.INFO,
        "WARN":     logging.WARNING,
        "ERR":      logging.ERROR,
        "FATAL":    logging.CRITICAL
    }

    def __init__(self, name: str) -> None:

        self.logger: logging.Logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        ch: logging.StreamHandler = logging.StreamHandler(stream=sys.stdout)
        ch.setLevel(logging.DEBUG)
        ch_fmt: logging.Formatter = logging.Formatter(
            fmt='[%(asctime)s.%(msecs)03d][%(name)s][%(levelname)s]: %(message)s',
            datefmt='%H:%M:%S')
        ch.setFormatter(ch_fmt)

        self.logger.addHandler(ch)

    def LOG(
        self,
        log_level: str,
        message: str
    ) -> None:
    
        if log_level not in log_levels.keys():
            raise KeyError(f"Un-supported log level <{log_level}> provided. Supported levels are {self.log_levels.keys()}")

        self.logger.log(log_levels[log_level], message)

    def set_log_level(
        self,
        log_level: str,
    ) -> None:
        
        if log_level not in log_levels.keys():
            raise KeyError(f"Un-supported log level <{log_level}> provided. Supported levels are {self.log_levels.keys()}")

        self.logger.setLevel(log_levels[log_level])