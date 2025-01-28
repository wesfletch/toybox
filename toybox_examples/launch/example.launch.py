#!/usr/bin/env python3

import pathlib

from toybox_core.launch import LaunchDescription, get_launch_description, NodeParam, LaunchType, \
    find_launch_file, get_launch_descs_from_file, get_launch_params_from_file


def get_launch_params() -> list[NodeParam]:

    listener_name: NodeParam = NodeParam(
        name="other_listener_name",
        type=str,
        required=True)
    
    return [listener_name]

def get_launch_descriptions(launch_params: dict[str,NodeParam]) -> LaunchDescription:

    # Unpack the params that we declared in get_launch_params()
    other_listener_name: NodeParam = launch_params.get("other_listener_name", "default")

    listener: LaunchDescription = get_launch_description("Listener")
    listener.set_params({
        "name": "listener",
        "topic": None
    })

    pico_bridge: LaunchDescription = get_launch_description("PicoBridge")
    pico_bridge.set_params({"name": "pico_bridge"})
    
    listener_launch_file: pathlib.Path = find_launch_file(
        package="toybox_examples", 
        launch_file_name="listener.launch.py")

    listener_launch_params: dict[str,NodeParam] = get_launch_params_from_file(listener_launch_file)
    listener_launch_params["listener_name"].value = other_listener_name.value
    listener_launch_params["finish_early"].value = True

    listener_launch_file: LaunchDescription = get_launch_descs_from_file(
        launch_file_path=listener_launch_file,
        launch_params=listener_launch_params)
    
    launch_desc: LaunchDescription = LaunchDescription(
        name="listener+pico_bridge",
        launch_type=LaunchType.GROUP,)
    launch_desc.to_launch = [listener, pico_bridge, listener_launch_file]
    # launch_desc.to_launch = [listener, pico_bridge]
    return launch_desc
