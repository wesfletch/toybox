#!/usr/bin/env python3

from toybox_core.Launch import LaunchDescription, get_launch_description


def get_launch_descriptions() -> list[LaunchDescription]:

    launch_descs: list[LaunchDescription] = []

    listener: LaunchDescription = get_launch_description("Listener")
    listener.set_params({
        "name": "listener",
        "topic": None
    })
    launch_descs.append(listener)

    pico_bridge: LaunchDescription = get_launch_description("PicoBridge")
    pico_bridge.set_params({
        "name": "pico_bridge",
    })
    launch_descs.append(pico_bridge)

    return launch_descs
