#!/usr/bin/env python3

import pathlib

from toybox_core.launch import LaunchDescription, get_launch_description, NodeParam, LaunchType, \
    find_launch_file, get_launch_descs_from_file, get_launch_params_from_file


def get_launch_params() -> list[NodeParam]:

    listener_name: NodeParam = NodeParam(
        name="listener_name",
        type=str,
        required=True)
    
    return [listener_name]

def get_launch_descriptions(launch_params: dict[str,NodeParam]) -> list[LaunchDescription]:

    # Unpack the params that we declared in get_launch_params()
    listener_name: NodeParam = launch_params.get("listener_name", "default")

    listener: LaunchDescription = get_launch_description("Listener")
    listener.set_params({
        "name": listener_name.value,
        "topic": "/not/test/"
    })

    return [listener]