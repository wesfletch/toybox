#!/usr/bin/env python3

from toybox_core.Launch import LaunchDescription, get_launch_description, NodeParam


def get_launch_params() -> list[NodeParam]:

    listener_name: NodeParam = NodeParam(
        name="listener_name",
        type=str,
        required=False)

def get_launch_descriptions(launch_params: list[NodeParam]) -> list[LaunchDescription]:

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
