#!/usr/bin/env python3

import atexit
from typing import Dict, List, Tuple, Union, Callable

import importlib

from toybox_core.Launch import launch

def main() -> None:
    
    from toybox_examples.src.toybox_examples.pico_bridge import PicoBridge
    pico_bridge: PicoBridge = PicoBridge(name="pico_bridge")

    launch(to_launch=pico_bridge)


if __name__ == "__main__":
    main()