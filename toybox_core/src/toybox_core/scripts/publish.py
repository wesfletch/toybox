#!/usr/bin/env python3

from google.protobuf.message import Message
import importlib
import sys
from typing import Any, List
import uuid

import toybox_core as tbx


def main() -> None:

    message_type: str = sys.argv[1]
    topic: str = sys.argv[2]

    # Attempt to import the message we're listening for
    split_msg: List[str] = message_type.split("/")
    if len(split_msg) != 3:
        exit(1)

    module_name: str = f"toybox_msgs.{split_msg[0]}.{split_msg[1]}_pb2"
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        print(f"Spec not found for {module_name}")
        exit(1)

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    publish_node: tbx.Node.Node = tbx.init_node(
        name=f"publisher_{str(uuid.uuid4())}", log_level="DEBUG")

    publisher: tbx.Publisher | None = publish_node.advertise(
        topic_name=topic, message_type=getattr(module, split_msg[2]))
    
    if publisher is None:
        print(f"Failed to create publisher for topic {topic} with type {message_type}")
        exit(1)
    
    # TODO: How am I going to input messages??? ROS gives you auto-complete JSON 
    # skeletons to fill... Do I want to go to all of that effort?

if __name__ == "__main__":
    main()