#!/usr/bin/env python3

from dataclasses import dataclass, field
import pathlib
import sys

import grpc

from toybox_core.Launch import get_launch_description, launch, launch_all, LaunchDescription, get_launch_descs_from_file
from toybox_core.Logging import LOG
from toybox_core.metadata import ToyboxMetadata, find_pyproject_toml


# TBX_SERVER_DEFAULT_PORT: int = 50051

# '[::]:50051'

def is_tbx_server_running(channel: grpc.Channel) -> bool:

    timeout_sec: int = 1
    try:
        grpc.channel_ready_future(channel).result(timeout=timeout_sec)
    except grpc.FutureTimeoutError:
        return False
    
    return True

def launch_a_node(node_name: str, **kwargs) -> None:

    node: LaunchDescription = get_launch_description(node_name)
    node.set_params(params=kwargs)
    launch(node)
    # node.set_params({
        # "name": "listener",
    #     "topic": None
    # })


def launch_a_file(module_name: str, launch_file_name: str) -> None:

    try:
        toml_path: pathlib.Path = find_pyproject_toml(module_name=module_name)
    except Exception as e:
        LOG("FATAL", f"Failed to find pyproject.toml for {module_name}. Exception was: {e}")
        sys.exit(1)

    meta: ToyboxMetadata = ToyboxMetadata.extract_from_toml(toml_path=toml_path)

    launch_file: pathlib.Path = meta.get_launch_file(launch_file_name=launch_file_name)
    launch_group: list[LaunchDescription] = get_launch_descs_from_file(launch_file_path=launch_file)

    launch_all(launch_descs=launch_group)

def main() -> None:

    launch_type: str = sys.argv[1] # 'file', 'node', etc....
    if launch_type == "file":
        # Or you could just do proper argparse stuff...
        assert len(sys.argv) >= 3
        module_name: str = sys.argv[2]
        file_name: str = sys.argv[3]
        launch_a_file(module_name,file_name)
    else: 
        assert len(sys.argv) >= 2
        node_name: str = sys.argv[2]
        launch_a_node(node_name, **dict(arg.split("=") for arg in sys.argv[3:]))

if __name__ == "__main__":
    main()