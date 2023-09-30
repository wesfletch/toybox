#!/usr/bin/env python3

import logging
import sys

from typing import Dict

logger: logging.Logger = logging.getLogger("tbx")
logger.setLevel(logging.DEBUG)

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
    
    if log_level not in log_levels.keys():
        raise Exception(f"Invalid log level <{log_level}>")

    logger.log(log_levels[log_level], message)