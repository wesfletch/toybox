#!/usr/bin/env python3


from toybox_core.launch import LaunchDescription, get_launch_description, NodeParam


def get_launch_params() -> list[NodeParam]:

    listener_name: NodeParam = NodeParam(
        name="listener_name",
        type=str,
        required=True)
    
    finish_early: NodeParam = NodeParam(
        name="finish_early",
        type=bool,
        required=False)
    
    return [listener_name, finish_early]

def get_launch_descriptions(launch_params: dict[str,NodeParam]) -> list[LaunchDescription]:

    # Unpack the params that we declared in get_launch_params()
    listener_name: NodeParam = launch_params.get("listener_name", "default")
    finish_early: NodeParam = launch_params.get("finish_early", False)

    listener: LaunchDescription = get_launch_description("Listener")
    listener.set_params({
        "name": listener_name.value,
        "topic": "/test",
        "finish_early": finish_early.value
    })

    return [listener]