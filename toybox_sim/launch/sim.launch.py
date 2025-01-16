#!/usr/bin/env python3

import pathlib

from toybox_core.launch import LaunchDescription, NodeParam, get_launch_description

def get_launch_params() -> list[NodeParam]:
    return []

def get_launch_descriptions(launch_params: dict[str,NodeParam]) -> list[LaunchDescription]:

    sim: LaunchDescription = get_launch_description("ToyboxSim")
    sim.set_params({
        "name": "sim",
        "world": "/home/wfletcher/toybox/toybox_sim/resources/base_config.json",
        "use_gui": True,
    })

    diff_driver: LaunchDescription = get_launch_description("DiffDriver")
    diff_driver.set_params({
        "name": "diff_driver" 
    })

    return [sim, diff_driver]