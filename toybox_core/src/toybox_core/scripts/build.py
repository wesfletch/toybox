#!/usr/bin/env python3

import sys

from toybox_core.scripts.build_messages import build_messages


def full_build_process() -> None:
    """
    There will be more here, eventually. Maybe.
    """
    build_messages()

def main() -> None:

    if len(sys.argv) == 1:
        full_build_process()

if __name__ == "__main__":
    main()