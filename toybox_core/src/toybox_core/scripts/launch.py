#!/usr/bin/env python3

from typing import List

from toybox_core.Launch import launch_all, Launchable, get_launch_description, LaunchDescription
from toybox_core.Logging import LOG

def main() -> None:
    # TODO: for now, this is just an example of using LaunchDescriptions
    # and the launch_all() func the way I would in a to-be-developed *.launch.py file. 
    # This specific script will eventually be a CLI tool for launching nodes.
    
    listener: LaunchDescription = get_launch_description("Listener")
    listener.set_params({
        "name": "listener",
        "topic": None
    })

    pico_bridge: LaunchDescription = get_launch_description("PicoBridge")
    pico_bridge.set_params({
        "name": "pico_bridge",
    })

    launch_group: List[LaunchDescription] = [listener, pico_bridge]

    launch_all(launch_group)


if __name__ == "__main__":
    main()