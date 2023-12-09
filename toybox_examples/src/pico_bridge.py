#!/usr/bin/env python3

import sys
from typing import Union
# this has got to go
sys.path.append('/home/dev/toybox')

from toybox_core.src import (
    toybox,
    Node,
    Publisher
)

from toybox_msgs.core.Test_pb2 import TestMessage

def test_callback(self, message: TestMessage) -> None:
    print(message.test_string)

def main() -> None:

    node: Node = toybox.init_node("pico_bridge")
    test_pub: Union[Publisher,None] = node.advertise(
        topic_name="/test",
        message_type=TestMessage)
    if not test_pub:
        return

    # TODO: this doesn't actually work yet
    while not toybox.is_shutdown():
        test_pub.publish(TestMessage(test_string="test test test"))

if __name__ == "__main__":
    main()