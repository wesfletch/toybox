#!/usr/bin/env python3


from toybox_core.logging import set_log_level
from toybox_core.server import ToyboxServer


def main() -> None:

    set_log_level("DEBUG")

    tbx: ToyboxServer = ToyboxServer()
    tbx.serve()


if __name__ == "__main__":
    main()